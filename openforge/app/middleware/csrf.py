import secrets
from functools import wraps
from typing import Optional

from flask import current_app, g, jsonify, request


def generate_csrf_token() -> str:
    """Generate a new CSRF token."""
    return secrets.token_urlsafe(32)


def get_csrf_token() -> Optional[str]:
    """Get CSRF token from request headers or form data."""
    # Check for CSRF token in headers first (for AJAX requests)
    csrf_token = request.headers.get("X-CSRF-Token")
    if csrf_token:
        return csrf_token

    # Check for CSRF token in form data (for regular form submissions)
    csrf_token = request.form.get("csrf_token")
    if csrf_token:
        return csrf_token

    # Check for CSRF token in JSON body (for API requests)
    if request.is_json:
        try:
            data = request.get_json()
            if data and "csrf_token" in data:
                return data["csrf_token"]
        except Exception as e:
            # Log malformed JSON attempts for security monitoring
            current_app.logger.warning(f"Malformed JSON in CSRF token extraction: {e}")
            return None

    return None


def validate_csrf_token(expected_token: str, provided_token: Optional[str]) -> bool:
    """Validate CSRF token using constant-time comparison."""
    if not provided_token:
        return False

    # Use constant-time comparison to prevent timing attacks
    return secrets.compare_digest(expected_token, provided_token)


def csrf_protect(f):
    """Decorator to protect routes from CSRF attacks."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Only protect state-changing methods
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return f(*args, **kwargs)

        # Check if request is authenticated via session
        # (CSRF token will be set by @authenticate)
        expected_token = getattr(g, "csrf_token", None)
        if not expected_token:
            # No CSRF token in g, so this is likely API key authentication
            # CSRF protection is not needed for API key requests
            return f(*args, **kwargs)

        # Get provided CSRF token
        provided_token = get_csrf_token()

        # Validate CSRF token
        if not validate_csrf_token(expected_token, provided_token):
            return jsonify({"error": "Invalid CSRF token"}), 403

        return f(*args, **kwargs)

    return decorated_function
