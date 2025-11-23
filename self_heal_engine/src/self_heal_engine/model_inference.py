"""
Model inference utilities for the trained ranker.
"""

import lightgbm as lgb
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path

from .ranker import extract_features
from .parser import parse_html


class RankerModel:
    """Wrapper for the trained ranking model."""

    def __init__(self, model_path: str = "models/ranker.json"):
        """
        Initialize the ranker model.

        Args:
            model_path: Path to the trained model file
        """
        self.model_path = Path(model_path)
        self.info_path = self.model_path.with_suffix('.json.info.json')

        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        # Load model
        self.model = lgb.Booster(model_file=str(self.model_path))

        # Load feature info
        if self.info_path.exists():
            with open(self.info_path, 'r') as f:
                self.feature_info = json.load(f)
            self.feature_names = self.feature_info.get('feature_names', [])
        else:
            # Fallback: try to infer feature names from model
            self.feature_names = [f"feature_{i}" for i in range(self.model.num_feature())]
            self.feature_info = {}

    def score_candidates_with_model(self, candidates: List[Dict[str, Any]],
                                   soup) -> List[Dict[str, Any]]:
        """
        Score candidates using the trained model.

        Args:
            candidates: List of candidate dictionaries
            soup: BeautifulSoup object

        Returns:
            Candidates with updated model scores
        """
        if not candidates:
            return candidates

        # Extract features for all candidates
        feature_rows = []
        for candidate in candidates:
            features = extract_features(candidate, soup)
            feature_rows.append(features)

        # Create feature DataFrame
        df = pd.DataFrame(feature_rows)

        # Ensure we have the expected features
        available_features = [col for col in self.feature_names if col in df.columns]

        if not available_features:
            # Fall back to original scoring if no features match
            return candidates

        X = df[available_features]

        # Handle missing features by filling with 0
        for expected_feature in self.feature_names:
            if expected_feature not in X.columns:
                X[expected_feature] = 0.0

        # Reorder columns to match training
        X = X[self.feature_names]

        # Predict scores
        model_scores = self.model.predict(X.values)

        # Update candidates with model scores
        scored_candidates = []
        for candidate, model_score in zip(candidates, model_scores):
            candidate_copy = candidate.copy()
            candidate_copy['model_score'] = float(model_score)
            # Blend model score with original score
            candidate_copy['blended_score'] = 0.7 * model_score + 0.3 * candidate.get('score', 0.0)
            scored_candidates.append(candidate_copy)

        # Sort by blended score
        scored_candidates.sort(key=lambda x: x['blended_score'], reverse=True)

        return scored_candidates

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from the model."""
        if not hasattr(self.model, 'feature_importance'):
            return {}

        importance_values = self.model.feature_importance()
        return dict(zip(self.feature_names, importance_values.tolist()))

    def get_model_info(self) -> Dict[str, Any]:
        """Get model metadata."""
        return {
            'model_path': str(self.model_path),
            'num_features': self.model.num_feature(),
            'num_trees': self.model.num_trees(),
            'feature_names': self.feature_names,
            'training_info': self.feature_info
        }


def score_candidates_with_model(candidates: List[Dict[str, Any]],
                               soup, model_path: str = "models/ranker.json") -> List[Dict[str, Any]]:
    """
    Convenience function to score candidates with a trained model.

    Args:
        candidates: List of candidate dictionaries
        soup: BeautifulSoup object
        model_path: Path to the trained model

    Returns:
        Scored candidates
    """
    try:
        ranker = RankerModel(model_path)
        return ranker.score_candidates_with_model(candidates, soup)
    except Exception as e:
        # Fall back to original candidates if model loading fails
        print(f"Model inference failed: {e}")
        return candidates


def is_model_available(model_path: str = "models/ranker.json") -> bool:
    """
    Check if a trained model is available.

    Args:
        model_path: Path to check for model file

    Returns:
        True if model exists and is loadable
    """
    try:
        RankerModel(model_path)
        return True
    except Exception:
        return False


def get_model_stats(model_path: str = "models/ranker.json") -> Dict[str, Any]:
    """
    Get statistics about the trained model.

    Args:
        model_path: Path to the model

    Returns:
        Model statistics dictionary
    """
    try:
        ranker = RankerModel(model_path)
        info = ranker.get_model_info()
        importance = ranker.get_feature_importance()

        return {
            'available': True,
            'model_info': info,
            'feature_importance': importance,
            'top_features': sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10]
        }
    except Exception as e:
        return {
            'available': False,
            'error': str(e)
        }


if __name__ == "__main__":
    # Example usage
    if is_model_available():
        print("Model is available")
        stats = get_model_stats()
        print(f"Model has {stats['model_info']['num_features']} features")
        print("Top 5 important features:")
        for feature, importance in stats['top_features'][:5]:
            print(f"  {feature}: {importance}")
    else:
        print("No trained model available")
