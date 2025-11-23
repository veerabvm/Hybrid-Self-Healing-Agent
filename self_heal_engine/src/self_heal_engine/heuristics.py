import difflib
import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup, Tag


def generate_candidates(
    soup: BeautifulSoup,
    original_locator: str,
    original_type: str,
    context: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Generate candidate locators using various heuristic rules.

    Args:
        soup: BeautifulSoup object of the page
        original_locator: The original locator that failed
        original_type: The type of the original locator ('css', 'xpath', 'id', 'name')
        context: Optional context information (e.g., visible text, surrounding elements)

    Returns:
        List of candidate dictionaries, sorted by score descending
    """
    candidates = []

    # Rule 1: data-test-* exact match
    candidates.extend(_rule_data_test_exact(soup, original_locator))

    # Rule 2: id exact match
    candidates.extend(_rule_id_exact(soup, original_locator))

    # Rule 3: name exact match
    candidates.extend(_rule_name_exact(soup, original_locator))

    # Rule 4: tokenized id/class fuzzy match
    candidates.extend(_rule_tokenized_fuzzy(soup, original_locator))

    # Rule 5: visible text similarity match
    candidates.extend(_rule_visible_text_similarity(soup, original_locator, context))

    # Rule 6: class name exact match
    candidates.extend(_rule_class_exact(soup, original_locator))

    # Rule 7: css selector direct match + simplified selector fallback
    candidates.extend(_rule_css_selector(soup, original_locator))

    # Rule 8: hyperlink text exact match
    candidates.extend(_rule_hyperlink_exact(soup, original_locator))

    # Rule 9: hyperlink partial text match
    candidates.extend(_rule_hyperlink_partial(soup, original_locator))

    # Rule 10: combined id/name/class similarity
    candidates.extend(_rule_combined_similarity(soup, original_locator))

    # Sort by score descending and return
    return sorted(candidates, key=lambda x: x['score'], reverse=True)


def _rule_data_test_exact(soup: BeautifulSoup, original_locator: str) -> List[Dict[str, Any]]:
    """Rule 1: data-test-* exact match"""
    candidates = []

    # Look for data-test attributes that match the original locator
    for attr in ['data-test', 'data-testid', 'data-test-id', 'data-cy']:
        elements = soup.find_all(attrs={attr: original_locator})
        for element in elements:
            candidates.append({
                'locator': f'[{attr}="{original_locator}"]',
                'type': 'css',
                'score': 1.0,
                'reason': f'data-test-{attr.replace("data-", "")} exact match'
            })

    return candidates


def _rule_id_exact(soup: BeautifulSoup, original_locator: str) -> List[Dict[str, Any]]:
    """Rule 2: id exact match"""
    candidates = []

    element = soup.find(id=original_locator)
    if element:
        candidates.append({
            'locator': f'#{original_locator}',
            'type': 'css',
            'score': 1.0,
            'reason': 'id exact match'
        })

    return candidates


def _rule_name_exact(soup: BeautifulSoup, original_locator: str) -> List[Dict[str, Any]]:
    """Rule 3: name exact match"""
    candidates = []

    elements = soup.find_all(attrs={'name': original_locator})
    for element in elements:
        candidates.append({
            'locator': f'[name="{original_locator}"]',
            'type': 'css',
            'score': 1.0,
            'reason': 'name exact match'
        })

    return candidates


def _rule_tokenized_fuzzy(soup: BeautifulSoup, original_locator: str) -> List[Dict[str, Any]]:
    """Rule 4: tokenized id/class fuzzy match using Jaccard similarity"""
    candidates = []

    # Tokenize original locator
    original_tokens = _tokenize_locator(original_locator)

    # Check all elements with id or class attributes
    for element in soup.find_all(attrs={'id': True}):
        element_tokens = _tokenize_locator(element['id'])
        score = _jaccard_similarity(original_tokens, element_tokens)
        if score > 0.3:  # Minimum threshold
            candidates.append({
                'locator': f'#{element["id"]}',
                'type': 'css',
                'score': score,
                'reason': f'id tokenized fuzzy match (Jaccard: {score:.2f})'
            })

    for element in soup.find_all(attrs={'class': True}):
        for class_name in element['class']:
            element_tokens = _tokenize_locator(class_name)
            score = _jaccard_similarity(original_tokens, element_tokens)
            if score > 0.3:
                candidates.append({
                    'locator': f'.{class_name}',
                    'type': 'css',
                    'score': score,
                    'reason': f'class tokenized fuzzy match (Jaccard: {score:.2f})'
                })

    return candidates


def _rule_visible_text_similarity(
    soup: BeautifulSoup,
    original_locator: str,
    context: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Rule 5: visible text similarity match"""
    candidates = []

    # Get expected text from context or try to extract from original locator
    expected_text = None
    if context and 'visible_text' in context:
        expected_text = context['visible_text']
    elif original_locator.startswith('//*') and 'text()' in original_locator:
        # Try to extract text from XPath like //*[text()='Login']
        match = re.search(r"text\(\)='([^']+)'", original_locator)
        if match:
            expected_text = match.group(1)

    if not expected_text:
        return candidates

    # Find elements with similar visible text
    for element in soup.find_all():
        element_text = element.get_text(strip=True)
        if element_text:
            similarity = difflib.SequenceMatcher(None, expected_text, element_text).ratio()
            if similarity > 0.6:  # Minimum threshold
                # Generate a locator for this element
                locator = _generate_element_locator(element)
                if locator:
                    candidates.append({
                        'locator': locator,
                        'type': 'css',
                        'score': similarity,
                        'reason': f'visible text similarity ({similarity:.2f})'
                    })

    return candidates


def _rule_relaxed_xpath(soup: BeautifulSoup, original_locator: str) -> List[Dict[str, Any]]:
    """Rule 6: relaxed XPath match (remove [n] indices)"""
    candidates = []

    # Remove position indices like [1], [2], etc.
    relaxed_xpath = re.sub(r'\[\d+\]', '', original_locator)

    if relaxed_xpath != original_locator:
        # Try to find elements matching the relaxed XPath
        try:
            # This is a simplified approach - in practice you'd need XPath evaluation
            # For now, we'll use CSS selector equivalents where possible
            css_equivalent = _xpath_to_css(relaxed_xpath)
            if css_equivalent:
                count = len(soup.select(css_equivalent))
                if count > 0:
                    candidates.append({
                        'locator': css_equivalent,
                        'type': 'css',
                        'score': 0.8,  # High but not perfect score
                        'reason': 'relaxed XPath (removed indices)'
                    })
        except Exception:
            pass  # Skip if conversion fails

    return candidates


def _tokenize_locator(locator: str) -> set:
    """Tokenize a locator string by splitting on delimiters and converting to lowercase"""
    # Split on common delimiters and convert to lowercase
    tokens = re.split(r'[-_\s]+', locator.lower())
    # Remove empty tokens and filter out common words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    return {token for token in tokens if token and token not in stop_words}


def _jaccard_similarity(set1: set, set2: set) -> float:
    """Calculate Jaccard similarity between two sets"""
    if not set1 and not set2:
        return 1.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


def _generate_element_locator(element: Tag) -> Optional[str]:
    """Generate a CSS locator for an element"""
    # Try id first
    if element.get('id'):
        return f'#{element["id"]}'

    # Try data-testid or data-test
    for attr in ['data-testid', 'data-test', 'data-cy']:
        if element.get(attr):
            return f'[{attr}="{element[attr]}"]'

    # Try name
    if element.get('name'):
        return f'[name="{element["name"]}"]'

    # Try class combination
    if element.get('class'):
        # Use first class for simplicity
        return f'.{element["class"][0]}'

    # Fallback to tag name only (not very specific)
    return element.name


def _xpath_to_css(xpath: str) -> Optional[str]:
    """Convert simple XPath to CSS selector (simplified implementation)"""
    # This is a very basic conversion for common cases
    # Remove leading // and handle simple cases
    if xpath.startswith('//'):
        xpath = xpath[2:]

    # Handle simple tag selectors
    if '/' not in xpath and '[' not in xpath:
        return xpath

    # Handle some common patterns
    if xpath == '*':
        return '*'

    # More complex XPath would need proper parsing
    # For now, return None for unsupported patterns
    return None


def _rule_class_exact(soup: BeautifulSoup, original_locator: str) -> List[Dict[str, Any]]:
    """Rule 6: class name exact match"""
    candidates = []

    elements = soup.find_all(attrs={'class': True})
    for element in elements:
        for class_name in element['class']:
            if class_name == original_locator:
                candidates.append({
                    'locator': f'.{class_name}',
                    'type': 'css',
                    'score': 1.0,
                    'reason': 'class name exact match'
                })

    return candidates


def _rule_css_selector(soup: BeautifulSoup, original_locator: str) -> List[Dict[str, Any]]:
    """Rule 7: css selector direct match + simplified selector fallback"""
    candidates = []

    # Try the original locator as a CSS selector
    try:
        elements = soup.select(original_locator)
        if elements:
            candidates.append({
                'locator': original_locator,
                'type': 'css',
                'score': 1.0,
                'reason': 'css selector direct match'
            })
    except Exception:
        pass

    # Try simplified fallback - remove last part of complex selectors
    if ' ' in original_locator:
        parts = original_locator.split()
        for i in range(len(parts) - 1, 0, -1):
            simplified = ' '.join(parts[:i])
            try:
                elements = soup.select(simplified)
                if elements:
                    candidates.append({
                        'locator': simplified,
                        'type': 'css',
                        'score': 0.8,
                        'reason': 'css selector simplified fallback'
                    })
                    break  # Only add the first working simplification
            except Exception:
                continue

    return candidates


def _rule_hyperlink_exact(soup: BeautifulSoup, original_locator: str) -> List[Dict[str, Any]]:
    """Rule 8: hyperlink text exact match"""
    candidates = []

    links = soup.find_all('a')
    for link in links:
        link_text = link.get_text(strip=True)
        if link_text == original_locator:
            locator = _generate_element_locator(link)
            if locator:
                candidates.append({
                    'locator': locator,
                    'type': 'css',
                    'score': 0.9,
                    'reason': 'hyperlink text exact match'
                })

    return candidates


def _rule_hyperlink_partial(soup: BeautifulSoup, original_locator: str) -> List[Dict[str, Any]]:
    """Rule 9: hyperlink partial text match"""
    candidates = []

    links = soup.find_all('a')
    for link in links:
        link_text = link.get_text(strip=True)
        if original_locator.lower() in link_text.lower() and link_text:
            similarity = len(original_locator) / len(link_text) if len(link_text) > 0 else 0
            if similarity > 0.5:  # At least 50% match
                locator = _generate_element_locator(link)
                if locator:
                    candidates.append({
                        'locator': locator,
                        'type': 'css',
                        'score': similarity * 0.8,
                        'reason': f'hyperlink partial text match ({similarity:.2f})'
                    })

    return candidates


def _rule_combined_similarity(soup: BeautifulSoup, original_locator: str) -> List[Dict[str, Any]]:
    """Rule 10: combined id/name/class similarity"""
    candidates = []

    original_tokens = _tokenize_locator(original_locator)

    # Check elements with id, name, or class attributes
    for element in soup.find_all():
        combined_tokens = set()

        # Add id tokens
        if element.get('id'):
            combined_tokens.update(_tokenize_locator(element['id']))

        # Add name tokens
        if element.get('name'):
            combined_tokens.update(_tokenize_locator(element['name']))

        # Add class tokens
        if element.get('class'):
            for class_name in element['class']:
                combined_tokens.update(_tokenize_locator(class_name))

        if combined_tokens:
            similarity = _jaccard_similarity(original_tokens, combined_tokens)
            if similarity > 0.4:  # Minimum threshold
                locator = _generate_element_locator(element)
                if locator:
                    candidates.append({
                        'locator': locator,
                        'type': 'css',
                        'score': similarity,
                        'reason': f'combined id/name/class similarity ({similarity:.2f})'
                    })

    return candidates
