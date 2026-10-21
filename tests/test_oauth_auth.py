from unittest.mock import MagicMock, patch

import pytest

from openforge.app import init_app
from openforge.app.index import app as create_app


@pytest.fixture
def app():
    """Create test app with test config."""
    app = create_app
    app.config["TESTING"] = True
    init_app(app)
    # Set OAuth config after init_app
    app.config["PATREON_CLIENT_ID"] = "test-patreon-client"
    app.config["PATREON_CLIENT_SECRET"] = "test-patreon-secret"
    app.config["GOOGLE_CLIENT_ID"] = "test-google-client"
    app.config["GOOGLE_CLIENT_SECRET"] = "test-google-secret"
    app.config["FRONTEND_URL"] = "http://localhost:3000"
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestOAuthEndpoints:
    """Test OAuth authentication endpoints."""

    @patch("openforge.app.routes.auth.OAuthService")
    def test_patreon_login_redirect(self, mock_oauth_class, client):
        """Test Patreon login redirects to Patreon OAuth."""
        # Mock the OAuth service
        mock_oauth = MagicMock()
        mock_oauth.get_patreon_auth_url.return_value = (
            "https://www.patreon.com/oauth2/authorize?"
            "response_type=code&client_id=test-patreon-client&"
            "redirect_uri=http://localhost/api/auth/callback/patreon&"
            "scope=identity+identity.memberships&state=test-state"
        )
        mock_oauth_class.return_value = mock_oauth

        response = client.get("/api/auth/login/patreon")
        assert response.status_code == 302
        assert "www.patreon.com/oauth2/authorize" in response.location
        assert "client_id=test-patreon-client" in response.location
        assert "scope=identity+identity.memberships" in response.location

    @patch("openforge.app.routes.auth.OAuthService")
    def test_google_login_redirect(self, mock_oauth_class, client):
        """Test Google login redirects to Google OAuth."""
        # Mock the OAuth service
        mock_oauth = MagicMock()
        mock_oauth.get_google_auth_url.return_value = (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            "response_type=code&client_id=test-google-client&"
            "redirect_uri=http://localhost/api/auth/callback/google&"
            "scope=openid%20email%20profile&state=test-state&"
            "access_type=offline&prompt=consent"
        )
        mock_oauth_class.return_value = mock_oauth

        response = client.get("/api/auth/login/google")
        assert response.status_code == 302
        assert "accounts.google.com/o/oauth2/v2/auth" in response.location
        assert "client_id=test-google-client" in response.location
        assert "scope=openid%20email%20profile" in response.location

    def test_invalid_provider_login(self, client):
        """Test invalid provider returns error."""
        response = client.get("/api/auth/login/facebook")
        assert response.status_code == 400

    @patch("openforge.app.services.oauth_service.OAuthService.exchange_patreon_code")
    @patch("openforge.app.services.oauth_service.OAuthService.get_patreon_user_info")
    @patch("openforge.app.services.oauth_service.OAuthService.find_or_create_user")
    @patch("openforge.app.services.session_service.SessionService.create_user_session")
    def test_patreon_callback_success(
        self,
        mock_create_session,
        mock_find_user,
        mock_get_user_info,
        mock_exchange_code,
        client,
    ):
        """Test successful Patreon OAuth callback."""
        # Mock the OAuth flow
        mock_exchange_code.return_value = {"access_token": "test-token"}
        mock_get_user_info.return_value = (
            {
                "provider_id": "123",
                "email": "test@example.com",
                "full_name": "Test User",
            },
            "Bronze",  # tier
        )
        mock_find_user.return_value = {
            "id": "user-123",
            "email": "test@example.com",
            "role": "user",
            "patreon_tier": "Bronze",
        }
        mock_create_session.return_value = {
            "session_token": "test-session-token",
            "csrf_token": "test-csrf-token",
            "expires_at": "2024-01-01T00:00:00Z",
        }

        response = client.get("/api/auth/callback/patreon?code=test-code")
        assert response.status_code == 302
        assert response.location.startswith("http://localhost:3000/auth/success")
        assert "token=test-session-token" in response.location
        assert "csrf=test-csrf-token" in response.location

    def test_patreon_callback_error(self, client):
        """Test Patreon OAuth callback with error."""
        response = client.get("/api/auth/callback/patreon?error=access_denied")
        assert response.status_code == 302
        assert response.location.startswith("http://localhost:3000/auth/error")
        assert "error=access_denied" in response.location

    def test_get_current_user_authenticated(self, client):
        """Test getting current user when authenticated."""
        with patch(
            "openforge.app.services.session_service.SessionService.validate_session"
        ) as mock_validate:
            from datetime import datetime, timezone

            mock_validate.return_value = {
                "id": "session-123",
                "user": {
                    "id": "user-123",
                    "email": "test@example.com",
                    "role": "user",
                    "patreon_tier": "Bronze",
                },
                "expires_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            }

            response = client.get(
                "/api/auth/me", headers={"Authorization": "Bearer test-token"}
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data["user"]["email"] == "test@example.com"
            assert data["user"]["patreon_tier"] == "Bronze"

    def test_get_current_user_unauthenticated(self, client):
        """Test getting current user when not authenticated."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_logout(self, client):
        """Test logout endpoint."""
        with patch(
            "openforge.app.services.session_service.SessionService.delete_session"
        ) as mock_delete:
            mock_delete.return_value = True

            response = client.post(
                "/api/auth/logout", headers={"Authorization": "Bearer test-token"}
            )
            assert response.status_code == 200
            assert response.get_json()["message"] == "Logged out successfully"
