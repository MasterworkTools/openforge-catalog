"""
Pytest tests for Session Management System.
"""

import requests

from .test_constants import TEST_DATA_PREFIX


class TestSessionManagement:
    """Test session management functionality."""

    def test_create_session_with_valid_api_key(self, api_client_no_auth, api_key):
        """Test creating a session with a valid API key."""
        response = api_client_no_auth.post(
            "/api/admin/sessions", json={"api_key": api_key}
        )

        assert response.status_code == 201
        data = response.json()
        assert "message" in data
        assert "expires_at" in data
        assert "csrf_token" in data

        # Check for session cookie
        cookies = response.cookies
        assert "session_token" in cookies
        session_token = cookies["session_token"]
        assert len(session_token) > 0

        # Check for CSRF token in headers
        assert "X-CSRF-Token" in response.headers
        csrf_token = response.headers["X-CSRF-Token"]
        assert len(csrf_token) > 0

    def test_create_session_with_invalid_api_key(self, api_client_no_auth):
        """Test creating a session with an invalid API key."""
        response = api_client_no_auth.post(
            "/api/admin/sessions", json={"api_key": "invalid_key"}
        )

        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "Invalid API key" in data["error"]

    def test_create_session_without_api_key(self, api_client_no_auth):
        """Test creating a session without providing an API key."""
        response = api_client_no_auth.post("/api/admin/sessions", json={})

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "API key required" in data["error"]

    def test_validate_session_with_valid_cookie(self, api_client_no_auth, api_key):
        """Test validating a session with a valid session cookie."""
        # First create a session
        create_response = api_client_no_auth.post(
            "/api/admin/sessions", json={"api_key": api_key}
        )

        # Extract session token from cookie
        session_token = create_response.cookies["session_token"]

        # Create a new client with the session cookie
        session_client = requests.Session()
        session_client.cookies.set("session_token", session_token)

        # Validate the session
        response = session_client.get(
            f"{api_client_no_auth.base_url}/api/admin/sessions/validate"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert "expires_at" in data
        assert "csrf_token" in data
        assert "X-CSRF-Token" in response.headers

    def test_validate_session_without_cookie(self, api_client_no_auth):
        """Test validating a session without a session cookie."""
        response = api_client_no_auth.get("/api/admin/sessions/validate")

        assert response.status_code == 401
        data = response.json()
        assert data["valid"] is False
        assert "error" in data
        assert "No session token" in data["error"]

    def test_validate_session_with_invalid_cookie(self, api_client_no_auth):
        """Test validating a session with an invalid session cookie."""
        # Create a client with an invalid session token
        session_client = requests.Session()
        session_client.cookies.set("session_token", "invalid_session_token")

        response = session_client.get(
            f"{api_client_no_auth.base_url}/api/admin/sessions/validate"
        )

        assert response.status_code == 401
        data = response.json()
        assert data["valid"] is False
        assert "error" in data
        assert "Invalid or expired session" in data["error"]

    def test_delete_session_with_valid_csrf(self, api_client_no_auth, api_key):
        """Test deleting a session with a valid CSRF token."""
        # First create a session
        create_response = api_client_no_auth.post(
            "/api/admin/sessions", json={"api_key": api_key}
        )

        # Extract session token and CSRF token
        session_token = create_response.cookies["session_token"]
        csrf_token = create_response.headers["X-CSRF-Token"]

        # Create a session client
        session_client = requests.Session()
        session_client.cookies.set("session_token", session_token)

        # Delete the session
        response = session_client.delete(
            f"{api_client_no_auth.base_url}/api/admin/sessions",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Session deleted successfully" in data["message"]

        # Check that session cookie was cleared
        # The cookie should be deleted, which means it won't be in response.cookies
        # Instead, we check that the response indicates successful deletion

    def test_delete_session_without_csrf(self, api_client_no_auth, api_key):
        """Test deleting a session without a CSRF token."""
        # First create a session
        create_response = api_client_no_auth.post(
            "/api/admin/sessions", json={"api_key": api_key}
        )

        # Extract session token
        session_token = create_response.cookies["session_token"]

        # Create a session client
        session_client = requests.Session()
        session_client.cookies.set("session_token", session_token)

        # Try to delete without CSRF token
        response = session_client.delete(
            f"{api_client_no_auth.base_url}/api/admin/sessions"
        )

        assert response.status_code == 403
        data = response.json()
        assert "error" in data
        assert "Invalid CSRF token" in data["error"]

    def test_delete_session_with_invalid_csrf(self, api_client_no_auth, api_key):
        """Test deleting a session with an invalid CSRF token."""
        # First create a session
        create_response = api_client_no_auth.post(
            "/api/admin/sessions", json={"api_key": api_key}
        )

        # Extract session token
        session_token = create_response.cookies["session_token"]

        # Create a session client
        session_client = requests.Session()
        session_client.cookies.set("session_token", session_token)

        # Try to delete with invalid CSRF token
        response = session_client.delete(
            f"{api_client_no_auth.base_url}/api/admin/sessions",
            headers={"X-CSRF-Token": "invalid_csrf_token"},
        )

        assert response.status_code == 403
        data = response.json()
        assert "error" in data
        assert "Invalid CSRF token" in data["error"]

    def test_delete_session_without_cookie(self, api_client_no_auth):
        """Test deleting a session without a session cookie."""
        response = api_client_no_auth.delete("/api/admin/sessions")

        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "Unauthorized" in data["error"]


class TestSessionAuthenticationIntegration:
    """Test session authentication integration with existing endpoints."""

    def test_authenticated_endpoint_with_session(
        self, api_client_no_auth, test_blueprint_id, api_key
    ):
        """Test that authenticated endpoints work with session cookies."""
        # First create a session
        create_response = api_client_no_auth.post(
            "/api/admin/sessions", json={"api_key": api_key}
        )

        # Extract session token
        session_token = create_response.cookies["session_token"]

        # Create a session client
        session_client = requests.Session()
        session_client.cookies.set("session_token", session_token)

        # Try to access an authenticated endpoint
        test_doc = {
            "document": f"{TEST_DATA_PREFIX} Test documentation for session auth",
            "document_type": "changelog",
        }

        response = session_client.post(
            f"{api_client_no_auth.base_url}/api/blueprints/{test_blueprint_id}/documentation",
            json=test_doc,
        )

        # Should not get 401 (though might get 400 for invalid data)
        assert response.status_code != 401

        # Clean up the created documentation if it was successful
        if response.status_code == 201:
            data = response.json()
            doc_id = data["documentation"]["id"]

            # Get CSRF token for deletion
            csrf_token = create_response.headers["X-CSRF-Token"]

            # Delete the test documentation
            session_client.delete(
                f"{api_client_no_auth.base_url}/api/blueprints/{test_blueprint_id}/documentation/{doc_id}",
                headers={"X-CSRF-Token": csrf_token},
            )

    def test_authenticated_endpoint_without_session(
        self, api_client_no_auth, test_blueprint_id
    ):
        """Test that authenticated endpoints require authentication."""
        test_doc = {
            "document": f"{TEST_DATA_PREFIX} Test documentation without auth",
            "document_type": "changelog",
        }

        response = api_client_no_auth.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", json=test_doc
        )

        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "Unauthorized" in data["error"]

    def test_api_key_still_works(self, api_client, test_blueprint_id):
        """Test that API key authentication still works alongside sessions."""
        test_doc = {
            "document": f"{TEST_DATA_PREFIX} Test documentation with API key",
            "document_type": "changelog",
        }

        response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", json=test_doc
        )

        # Should not get 401 (though might get 400 for invalid data)
        assert response.status_code != 401

        # Clean up the created documentation if it was successful
        if response.status_code == 201:
            data = response.json()
            doc_id = data["documentation"]["id"]

            # Delete the test documentation
            api_client.delete(
                f"/api/blueprints/{test_blueprint_id}/documentation/{doc_id}"
            )


class TestSessionSecurity:
    """Test session security features."""

    def test_session_cookie_security_attributes(self, api_client_no_auth, api_key):
        """Test that session cookies have proper security attributes."""
        response = api_client_no_auth.post(
            "/api/admin/sessions", json={"api_key": api_key}
        )

        # Verify the response indicates successful session creation
        assert response.status_code == 201
        data = response.json()
        assert "message" in data
        assert "Session created successfully" in data["message"]

        # Check that the session cookie exists
        assert "session_token" in response.cookies
        session_cookie = response.cookies["session_token"]
        assert session_cookie is not None
        assert len(str(session_cookie)) > 0

        # Parse Set-Cookie header to check security attributes
        set_cookie_header = response.headers.get("Set-Cookie", "")
        assert "session_token=" in set_cookie_header

        # Check for security attributes (case-insensitive)
        set_cookie_lower = set_cookie_header.lower()
        assert (
            "httponly" in set_cookie_lower
        ), "Session cookie should have HttpOnly flag"
        assert "secure" in set_cookie_lower, "Session cookie should have Secure flag"
        assert (
            "samesite=strict" in set_cookie_lower
        ), "Session cookie should have SameSite=Strict"

    def test_csrf_token_consistency(self, api_client_no_auth, api_key):
        """Test that CSRF tokens are consistent for the same session."""

        # Create first session
        create_response1 = api_client_no_auth.post(
            "/api/admin/sessions", json={"api_key": api_key}
        )
        session_token1 = create_response1.cookies["session_token"]
        csrf_token1 = create_response1.headers["X-CSRF-Token"]

        # Validate session and get CSRF token again
        session_client = requests.Session()
        session_client.cookies.set("session_token", session_token1)

        validate_response = session_client.get(
            f"{api_client_no_auth.base_url}/api/admin/sessions/validate"
        )
        csrf_token2 = validate_response.headers["X-CSRF-Token"]

        # CSRF tokens should be consistent for the same session
        assert csrf_token1 == csrf_token2


class TestSessionErrorHandling:
    """Test session error handling."""

    def test_malformed_session_token(self, api_client_no_auth):
        """Test handling of malformed session tokens."""
        session_client = requests.Session()
        session_client.cookies.set(
            "session_token", "malformed_token_with_invalid_chars!"
        )

        response = session_client.get(
            f"{api_client_no_auth.base_url}/api/admin/sessions/validate"
        )

        assert response.status_code == 401
        data = response.json()
        assert data["valid"] is False

    def test_empty_session_token(self, api_client_no_auth):
        """Test handling of empty session tokens."""
        session_client = requests.Session()
        session_client.cookies.set("session_token", "")

        response = session_client.get(
            f"{api_client_no_auth.base_url}/api/admin/sessions/validate"
        )

        assert response.status_code == 401
        data = response.json()
        assert data["valid"] is False
