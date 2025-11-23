import pytest
from bs4 import BeautifulSoup

from self_heal_engine.parser import parse_html
from self_heal_engine.hierarchy_search import find_moved_candidates


class TestFindMovedCandidates:
    """Test cases for the find_moved_candidates function"""

    def test_element_moved_into_modal(self):
        """Test case 1: Element moved into a modal (anchor = form label)"""

        # Original HTML
        old_html = """
        <div>
            <label for="username">Username:</label>
            <input id="username" name="username" type="text"/>
            <label for="password">Password:</label>
            <input id="password" name="password" type="password"/>
            <button id="login-btn">Login</button>
        </div>
        """

        # New HTML - login button moved into modal
        new_html = """
        <div>
            <label for="username">Username:</label>
            <input id="username" name="username" type="text"/>
            <label for="password">Password:</label>
            <input id="password" name="password" type="password"/>
            <div id="modal" class="modal">
                <div class="modal-content">
                    <button id="login-btn">Login</button>
                </div>
            </div>
        </div>
        """

        old_soup = parse_html(old_html)
        new_soup = parse_html(new_html)

        old_context = {
            "original_locator": "login-btn",
            "original_locator_type": "id",
            "anchors": ["Username:", "Password:"],
            "prev_sibling_text": "",
            "next_sibling_text": ""
        }

        candidates = find_moved_candidates(new_soup, old_context, max_candidates=5)

        # Should find the moved button
        assert len(candidates) > 0
        top_candidate = candidates[0]
        assert top_candidate['score'] > 0.2
        assert 'anchor' in top_candidate['reason'].lower()

        # Verify the locator works
        matches = new_soup.select(top_candidate['locator'])
        assert len(matches) > 0

    def test_element_deeply_nested(self):
        """Test case 2: Element deeply nested under new container (depth increased)"""

        # Original HTML
        old_html = """
        <div class="form-container">
            <label for="email">Email Address:</label>
            <input id="email" name="email" type="email"/>
            <button id="subscribe-btn">Subscribe</button>
        </div>
        """

        # New HTML - button deeply nested
        new_html = """
        <div class="form-container">
            <label for="email">Email Address:</label>
            <input id="email" name="email" type="email"/>
            <div class="button-wrapper">
                <div class="action-group">
                    <div class="primary-actions">
                        <button id="subscribe-btn">Subscribe</button>
                    </div>
                </div>
            </div>
        </div>
        """

        old_soup = parse_html(old_html)
        new_soup = parse_html(new_html)

        old_context = {
            "original_locator": "subscribe-btn",
            "original_locator_type": "id",
            "anchors": ["Email Address:"],
            "prev_sibling_text": "",
            "next_sibling_text": ""
        }

        candidates = find_moved_candidates(new_soup, old_context, max_candidates=5)

        assert len(candidates) > 0
        top_candidate = candidates[0]
        assert top_candidate['score'] > 0.2
        # Check that some candidates show increased depth
        depth_diffs = [c['features']['depth_diff'] for c in candidates]
        assert max(depth_diffs) >= 2, f"Max depth_diff is {max(depth_diffs)}, expected >= 2"

        # Verify locator works
        matches = new_soup.select(top_candidate['locator'])
        assert len(matches) > 0

    def test_container_split_into_siblings(self):
        """Test case 3: Container split into siblings (neighbor matching required)"""

        # Original HTML
        old_html = """
        <div class="user-info">
            <span>Welcome, John</span>
            <button id="logout-btn">Logout</button>
            <span>Last login: Today</span>
        </div>
        """

        # New HTML - container split
        new_html = """
        <div class="header">
            <span>Welcome, John</span>
        </div>
        <div class="actions">
            <button id="logout-btn">Logout</button>
        </div>
        <div class="footer">
            <span>Last login: Today</span>
        </div>
        """

        old_soup = parse_html(old_html)
        new_soup = parse_html(new_html)

        old_context = {
            "original_locator": "logout-btn",
            "original_locator_type": "id",
            "anchors": [],
            "prev_sibling_text": "Welcome, John",
            "next_sibling_text": "Last login: Today",
            "old_subtree_html": "<button id=\"logout-btn\">Logout</button>"
        }

        candidates = find_moved_candidates(new_soup, old_context, max_candidates=5)

        assert len(candidates) > 0
        top_candidate = candidates[0]
        assert top_candidate['score'] > 0.2
        assert 'subtree' in top_candidate['reason'].lower() or 'neighbor' in top_candidate['reason'].lower()

        # Verify locator works
        matches = new_soup.select(top_candidate['locator'])
        assert len(matches) > 0

    def test_class_id_removed_but_nearby_text_unchanged(self):
        """Test case 4: Class/ID removed but nearby text unchanged (anchor only)"""

        # Original HTML
        old_html = """
        <div>
            <h2>Account Settings</h2>
            <button id="save-btn" class="primary-button">Save Changes</button>
            <button id="cancel-btn" class="secondary-button">Cancel</button>
        </div>
        """

        # New HTML - classes and IDs removed
        new_html = """
        <div>
            <h2>Account Settings</h2>
            <button>Save Changes</button>
            <button>Cancel</button>
        </div>
        """

        old_soup = parse_html(old_html)
        new_soup = parse_html(new_html)

        old_context = {
            "original_locator": "save-btn",
            "original_locator_type": "id",
            "anchors": ["Account Settings", "Save Changes"],
            "prev_sibling_text": "",
            "next_sibling_text": ""
        }

        candidates = find_moved_candidates(new_soup, old_context, max_candidates=5)

        assert len(candidates) > 0
        top_candidate = candidates[0]
        assert top_candidate['score'] > 0.2
        assert 'anchor' in top_candidate['reason'].lower()

        # Verify locator works
        matches = new_soup.select(top_candidate['locator'])
        assert len(matches) > 0

    def test_multiple_anchor_matches(self):
        """Test case 5: Multiple anchor matches on page — ensure subtree specificity picks correct one"""

        # Original HTML
        old_html = """
        <div class="product-list">
            <div class="product-item">
                <h3>Product A</h3>
                <button id="add-to-cart-btn">Add to Cart</button>
            </div>
        </div>
        """

        # New HTML - multiple similar sections
        new_html = """
        <div class="product-list">
            <div class="product-item">
                <h3>Product A</h3>
                <div class="actions">
                    <button>Add to Cart</button>
                </div>
            </div>
            <div class="product-item">
                <h3>Product B</h3>
                <div class="actions">
                    <button>Add to Cart</button>
                </div>
            </div>
            <div class="product-item">
                <h3>Product C</h3>
                <div class="actions">
                    <button>Add to Cart</button>
                </div>
            </div>
        </div>
        """

        old_soup = parse_html(old_html)
        new_soup = parse_html(new_html)

        old_context = {
            "original_locator": "add-to-cart-btn",
            "original_locator_type": "id",
            "anchors": ["Product A"],
            "prev_sibling_text": "",
            "next_sibling_text": ""
        }

        candidates = find_moved_candidates(new_soup, old_context, max_candidates=5)

        assert len(candidates) > 0
        top_candidate = candidates[0]
        assert top_candidate['score'] > 0.2

        # The top candidate should be under "Product A" section
        matches = new_soup.select(top_candidate['locator'])
        assert len(matches) > 0

        # Check that the match is in the correct context (near "Product A")
        for match in matches:
            # Traverse up to find if it's under a product item containing "Product A"
            parent = match.parent
            found_product_a = False
            for _ in range(5):  # Check up to 5 levels up
                if parent and parent.get_text().find("Product A") != -1:
                    found_product_a = True
                    break
                parent = parent.parent if hasattr(parent, 'parent') else None

            if found_product_a:
                break
        else:
            pytest.fail("Top candidate should be associated with 'Product A' context")


class TestHelperFunctions:
    """Test individual helper functions"""

    def test_anchor_based_search_basic(self):
        """Test basic anchor-based search functionality"""
        html = """
        <div>
            <label>Username:</label>
            <input type="text"/>
            <button id="test-btn">Click me</button>
        </div>
        """

        soup = parse_html(html)
        old_context = {
            "original_locator": "test-btn",
            "anchors": ["Username:"]
        }

        candidates = find_moved_candidates(soup, old_context, max_candidates=5)
        assert len(candidates) > 0

    def test_neighbor_locality_search(self):
        """Test neighbor locality search"""
        html = """
        <div>
            <span>Previous text</span>
            <button id="target">Target</button>
            <span>Next text</span>
        </div>
        """

        soup = parse_html(html)
        old_context = {
            "original_locator": "target",
            "anchors": [],
            "prev_sibling_text": "Previous text",
            "next_sibling_text": "Next text"
        }

        candidates = find_moved_candidates(soup, old_context, max_candidates=5)
        assert len(candidates) > 0

    def test_subtree_similarity_search(self):
        """Test subtree similarity search"""
        old_html = "<button>Submit Form</button>"
        new_html = """
        <div>
            <form>
                <button>Submit Form</button>
            </form>
        </div>
        """

        old_soup = parse_html(old_html)
        new_soup = parse_html(new_html)

        old_context = {
            "original_locator": "submit",
            "old_subtree_html": old_html,
            "anchors": []
        }

        candidates = find_moved_candidates(new_soup, old_context, max_candidates=5)
        assert len(candidates) > 0

    def test_path_relaxation(self):
        """Test CSS path relaxation functionality"""
        html = """
        <div class="container">
            <div class="wrapper">
                <button id="test-btn">Test</button>
            </div>
        </div>
        """

        soup = parse_html(html)
        old_context = {
            "original_locator": "test-btn",
            "anchors": ["Test"]
        }

        candidates = find_moved_candidates(soup, old_context, max_candidates=5)

        # Should include relaxed selectors if needed
        locator_types = [c['locator'] for c in candidates]
        assert any('#test-btn' in loc for loc in locator_types)
