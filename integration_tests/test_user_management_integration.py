"""
Integration tests for user management functionality.
"""

import os

import pytest
from psycopg.rows import dict_row

from openforge.app.services.oauth_service import OAuthService
from openforge.app.services.session_service import SessionService
from openforge.app.services.user_service import UserService


@pytest.fixture
def admin_user(db):
    """Create an admin user for testing."""
    oauth_service = OAuthService(db)

    # Check if admin user already exists
    with db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            curs.execute(
                "SELECT * FROM users WHERE email = %s", ("admin-integration@test.com",)
            )
            existing_user = curs.fetchone()
            if existing_user:
                # Update role to admin in case it changed
                user_service = UserService(db)
                user_service.update_user(user_id=str(existing_user["id"]), role="admin")
                return user_service.get_user_by_id(str(existing_user["id"]))

    # Create admin user
    user = oauth_service.find_or_create_user(
        provider="google",
        provider_id="admin-google-integration-id",
        email="admin-integration@test.com",
        patreon_tier=None,
    )

    # Manually update role to admin
    user_service = UserService(db)
    user_service.update_user(user_id=str(user["id"]), role="admin")

    return user_service.get_user_by_id(str(user["id"]))


@pytest.fixture
def regular_user(db):
    """Create a regular user for testing."""
    oauth_service = OAuthService(db)

    # Check if user already exists
    with db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            curs.execute(
                "SELECT * FROM users WHERE email = %s", ("user-integration@test.com",)
            )
            existing_user = curs.fetchone()
            if existing_user:
                user_service = UserService(db)
                return user_service.get_user_by_id(str(existing_user["id"]))

    # Create regular user
    user = oauth_service.find_or_create_user(
        provider="patreon",
        provider_id="user-patreon-integration-id",
        email="user-integration@test.com",
        patreon_tier="Silver",
    )

    user_service = UserService(db)
    return user_service.get_user_by_id(str(user["id"]))


@pytest.fixture
def admin_session(db, admin_user):
    """Create admin session for testing."""
    # Get secret key from environment or use a test default
    secret_key = os.environ.get("SECRET_KEY", "test-secret-key")
    session_service = SessionService(db, secret_key=secret_key)
    session_data = session_service.create_user_session(str(admin_user["id"]))

    yield session_data

    # Clean up session
    try:
        session_service.delete_session(session_data["session_token"])
    except Exception:
        pass


@pytest.fixture
def user_session(db, regular_user):
    """Create user session for testing."""
    # Get secret key from environment or use a test default
    secret_key = os.environ.get("SECRET_KEY", "test-secret-key")
    session_service = SessionService(db, secret_key=secret_key)
    session_data = session_service.create_user_session(str(regular_user["id"]))

    yield session_data

    # Clean up session
    try:
        session_service.delete_session(session_data["session_token"])
    except Exception:
        pass


def test_list_users_as_admin(
    api_client_no_auth, admin_session, admin_user, regular_user
):
    """Test admin can list all users."""
    response = api_client_no_auth.get(
        "/api/users",
        headers={
            "Authorization": f"Bearer {admin_session['session_token']}",
            "X-CSRF-Token": admin_session["csrf_token"],
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Should have at least 2 users (admin and regular)
    assert data["total"] >= 2
    assert len(data["users"]) >= 2

    # Verify user data structure
    emails = [u["email"] for u in data["users"]]
    assert "admin-integration@test.com" in emails
    assert "user-integration@test.com" in emails

    # Check identities are included
    for user in data["users"]:
        if user["email"] == "admin-integration@test.com":
            assert user["role"] == "admin"
            assert any(
                i["provider"] == "google" for i in (user.get("identities") or [])
            )
        elif user["email"] == "user-integration@test.com":
            assert user["role"] == "user"
            assert user["patreon_tier"] == "Silver"
            assert any(
                i["provider"] == "patreon" for i in (user.get("identities") or [])
            )


def test_list_users_with_search(api_client_no_auth, admin_session):
    """Test searching users by email."""
    response = api_client_no_auth.get(
        "/api/users?search=admin",
        headers={
            "Authorization": f"Bearer {admin_session['session_token']}",
            "X-CSRF-Token": admin_session["csrf_token"],
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Should only find admin user
    assert data["total"] >= 1
    assert all("admin" in u["email"].lower() for u in data["users"])


def test_list_users_by_role(api_client_no_auth, admin_session):
    """Test filtering users by role."""
    response = api_client_no_auth.get(
        "/api/users?role=admin",
        headers={
            "Authorization": f"Bearer {admin_session['session_token']}",
            "X-CSRF-Token": admin_session["csrf_token"],
        },
    )

    assert response.status_code == 200
    data = response.json()

    # All returned users should be admins
    assert all(u["role"] == "admin" for u in data["users"])


def test_list_users_as_regular_user(api_client_no_auth, user_session):
    """Test regular user cannot list users."""
    response = api_client_no_auth.get(
        "/api/users",
        headers={
            "Authorization": f"Bearer {user_session['session_token']}",
            "X-CSRF-Token": user_session["csrf_token"],
        },
    )

    assert response.status_code == 403


def test_get_own_user_profile(api_client_no_auth, user_session, regular_user):
    """Test user can get their own profile."""
    response = api_client_no_auth.get(
        f"/api/users/{regular_user['id']}",
        headers={
            "Authorization": f"Bearer {user_session['session_token']}",
            "X-CSRF-Token": user_session["csrf_token"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(regular_user["id"])
    assert data["email"] == "user-integration@test.com"
    assert data["role"] == "user"
    assert data["patreon_tier"] == "Silver"


def test_get_other_user_profile_as_admin(
    api_client_no_auth, admin_session, regular_user
):
    """Test admin can get any user's profile."""
    response = api_client_no_auth.get(
        f"/api/users/{regular_user['id']}",
        headers={
            "Authorization": f"Bearer {admin_session['session_token']}",
            "X-CSRF-Token": admin_session["csrf_token"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(regular_user["id"])


def test_get_other_user_profile_as_regular_user(
    api_client_no_auth, user_session, admin_user
):
    """Test regular user cannot get other user's profile."""
    response = api_client_no_auth.get(
        f"/api/users/{admin_user['id']}",
        headers={
            "Authorization": f"Bearer {user_session['session_token']}",
            "X-CSRF-Token": user_session["csrf_token"],
        },
    )

    assert response.status_code == 403


def test_update_user_role(api_client_no_auth, db, admin_session):
    """Test admin can update user role."""
    # Create a test user to update
    oauth_service = OAuthService(db)
    user = oauth_service.find_or_create_user(
        provider="google",
        provider_id="update-role-test-id",
        email="update-role@test.com",
        patreon_tier=None,
    )
    user_id = str(user["id"])

    try:
        response = api_client_no_auth.patch(
            f"/api/users/{user_id}",
            headers={
                "Authorization": f"Bearer {admin_session['session_token']}",
                "X-CSRF-Token": admin_session["csrf_token"],
            },
            data={"role": "admin"},
        )

        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response: {response.json()}")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"

        # Verify change persisted
        response = api_client_no_auth.get(
            f"/api/users/{user_id}",
            headers={
                "Authorization": f"Bearer {admin_session['session_token']}",
                "X-CSRF-Token": admin_session["csrf_token"],
            },
        )
        data = response.json()
        assert data["role"] == "admin"
    finally:
        # Clean up
        user_service = UserService(db)
        try:
            user_service.delete_user(user_id)
        except Exception:
            pass


def test_update_user_patreon_tier(api_client_no_auth, admin_session, regular_user):
    """Test admin can update user's Patreon tier."""
    response = api_client_no_auth.patch(
        f"/api/users/{regular_user['id']}",
        headers={
            "Authorization": f"Bearer {admin_session['session_token']}",
            "X-CSRF-Token": admin_session["csrf_token"],
        },
        data={"patreon_tier": "Platinum"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["patreon_tier"] == "Platinum"


def test_block_user_flow(api_client_no_auth, db, admin_session):
    """Test complete user blocking flow."""
    # Create a test user to block
    oauth_service = OAuthService(db)
    user = oauth_service.find_or_create_user(
        provider="google",
        provider_id="block-test-id",
        email="block-test@test.com",
        patreon_tier=None,
    )
    user_id = str(user["id"])

    try:
        # First create some sessions for the user
        secret_key = os.environ.get("SECRET_KEY", "test-secret-key")
        session_service = SessionService(db, secret_key=secret_key)
        session1 = session_service.create_user_session(user_id)
        session_service.create_user_session(user_id)  # Create second session

        # Verify user can authenticate with session
        response = api_client_no_auth.get(
            f"/api/users/{user_id}",
            headers={
                "Authorization": f"Bearer {session1['session_token']}",
                "X-CSRF-Token": session1["csrf_token"],
            },
        )
        assert response.status_code == 200

        # Block the user
        response = api_client_no_auth.post(
            f"/api/users/{user_id}/block",
            headers={
                "Authorization": f"Bearer {admin_session['session_token']}",
                "X-CSRF-Token": admin_session["csrf_token"],
            },
            data={"reason": "Test blocking"},
        )

        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response: {response.json()}")
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["blocked"] is True
        assert data["user"]["blocked_reason"] == "Test blocking"
        assert data["sessions_revoked"] >= 2

        # Verify blocked user cannot authenticate
        response = api_client_no_auth.get(
            f"/api/users/{user_id}",
            headers={
                "Authorization": f"Bearer {session1['session_token']}",
                "X-CSRF-Token": session1["csrf_token"],
            },
        )
        assert response.status_code == 401  # Session should be invalid

        # Verify user shows as blocked
        response = api_client_no_auth.get(
            f"/api/users/{user_id}",
            headers={
                "Authorization": f"Bearer {admin_session['session_token']}",
                "X-CSRF-Token": admin_session["csrf_token"],
            },
        )
        data = response.json()
        assert data["blocked"] is True
        assert data["blocked_reason"] == "Test blocking"
        assert data["blocked_at"] is not None
    finally:
        # Clean up
        user_service = UserService(db)
        try:
            user_service.delete_user(user_id)
        except Exception:
            pass


def test_unblock_user(api_client_no_auth, db, admin_session):
    """Test unblocking a user."""
    # Create a test user to block/unblock
    oauth_service = OAuthService(db)
    user = oauth_service.find_or_create_user(
        provider="google",
        provider_id="unblock-test-id",
        email="unblock-test@test.com",
        patreon_tier=None,
    )
    user_id = str(user["id"])

    try:
        # First block the user
        api_client_no_auth.post(
            f"/api/users/{user_id}/block",
            headers={
                "Authorization": f"Bearer {admin_session['session_token']}",
                "X-CSRF-Token": admin_session["csrf_token"],
            },
            data={"reason": "Test"},
        )

        # Unblock the user
        response = api_client_no_auth.post(
            f"/api/users/{user_id}/unblock",
            headers={
                "Authorization": f"Bearer {admin_session['session_token']}",
                "X-CSRF-Token": admin_session["csrf_token"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["blocked"] is False
        assert data["blocked_reason"] is None
        assert data["blocked_at"] is None

        # User should be able to create new sessions and authenticate
        secret_key = os.environ.get("SECRET_KEY", "test-secret-key")
        session_service = SessionService(db, secret_key=secret_key)
        new_session = session_service.create_user_session(user_id)

        response = api_client_no_auth.get(
            f"/api/users/{user_id}",
            headers={
                "Authorization": f"Bearer {new_session['session_token']}",
                "X-CSRF-Token": new_session["csrf_token"],
            },
        )
        assert response.status_code == 200
    finally:
        # Clean up
        user_service = UserService(db)
        try:
            user_service.delete_user(user_id)
        except Exception:
            pass


def test_delete_user(api_client_no_auth, db, admin_session):
    """Test deleting a user."""
    # Create a test user to delete
    oauth_service = OAuthService(db)
    user = oauth_service.find_or_create_user(
        provider="google",
        provider_id="delete-test-id",
        email="delete@test.com",
        patreon_tier=None,
    )
    user_id = str(user["id"])

    # Create some sessions for the user
    secret_key = os.environ.get("SECRET_KEY", "test-secret-key")
    session_service = SessionService(db, secret_key=secret_key)
    session_service.create_user_session(user_id)

    # Delete the user
    response = api_client_no_auth.delete(
        f"/api/users/{user_id}",
        headers={
            "Authorization": f"Bearer {admin_session['session_token']}",
            "X-CSRF-Token": admin_session["csrf_token"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "User deleted successfully"

    # Verify user is gone
    response = api_client_no_auth.get(
        f"/api/users/{user_id}",
        headers={
            "Authorization": f"Bearer {admin_session['session_token']}",
            "X-CSRF-Token": admin_session["csrf_token"],
        },
    )
    assert response.status_code == 404

    # Verify cascading deletes worked (identities and sessions)
    user_service = UserService(db)
    sessions = user_service.get_user_sessions(user_id)
    assert len(sessions) == 0


def test_prevent_self_deletion(api_client_no_auth, admin_session, admin_user):
    """Test admin cannot delete themselves."""
    response = api_client_no_auth.delete(
        f"/api/users/{admin_user['id']}",
        headers={
            "Authorization": f"Bearer {admin_session['session_token']}",
            "X-CSRF-Token": admin_session["csrf_token"],
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert "Cannot delete your own account" in data["message"]


def test_get_user_sessions(api_client_no_auth, db, admin_session, regular_user):
    """Test getting user's active sessions."""
    # Create multiple sessions
    secret_key = os.environ.get("SECRET_KEY", "test-secret-key")
    session_service = SessionService(db, secret_key=secret_key)
    sessions = []
    for i in range(3):
        session_data = session_service.create_user_session(str(regular_user["id"]))
        sessions.append(session_data)

    try:
        # Get user sessions
        response = api_client_no_auth.get(
            f"/api/users/{regular_user['id']}/sessions",
            headers={
                "Authorization": f"Bearer {admin_session['session_token']}",
                "X-CSRF-Token": admin_session["csrf_token"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) >= 3

        # Verify session data structure
        for session in data["sessions"]:
            assert "id" in session
            assert "created_at" in session
            assert "expires_at" in session
            assert "last_used_at" in session
    finally:
        # Clean up sessions
        for session in sessions:
            try:
                session_service.delete_session(session["session_token"])
            except Exception:
                pass


def test_revoke_user_sessions(api_client_no_auth, db, admin_session):
    """Test revoking all user sessions."""
    # Create test user
    oauth_service = OAuthService(db)
    user = oauth_service.find_or_create_user(
        provider="google",
        provider_id="revoke-test-id",
        email="revoke-test@test.com",
        patreon_tier=None,
    )
    user_id = str(user["id"])

    try:
        # Create sessions
        secret_key = os.environ.get("SECRET_KEY", "test-secret-key")
        session_service = SessionService(db, secret_key=secret_key)
        session1 = session_service.create_user_session(user_id)
        session2 = session_service.create_user_session(user_id)

        # Revoke all sessions
        response = api_client_no_auth.delete(
            f"/api/users/{user_id}/sessions",
            headers={
                "Authorization": f"Bearer {admin_session['session_token']}",
                "X-CSRF-Token": admin_session["csrf_token"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 2

        # Verify sessions are revoked
        assert session_service.validate_session(session1["session_token"]) is None
        assert session_service.validate_session(session2["session_token"]) is None
    finally:
        # Clean up
        user_service = UserService(db)
        try:
            user_service.delete_user(user_id)
        except Exception:
            pass


def test_pagination(api_client_no_auth, db, admin_session):
    """Test user list pagination."""
    # Create more users
    oauth_service = OAuthService(db)
    created_users = []
    for i in range(10):
        user = oauth_service.find_or_create_user(
            provider="google",
            provider_id=f"test-user-{i}",
            email=f"test{i}@example.com",
            patreon_tier=None,
        )
        created_users.append(str(user["id"]))

    try:
        # Get first page
        response = api_client_no_auth.get(
            "/api/users?limit=5&offset=0",
            headers={
                "Authorization": f"Bearer {admin_session['session_token']}",
                "X-CSRF-Token": admin_session["csrf_token"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]) == 5
        assert data["limit"] == 5
        assert data["offset"] == 0
        assert data["total"] >= 10

        # Get second page
        response = api_client_no_auth.get(
            "/api/users?limit=5&offset=5",
            headers={
                "Authorization": f"Bearer {admin_session['session_token']}",
                "X-CSRF-Token": admin_session["csrf_token"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]) == 5
        assert data["offset"] == 5
    finally:
        # Clean up
        user_service = UserService(db)
        for user_id in created_users:
            try:
                user_service.delete_user(user_id)
            except Exception:
                pass
