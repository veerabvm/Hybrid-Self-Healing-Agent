"""
Tests for the FastAPI application endpoints.
"""

import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient

from self_heal_engine.app import app


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


@pytest.fixture
async def async_client():
    """Async test client fixture."""
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


class TestHealthEndpoint:
    """Test the health check endpoint."""

    def test_health_check(self, client):
        """Test basic health check."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_health_check_async(self, async_client):
        """Test health check with async client."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data == {"status": "ok"}


class TestHealEndpoint:
    """Test the healing endpoint."""

    def test_heal_missing_fields(self, client):
        """Test healing with missing required fields."""
        # Missing page_html
        response = client.post("/heal", json={
            "request_id": "req-001",
            "original_locator": "test",
            "original_locator_type": "css",
            "action": "click"
        })
        assert response.status_code == 422  # Validation error

        # Missing original_locator
        response = client.post("/heal", json={
            "request_id": "req-001",
            "original_locator_type": "css",
            "action": "click",
            "page_html": "<div>test</div>"
        })
        assert response.status_code == 422

    def test_heal_invalid_html(self, client):
        """Test healing with invalid HTML."""
        response = client.post("/heal", json={
            "request_id": "req-001",
            "original_locator": "test",
            "original_locator_type": "css",
            "action": "click",
            "page_html": ""  # Empty HTML
        })
        assert response.status_code == 200
        data = response.json()
        assert data["healed_locator"] is None

    def test_heal_basic_functionality(self, client):
        """Test basic healing functionality with full payload."""
        payload = {
            "request_id": "req-001",
            "test_id": "login_smoke",
            "page_url": "https://app.example.com/login",
            "original_locator": "#loginBtn",
            "original_locator_type": "css",
            "action": "click",
            "page_html": "<html><body><button id=\"loginBtn\">Sign in</button></body></html>",
            "element_outer_html": "<button id=\"loginBtn\">Sign in</button>",
            "anchors": ["Email address", "Password"],
            "prev_sibling_text": "Password",
            "next_sibling_text": "Forgot password?",
            "screenshot_base64": None,
            "user_id": None,
            "username": None,
            "pii_masked": True
        }

        response = client.post("/heal", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "request_id" in data
        assert data["request_id"] == "req-001"
        assert "healed_locator" in data
        assert data["healed_locator"] is not None
        assert data["healed_locator"]["locator"] == "#loginBtn"
        assert data["healed_locator"]["type"] == "css"
        assert "candidates" in data
        assert data["candidates"] == []
        assert "auto_apply_index" in data
        assert data["auto_apply_index"] == -1
        assert "verify_action" in data
        assert data["verify_action"] is None
        assert "warning" in data
        assert data["warning"] is None
        assert "message" in data
        assert data["message"] == "updated API: received payload"

    def test_heal_with_context(self, client):
        """Test healing with additional context."""
        payload = {
            "request_id": "req-002",
            "original_locator": "#login-btn",
            "original_locator_type": "css",
            "action": "click",
            "page_html": """
            <html>
            <body>
                <form>
                    <label>Username:</label>
                    <input name="username" type="text"/>
                    <button id="login-btn">Login</button>
                </form>
            </body>
            </html>
            """,
            "anchors": ["Username:"],
            "visible_text": "Login"
        }

        response = client.post("/heal", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == "req-002"
        assert data["healed_locator"] is not None

    def test_heal_invalid_locator_type(self, client):
        """Test healing with invalid original_locator_type."""
        response = client.post("/heal", json={
            "request_id": "req-003",
            "original_locator": "#test",
            "original_locator_type": "invalid",
            "action": "click",
            "page_html": "<div>test</div>"
        })
        assert response.status_code == 422  # Validation error

    def test_heal_pii_warning(self, client):
        """Test healing with PII detection when not masked."""
        response = client.post("/heal", json={
            "request_id": "req-004",
            "original_locator": "#test",
            "original_locator_type": "css",
            "action": "click",
            "page_html": "<div>Contact: user@example.com</div>",
            "pii_masked": False
        })
        assert response.status_code == 200
        data = response.json()
        assert data["warning"] == "PII detected"


class TestConfirmEndpoint:
    """Test the confirmation endpoint."""

    def test_confirm_basic(self, client):
        """Test basic confirmation."""
        response = client.post("/confirm", json={
            "request_id": "test-123",
            "accepted_index": 0
        })

        assert response.status_code == 200
        data = response.json()
        assert data == {"status": "confirmed", "request_id": "test-123"}

    def test_confirm_missing_fields(self, client):
        """Test confirmation with missing fields."""
        response = client.post("/confirm", json={
            "accepted_index": 0
            # Missing request_id
        })
        assert response.status_code == 422

    def test_confirm_with_metadata(self, client):
        """Test confirmation with metadata."""
        response = client.post("/confirm", json={
            "request_id": "test-456",
            "accepted_index": 1,
            "metadata": {
                "test_session": "regression_test_001",
                "browser": "chrome",
                "environment": "staging"
            }
        })

        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == "test-456"


class TestIntegration:
    """Integration tests for the full healing workflow."""

    def test_full_healing_workflow(self, client):
        """Test complete healing workflow from request to confirmation."""
        # Sample HTML with a button that might be hard to locate
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Test Page</title></head>
        <body>
            <div class="container">
                <h1>Welcome</h1>
                <form id="login-form">
                    <div class="form-group">
                        <label for="username">Username:</label>
                        <input type="text" id="username" name="username"/>
                    </div>
                    <div class="form-group">
                        <label for="password">Password:</label>
                        <input type="password" id="password" name="password"/>
                    </div>
                    <button type="submit" class="btn btn-primary" data-testid="login-button">
                        Sign In
                    </button>
                </form>
            </div>
        </body>
        </html>
        """

        # Step 1: Request healing
        heal_response = client.post("/heal", json={
            "request_id": "req-integration",
            "original_locator": ".login-btn",  # This doesn't exist
            "original_locator_type": "css",
            "action": "click",
            "page_html": html,
            "anchors": ["Username:", "Password:"],
            "visible_text": "Sign In"
        })

        assert heal_response.status_code == 200
        heal_data = heal_response.json()
        request_id = heal_data["request_id"]
        candidates = heal_data["candidates"]

        assert request_id == "req-integration"
        assert candidates == []  # placeholder

        # Step 2: Confirm the healing (assume we accepted the first candidate)
        confirm_response = client.post("/confirm", json={
            "request_id": request_id,
            "accepted_index": 0,
            "metadata": {
                "test_name": "integration_test",
                "locator_strategy": "healing"
            }
        })

        assert confirm_response.status_code == 200
        confirm_data = confirm_response.json()
        assert confirm_data["status"] == "confirmed"
        assert confirm_data["request_id"] == request_id
