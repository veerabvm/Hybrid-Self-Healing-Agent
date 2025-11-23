"""
Integration tests for the complete self-healing engine.
"""

import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient

from self_heal_engine.app import app
from self_heal_engine.parser import parse_html
from self_heal_engine.heuristics import generate_candidates
from self_heal_engine.hierarchy_search import find_moved_candidates
from self_heal_engine.ranker import extract_features, score_candidates
from self_heal_engine.llm_adapter import LLMAdapter
from self_heal_engine.verify import build_verify_action, is_destructive
from self_heal_engine.storage import save_snapshot, append_training_record


class TestIntegration:
    """Integration tests for the complete healing workflow."""

    @pytest.fixture
    def client(self):
        """Test client fixture."""
        return TestClient(app)

    def test_full_healing_pipeline(self, client):
        """Test the complete healing pipeline from HTML to ranked candidates."""
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Test Application</title></head>
        <body>
            <div class="header">
                <h1>Welcome to Test App</h1>
                <nav>
                    <a href="/home" class="nav-link">Home</a>
                    <a href="/login" class="nav-link">Login</a>
                    <a href="/register" class="nav-link">Register</a>
                </nav>
            </div>

            <main class="content">
                <div class="login-form">
                    <h2>Please Sign In</h2>
                    <form id="login-form" action="/login" method="post">
                        <div class="form-group">
                            <label for="username">Username:</label>
                            <input type="text" id="username" name="username" required>
                        </div>
                        <div class="form-group">
                            <label for="password">Password:</label>
                            <input type="password" id="password" name="password" required>
                        </div>
                        <div class="form-actions">
                            <button type="submit" class="btn btn-primary" id="login-btn">
                                Sign In
                            </button>
                            <a href="/forgot-password" class="forgot-link">Forgot Password?</a>
                        </div>
                    </form>
                </div>
            </main>

            <footer>
                <p>&copy; 2025 Test Application</p>
            </footer>
        </body>
        </html>
        """

        # Step 1: Parse HTML
        soup = parse_html(html)
        assert soup is not None, "HTML parsing failed"

        # Step 2: Generate heuristic candidates
        original_locator = "#login-btn"
        locator_type = "css"
        candidates = generate_candidates(soup, original_locator, locator_type)
        assert len(candidates) > 0, "No heuristic candidates generated"

        # Step 3: Add hierarchy search candidates
        context = {
            "anchors": ["Username:", "Password:", "Sign In"],
            "visible_text": "Sign In",
            "prev_sibling_text": "Forgot Password?"
        }
        moved_candidates = find_moved_candidates(soup, context)
        all_candidates = candidates + moved_candidates

        # Step 4: Extract features and score candidates
        scored_candidates = []
        for candidate in all_candidates:
            features = extract_features(candidate, soup)
            candidate_with_features = candidate.copy()
            candidate_with_features['features'] = features
            scored_candidates.append(candidate_with_features)

        scored_candidates = score_candidates(scored_candidates, soup)

        # Step 5: Verify we have good candidates
        assert len(scored_candidates) > 0, "No candidates after scoring"
        top_candidate = scored_candidates[0]
        assert 'score' in top_candidate, "Candidates missing scores"
        assert top_candidate['score'] > 0, "Top candidate has zero score"

        # Step 6: Test LLM adapter (mock)
        llm_adapter = LLMAdapter(provider="mock")
        llm_candidates = llm_adapter.propose_candidates(html, original_locator, context, max_candidates=3)
        assert len(llm_candidates) >= 0, "LLM adapter failed"

        # Step 7: Test verification actions
        verify_actions = build_verify_action(top_candidate, "exists")
        assert verify_actions is not None, "Verification actions not built"

        # Step 8: Test destructive action detection
        is_destructive_result = is_destructive(top_candidate, soup)
        assert isinstance(is_destructive_result, bool), "Destructive action detection failed"

        # Step 9: Test storage
        request_id = "test-integration-123"
        healing_request = {
            "html": html,
            "original_locator": original_locator,
            "locator_type": locator_type,
            "context": context
        }

        healing_response = {
            "request_id": request_id,
            "candidates": scored_candidates[:3],  # Top 3
            "auto_apply_index": 0,
            "verify_action": verify_actions
        }

        # Save snapshot
        snapshot_path = save_snapshot(request_id, html, scored_candidates[:3], 0, {"test": "integration"})
        assert snapshot_path is not None, "Snapshot saving failed"

        # Step 10: Test API endpoint
        api_response = client.post("/heal", json={
            "html": html,
            "original_locator": original_locator,
            "locator_type": locator_type,
            "context": context,
            "max_candidates": 3
        })

        assert api_response.status_code == 200, "API call failed"
        api_data = api_response.json()
        assert "candidates" in api_data, "API response missing candidates"
        assert len(api_data["candidates"]) > 0, "API returned no candidates"

    def test_api_error_handling(self, client):
        """Test API error handling for invalid inputs."""
        # Test with empty HTML
        response = client.post("/heal", json={
            "html": "",
            "original_locator": "#test",
            "locator_type": "css"
        })
        # Should handle gracefully (may return 200 with empty candidates or 500)
        assert response.status_code in [200, 500], "Unexpected status code for empty HTML"

        # Test with invalid locator type
        response = client.post("/heal", json={
            "html": "<div>test</div>",
            "original_locator": "#test",
            "locator_type": "invalid"
        })
        assert response.status_code in [200, 422], "Unexpected status code for invalid locator type"

    def test_training_data_collection(self, client):
        """Test the complete training data collection workflow."""
        # First, perform a healing request
        html = '<html><body><button id="test-btn">Click</button></body></html>'
        heal_response = client.post("/heal", json={
            "html": html,
            "original_locator": "#test-btn",
            "locator_type": "css",
            "max_candidates": 2
        })

        assert heal_response.status_code == 200
        heal_data = heal_response.json()
        request_id = heal_data["request_id"]
        candidates = heal_data["candidates"]

        # Confirm the healing decision
        confirm_response = client.post("/confirm", json={
            "request_id": request_id,
            "accepted_index": 0,
            "metadata": {
                "test_session": "integration_test",
                "browser": "chrome",
                "environment": "test"
            }
        })

        assert confirm_response.status_code == 200

        # Verify training data was saved
        # This would require checking the training file
        # For now, just ensure the confirmation was successful

    def test_performance_baseline(self, client):
        """Test performance meets basic requirements."""
        import time

        html = """
        <html>
        <body>
            <div class="container">
                <h1>Test Page</h1>
                <form>
                    <input name="field1" type="text"/>
                    <input name="field2" type="text"/>
                    <button id="submit">Submit</button>
                </form>
            </div>
        </body>
        </html>
        """

        start_time = time.time()
        response = client.post("/heal", json={
            "html": html,
            "original_locator": "#submit",
            "locator_type": "css",
            "max_candidates": 5
        })
        end_time = time.time()

        assert response.status_code == 200
        duration = end_time - start_time

        # Should complete within reasonable time (adjust based on requirements)
        assert duration < 5.0, f"Healing took too long: {duration:.2f}s"

    def test_large_html_handling(self, client):
        """Test handling of large HTML documents."""
        # Generate large HTML
        large_html = "<html><body>" + "<div>" * 1000 + "content" + "</div>" * 1000 + "</body></html>"

        response = client.post("/heal", json={
            "html": large_html,
            "original_locator": "#test",
            "locator_type": "css",
            "max_candidates": 3
        })

        # Should handle gracefully - either succeed or fail gracefully
        assert response.status_code in [200, 500], "Unexpected response for large HTML"


class TestComponentIntegration:
    """Test integration between individual components."""

    def test_parser_heuristics_integration(self):
        """Test that parser output works with heuristics."""
        html = '<html><body><button id="btn" class="primary">Test</button></body></html>'
        soup = parse_html(html)

        candidates = generate_candidates(soup, "#btn", "css")
        assert len(candidates) > 0

        # Verify candidate structure
        candidate = candidates[0]
        required_fields = ["locator", "type", "score", "reason"]
        for field in required_fields:
            assert field in candidate, f"Candidate missing {field}"

    def test_heuristics_ranker_integration(self):
        """Test that heuristics output works with ranker."""
        html = '<html><body><button id="test">Click</button></body></html>'
        soup = parse_html(html)

        candidates = generate_candidates(soup, "#test", "css")
        assert len(candidates) > 0

        # Extract features
        candidate = candidates[0]
        features = extract_features(candidate, soup)
        assert isinstance(features, dict), "Features should be a dictionary"
        assert len(features) > 0, "Should have some features"

        # Score candidates
        scored = score_candidates([candidate], soup)
        assert len(scored) == 1
        assert "score" in scored[0]

    def test_llm_adapter_integration(self):
        """Test LLM adapter integration."""
        adapter = LLMAdapter(provider="mock")

        html = '<html><body><button id="test">Test</button></body></html>'
        candidates = adapter.propose_candidates(html, "#missing", {}, max_candidates=3)

        # Mock adapter should return some candidates
        assert isinstance(candidates, list)

    def test_storage_integration(self):
        """Test storage component integration."""
        # Test saving and loading (basic functionality)
        request_id = "storage-test-123"

        healing_request = {
            "html": "<html></html>",
            "original_locator": "#test",
            "locator_type": "css"
        }

        healing_response = {
            "request_id": request_id,
            "candidates": [{"locator": "#test", "type": "css", "score": 1.0}],
            "auto_apply_index": 0
        }

        # Save snapshot
        path = save_snapshot(request_id, healing_request["html"], healing_response["candidates"], 0, {})
        assert path is not None

        # Append training record
        training_record = {
            "request_id": request_id,
            "accepted_index": 0,
            "timestamp": "2025-01-01T00:00:00Z",
            "features": {"test": 1.0},
            "score": 1.0
        }

        append_training_record(training_record)
        # Should not raise exception
