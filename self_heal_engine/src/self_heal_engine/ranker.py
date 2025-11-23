"""
Candidate ranking and feature extraction for self-healing locators.
"""

import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup, Tag

from .parser import node_depth, css_count
from .heuristics import _tokenize_locator, _jaccard_similarity


def extract_features(candidate: Dict[str, Any], soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Extract features for a candidate locator.

    Args:
        candidate: Candidate dictionary with locator, type, score, reason
        soup: BeautifulSoup object of the page

    Returns:
        Dictionary of features
    """
    locator = candidate['locator']
    features = {}

    try:
        elements = soup.select(locator)
        if not elements:
            # Invalid selector
            return {
                'uniqueness_count': 0,
                'depth': 0,
                'visible_flag': False,
                'text_similarity': 0.0,
                'attribute_similarity': 0.0,
                'structural_score': 0.0
            }

        element = elements[0]  # Use first match for features

        features['uniqueness_count'] = len(elements)
        features['depth'] = node_depth(element)
        features['visible_flag'] = _is_visible(element)

        # Text similarity (placeholder - would need original text)
        features['text_similarity'] = 0.0

        # Attribute similarity (placeholder - would need original locator)
        features['attribute_similarity'] = _calculate_attribute_similarity(element, locator)

        # Structural score based on selector complexity
        features['structural_score'] = _calculate_structural_score(locator)

    except Exception:
        # Handle invalid selectors
        features = {
            'uniqueness_count': 0,
            'depth': 0,
            'visible_flag': False,
            'text_similarity': 0.0,
            'attribute_similarity': 0.0,
            'structural_score': 0.0
        }

    return features


def score_candidates(candidates: List[Dict[str, Any]], soup: BeautifulSoup,
                    weights: Dict[str, float] = None) -> List[Dict[str, Any]]:
    """
    Score and rank candidates using feature-based approach.

    Args:
        candidates: List of candidate dictionaries
        soup: BeautifulSoup object of the page
        weights: Optional custom weights for scoring

    Returns:
        List of candidates with updated scores, sorted by score descending
    """
    if weights is None:
        weights = {
            'base_score': 0.3,
            'uniqueness': 0.25,
            'visibility': 0.15,
            'depth_penalty': 0.1,
            'structural': 0.1,
            'similarity': 0.1
        }

    scored_candidates = []

    for candidate in candidates:
        # Extract features
        features = extract_features(candidate, soup)

        # Calculate composite score
        score = (
            weights['base_score'] * candidate['score'] +
            weights['uniqueness'] * _uniqueness_score(features['uniqueness_count']) +
            weights['visibility'] * (1.0 if features['visible_flag'] else 0.0) +
            weights['depth_penalty'] * _depth_penalty(features['depth']) +
            weights['structural'] * features['structural_score'] +
            weights['similarity'] * (features['text_similarity'] + features['attribute_similarity']) / 2
        )

        # Normalize to 0-1 range
        score = max(0.0, min(1.0, score))

        candidate_copy = candidate.copy()
        candidate_copy['score'] = score
        candidate_copy['features'] = features
        scored_candidates.append(candidate_copy)

    # Sort by score descending
    return sorted(scored_candidates, key=lambda x: x['score'], reverse=True)


def _calculate_attribute_similarity(element: Tag, locator: str) -> float:
    """Calculate similarity between locator and element attributes."""
    locator_tokens = _tokenize_locator(locator)
    element_tokens = set()

    # Extract tokens from element attributes
    if element.get('id'):
        element_tokens.update(_tokenize_locator(element['id']))

    if element.get('name'):
        element_tokens.update(_tokenize_locator(element['name']))

    if element.get('class'):
        for class_name in element['class']:
            element_tokens.update(_tokenize_locator(class_name))

    # Extract tokens from data attributes
    for attr in element.attrs:
        if attr.startswith('data-'):
            element_tokens.update(_tokenize_locator(element[attr]))

    return _jaccard_similarity(locator_tokens, element_tokens)


def _calculate_structural_score(locator: str) -> float:
    """Calculate structural score based on selector complexity."""
    score = 0.0

    # Prefer simpler selectors
    if locator.startswith('#'):
        score += 0.8  # ID selectors
    elif locator.startswith('.'):
        score += 0.6  # Class selectors
    elif '[' in locator:
        score += 0.7  # Attribute selectors
    else:
        score += 0.4  # Tag selectors

    # Penalize complex selectors
    complexity_penalty = min(0.5, len(locator.split()) * 0.1)
    score -= complexity_penalty

    # Prefer unique selectors (this is approximate)
    if ' ' not in locator and ',' not in locator:
        score += 0.2

    return max(0.0, min(1.0, score))


def _uniqueness_score(count: int) -> float:
    """Convert uniqueness count to score (higher is better)."""
    if count == 1:
        return 1.0
    elif count == 0:
        return 0.0
    else:
        # Penalize multiple matches, but not completely
        return max(0.1, 1.0 / count)


def _depth_penalty(depth: int) -> float:
    """Calculate depth penalty (shallower is better)."""
    # Penalize deep nesting, but not too harshly
    return max(0.0, 1.0 - (depth * 0.1))


def _is_visible(element: Tag) -> bool:
    """Check if element is likely visible."""
    # Check for hidden attributes
    if element.get('hidden') is not None:
        return False

    # Check CSS classes
    classes = element.get('class', [])
    if any(cls in ['hidden', 'invisible', 'd-none', 'display-none'] for cls in classes):
        return False

    # Check style attribute
    style = element.get('style', '').lower()
    if 'display: none' in style or 'visibility: hidden' in style:
        return False

    # Check parent visibility (simplified)
    parent = element.parent
    while parent and parent.name != '[document]':
        if parent.get('hidden') is not None:
            return False
        parent_style = parent.get('style', '').lower()
        if 'display: none' in parent_style or 'visibility: hidden' in parent_style:
            return False
        parent = parent.parent

    return True
