"""
Training pipeline for the locator ranker model.
"""

import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
import json
from pathlib import Path
from typing import Dict, Any, List

from .storage import load_training_data
from .ranker import extract_features
from .parser import parse_html


def prepare_training_data() -> pd.DataFrame:
    """
    Prepare training data from stored records.

    Returns:
        DataFrame with features and labels
    """
    records = load_training_data()

    training_rows = []

    for record in records:
        candidates = record.get('candidates', [])
        accepted_index = record.get('accepted_index', -1)
        page_html = record.get('page_html', '')

        if not candidates or not page_html:
            continue

        try:
            soup = parse_html(page_html)

            for i, candidate in enumerate(candidates):
                # Extract features
                features = extract_features(candidate, soup)

                # Create training row
                row = {
                    'candidate_index': i,
                    'accepted': 1 if i == accepted_index else 0,
                    'locator': candidate.get('locator', ''),
                    'locator_type': candidate.get('type', ''),
                    'reason': candidate.get('reason', ''),
                    'original_score': candidate.get('score', 0.0),
                    **features  # Unpack features
                }

                training_rows.append(row)

        except Exception as e:
            print(f"Error processing record {record.get('request_id')}: {e}")
            continue

    return pd.DataFrame(training_rows)


def train_ranker_model(output_path: str = "models/ranker.json",
                      test_size: float = 0.2,
                      random_state: int = 42) -> Dict[str, Any]:
    """
    Train the LightGBM ranker model.

    Args:
        output_path: Path to save the trained model
        test_size: Fraction of data for testing
        random_state: Random state for reproducibility

    Returns:
        Training results dictionary
    """
    # Prepare data
    df = prepare_training_data()

    if df.empty:
        raise ValueError("No training data available")

    print(f"Prepared {len(df)} training samples")

    # Prepare features and labels
    feature_cols = [col for col in df.columns if col not in
                   ['candidate_index', 'accepted', 'locator', 'locator_type', 'reason']]

    X = df[feature_cols]
    y = df['accepted']

    # For ranking, we need query groups (group by request)
    # This is a simplified approach - in practice you'd group by request_id
    groups = df.groupby(df.index // 10).size().values  # Rough grouping

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    # Create LightGBM datasets
    train_data = lgb.Dataset(X_train, label=y_train, group=groups[:len(X_train)])
    test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

    # Model parameters for ranking
    params = {
        'objective': 'lambdarank',
        'metric': 'ndcg',
        'boosting_type': 'gbdt',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.9,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': -1
    }

    # Train model
    print("Training LightGBM ranker...")
    model = lgb.train(
        params,
        train_data,
        num_boost_round=100,
        valid_sets=[train_data, test_data],
        callbacks=[
            lgb.early_stopping(stopping_rounds=10),
            lgb.log_evaluation(10)
        ]
    )

    # Evaluate
    y_pred = model.predict(X_test)
    # Convert to binary predictions for evaluation
    y_pred_binary = (y_pred > 0.5).astype(int)

    accuracy = accuracy_score(y_test, y_pred_binary)
    report = classification_report(y_test, y_pred_binary, output_dict=True)

    print(".3f")
    print("Classification Report:")
    print(classification_report(y_test, y_pred_binary))

    # Save model
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    model.save_model(output_path)

    # Save feature names for inference
    feature_info = {
        'feature_names': feature_cols,
        'model_path': output_path,
        'training_samples': len(df),
        'accuracy': accuracy
    }

    with open(f"{output_path}.info.json", 'w') as f:
        json.dump(feature_info, f, indent=2)

    return {
        'accuracy': accuracy,
        'classification_report': report,
        'feature_importance': dict(zip(feature_cols, model.feature_importance().tolist())),
        'model_path': output_path
    }


def validate_model(model_path: str = "models/ranker.json") -> Dict[str, Any]:
    """
    Validate the trained model on test data.

    Args:
        model_path: Path to the trained model

    Returns:
        Validation results
    """
    # Load model
    model = lgb.Booster(model_file=model_path)

    # Load feature info
    info_path = f"{model_path}.info.json"
    with open(info_path, 'r') as f:
        feature_info = json.load(f)

    feature_names = feature_info['feature_names']

    # Prepare test data
    df = prepare_training_data()
    if df.empty:
        raise ValueError("No test data available")

    # Use only features that exist in both training and current data
    available_features = [col for col in feature_names if col in df.columns]
    X = df[available_features]
    y = df['accepted']

    # Predict
    y_pred = model.predict(X)
    y_pred_binary = (y_pred > 0.5).astype(int)

    # Evaluate
    accuracy = accuracy_score(y, y_pred_binary)
    report = classification_report(y, y_pred_binary, output_dict=True)

    return {
        'accuracy': accuracy,
        'classification_report': report,
        'samples_evaluated': len(df)
    }


if __name__ == "__main__":
    # Example usage
    try:
        results = train_ranker_model()
        print("Training completed successfully!")
        print(f"Model saved to: {results['model_path']}")
        print(".3f")
    except Exception as e:
        print(f"Training failed: {e}")
