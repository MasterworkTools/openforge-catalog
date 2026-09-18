import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from flask import current_app
from psycopg import sql
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


class SessionService:
    def __init__(self, db, api_token: str = None, secret_key: str = None):
        self.db = db
        self.api_token = api_token
        self.secret_key = secret_key

    def create_session(self, api_key: str) -> Dict:
        """Create new session (30 days duration, currently admin-only)."""
        # Get API token from instance or Flask app configuration
        api_token = self.api_token
        if not api_token:
            try:
                api_token = current_app.config.get("API_TOKEN")
            except RuntimeError:
                raise ValueError(
                    "API_TOKEN not provided to SessionService and no Flask app "
                    "context available"
                )

        if not api_token:
            raise ValueError("API_TOKEN not configured")

        if not secrets.compare_digest(api_key, api_token):
            raise ValueError("Invalid API key")

        # Generate secure session token
        session_token = secrets.token_urlsafe(32)
        session_token_hash = self._hash_token(session_token)

        # Set expiration to 30 days from now
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        # Store hash in database
        session_id = self._insert_session(session_token_hash, expires_at)

        # Generate CSRF token for the session
        csrf_token = self.get_csrf_token_for_session(session_id)

        return {
            "session_token": session_token,
            "expires_at": expires_at.isoformat(),
            "csrf_token": csrf_token,
        }

    def validate_session(self, session_token: str) -> Optional[Dict]:
        """Validate session token and update last_used_at (throttled by trigger).

        Returns safe session data if valid.
        """
        session_token_hash = self._hash_token(session_token)

        # First validate the session exists and is not expired
        session = self._get_session_by_hash(session_token_hash)
        if not session or session["expires_at"] < datetime.now(timezone.utc):
            return None

        # If valid, trigger an UPDATE to refresh last_used_at
        # (throttled by trigger)
        # This UPDATE will be caught by the trigger which only updates
        # if >1 hour has passed
        try:
            self._update_session_last_used(session_token_hash)
        except Exception:
            # Log the error with full stack trace but don't fail validation
            # - the session is still valid
            # The last_used_at update is a performance optimization,
            # not critical
            logger.exception("Failed to update session last_used_at")

        # Return safe session data (exclude sensitive fields like session_token_hash)
        return {
            "id": session["id"],
            "created_at": session["created_at"],
            "expires_at": session["expires_at"],
            "last_used_at": session["last_used_at"],
        }

    def delete_session(self, session_token: str) -> bool:
        """Delete session (logout).

        To invalidate compromised sessions, simply delete the record.
        """
        session_token_hash = self._hash_token(session_token)
        return self._delete_session_by_hash(session_token_hash)

    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions (run during validation)."""
        return self._delete_expired_sessions()

    def get_csrf_token_for_session(self, session_id: str) -> str:
        """Generate a consistent CSRF token for a session based on session ID."""
        # Use session ID + a dedicated secret to generate consistent CSRF tokens
        # This ensures the same session always gets the same CSRF token
        secret = self.secret_key
        if not secret:
            try:
                secret = current_app.config["SECRET_KEY"]
            except RuntimeError:
                raise ValueError(
                    "SECRET_KEY not provided to SessionService and no Flask app "
                    "context available"
                )

        if not secret:
            raise ValueError("SECRET_KEY not configured, cannot generate CSRF token.")

        csrf_seed = f"{session_id}:{secret}"
        return hashlib.sha256(csrf_seed.encode()).hexdigest()

    def _hash_token(self, session_token: str) -> str:
        """Hash a session token for storage."""
        return hashlib.sha256(session_token.encode()).hexdigest()

    def _insert_session(self, session_token_hash: str, expires_at: datetime) -> str:
        """Insert new session into database."""
        with self.db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                query = sql.SQL(
                    """
                    INSERT INTO sessions (session_token_hash, expires_at)
                    VALUES ({session_token_hash}, {expires_at})
                    RETURNING id
                    """
                ).format(
                    session_token_hash=sql.Placeholder("session_token_hash"),
                    expires_at=sql.Placeholder("expires_at"),
                )
                curs.execute(
                    query,
                    {
                        "session_token_hash": session_token_hash,
                        "expires_at": expires_at,
                    },
                )
                result = curs.fetchone()
                return str(result["id"])

    def _get_session_by_hash(self, session_token_hash: str) -> Optional[Dict]:
        """Get session by token hash."""
        with self.db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                query = sql.SQL(
                    """
                    SELECT id, session_token_hash, created_at, expires_at, last_used_at
                    FROM sessions
                    WHERE session_token_hash = {session_token_hash}
                    """
                ).format(session_token_hash=sql.Placeholder("session_token_hash"))
                curs.execute(query, {"session_token_hash": session_token_hash})
                return curs.fetchone()

    def _update_session_last_used(self, session_token_hash: str) -> bool:
        """Update last_used_at for session (triggers throttled update)."""
        with self.db.connection() as conn:
            with conn.cursor() as curs:
                query = sql.SQL(
                    """
                    UPDATE sessions
                    SET last_used_at = now()
                    WHERE session_token_hash = {session_token_hash}
                    """
                ).format(session_token_hash=sql.Placeholder("session_token_hash"))
                curs.execute(query, {"session_token_hash": session_token_hash})
                return curs.rowcount > 0

    def _delete_session_by_hash(self, session_token_hash: str) -> bool:
        """Delete session by token hash."""
        with self.db.connection() as conn:
            with conn.cursor() as curs:
                query = sql.SQL(
                    """
                    DELETE FROM sessions
                    WHERE session_token_hash = {session_token_hash}
                    """
                ).format(session_token_hash=sql.Placeholder("session_token_hash"))
                curs.execute(query, {"session_token_hash": session_token_hash})
                return curs.rowcount > 0

    def _delete_expired_sessions(self) -> int:
        """Delete expired sessions and return count of deleted sessions."""
        with self.db.connection() as conn:
            with conn.cursor() as curs:
                query = sql.SQL(
                    """
                    DELETE FROM sessions
                    WHERE expires_at < now()
                    """
                )
                curs.execute(query)
                return curs.rowcount
