import pytest

from openforge.app.index import app as flask_app
from openforge.app.services.session_service import SessionService


@pytest.fixture
def client(test_db):
    flask_app.config["TESTING"] = True
    flask_app.db = test_db
    with flask_app.test_client() as client:
        yield client


@pytest.fixture
def session_service(test_db):
    return SessionService(test_db, "test_token", "test_secret_key_for_csrf_tokens")


class TestSessionService:
    """Test the SessionService class."""

    def test_create_session_valid_key(self, session_service):
        """Test creating a session with a valid API key."""
        session_data = session_service.create_session("test_token")

        assert "session_token" in session_data
        assert "expires_at" in session_data
        assert len(session_data["session_token"]) > 0

        # Verify session was stored in database
        session = session_service.validate_session(session_data["session_token"])
        assert session is not None
        assert session["id"] is not None

    def test_create_session_invalid_key(self, session_service):
        """Test creating a session with an invalid API key."""
        with pytest.raises(ValueError, match="Invalid API key"):
            session_service.create_session("invalid_key")

    def test_validate_session_valid(self, session_service):
        """Test validating a valid session."""
        # Create a session first
        session_data = session_service.create_session("test_token")

        # Validate the session
        session = session_service.validate_session(session_data["session_token"])
        assert session is not None
        assert session["id"] is not None
        assert session["expires_at"] is not None

    def test_validate_session_invalid(self, session_service):
        """Test validating an invalid session."""
        session = session_service.validate_session("invalid_token")
        assert session is None

    def test_delete_session(self, session_service):
        """Test deleting a session."""
        # Create a session first
        session_data = session_service.create_session("test_token")

        # Verify session exists
        session = session_service.validate_session(session_data["session_token"])
        assert session is not None

        # Delete the session
        success = session_service.delete_session(session_data["session_token"])
        assert success is True

        # Verify session is gone
        session = session_service.validate_session(session_data["session_token"])
        assert session is None

    def test_cleanup_expired_sessions(self, session_service):
        """Test cleaning up expired sessions."""
        # Create a session
        session_data = session_service.create_session("test_token")

        # Manually expire the session in the database
        with session_service.db.connection() as conn:
            with conn.cursor() as curs:
                session_hash = session_service._hash_token(
                    session_data["session_token"]
                )
                curs.execute(
                    "UPDATE sessions SET expires_at = now() - interval '1 hour' "
                    "WHERE session_token_hash = %s",
                    (session_hash,),
                )

        # Clean up expired sessions
        cleaned_count = session_service.cleanup_expired_sessions()
        assert cleaned_count == 1

        # Verify session is gone
        session = session_service.validate_session(session_data["session_token"])
        assert session is None


class TestSessionRoutes:
    """Test the session management routes."""

    def test_create_session_route(self, client):
        """Test the create session route."""
        response = client.post("/api/admin/sessions", json={"api_key": "test_token"})

        assert response.status_code == 201
        data = response.get_json()
        assert "message" in data
        assert "expires_at" in data
        assert "csrf_token" in data

        # Check for session cookie
        assert "session_token" in response.headers.getlist("Set-Cookie")[0]
        assert "X-CSRF-Token" in response.headers

    def test_create_session_invalid_key(self, client):
        """Test creating session with invalid API key."""
        response = client.post("/api/admin/sessions", json={"api_key": "invalid_key"})

        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_create_session_missing_key(self, client):
        """Test creating session without API key."""
        response = client.post("/api/admin/sessions", json={})

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_validate_session_route(self, client):
        """Test the validate session route."""
        # First create a session.
        # The cookie is automatically added to the client's cookie jar.
        client.post("/api/admin/sessions", json={"api_key": "test_token"})

        # Validate the session. The client will automatically send the session cookie.
        response = client.get("/api/admin/sessions/validate")

        assert response.status_code == 200
        data = response.get_json()
        assert data["valid"] is True
        assert "expires_at" in data
        assert "csrf_token" in data
        assert "X-CSRF-Token" in response.headers

    def test_validate_session_no_cookie(self, client):
        """Test validating session without cookie."""
        response = client.get("/api/admin/sessions/validate")

        assert response.status_code == 401
        data = response.get_json()
        assert data["valid"] is False
        assert "error" in data

    def test_delete_session_route(self, client):
        """Test the delete session route."""
        # First create a session.
        # The cookie is automatically added to the client's cookie jar.
        create_response = client.post(
            "/api/admin/sessions", json={"api_key": "test_token"}
        )

        # Get CSRF token
        csrf_token = create_response.headers.get("X-CSRF-Token")

        # Delete the session. The client will automatically send the session cookie.
        response = client.delete(
            "/api/admin/sessions", headers={"X-CSRF-Token": csrf_token}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "message" in data

        # Check that session cookie was cleared
        assert "session_token=;" in response.headers.getlist("Set-Cookie")[0]

    def test_delete_session_no_csrf(self, client):
        """Test deleting session without CSRF token."""
        # First create a session.
        # The cookie is automatically added to the client's cookie jar.
        client.post("/api/admin/sessions", json={"api_key": "test_token"})

        # Try to delete without CSRF token.
        # The client will automatically send the session cookie.
        response = client.delete("/api/admin/sessions")

        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data


class TestAuthenticationIntegration:
    """Test authentication integration with existing routes."""

    def test_authenticated_route_with_session(self, client):
        """Test that authenticated routes work with session cookies."""
        # Create a session.
        # The cookie is automatically added to the client's cookie jar.
        client.post("/api/admin/sessions", json={"api_key": "test_token"})

        # Try to access an authenticated route.
        # The client will automatically send the session cookie.
        response = client.post("/api/blueprints", json={"blueprint_name": "test"})

        # Should not get 401 (though might get 400 for invalid data)
        assert response.status_code != 401

    def test_authenticated_route_with_api_key(self, client):
        """Test that authenticated routes work with API keys."""
        # Try to access an authenticated route with API key
        response = client.post(
            "/api/blueprints",
            json={"blueprint_name": "test"},
            headers={"Authorization": "Bearer test_token"},
        )

        # Should not get 401 (though might get 400 for invalid data)
        assert response.status_code != 401

    def test_authenticated_route_no_auth(self, client):
        """Test that authenticated routes require authentication."""
        # Try to access an authenticated route without auth
        response = client.post("/api/blueprints", json={"blueprint_name": "test"})

        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data
        assert "message" in data
