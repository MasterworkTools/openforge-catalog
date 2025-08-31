import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from openforge.app.routes.users import users_bp


@pytest.fixture
def app(admin_session, user_session):
    """Create a Flask app for testing."""
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(users_bp, url_prefix="/api")
    app.config["DB"] = Mock()
    app.config["SECRET_KEY"] = "test-secret"
    app.config["API_TOKEN"] = "test-api-token"

    # Add mock session_service that returns appropriate session based on token
    app.session_service = Mock()

    def validate_session_side_effect(token):
        if token == "test-token":
            return admin_session
        elif token == "user-token":
            return user_session
        return None

    app.session_service.validate_session.side_effect = validate_session_side_effect
    app.session_service.get_csrf_token_for_session.return_value = "test-csrf-token"

    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def admin_session():
    """Mock admin session data."""
    return {
        "id": "session-123",
        "user": {
            "id": "admin-user-id",
            "email": "admin@example.com",
            "role": "admin",
            "patreon_tier": None,
        },
        "expires_at": datetime.now(timezone.utc),
        "csrf_token": "test-csrf-token",
    }


@pytest.fixture
def user_session():
    """Mock regular user session data."""
    return {
        "id": "session-456",
        "user": {
            "id": "regular-user-id",
            "email": "user@example.com",
            "role": "user",
            "patreon_tier": "Silver",
        },
        "expires_at": datetime.now(timezone.utc),
        "csrf_token": "test-csrf-token",
    }


@pytest.fixture
def sample_users():
    """Sample user list for tests."""
    return [
        {
            "id": "user-1",
            "email": "user1@example.com",
            "role": "user",
            "patreon_tier": "Bronze",
            "blocked": False,
            "identities": [{"provider": "patreon", "provider_id": "123"}],
        },
        {
            "id": "user-2",
            "email": "user2@example.com",
            "role": "admin",
            "patreon_tier": None,
            "blocked": False,
            "identities": [{"provider": "google", "provider_id": "456"}],
        },
    ]


@patch("openforge.app.routes.users.UserService")
def test_list_users_admin_success(
    mock_user_service, client, admin_session, sample_users
):
    """Test admin can list users."""
    # Setup mocks
    mock_user_service.return_value.get_users.return_value = {
        "users": sample_users,
        "total": 2,
        "limit": 100,
        "offset": 0,
    }

    # Make request
    response = client.get(
        "/api/users",
        headers={
            "Authorization": "Bearer test-token",
            "X-CSRF-Token": "test-csrf-token",
        },
    )

    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["total"] == 2
    assert len(data["users"]) == 2
    assert data["users"][0]["email"] == "user1@example.com"


def test_list_users_non_admin_forbidden(client, user_session):
    """Test non-admin cannot list users."""
    # Make request
    response = client.get(
        "/api/users",
        headers={
            "Authorization": "Bearer user-token",
            "X-CSRF-Token": "test-csrf-token",
        },
    )

    # Should be forbidden
    assert response.status_code == 403


def test_list_users_no_auth(client):
    """Test listing users without auth fails."""

    # Make request
    response = client.get("/api/users")

    # Should be unauthorized
    assert response.status_code == 401


@patch("openforge.app.routes.users.UserService")
def test_list_users_with_filters(mock_user_service, client, admin_session):
    """Test listing users with various filters."""
    mock_user_service.return_value.get_users.return_value = {
        "users": [],
        "total": 0,
        "limit": 50,
        "offset": 10,
    }

    # Make request with filters
    response = client.get(
        "/api/users?limit=50&offset=10&search=admin&role=admin&blocked=true&patreon_tier=Gold",
        headers={
            "Authorization": "Bearer test-token",
            "X-CSRF-Token": "test-csrf-token",
        },
    )

    # Verify response
    assert response.status_code == 200

    # Verify service was called with correct parameters
    mock_user_service.return_value.get_users.assert_called_once_with(
        limit=50,
        offset=10,
        search="admin",
        role="admin",
        blocked=True,
        patreon_tier="Gold",
    )


@patch("openforge.app.routes.users.UserService")
def test_get_user_admin_any_user(
    mock_user_service, client, admin_session, sample_users
):
    """Test admin can get any user."""
    mock_user_service.return_value.get_user_by_id.return_value = sample_users[0]

    # Make request
    response = client.get(
        "/api/users/user-1",
        headers={
            "Authorization": "Bearer test-token",
            "X-CSRF-Token": "test-csrf-token",
        },
    )

    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["id"] == "user-1"
    assert data["email"] == "user1@example.com"


@patch("openforge.app.routes.users.UserService")
def test_get_user_own_profile(mock_user_service, client, user_session, sample_users):
    """Test user can get their own profile."""
    mock_user_service.return_value.get_user_by_id.return_value = {
        "id": "regular-user-id",
        "email": "user@example.com",
        "role": "user",
        "patreon_tier": "Silver",
    }

    # Make request for own profile
    response = client.get(
        "/api/users/regular-user-id",
        headers={
            "Authorization": "Bearer user-token",
            "X-CSRF-Token": "test-csrf-token",
        },
    )

    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["id"] == "regular-user-id"


def test_get_user_other_profile_forbidden(client, user_session):
    """Test user cannot get other user's profile."""

    # Make request for different user
    response = client.get(
        "/api/users/other-user-id",
        headers={
            "Authorization": "Bearer user-token",
            "X-CSRF-Token": "test-csrf-token",
        },
    )

    # Should be forbidden
    assert response.status_code == 403


@patch("openforge.app.routes.users.UserService")
def test_update_user_admin_success(mock_user_service, client, admin_session):
    """Test admin can update user."""
    updated_user = {
        "id": "user-1",
        "email": "user1@example.com",
        "role": "admin",
        "patreon_tier": "Platinum",
    }
    mock_user_service.return_value.update_user.return_value = updated_user

    # Make request
    response = client.patch(
        "/api/users/user-1",
        headers={
            "Authorization": "Bearer test-token",
            "X-CSRF-Token": "test-csrf-token",
            "Content-Type": "application/json",
        },
        data=json.dumps({"role": "admin", "patreon_tier": "Platinum"}),
    )

    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["role"] == "admin"
    assert data["patreon_tier"] == "Platinum"

    # Verify service was called correctly
    mock_user_service.return_value.update_user.assert_called_once_with(
        user_id="user-1",
        role="admin",
        patreon_tier="Platinum",
        blocked=None,
        blocked_reason=None,
    )


def test_update_user_invalid_role(client, admin_session):
    """Test updating user with invalid role fails."""

    # Make request with invalid role
    response = client.patch(
        "/api/users/user-1",
        headers={
            "Authorization": "Bearer test-token",
            "X-CSRF-Token": "test-csrf-token",
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "role": "superuser"  # Invalid role
            }
        ),
    )

    # Should be bad request
    assert response.status_code == 400
    # Error might be HTML or JSON depending on Flask configuration
    try:
        data = json.loads(response.data)
        assert "Invalid role" in data.get("message", "") or "Invalid role" in data.get(
            "description", ""
        )
    except json.JSONDecodeError:
        # If HTML response, check the content
        assert b"Invalid role" in response.data


def test_update_user_invalid_tier(client, admin_session):
    """Test updating user with invalid tier fails."""

    # Make request with invalid tier
    response = client.patch(
        "/api/users/user-1",
        headers={
            "Authorization": "Bearer test-token",
            "X-CSRF-Token": "test-csrf-token",
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "patreon_tier": "Diamond"  # Invalid tier
            }
        ),
    )

    # Should be bad request
    assert response.status_code == 400
    # Error might be HTML or JSON depending on Flask configuration
    try:
        data = json.loads(response.data)
        assert "Invalid patreon_tier" in data.get(
            "message", ""
        ) or "Invalid patreon_tier" in data.get("description", "")
    except json.JSONDecodeError:
        # If HTML response, check the content
        assert b"Invalid patreon_tier" in response.data


@patch("openforge.app.routes.users.UserService")
def test_delete_user_admin_success(mock_user_service, client, admin_session):
    """Test admin can delete user."""
    mock_user_service.return_value.delete_user.return_value = True

    # Make request
    response = client.delete(
        "/api/users/user-1",
        headers={
            "Authorization": "Bearer test-token",
            "X-CSRF-Token": "test-csrf-token",
        },
    )

    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["message"] == "User deleted successfully"


def test_delete_user_self_deletion_prevented(client, admin_session):
    """Test admin cannot delete themselves."""

    # Try to delete self
    response = client.delete(
        f"/api/users/{admin_session['user']['id']}",
        headers={
            "Authorization": "Bearer test-token",
            "X-CSRF-Token": "test-csrf-token",
        },
    )

    # Should be bad request
    assert response.status_code == 400
    # Error might be HTML or JSON depending on Flask configuration
    try:
        data = json.loads(response.data)
        assert "Cannot delete your own account" in data.get(
            "message", ""
        ) or "Cannot delete your own account" in data.get("description", "")
    except json.JSONDecodeError:
        # If HTML response, check the content
        assert b"Cannot delete your own account" in response.data


@patch("openforge.app.routes.users.UserService")
def test_get_user_sessions_own(mock_user_service, client, user_session):
    """Test user can get their own sessions."""
    sessions = [
        {
            "id": "session-1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": datetime.now(timezone.utc).isoformat(),
            "last_used_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    mock_user_service.return_value.get_user_sessions.return_value = sessions

    # Make request
    response = client.get(
        f"/api/users/{user_session['user']['id']}/sessions",
        headers={
            "Authorization": "Bearer user-token",
            "X-CSRF-Token": "test-csrf-token",
        },
    )

    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data["sessions"]) == 1


@patch("openforge.app.routes.users.UserService")
def test_revoke_user_sessions(mock_user_service, client, admin_session):
    """Test revoking user sessions."""
    mock_user_service.return_value.revoke_user_sessions.return_value = 3

    # Make request
    response = client.delete(
        "/api/users/user-1/sessions",
        headers={
            "Authorization": "Bearer test-token",
            "X-CSRF-Token": "test-csrf-token",
        },
    )

    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["count"] == 3
    assert "Revoked 3 session(s)" in data["message"]


@patch("openforge.app.routes.users.UserService")
def test_block_user_admin_success(mock_user_service, client, admin_session):
    """Test admin can block user."""
    blocked_user = {
        "id": "user-1",
        "email": "user1@example.com",
        "blocked": True,
        "blocked_reason": "Terms violation",
    }
    mock_user_service.return_value.update_user.return_value = blocked_user
    mock_user_service.return_value.revoke_user_sessions.return_value = 2

    # Make request
    response = client.post(
        "/api/users/user-1/block",
        headers={
            "Authorization": "Bearer test-token",
            "X-CSRF-Token": "test-csrf-token",
            "Content-Type": "application/json",
        },
        data=json.dumps({"reason": "Terms violation"}),
    )

    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["user"]["blocked"] is True
    assert data["sessions_revoked"] == 2

    # Verify service calls
    mock_user_service.return_value.update_user.assert_called_once_with(
        user_id="user-1", blocked=True, blocked_reason="Terms violation"
    )
    mock_user_service.return_value.revoke_user_sessions.assert_called_once_with(
        "user-1"
    )


@patch("openforge.app.routes.users.UserService")
def test_unblock_user_admin_success(mock_user_service, client, admin_session):
    """Test admin can unblock user."""
    unblocked_user = {
        "id": "user-1",
        "email": "user1@example.com",
        "blocked": False,
        "blocked_reason": None,
    }
    mock_user_service.return_value.update_user.return_value = unblocked_user

    # Make request
    response = client.post(
        "/api/users/user-1/unblock",
        headers={
            "Authorization": "Bearer test-token",
            "X-CSRF-Token": "test-csrf-token",
        },
    )

    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["blocked"] is False

    # Verify service call
    mock_user_service.return_value.update_user.assert_called_once_with(
        user_id="user-1", blocked=False
    )
