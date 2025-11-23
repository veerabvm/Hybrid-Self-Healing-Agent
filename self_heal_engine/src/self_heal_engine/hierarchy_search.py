import difflib
import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup, Tag
from collections import Counter

from .parser import parse_html
from .heuristics import _tokenize_locator, _jaccard_similarity, _generate_element_locator


def find_moved_candidates(soup: BeautifulSoup, old_context: dict, max_candidates: int = 5) -> list[dict]:
    """
    Find candidate elements that may have moved in the DOM hierarchy using anchor-based search,
    neighbor locality, and subtree similarity.

    Args:
        soup: BeautifulSoup object of the current page
        old_context: Dictionary containing context about the original element
            - "original_locator": str
            - "original_locator_type": str
            - "old_subtree_html": str (optional)
            - "anchors": list[str] (optional)
            - "prev_sibling_text": str (optional)
            - "next_sibling_text": str (optional)
        max_candidates: Maximum number of candidates to return

    Returns:
        List of candidate dictionaries sorted by score descending, each containing:
        - locator: CSS/XPath selector
        - type: 'css', 'xpath', 'id', or 'name'
        - score: Aggregate score
        - reason: Explanation of match
        - features: Dictionary with detailed scoring components
    """
    candidates = []

    # Extract context information
    original_locator = old_context.get("original_locator", "")
    anchors = old_context.get("anchors", [])
    prev_sibling_text = old_context.get("prev_sibling_text", "")
    next_sibling_text = old_context.get("next_sibling_text", "")
    old_subtree_html = old_context.get("old_subtree_html")

    # 1. Anchor-based search
    anchor_candidates = _anchor_based_search(soup, anchors, original_locator)
    candidates.extend(anchor_candidates)

    # 2. Neighbor locality search
    neighbor_candidates = _neighbor_locality_search(
        soup, prev_sibling_text, next_sibling_text, original_locator
    )
    candidates.extend(neighbor_candidates)

    # 3. Subtree similarity search (if old_subtree_html provided)
    if old_subtree_html:
        subtree_candidates = _subtree_similarity_search(soup, old_subtree_html, original_locator)
        candidates.extend(subtree_candidates)

    # 4. Path relaxation for non-unique candidates
    candidates = _apply_path_relaxation(soup, candidates)

    # 5. Aggregate scores and features
    _compute_aggregate_scores(candidates)

    # 6. Return top candidates sorted by score
    return sorted(candidates, key=lambda x: x['score'], reverse=True)[:max_candidates]


def _anchor_based_search(soup: BeautifulSoup, anchors: List[str], original_locator: str) -> List[Dict[str, Any]]:
    """Perform anchor-based search for moved elements."""
    candidates = []

    for anchor_text in anchors:
        # Find exact anchor matches
        exact_anchors = soup.find_all(string=re.compile(re.escape(anchor_text), re.IGNORECASE))
        for anchor in exact_anchors:
            anchor_element = anchor.parent if hasattr(anchor, 'parent') else anchor
            _search_anchor_subtree(soup, anchor_element, original_locator, candidates, 1.0, "exact anchor match")
            _search_anchor_siblings(soup, anchor_element, original_locator, candidates, 1.0, "exact anchor sibling")

        # Find fuzzy anchor matches
        all_text_elements = soup.find_all(string=True)
        for text_element in all_text_elements:
            similarity = difflib.SequenceMatcher(None, anchor_text.lower(), text_element.strip().lower()).ratio()
            if similarity > 0.8:  # High similarity threshold
                anchor_element = text_element.parent if hasattr(text_element, 'parent') else text_element
                _search_anchor_subtree(soup, anchor_element, original_locator, candidates, similarity * 0.9, f"fuzzy anchor match ({similarity:.2f})")

    return candidates


def _search_anchor_subtree(soup: BeautifulSoup, anchor_element: Tag, original_locator: str, candidates: List[Dict[str, Any]],
                          anchor_score: float, reason_prefix: str) -> None:
    """Search subtree of anchor element for candidate matches, limited to depth 6."""
    if not anchor_element:
        return

    # Define target element types
    target_tags = {'button', 'input', 'a', 'span', 'div', 'select', 'textarea'}

    # BFS search with depth limit
    queue = [(anchor_element, 0)]  # (element, depth)
    visited = set()

    while queue:
        current_element, depth = queue.pop(0)

        if depth > 6 or id(current_element) in visited:
            continue
        visited.add(id(current_element))

        # Check if current element is a candidate
        if current_element.name in target_tags:
            locator = _generate_element_locator(current_element)
            if locator:
                # Calculate heuristic score if possible
                heuristic_score = _calculate_heuristic_score(current_element, original_locator)

                candidates.append({
                    'locator': locator,
                    'type': 'css',
                    'anchor_match_score': anchor_score,
                    'neighbor_similarity': 0.0,  # Will be updated later if applicable
                    'subtree_similarity': 0.0,  # Will be updated later if applicable
                    'uniqueness_count': _check_uniqueness(soup, locator),
                    'visibility_flag': _is_visible(current_element),
                    'depth_diff': depth,
                    'heuristic_score': heuristic_score,
                    'reason': f"{reason_prefix}, depth {depth}"
                })

        # Add children to queue
        if hasattr(current_element, 'children'):
            for child in current_element.children:
                if hasattr(child, 'name') and child.name:
                    queue.append((child, depth + 1))


def _search_anchor_siblings(soup: BeautifulSoup, anchor_element: Tag, original_locator: str, candidates: List[Dict[str, Any]],
                           anchor_score: float, reason_prefix: str) -> None:
    """Search siblings of anchor element for candidate matches."""
    if not anchor_element or not hasattr(anchor_element, 'parent') or not anchor_element.parent:
        return

    # Define target element types
    target_tags = {'button', 'input', 'a', 'span', 'div', 'select', 'textarea'}

    # Check siblings
    siblings = list(anchor_element.parent.children)
    try:
        current_index = siblings.index(anchor_element)
    except ValueError:
        return

    # Check siblings within reasonable range (±5)
    for offset in range(-5, 6):
        if offset == 0:
            continue
        sibling_index = current_index + offset
        if 0 <= sibling_index < len(siblings):
            sibling = siblings[sibling_index]
            if hasattr(sibling, 'name'):
                # Search subtree of this sibling
                _search_anchor_subtree(soup, sibling, original_locator, candidates, anchor_score, f"exact anchor sibling subtree, offset {offset}")
                
                # Also check if sibling itself is a candidate
                if sibling.name in target_tags:
                    locator = _generate_element_locator(sibling)
                    if locator:
                        # Calculate heuristic score
                        heuristic_score = _calculate_heuristic_score(sibling, original_locator)

                        candidates.append({
                            'locator': locator,
                            'type': 'css',
                            'anchor_match_score': anchor_score,
                            'neighbor_similarity': 0.0,
                            'subtree_similarity': 0.0,
                            'uniqueness_count': _check_uniqueness(soup, locator),
                            'visibility_flag': _is_visible(sibling),
                            'depth_diff': abs(offset),
                            'heuristic_score': heuristic_score,
                            'reason': f"{reason_prefix}, sibling offset {offset}"
                        })


def _neighbor_locality_search(soup: BeautifulSoup, prev_sibling_text: str, next_sibling_text: str,
                             original_locator: str) -> List[Dict[str, Any]]:
    """Find candidates based on sibling text matches."""
    candidates = []

    # Find elements with matching previous sibling
    if prev_sibling_text:
        prev_matches = soup.find_all(string=re.compile(re.escape(prev_sibling_text), re.IGNORECASE))
        for match in prev_matches:
            element = match.parent if hasattr(match, 'parent') else match
            _check_sibling_candidates(soup, element, original_locator, candidates, "prev", prev_sibling_text)

    # Find elements with matching next sibling
    if next_sibling_text:
        next_matches = soup.find_all(string=re.compile(re.escape(next_sibling_text), re.IGNORECASE))
        for match in next_matches:
            element = match.parent if hasattr(match, 'parent') else match
            _check_sibling_candidates(soup, element, original_locator, candidates, "next", next_sibling_text)

    return candidates


def _check_sibling_candidates(soup: BeautifulSoup, parent_element: Tag, original_locator: str, candidates: List[Dict[str, Any]],
                             sibling_type: str, sibling_text: str) -> None:
    """Check nearby siblings (±3) of parent element for candidates."""
    if not parent_element or not hasattr(parent_element, 'parent') or not parent_element.parent:
        return

    siblings = list(parent_element.parent.children)
    try:
        current_index = siblings.index(parent_element)
    except ValueError:
        return

    # Check siblings within ±3 range
    for offset in range(-3, 4):
        if offset == 0:
            continue
        sibling_index = current_index + offset
        if 0 <= sibling_index < len(siblings):
            sibling = siblings[sibling_index]
            if hasattr(sibling, 'name') and sibling.name:
                # Calculate neighbor similarity
                neighbor_tokens = _tokenize_locator(sibling.get_text(strip=True))
                original_tokens = _tokenize_locator(original_locator)
                similarity = _jaccard_similarity(neighbor_tokens, original_tokens)

                locator = _generate_element_locator(sibling)
                if locator and similarity > 0.1:
                    heuristic_score = _calculate_heuristic_score(sibling, original_locator)
                    candidates.append({
                        'locator': locator,
                        'type': 'css',
                        'anchor_match_score': 0.0,
                        'neighbor_similarity': similarity,
                        'subtree_similarity': 0.0,
                        'uniqueness_count': _check_uniqueness(soup, locator),
                        'visibility_flag': _is_visible(sibling),
                        'depth_diff': abs(offset),
                        'heuristic_score': heuristic_score,
                        'reason': f"neighbor {sibling_type} sibling match ({similarity:.2f})"
                    })


def _subtree_similarity_search(soup: BeautifulSoup, old_subtree_html: str, original_locator: str) -> List[Dict[str, Any]]:
    """Find candidates based on subtree similarity."""
    candidates = []

    # Parse old subtree
    old_soup = parse_html(f"<div>{old_subtree_html}</div>")
    if not old_soup:
        return candidates

    old_text = old_soup.get_text(strip=True)
    old_tokens = _tokenize_locator(old_text)

    # Check all elements for subtree similarity
    for element in soup.find_all():
        if element.name in {'button', 'input', 'a', 'span', 'div', 'select', 'textarea'}:
            element_text = element.get_text(strip=True)
            element_tokens = _tokenize_locator(element_text)

            # Calculate Jaccard similarity
            similarity = _jaccard_similarity(old_tokens, element_tokens)

            if similarity > 0.3:  # Minimum threshold
                locator = _generate_element_locator(element)
                if locator:
                    heuristic_score = _calculate_heuristic_score(element, original_locator)
                    candidates.append({
                        'locator': locator,
                        'type': 'css',
                        'anchor_match_score': 0.0,
                        'neighbor_similarity': 0.0,
                        'subtree_similarity': similarity,
                        'uniqueness_count': _check_uniqueness(soup, locator),
                        'visibility_flag': _is_visible(element),
                        'depth_diff': 0,  # Not applicable for subtree similarity
                        'heuristic_score': heuristic_score,
                        'reason': f"subtree similarity ({similarity:.2f})"
                    })

    return candidates


def _apply_path_relaxation(soup: BeautifulSoup, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply CSS path relaxation for non-unique candidates."""
    relaxed_candidates = []

    for candidate in candidates:
        locator = candidate['locator']
        uniqueness = candidate['uniqueness_count']

        # If locator is unique, keep as is
        if uniqueness == 1:
            relaxed_candidates.append(candidate)
            continue

        # Try to relax the path by removing parent selectors
        parts = locator.split(' ')
        for i in range(len(parts) - 1, 0, -1):
            relaxed_locator = ' '.join(parts[i:])
            relaxed_uniqueness = _check_uniqueness(soup, relaxed_locator)

            if relaxed_uniqueness == 1:
                # Create relaxed candidate
                relaxed_candidate = candidate.copy()
                relaxed_candidate['locator'] = relaxed_locator
                relaxed_candidate['uniqueness_count'] = relaxed_uniqueness
                relaxed_candidate['reason'] += f", relaxed from '{locator}'"
                relaxed_candidates.append(relaxed_candidate)
                break
        else:
            # No relaxation worked, keep original
            relaxed_candidates.append(candidate)

    return relaxed_candidates


def _compute_aggregate_scores(candidates: List[Dict[str, Any]]) -> None:
    """Compute aggregate scores for all candidates."""
    for candidate in candidates:
        # Weighted combination of features
        weights = {
            'anchor_match_score': 0.4,
            'neighbor_similarity': 0.3,
            'subtree_similarity': 0.2,
            'heuristic_score': 0.1
        }

        score = (
            weights['anchor_match_score'] * candidate['anchor_match_score'] +
            weights['neighbor_similarity'] * candidate['neighbor_similarity'] +
            weights['subtree_similarity'] * candidate['subtree_similarity'] +
            weights['heuristic_score'] * candidate['heuristic_score']
        )

        # Boost for unique locators and visible elements
        if candidate['uniqueness_count'] == 1:
            score *= 1.2
        if candidate['visibility_flag']:
            score *= 1.1

        # Penalize for large depth differences
        depth_penalty = max(0, candidate['depth_diff'] - 2) * 0.1
        score = max(0, score - depth_penalty)

        candidate['score'] = score
        candidate['features'] = {
            'anchor_match_score': candidate['anchor_match_score'],
            'neighbor_similarity': candidate['neighbor_similarity'],
            'subtree_similarity': candidate['subtree_similarity'],
            'uniqueness_count': candidate['uniqueness_count'],
            'visibility_flag': candidate['visibility_flag'],
            'depth_diff': candidate['depth_diff'],
            'heuristic_score': candidate['heuristic_score']
        }


def _calculate_heuristic_score(element: Tag, original_locator: str) -> float:
    """Calculate a heuristic score based on element attributes matching original locator."""
    score = 0.0

    # Check ID match
    if element.get('id') and element['id'] in original_locator:
        score += 0.3

    # Check class match
    if element.get('class'):
        for cls in element['class']:
            if cls in original_locator:
                score += 0.2

    # Check name match
    if element.get('name') and element['name'] in original_locator:
        score += 0.3

    # Check text content similarity
    element_text = element.get_text(strip=True)
    if element_text:
        original_tokens = _tokenize_locator(original_locator)
        text_tokens = _tokenize_locator(element_text)
        similarity = _jaccard_similarity(original_tokens, text_tokens)
        score += similarity * 0.2

    return min(1.0, score)


def _check_uniqueness(soup: BeautifulSoup, locator: str) -> int:
    """Check how many elements match the given locator."""
    try:
        return len(soup.select(locator))
    except Exception:
        return 0


def _is_visible(element: Tag) -> bool:
    """Simple visibility check (doesn't account for CSS, just basic attributes)."""
    # Check if element or ancestors have display:none or visibility:hidden
    current = element
    while current:
        style = current.get('style', '')
        if 'display:none' in style or 'visibility:hidden' in style:
            return False
        current = current.parent if hasattr(current, 'parent') else None
    return True
