import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from psycopg import sql
from psycopg.rows import dict_row
from werkzeug.exceptions import BadRequest, NotFound

logger = logging.getLogger(__name__)


class UserService:
    """Service for managing users."""

    def __init__(self, db):
        self.db = db

    def get_users(
        self,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
        role: Optional[str] = None,
        blocked: Optional[bool] = None,
        patreon_tier: Optional[str] = None,
    ) -> Dict:
        """Get paginated list of users with optional filtering."""
        with self.db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                # Build query with filters
                conditions = []
                params = {}

                if search:
                    conditions.append("email ILIKE {search}")
                    params["search"] = f"%{search}%"

                if role:
                    conditions.append("role = {role}")
                    params["role"] = role

                if blocked is not None:
                    conditions.append("blocked = {blocked}")
                    params["blocked"] = blocked

                if patreon_tier:
                    conditions.append("patreon_tier = {tier}")
                    params["tier"] = patreon_tier

                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)

                # Get total count
                count_query = sql.SQL(f"""
                    SELECT COUNT(*) as total
                    FROM users
                    {where_clause}
                """)
                if params:
                    count_query = count_query.format(
                        **{k: sql.Placeholder(k) for k in params}
                    )

                curs.execute(count_query, params)
                total = curs.fetchone()["total"]

                # Get users
                query = sql.SQL(f"""
                    SELECT u.*,
                           array_agg(
                               json_build_object(
                                   'provider', ui.provider,
                                   'provider_id', ui.provider_id
                               ) ORDER BY ui.created_at
                           ) FILTER (WHERE ui.provider IS NOT NULL) as identities
                    FROM users u
                    LEFT JOIN user_identities ui ON u.id = ui.user_id
                    {where_clause}
                    GROUP BY u.id
                    ORDER BY u.created_at DESC
                    LIMIT {{limit}} OFFSET {{offset}}
                """)

                format_params = {k: sql.Placeholder(k) for k in params}
                format_params["limit"] = sql.Placeholder("limit")
                format_params["offset"] = sql.Placeholder("offset")

                if params or format_params:
                    query = query.format(**format_params)

                params["limit"] = limit
                params["offset"] = offset

                curs.execute(query, params)
                users = curs.fetchall()

                return {
                    "users": users,
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                }

    def get_user_by_id(self, user_id: str) -> Dict:
        """Get user by ID with identities."""
        with self.db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                query = sql.SQL("""
                    SELECT u.*,
                           array_agg(
                               json_build_object(
                                   'provider', ui.provider,
                                   'provider_id', ui.provider_id,
                                   'created_at', ui.created_at
                               ) ORDER BY ui.created_at
                           ) FILTER (WHERE ui.provider IS NOT NULL) as identities
                    FROM users u
                    LEFT JOIN user_identities ui ON u.id = ui.user_id
                    WHERE u.id = {user_id}
                    GROUP BY u.id
                """).format(user_id=sql.Placeholder("user_id"))

                curs.execute(query, {"user_id": user_id})
                user = curs.fetchone()

                if not user:
                    raise NotFound(f"User {user_id} not found")

                return user

    def update_user(
        self,
        user_id: str,
        role: Optional[str] = None,
        patreon_tier: Optional[str] = None,
        blocked: Optional[bool] = None,
        blocked_reason: Optional[str] = None,
    ) -> Dict:
        """Update user details."""
        with self.db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                # Build update fields
                updates = []
                params = {"user_id": user_id}

                if role is not None:
                    updates.append("role = {role}")
                    params["role"] = role

                if patreon_tier is not None:
                    updates.append("patreon_tier = {tier}")
                    params["tier"] = patreon_tier

                if blocked is not None:
                    updates.append("blocked = {blocked}")
                    params["blocked"] = blocked

                    if blocked:
                        updates.append("blocked_at = {blocked_at}")
                        params["blocked_at"] = datetime.now(timezone.utc)

                        if blocked_reason:
                            updates.append("blocked_reason = {blocked_reason}")
                            params["blocked_reason"] = blocked_reason
                    else:
                        # Unblocking - clear blocked fields
                        updates.append("blocked_at = NULL")
                        updates.append("blocked_reason = NULL")

                if not updates:
                    raise BadRequest("No fields to update")

                # Always update updated_at
                updates.append("updated_at = now()")

                query = sql.SQL(f"""
                    UPDATE users
                    SET {", ".join(updates)}
                    WHERE id = {{user_id}}
                    RETURNING *
                """).format(
                    **{k: sql.Placeholder(k) for k in params if k != "user_id"},
                    user_id=sql.Placeholder("user_id"),
                )

                curs.execute(query, params)
                user = curs.fetchone()

                if not user:
                    raise NotFound(f"User {user_id} not found")

                # Get updated user with identities
                return self.get_user_by_id(user_id)

    def delete_user(self, user_id: str) -> bool:
        """Delete a user and all associated data."""
        with self.db.connection() as conn:
            with conn.cursor() as curs:
                # User identities and sessions will be deleted by CASCADE
                query = sql.SQL("""
                    DELETE FROM users
                    WHERE id = {user_id}
                """).format(user_id=sql.Placeholder("user_id"))

                curs.execute(query, {"user_id": user_id})

                if curs.rowcount == 0:
                    raise NotFound(f"User {user_id} not found")

                return True

    def get_user_sessions(self, user_id: str) -> List[Dict]:
        """Get all active sessions for a user."""
        with self.db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                query = sql.SQL("""
                    SELECT id, created_at, expires_at, last_used_at
                    FROM sessions
                    WHERE user_id = {user_id}
                    AND expires_at > now()
                    ORDER BY last_used_at DESC
                """).format(user_id=sql.Placeholder("user_id"))

                curs.execute(query, {"user_id": user_id})
                return curs.fetchall()

    def revoke_user_sessions(self, user_id: str) -> int:
        """Revoke all sessions for a user."""
        with self.db.connection() as conn:
            with conn.cursor() as curs:
                query = sql.SQL("""
                    DELETE FROM sessions
                    WHERE user_id = {user_id}
                """).format(user_id=sql.Placeholder("user_id"))

                curs.execute(query, {"user_id": user_id})
                return curs.rowcount

    def check_user_permission(self, user: Dict, required_role: str = "admin") -> bool:
        """Check if user has required role permission."""
        if not user:
            return False

        # Check if user is blocked
        if user.get("blocked"):
            return False

        # For now, simple role check
        # Could be expanded to more complex permission system
        return user.get("role") == required_role
