"""
Verification and safety checks for locator candidates.
"""

from typing import Dict, Any, List
from bs4 import BeautifulSoup, Tag


def build_verify_action(candidate: Dict[str, Any], action: str) -> Dict[str, Any]:
    """
    Build a verification action for a candidate locator.

    Args:
        candidate: Candidate dictionary
        action: Type of verification action

    Returns:
        Verification action dictionary
    """
    if action == "exists":
        return {
            "type": "exists",
            "locator": candidate['locator'],
            "locator_type": candidate['type'],
            "expected_count": 1,
            "details": {
                "description": "Verify that the locator matches exactly one element",
                "timeout": 5000,  # milliseconds
                "retries": 2
            }
        }
    elif action == "click_and_check":
        return {
            "type": "click_and_check",
            "locator": candidate['locator'],
            "locator_type": candidate['type'],
            "details": {
                "description": "Click the element and verify no error occurs",
                "timeout": 10000,
                "expected_url_change": False,
                "error_selectors": [".error", ".alert", "[class*='error']"]
            }
        }
    elif action == "text_match":
        return {
            "type": "text_match",
            "locator": candidate['locator'],
            "locator_type": candidate['type'],
            "details": {
                "description": "Verify element contains expected text",
                "expected_text": candidate.get('expected_text', ''),
                "partial_match": True
            }
        }
    else:
        return {
            "type": "custom",
            "locator": candidate['locator'],
            "locator_type": candidate['type'],
            "details": {
                "action": action,
                "description": f"Custom verification: {action}"
            }
        }


def is_destructive(candidate: Dict[str, Any], soup: BeautifulSoup) -> bool:
    """
    Check if a candidate locator might be destructive.

    Args:
        candidate: Candidate dictionary
        soup: BeautifulSoup object

    Returns:
        True if potentially destructive
    """
    locator = candidate['locator']
    reason = candidate.get('reason', '').lower()

    # Check for destructive keywords in reason
    destructive_keywords = [
        'delete', 'remove', 'confirm purchase', 'submit payment',
        'unsubscribe', 'cancel account', 'delete account'
    ]

    if any(keyword in reason for keyword in destructive_keywords):
        return True

    # Try to analyze the element if we can find it
    try:
        elements = soup.select(locator)
        if elements:
            element = elements[0]

            # Check element attributes
            element_text = element.get_text(strip=True).lower()

            # Check for destructive text content
            if any(keyword in element_text for keyword in destructive_keywords):
                return True

            # Check for dangerous element types
            if element.name in ['button', 'input']:
                input_type = element.get('type', '').lower()
                if input_type in ['submit', 'reset']:
                    # Additional check for submit buttons with destructive text
                    if any(keyword in element_text for keyword in ['delete', 'remove', 'cancel']):
                        return True

            # Check for forms that might be payment or deletion forms
            if element.name == 'form':
                form_action = element.get('action', '').lower()
                if any(word in form_action for word in ['delete', 'remove', 'cancel']):
                    return True

    except Exception:
        # If we can't analyze, assume safe
        pass

    return False


def verify_locator_exists(soup: BeautifulSoup, locator: str, locator_type: str) -> Dict[str, Any]:
    """
    Verify that a locator exists and return details.

    Args:
        soup: BeautifulSoup object
        locator: Locator string
        locator_type: Type of locator

    Returns:
        Verification result dictionary
    """
    try:
        if locator_type == 'css':
            elements = soup.select(locator)
        elif locator_type == 'xpath':
            # For XPath, we'd need lxml or xpath support
            elements = []  # Placeholder
        else:
            elements = []

        return {
            "exists": len(elements) > 0,
            "count": len(elements),
            "elements": [{"tag": el.name, "text": el.get_text(strip=True)[:50]} for el in elements[:3]]
        }

    except Exception as e:
        return {
            "exists": False,
            "error": str(e),
            "count": 0,
            "elements": []
        }


def calculate_risk_score(candidate: Dict[str, Any], soup: BeautifulSoup) -> float:
    """
    Calculate a risk score for a candidate (0.0 = safe, 1.0 = high risk).

    Args:
        candidate: Candidate dictionary
        soup: BeautifulSoup object

    Returns:
        Risk score between 0.0 and 1.0
    """
    risk_score = 0.0

    # Base risk from destructive check
    if is_destructive(candidate, soup):
        risk_score += 0.8

    # Risk from multiple matches (unreliable locator)
    try:
        elements = soup.select(candidate['locator'])
        match_count = len(elements)

        if match_count == 0:
            risk_score += 1.0  # Doesn't work
        elif match_count > 1:
            risk_score += 0.3  # Multiple matches increase risk
    except Exception:
        risk_score += 0.5  # Invalid selector

    # Risk from complex selectors
    locator = candidate['locator']
    if len(locator.split()) > 3:  # Complex selector
        risk_score += 0.2

    # Risk from low confidence scores
    if candidate.get('score', 0.0) < 0.5:
        risk_score += 0.1

    return min(1.0, risk_score)


def get_safe_candidates(candidates: List[Dict[str, Any]], soup: BeautifulSoup,
                       max_risk: float = 0.3) -> List[Dict[str, Any]]:
    """
    Filter candidates to only include safe ones.

    Args:
        candidates: List of candidate dictionaries
        soup: BeautifulSoup object
        max_risk: Maximum acceptable risk score

    Returns:
        List of safe candidates
    """
    safe_candidates = []

    for candidate in candidates:
        risk_score = calculate_risk_score(candidate, soup)
        if risk_score <= max_risk:
            candidate_copy = candidate.copy()
            candidate_copy['risk_score'] = risk_score
            safe_candidates.append(candidate_copy)

    return safe_candidates
