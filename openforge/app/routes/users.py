from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.exceptions import BadRequest, Forbidden, Unauthorized

from openforge.app.middleware.csrf import csrf_protect
from openforge.app.routes import authenticate
from openforge.app.services.user_service import UserService

users_bp = Blueprint("users", __name__)


def _get_current_user():
    """Get current user from g.session."""
    if not hasattr(g, "session") or not g.session:
        raise Unauthorized("No authenticated session")

    if not g.session.get("user"):
        raise Unauthorized("Invalid session or not authenticated")

    return g.session["user"]


def _require_admin():
    """Ensure current user is an admin."""
    user = _get_current_user()
    if user.get("role") != "admin":
        raise Forbidden("Admin access required")
    return user


@users_bp.route("/users", methods=["GET"])
@authenticate(methods=["GET"])
def list_users():
    """List users with filtering and pagination (admin only)."""
    _require_admin()

    # Get query parameters
    limit = min(int(request.args.get("limit", 100)), 1000)
    offset = int(request.args.get("offset", 0))
    search = request.args.get("search")
    role = request.args.get("role")
    blocked = request.args.get("blocked")
    patreon_tier = request.args.get("patreon_tier")

    # Convert blocked to boolean if provided
    if blocked is not None:
        blocked = blocked.lower() in ["true", "1", "yes"]

    user_service = UserService(current_app.config["DB"])
    result = user_service.get_users(
        limit=limit,
        offset=offset,
        search=search,
        role=role,
        blocked=blocked,
        patreon_tier=patreon_tier,
    )

    return jsonify(result)


@users_bp.route("/users/<user_id>", methods=["GET"])
@authenticate(methods=["GET"])
def get_user(user_id):
    """Get user by ID (admin only or own user)."""
    current_user = _get_current_user()

    # Allow users to view their own profile or admins to view any
    if str(current_user["id"]) != user_id and current_user.get("role") != "admin":
        raise Forbidden("Access denied")

    user_service = UserService(current_app.config["DB"])
    user = user_service.get_user_by_id(user_id)

    return jsonify(user)


@users_bp.route("/users/<user_id>", methods=["PATCH"])
@authenticate(methods=["PATCH"])
@csrf_protect
def update_user(user_id):
    """Update user (admin only)."""
    _require_admin()

    # Get update data
    data = request.get_json()
    if not data:
        raise BadRequest("No data provided")

    # Extract allowed fields
    role = data.get("role")
    patreon_tier = data.get("patreon_tier")
    blocked = data.get("blocked")
    blocked_reason = data.get("blocked_reason")

    # Validate role if provided
    if role and role not in ["user", "admin"]:
        raise BadRequest("Invalid role. Must be 'user' or 'admin'")

    # Validate patreon_tier if provided
    valid_tiers = ["Bronze", "Silver", "Gold", "Platinum"]
    if patreon_tier and patreon_tier not in valid_tiers:
        raise BadRequest(
            f"Invalid patreon_tier. Must be one of: {', '.join(valid_tiers)}"
        )

    user_service = UserService(current_app.config["DB"])
    user = user_service.update_user(
        user_id=user_id,
        role=role,
        patreon_tier=patreon_tier,
        blocked=blocked,
        blocked_reason=blocked_reason,
    )

    return jsonify(user)


@users_bp.route("/users/<user_id>", methods=["DELETE"])
@authenticate(methods=["DELETE"])
@csrf_protect
def delete_user(user_id):
    """Delete user (admin only)."""
    current_user = _require_admin()

    # Prevent self-deletion
    if str(current_user["id"]) == user_id:
        raise BadRequest("Cannot delete your own account")

    user_service = UserService(current_app.config["DB"])
    user_service.delete_user(user_id)

    return jsonify({"message": "User deleted successfully"}), 200


@users_bp.route("/users/<user_id>/sessions", methods=["GET"])
@authenticate(methods=["GET"])
def get_user_sessions(user_id):
    """Get user's active sessions (admin only or own user)."""
    current_user = _get_current_user()

    # Allow users to view their own sessions or admins to view any
    if str(current_user["id"]) != user_id and current_user.get("role") != "admin":
        raise Forbidden("Access denied")

    user_service = UserService(current_app.config["DB"])
    sessions = user_service.get_user_sessions(user_id)

    return jsonify({"sessions": sessions})


@users_bp.route("/users/<user_id>/sessions", methods=["DELETE"])
@authenticate(methods=["DELETE"])
@csrf_protect
def revoke_user_sessions(user_id):
    """Revoke all user sessions (admin only or own user)."""
    current_user = _get_current_user()

    # Allow users to revoke their own sessions or admins to revoke any
    if str(current_user["id"]) != user_id and current_user.get("role") != "admin":
        raise Forbidden("Access denied")

    user_service = UserService(current_app.config["DB"])
    count = user_service.revoke_user_sessions(user_id)

    return jsonify({"message": f"Revoked {count} session(s)", "count": count}), 200


@users_bp.route("/users/<user_id>/block", methods=["POST"])
@authenticate(methods=["POST"])
@csrf_protect
def block_user(user_id):
    """Block a user (admin only)."""
    _require_admin()

    data = request.get_json() or {}
    reason = data.get("reason", "No reason provided")

    user_service = UserService(current_app.config["DB"])
    user = user_service.update_user(
        user_id=user_id, blocked=True, blocked_reason=reason
    )

    # Also revoke all sessions
    count = user_service.revoke_user_sessions(user_id)

    return jsonify({"user": user, "sessions_revoked": count})


@users_bp.route("/users/<user_id>/unblock", methods=["POST"])
@authenticate(methods=["POST"])
@csrf_protect
def unblock_user(user_id):
    """Unblock a user (admin only)."""
    _require_admin()

    user_service = UserService(current_app.config["DB"])
    user = user_service.update_user(user_id=user_id, blocked=False)

    return jsonify(user)
