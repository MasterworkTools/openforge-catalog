from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from werkzeug.exceptions import BadRequest, NotFound

from openforge.app.services.user_service import UserService


@pytest.fixture
def mock_db():
    """Create a mock database object."""
    db = Mock()
    return db


@pytest.fixture
def user_service(mock_db):
    """Create a UserService instance with mock db."""
    return UserService(mock_db)


@pytest.fixture
def sample_user():
    """Sample user data for tests."""
    return {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "email": "test@example.com",
        "role": "user",
        "patreon_tier": "Silver",
        "blocked": False,
        "blocked_at": None,
        "blocked_reason": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "identities": [
            {
                "provider": "patreon",
                "provider_id": "12345",
                "created_at": datetime.now(timezone.utc),
            }
        ],
    }


def test_get_users_basic(user_service, mock_db, sample_user):
    """Test getting users without filters."""
    # Setup mock connection and cursor
    mock_cursor = Mock()
    mock_cursor.fetchone.return_value = {"total": 1}
    mock_cursor.fetchall.return_value = [sample_user]
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    mock_db.connection.return_value = mock_conn

    # Test the method
    result = user_service.get_users()

    # Verify results
    assert result["total"] == 1
    assert len(result["users"]) == 1
    assert result["users"][0]["email"] == "test@example.com"
    assert result["limit"] == 100
    assert result["offset"] == 0

    # Verify queries were executed
    assert mock_cursor.execute.call_count == 2  # count + data queries


def test_get_users_with_search_filter(user_service, mock_db):
    """Test getting users with search filter."""
    # Setup mock
    mock_cursor = Mock()
    mock_cursor.fetchone.return_value = {"total": 0}
    mock_cursor.fetchall.return_value = []
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    mock_db.connection.return_value = mock_conn

    # Test with search
    user_service.get_users(search="admin@")

    # Verify parameters were used
    calls = mock_cursor.execute.call_args_list
    assert len(calls) == 2
    # Check that search parameter was passed
    assert "search" in calls[0][0][1]
    assert calls[0][0][1]["search"] == "%admin@%"


def test_get_users_with_role_filter(user_service, mock_db):
    """Test getting users with role filter."""
    # Setup mock
    mock_cursor = Mock()
    mock_cursor.fetchone.return_value = {"total": 0}
    mock_cursor.fetchall.return_value = []
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    mock_db.connection.return_value = mock_conn

    # Test with role filter
    user_service.get_users(role="admin")

    # Verify parameters
    calls = mock_cursor.execute.call_args_list
    assert "role" in calls[0][0][1]
    assert calls[0][0][1]["role"] == "admin"


def test_get_users_with_blocked_filter(user_service, mock_db):
    """Test getting users with blocked filter."""
    # Setup mock
    mock_cursor = Mock()
    mock_cursor.fetchone.return_value = {"total": 0}
    mock_cursor.fetchall.return_value = []
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    mock_db.connection.return_value = mock_conn

    # Test with blocked filter
    user_service.get_users(blocked=True)

    # Verify parameters
    calls = mock_cursor.execute.call_args_list
    assert "blocked" in calls[0][0][1]
    assert calls[0][0][1]["blocked"] is True


def test_get_user_by_id_success(user_service, mock_db, sample_user):
    """Test getting user by ID successfully."""
    # Setup mock
    mock_cursor = Mock()
    mock_cursor.fetchone.return_value = sample_user
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    mock_db.connection.return_value = mock_conn

    # Test the method
    result = user_service.get_user_by_id(sample_user["id"])

    # Verify results
    assert result["id"] == sample_user["id"]
    assert result["email"] == sample_user["email"]

    # Verify query parameters
    calls = mock_cursor.execute.call_args_list
    assert calls[0][0][1]["user_id"] == sample_user["id"]


def test_get_user_by_id_not_found(user_service, mock_db):
    """Test getting non-existent user raises NotFound."""
    # Setup mock
    mock_cursor = Mock()
    mock_cursor.fetchone.return_value = None
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    mock_db.connection.return_value = mock_conn

    # Test should raise NotFound
    with pytest.raises(NotFound) as exc:
        user_service.get_user_by_id("non-existent-id")

    assert "User non-existent-id not found" in str(exc.value)


def test_update_user_role(user_service, mock_db, sample_user):
    """Test updating user role."""
    # Setup mock - update returns None, then get_user_by_id is called
    mock_cursor = Mock()
    mock_cursor.fetchone.side_effect = [{"id": sample_user["id"]}, sample_user]
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    mock_db.connection.return_value = mock_conn

    # Test updating role
    user_service.update_user(user_id=sample_user["id"], role="admin")

    # Verify update query parameters
    update_call = mock_cursor.execute.call_args_list[0]
    assert "role" in update_call[0][1]
    assert update_call[0][1]["role"] == "admin"


def test_update_user_blocked_status(user_service, mock_db, sample_user):
    """Test blocking a user."""
    # Setup mock
    mock_cursor = Mock()
    mock_cursor.fetchone.side_effect = [{"id": sample_user["id"]}, sample_user]
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    mock_db.connection.return_value = mock_conn

    # Test blocking user
    user_service.update_user(
        user_id=sample_user["id"], blocked=True, blocked_reason="Violating terms"
    )

    # Verify update parameters
    update_call = mock_cursor.execute.call_args_list[0]
    assert "blocked" in update_call[0][1]
    assert update_call[0][1]["blocked"] is True
    assert "blocked_at" in update_call[0][1]
    assert "blocked_reason" in update_call[0][1]
    assert update_call[0][1]["blocked_reason"] == "Violating terms"


def test_update_user_unblock(user_service, mock_db, sample_user):
    """Test unblocking a user."""
    # Setup mock
    mock_cursor = Mock()
    mock_cursor.fetchone.side_effect = [{"id": sample_user["id"]}, sample_user]
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    mock_db.connection.return_value = mock_conn

    # Test unblocking user
    user_service.update_user(user_id=sample_user["id"], blocked=False)

    # Verify update clears blocked fields
    update_call = mock_cursor.execute.call_args_list[0]
    assert "blocked" in update_call[0][1]
    assert update_call[0][1]["blocked"] is False
    # Query should contain NULL assignments for blocked_at and blocked_reason


def test_update_user_no_fields(user_service, mock_db):
    """Test updating user with no fields raises BadRequest."""
    # Setup mock connection and cursor
    mock_cursor = Mock()
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    mock_db.connection.return_value = mock_conn

    with pytest.raises(BadRequest) as exc:
        user_service.update_user(user_id="some-id")

    assert "No fields to update" in str(exc.value)


def test_update_user_not_found(user_service, mock_db):
    """Test updating non-existent user raises NotFound."""
    # Setup mock
    mock_cursor = Mock()
    mock_cursor.fetchone.return_value = None
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    mock_db.connection.return_value = mock_conn

    # Test should raise NotFound
    with pytest.raises(NotFound) as exc:
        user_service.update_user(user_id="non-existent", role="admin")

    assert "User non-existent not found" in str(exc.value)


def test_delete_user_success(user_service, mock_db):
    """Test deleting user successfully."""
    # Setup mock
    mock_cursor = Mock()
    mock_cursor.rowcount = 1
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    mock_db.connection.return_value = mock_conn

    # Test deletion
    result = user_service.delete_user("user-id")

    assert result is True

    # Verify query parameters
    calls = mock_cursor.execute.call_args_list
    assert calls[0][0][1]["user_id"] == "user-id"


def test_delete_user_not_found(user_service, mock_db):
    """Test deleting non-existent user raises NotFound."""
    # Setup mock
    mock_cursor = Mock()
    mock_cursor.rowcount = 0
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    mock_db.connection.return_value = mock_conn

    # Test should raise NotFound
    with pytest.raises(NotFound) as exc:
        user_service.delete_user("non-existent")

    assert "User non-existent not found" in str(exc.value)


def test_get_user_sessions(user_service, mock_db):
    """Test getting user sessions."""
    # Setup mock sessions
    sessions = [
        {
            "id": "session-1",
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
            "last_used_at": datetime.now(timezone.utc),
        },
        {
            "id": "session-2",
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
            "last_used_at": datetime.now(timezone.utc) - timedelta(hours=1),
        },
    ]

    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = sessions
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    mock_db.connection.return_value = mock_conn

    # Test getting sessions
    result = user_service.get_user_sessions("user-id")

    assert len(result) == 2
    assert result[0]["id"] == "session-1"

    # Verify query parameters
    calls = mock_cursor.execute.call_args_list
    assert calls[0][0][1]["user_id"] == "user-id"


def test_revoke_user_sessions(user_service, mock_db):
    """Test revoking user sessions."""
    # Setup mock
    mock_cursor = Mock()
    mock_cursor.rowcount = 3
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    mock_db.connection.return_value = mock_conn

    # Test revoking sessions
    count = user_service.revoke_user_sessions("user-id")

    assert count == 3

    # Verify query parameters
    calls = mock_cursor.execute.call_args_list
    assert calls[0][0][1]["user_id"] == "user-id"


def test_check_user_permission_admin(user_service, sample_user):
    """Test checking admin permission."""
    # Test admin user
    admin_user = sample_user.copy()
    admin_user["role"] = "admin"

    assert user_service.check_user_permission(admin_user, "admin") is True
    assert user_service.check_user_permission(admin_user, "user") is False

    # Test regular user
    assert user_service.check_user_permission(sample_user, "admin") is False


def test_check_user_permission_blocked(user_service, sample_user):
    """Test blocked users have no permissions."""
    # Test blocked user
    blocked_user = sample_user.copy()
    blocked_user["blocked"] = True
    blocked_user["role"] = "admin"  # Even admin role should be denied

    assert user_service.check_user_permission(blocked_user, "admin") is False
    assert user_service.check_user_permission(blocked_user, "user") is False


def test_check_user_permission_none_user(user_service):
    """Test None user has no permissions."""
    assert user_service.check_user_permission(None, "admin") is False
    assert user_service.check_user_permission(None, "user") is False
