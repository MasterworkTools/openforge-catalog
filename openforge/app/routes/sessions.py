from flask import Response, current_app, jsonify, request


def _set_session_cookie(response: Response, session_token: str) -> None:
    """Set secure session cookie with consistent settings."""
    response.set_cookie(
        "session_token",
        session_token,
        max_age=30 * 24 * 60 * 60,  # 30 days in seconds
        httponly=True,
        secure=True,  # Requires HTTPS
        samesite="Strict",
    )


def create_session():
    """Create a new admin session."""
    try:
        data = request.get_json()
        if not data or "api_key" not in data:
            return jsonify({"error": "API key required"}), 400
    except Exception as e:
        # Log malformed JSON attempts for security monitoring
        current_app.logger.warning(f"Malformed JSON in session creation: {e}")
        return jsonify({"error": "Invalid JSON format"}), 400

    try:
        session_data = current_app.session_service.create_session(data["api_key"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 401

    # CSRF token is now included in session_data
    csrf_token = session_data["csrf_token"]

    # Set session cookie with secure settings
    response = jsonify(
        {
            "message": "Session created successfully",
            "expires_at": session_data["expires_at"],
            "csrf_token": csrf_token,
        }
    )

    # Set secure session cookie
    _set_session_cookie(response, session_data["session_token"])

    # Set CSRF token in response headers
    response.headers["X-CSRF-Token"] = csrf_token

    return response, 201


def validate_session():
    """Validate current session."""
    session_token = request.cookies.get("session_token")
    if not session_token:
        return jsonify({"valid": False, "error": "No session token"}), 401

    session_data = current_app.session_service.validate_session(session_token)

    if not session_data:
        return jsonify({"valid": False, "error": "Invalid or expired session"}), 401

    # Clean up expired sessions during validation
    cleaned_count = current_app.session_service.cleanup_expired_sessions()
    if cleaned_count > 0:
        current_app.logger.info(f"Cleaned up {cleaned_count} expired sessions")

    # Generate consistent CSRF token for the session
    csrf_token = current_app.session_service.get_csrf_token_for_session(
        session_data["id"]
    )

    response = jsonify(
        {
            "valid": True,
            "expires_at": session_data["expires_at"].isoformat()
            if session_data["expires_at"]
            else None,
            "csrf_token": csrf_token,
        }
    )

    # Set CSRF token in response headers
    response.headers["X-CSRF-Token"] = csrf_token

    return response


def delete_session():
    """Delete current session (logout)."""
    # Get session token from cookie (already validated by @authenticate)
    session_token = request.cookies.get("session_token")
    success = current_app.session_service.delete_session(session_token)

    if not success:
        return jsonify({"error": "Session not found"}), 404

    # Clear the session cookie
    response = jsonify({"message": "Session deleted successfully"})
    response.delete_cookie("session_token")

    return response
