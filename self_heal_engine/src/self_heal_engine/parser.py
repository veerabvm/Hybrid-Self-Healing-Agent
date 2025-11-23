from bs4 import BeautifulSoup, Tag
from typing import List
import re


def parse_html(html: str) -> BeautifulSoup:
    """
    Parse HTML string into a BeautifulSoup object.

    Args:
        html: HTML string to parse

    Returns:
        BeautifulSoup object

    Raises:
        ValueError: If html string is empty or None
    """
    if not html or not html.strip():
        raise ValueError("HTML string cannot be empty")

    return BeautifulSoup(html, 'html.parser')


def get_visible_texts(soup: BeautifulSoup) -> List[str]:
    """
    Extract all visible text nodes from a BeautifulSoup object.

    Args:
        soup: BeautifulSoup object

    Returns:
        List of non-empty visible text strings
    """
    # Find all text nodes that are not within script, style, or hidden elements
    texts = []
    for element in soup.find_all(string=True):
        text = element.strip()
        if not text:
            continue

        parent = element.parent
        if parent.name in ['script', 'style']:
            continue

        # Skip elements with CSS classes that indicate they're hidden
        if parent.get('class') and any(cls in ['hidden', 'invisible', 'none'] for cls in parent.get('class')):
            continue

        # Skip elements with style attributes that hide them
        style = parent.get('style', '').lower()
        if 'display: none' in style or 'visibility: hidden' in style:
            continue

        texts.append(text)
    return texts


def find_elements_by_attr(soup: BeautifulSoup, attr_name: str) -> List[Tag]:
    """
    Find all tags that have a specific attribute.

    Args:
        soup: BeautifulSoup object
        attr_name: Name of the attribute to search for

    Returns:
        List of Tag objects that have the specified attribute
    """
    return soup.find_all(attrs={attr_name: True})


def css_count(soup: BeautifulSoup, selector: str) -> int:
    """
    Count the number of elements matching a CSS selector.

    Args:
        soup: BeautifulSoup object
        selector: CSS selector string

    Returns:
        Number of matching elements
    """
    return len(soup.select(selector))


def node_depth(node: Tag) -> int:
    """
    Calculate the depth of a node in the DOM tree.

    Args:
        node: BeautifulSoup Tag object

    Returns:
        Depth level (0 for root, 1 for direct children, etc.)
    """
    depth = 0
    current = node
    while current.parent and current.parent.name != '[document]':
        depth += 1
        current = current.parent
    return depth


def get_subtree_html(node: Tag) -> str:
    """
    Extract the HTML of a node and its subtree.

    Args:
        node: BeautifulSoup Tag object

    Returns:
        HTML string of the node and its children
    """
    return str(node)


def mask_pii(html: str, rules: List[str] = None) -> str:
    """
    Mask personally identifiable information in HTML.

    Args:
        html: HTML string to process
        rules: List of PII types to mask (emails, phones, user_ids)

    Returns:
        HTML string with PII masked
    """
    if not rules:
        rules = ["emails", "phones", "user_ids"]

    masked_html = html

    if "emails" in rules:
        # Mask email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        masked_html = re.sub(email_pattern, '[EMAIL_MASKED]', masked_html)

    if "phones" in rules:
        # Mask phone numbers (basic pattern)
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        masked_html = re.sub(phone_pattern, '[PHONE_MASKED]', masked_html)

    if "user_ids" in rules:
        # Mask common user ID patterns
        user_id_pattern = r'\b(user|id|account)[\-_]?\d+\b'
        masked_html = re.sub(user_id_pattern, '[USER_ID_MASKED]', masked_html, flags=re.IGNORECASE)

    return masked_html
