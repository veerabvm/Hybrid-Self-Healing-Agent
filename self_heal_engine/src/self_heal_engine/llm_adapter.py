"""
LLM Adapter for generating additional locator candidates.
"""

import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from .parser import mask_pii


class LLMAdapter:
    """
    Adapter for LLM-based locator candidate generation.
    Supports multiple providers with fallback to mock implementation.
    """

    def __init__(self, provider: str = "mock"):
        """
        Initialize LLM adapter.

        Args:
            provider: LLM provider ('mock', 'openai', 'apex', 'local')
        """
        self.provider = provider
        self._validate_provider()

    def _validate_provider(self):
        """Validate that the provider is supported."""
        supported = ['mock', 'openai', 'apex', 'local']
        if self.provider not in supported:
            raise ValueError(f"Unsupported provider: {self.provider}. Supported: {supported}")

    def propose_candidates(self, html: str, original_locator: str,
                          context: Optional[Dict[str, Any]] = None,
                          max_candidates: int = 5) -> List[Dict[str, Any]]:
        """
        Generate candidate locators using LLM.

        Args:
            html: Page HTML
            original_locator: The failed locator
            context: Additional context
            max_candidates: Maximum candidates to return

        Returns:
            List of candidate dictionaries
        """
        # Mask PII for safety
        masked_html = mask_pii(html)

        if self.provider == "mock":
            return self._mock_propose_candidates(masked_html, original_locator, context, max_candidates)
        elif self.provider == "openai":
            return self._openai_propose_candidates(masked_html, original_locator, context, max_candidates)
        elif self.provider == "apex":
            return self._apex_propose_candidates(masked_html, original_locator, context, max_candidates)
        elif self.provider == "local":
            return self._local_propose_candidates(masked_html, original_locator, context, max_candidates)
        else:
            return []

    def validate_candidates(self, candidates: List[Dict[str, Any]],
                           soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Validate that candidate locators match at least one element.

        Args:
            candidates: List of candidate dictionaries
            soup: BeautifulSoup object

        Returns:
            List of valid candidates
        """
        valid_candidates = []

        for candidate in candidates:
            locator = candidate['locator']
            try:
                matches = soup.select(locator)
                if matches:  # At least one match
                    candidate_copy = candidate.copy()
                    candidate_copy['validation_count'] = len(matches)
                    valid_candidates.append(candidate_copy)
            except Exception:
                # Invalid selector, skip
                continue

        return valid_candidates

    def _mock_propose_candidates(self, html: str, original_locator: str,
                                context: Optional[Dict[str, Any]] = None,
                                max_candidates: int = 5) -> List[Dict[str, Any]]:
        """Mock implementation returning canned candidates."""
        candidates = []

        # Simple heuristics for mock implementation
        soup = BeautifulSoup(html, 'html.parser')

        # Try some common patterns
        patterns = [
            # Look for buttons with similar text
            lambda: self._find_similar_buttons(soup, original_locator),
            # Look for elements with similar IDs
            lambda: self._find_similar_ids(soup, original_locator),
            # Look for elements with similar classes
            lambda: self._find_similar_classes(soup, original_locator),
        ]

        for pattern_func in patterns:
            try:
                pattern_candidates = pattern_func()
                candidates.extend(pattern_candidates)
                if len(candidates) >= max_candidates:
                    break
            except Exception:
                continue

        # Limit to max_candidates
        candidates = candidates[:max_candidates]

        # Add LLM-generated metadata
        for candidate in candidates:
            candidate['source'] = 'llm_mock'
            candidate['confidence'] = 0.7

        return candidates

    def _openai_propose_candidates(self, html: str, original_locator: str,
                                  context: Optional[Dict[str, Any]] = None,
                                  max_candidates: int = 5) -> List[Dict[str, Any]]:
        """OpenAI GPT implementation (scaffold only)."""
        # TODO: Implement actual OpenAI API calls
        # This would require:
        # - openai package
        # - API key configuration
        # - Prompt engineering for locator generation
        # - Response parsing

        # For now, fall back to mock
        return self._mock_propose_candidates(html, original_locator, context, max_candidates)

    def _apex_propose_candidates(self, html: str, original_locator: str,
                                context: Optional[Dict[str, Any]] = None,
                                max_candidates: int = 5) -> List[Dict[str, Any]]:
        """APEX-specific implementation (scaffold only)."""
        # TODO: Implement APEX integration
        # This would require APEX-specific APIs and authentication

        # For now, fall back to mock
        return self._mock_propose_candidates(html, original_locator, context, max_candidates)

    def _local_propose_candidates(self, html: str, original_locator: str,
                                 context: Optional[Dict[str, Any]] = None,
                                 max_candidates: int = 5) -> List[Dict[str, Any]]:
        """Local LLM implementation (scaffold only)."""
        # TODO: Implement local LLM integration
        # This could use llama.cpp, transformers, etc.

        # For now, fall back to mock
        return self._mock_propose_candidates(html, original_locator, context, max_candidates)

    def _find_similar_buttons(self, soup: BeautifulSoup, original_locator: str) -> List[Dict[str, Any]]:
        """Find buttons with similar text or attributes."""
        candidates = []
        buttons = soup.find_all('button')

        for button in buttons:
            # Check text similarity
            button_text = button.get_text(strip=True)
            if button_text and len(button_text) > 2:
                similarity = self._text_similarity(original_locator, button_text)
                if similarity > 0.3:
                    candidates.append({
                        'locator': self._generate_locator(button),
                        'type': 'css',
                        'score': similarity * 0.8,
                        'reason': f'LLM: similar button text ({similarity:.2f})'
                    })

        return candidates[:3]  # Limit per pattern

    def _find_similar_ids(self, soup: BeautifulSoup, original_locator: str) -> List[Dict[str, Any]]:
        """Find elements with similar IDs."""
        candidates = []
        elements_with_ids = soup.find_all(attrs={'id': True})

        for element in elements_with_ids:
            element_id = element['id']
            similarity = self._text_similarity(original_locator, element_id)
            if similarity > 0.4:
                candidates.append({
                    'locator': f'#{element_id}',
                    'type': 'css',
                    'score': similarity * 0.9,
                    'reason': f'LLM: similar ID ({similarity:.2f})'
                })

        return candidates[:2]

    def _find_similar_classes(self, soup: BeautifulSoup, original_locator: str) -> List[Dict[str, Any]]:
        """Find elements with similar classes."""
        candidates = []
        elements_with_classes = soup.find_all(attrs={'class': True})

        for element in elements_with_classes:
            for class_name in element['class']:
                similarity = self._text_similarity(original_locator, class_name)
                if similarity > 0.4:
                    candidates.append({
                        'locator': f'.{class_name}',
                        'type': 'css',
                        'score': similarity * 0.7,
                        'reason': f'LLM: similar class ({similarity:.2f})'
                    })

        return candidates[:2]

    def _generate_locator(self, element) -> str:
        """Generate a CSS locator for an element."""
        if element.get('id'):
            return f'#{element["id"]}'
        elif element.get('class'):
            return f'.{element["class"][0]}'
        elif element.get('name'):
            return f'[name="{element["name"]}"]'
        else:
            return element.name

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity."""
        if not text1 or not text2:
            return 0.0

        # Simple token overlap
        tokens1 = set(text1.lower().split())
        tokens2 = set(text2.lower().split())

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union if union > 0 else 0.0
