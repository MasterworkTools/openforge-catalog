import secrets
from urllib.parse import urlencode

from flask import Blueprint, current_app, jsonify, redirect, request, url_for
from werkzeug.exceptions import BadRequest, Unauthorized

from openforge.app.services.oauth_service import OAuthService
from openforge.app.services.session_service import SessionService

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/auth/login/<provider>", methods=["GET"])
def login(provider):
    """Initiate OAuth login flow."""
    if provider not in ["patreon", "google"]:
        raise BadRequest(f"Unsupported OAuth provider: {provider}")

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Store state in session or temporary storage
    # For now, we'll pass it through the OAuth flow

    # Build redirect URI
    redirect_uri = url_for("auth.callback", provider=provider, _external=True)

    # Get OAuth service
    oauth_service = OAuthService(current_app.config["DB"])

    # Get authorization URL
    if provider == "patreon":
        auth_url = oauth_service.get_patreon_auth_url(redirect_uri, state)
    else:
        auth_url = oauth_service.get_google_auth_url(redirect_uri, state)

    # Redirect to OAuth provider
    return redirect(auth_url)


@auth_bp.route("/auth/callback/<provider>", methods=["GET"])
def callback(provider):
    """Handle OAuth callback."""
    if provider not in ["patreon", "google"]:
        raise BadRequest(f"Unsupported OAuth provider: {provider}")

    # Get authorization code and state
    code = request.args.get("code")
    # state = request.args.get("state")  # TODO: Implement CSRF validation
    error = request.args.get("error")

    if error:
        # OAuth error (user denied, etc)
        return redirect(
            f"{current_app.config['FRONTEND_URL']}/auth/error?"
            + urlencode({"error": error})
        )

    if not code:
        raise BadRequest("Missing authorization code")

    # TODO: Validate state for CSRF protection
    # For now, we're passing it through

    # Build redirect URI (must match exactly)
    redirect_uri = url_for("auth.callback", provider=provider, _external=True)

    # Get services
    oauth_service = OAuthService(current_app.config["DB"])
    session_service = SessionService(current_app.config["DB"])

    try:
        # Exchange code for token
        if provider == "patreon":
            token_data = oauth_service.exchange_patreon_code(code, redirect_uri)
            access_token = token_data["access_token"]

            # Get user info and tier
            user_info, tier = oauth_service.get_patreon_user_info(access_token)

            # Find or create user
            user = oauth_service.find_or_create_user(
                provider="patreon",
                provider_id=user_info["provider_id"],
                email=user_info["email"],
                patreon_tier=tier,
            )
        else:
            token_data = oauth_service.exchange_google_code(code, redirect_uri)
            access_token = token_data["access_token"]

            # Get user info
            user_info = oauth_service.get_google_user_info(access_token)

            # Find or create user
            user = oauth_service.find_or_create_user(
                provider="google",
                provider_id=user_info["provider_id"],
                email=user_info["email"],
            )

        # Create session
        session_data = session_service.create_user_session(str(user["id"]))

        # Redirect to frontend with session token
        # The frontend will store this in a secure cookie
        return redirect(
            f"{current_app.config['FRONTEND_URL']}/auth/success?"
            + urlencode(
                {
                    "token": session_data["session_token"],
                    "csrf": session_data["csrf_token"],
                }
            )
        )

    except Exception as e:
        current_app.logger.error(f"OAuth callback error: {e}")
        return redirect(
            f"{current_app.config['FRONTEND_URL']}/auth/error?"
            + urlencode({"error": "authentication_failed"})
        )


@auth_bp.route("/auth/logout", methods=["POST"])
def logout():
    """Logout current session."""
    # Get session token from header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise Unauthorized("Missing or invalid authorization header")

    session_token = auth_header[7:]  # Remove "Bearer " prefix

    # Delete session
    session_service = SessionService(current_app.config["DB"])
    deleted = session_service.delete_session(session_token)

    if not deleted:
        raise Unauthorized("Invalid session")

    return jsonify({"message": "Logged out successfully"}), 200


@auth_bp.route("/auth/me", methods=["GET"])
def get_current_user():
    """Get current authenticated user info."""
    # Get session token from header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise Unauthorized("Missing or invalid authorization header")

    session_token = auth_header[7:]  # Remove "Bearer " prefix

    # Validate session
    session_service = SessionService(current_app.config["DB"])
    session = session_service.validate_session(session_token)

    if not session or not session.get("user"):
        raise Unauthorized("Invalid session or not authenticated")

    # Handle expires_at whether it's a datetime or string
    expires_at = session["expires_at"]
    if hasattr(expires_at, "isoformat"):
        expires_at = expires_at.isoformat()

    return jsonify(
        {
            "user": session["user"],
            "session": {"expires_at": expires_at},
        }
    )


@auth_bp.route("/auth/refresh", methods=["POST"])
def refresh_session():
    """Refresh session expiration (extends by 30 days)."""
    # Get session token from header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise Unauthorized("Missing or invalid authorization header")

    session_token = auth_header[7:]  # Remove "Bearer " prefix

    # Validate session
    session_service = SessionService(current_app.config["DB"])
    session = session_service.validate_session(session_token)

    if not session:
        raise Unauthorized("Invalid session")

    # For now, sessions auto-extend on use
    # In the future, we might want to issue new tokens

    # Handle expires_at whether it's a datetime or string
    expires_at = session["expires_at"]
    if hasattr(expires_at, "isoformat"):
        expires_at = expires_at.isoformat()

    return jsonify(
        {
            "message": "Session refreshed",
            "expires_at": expires_at,
        }
    )
