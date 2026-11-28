import secrets
from functools import wraps
from typing import Union

from flask import current_app, g, jsonify, request


def authenticate(
    methods: list[str] = None,
    disable_sessions: list[str] = None,
    disable_api_keys: list[str] = None,
    disable_csrf: list[str] = None,
):
    """
    Configurable authentication decorator.

    Args:
        methods: List of HTTP methods that require authentication (default: all methods)
        disable_sessions: List of HTTP methods to disable session authentication for
        disable_api_keys: List of HTTP methods to disable API key authentication for
        disable_csrf: List of HTTP methods to disable CSRF token setting for
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Default to all methods if none specified
            if methods is None:
                auth_methods = [
                    "GET",
                    "POST",
                    "PUT",
                    "PATCH",
                    "DELETE",
                    "HEAD",
                    "OPTIONS",
                ]
            else:
                auth_methods = methods

            if request.method not in auth_methods:
                return f(*args, **kwargs)

            # Check if features are disabled for this method
            disable_sessions_for_method = (
                disable_sessions and request.method in disable_sessions
            )
            disable_api_keys_for_method = (
                disable_api_keys and request.method in disable_api_keys
            )
            disable_csrf_for_method = disable_csrf and request.method in disable_csrf

            authenticated = False

            # Check for session authentication (if not disabled for this method)
            if not disable_sessions_for_method:
                # Check for session token in cookie first
                session_token = request.cookies.get("session_token")

                # If not in cookie, check for Bearer token (for user sessions)
                if not session_token:
                    auth_header = request.headers.get("Authorization", "")
                    if auth_header.startswith("Bearer "):
                        session_token = auth_header[7:]

                if session_token:
                    session_data = current_app.session_service.validate_session(
                        session_token
                    )
                    if session_data:
                        authenticated = True
                        # Store session data in g for use by routes
                        g.session = session_data
                        # Set CSRF token in g for CSRF protection
                        # (if not disabled for this method)
                        if not disable_csrf_for_method:
                            g.csrf_token = (
                                current_app.session_service.get_csrf_token_for_session(
                                    session_data["id"]
                                )
                            )

            # Fall back to API key authentication
            # (if not disabled for this method and not already authenticated)
            if not authenticated and not disable_api_keys_for_method:
                token = request.headers.get("Authorization")
                if validate_api_token(token):
                    authenticated = True

            if not authenticated:
                error_message = "Valid "
                if not disable_sessions_for_method and not disable_api_keys_for_method:
                    error_message += "session or API key"
                elif not disable_sessions_for_method:
                    error_message += "session"
                elif not disable_api_keys_for_method:
                    error_message += "API key"
                else:
                    error_message += "authentication"
                error_message += " required"

                return jsonify({"error": "Unauthorized", "message": error_message}), 401

            return f(*args, **kwargs)

        return wrapper

    return decorator


def _get_api_token_from_header(token: str) -> str:
    """Extract API token from Authorization header."""
    parts = token.split(" ")
    if len(parts) == 1:
        return parts[0]
    elif len(parts) == 2:
        if parts[0] == "Bearer":
            return parts[1]
    raise ValueError("Invalid API token format")


def validate_api_token(token: Union[str, None]) -> bool:
    """Validate API token against configured token using constant-time comparison."""
    if not token:
        return False
    try:
        extracted_token = _get_api_token_from_header(token)
        return secrets.compare_digest(extracted_token, current_app.config["API_TOKEN"])
    except ValueError:
        return False
