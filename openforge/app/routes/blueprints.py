import re
import uuid
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from flask import abort, current_app, jsonify, make_response, redirect, request
from jsonschema.exceptions import ValidationError
from psycopg.rows import dict_row
from werkzeug.exceptions import NotFound

import openforge.db.sql.blueprints as blueprint_sql
import openforge.db.sql.images as image_sql
import openforge.db.sql.tags as tag_sql
from openforge.openapi import validate_schema


def _validate_uuid(uuid_string: str) -> None:
    """Validate that a string is a valid UUID, abort with 400 if not."""
    try:
        uuid.UUID(uuid_string)
    except ValueError:
        abort(400, description="Invalid UUID format.")


def _get_blueprint_thumbnail(cursor, blueprint_id):
    """Fetch the thumbnail image for a given blueprint.

    Args:
        cursor: Database cursor
        blueprint_id: UUID of the blueprint

    Returns:
        dict: Thumbnail image data, or None if not found
    """
    images = image_sql.get_images_for_blueprint(cursor, blueprint_id)
    thumbnails = [img for img in images if img.get("image_type") == "thumbnail"]
    if not thumbnails:
        return None
    return thumbnails[0]


def get_blueprints():
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            data = blueprint_sql.get_all_blueprints(cursor)
            return jsonify(data)


def get_deprecated_blueprints():
    """Get all deprecated blueprints with their successor information."""
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            data = blueprint_sql.get_deprecated_blueprints(cursor)
            if not data:
                return jsonify([]), 404
            return jsonify(data)


def _create_blueprint_words(data: dict):
    words = set()
    for t in data.get("tags", []):
        words.update(re.split(r"[^a-zA-Z0-9]", t))
    return list(words)


def create_blueprint():
    try:
        validate_schema("blueprint.yaml", request.json)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            req_data = request.json
            data = blueprint_sql.insert_blueprint(
                cursor, req_data, words=_create_blueprint_words(req_data)
            )
            if "tags" in req_data:
                for tag in req_data["tags"]:
                    tag_sql.insert_tag(cursor, data["id"], tag)
            if "images" in req_data:
                for image in req_data["images"]:
                    image_sql.insert_image_for_blueprint(cursor, data["id"], image)
            data["tags"] = [tag["tag"] for tag in tag_sql.get_tags(cursor, data["id"])]
            data["images"] = image_sql.get_images_for_blueprint(cursor, data["id"])
            return jsonify(data), 201


def get_blueprint_by_id(blueprint_id):
    _validate_uuid(blueprint_id)

    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            data = blueprint_sql.get_blueprint_by_id(cursor, blueprint_id)
            data["tags"] = [
                tag["tag"] for tag in tag_sql.get_tags(cursor, blueprint_id)
            ]
            data["images"] = image_sql.get_images_for_blueprint(cursor, data["id"])
            return jsonify(data)


def get_blueprint_by_md5(md5):
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            # Follow successor chain to get current version
            data = blueprint_sql.get_current_version_by_md5(cursor, md5)
            data["tags"] = [tag["tag"] for tag in tag_sql.get_tags(cursor, data["id"])]
            data["images"] = image_sql.get_images_for_blueprint(cursor, data["id"])
            return jsonify(data)


def update_blueprint(blueprint_id):
    _validate_uuid(blueprint_id)

    try:
        validate_schema("blueprint.yaml", request.json, required=False)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            req_data = request.json
            data = blueprint_sql.update_blueprint(cursor, blueprint_id, req_data)
            if "tags" in req_data:
                try:
                    tag_sql.delete_all_blueprint_tags(cursor, blueprint_id)
                except NotFound:
                    pass
                for tag in req_data["tags"]:
                    tag_sql.insert_tag(cursor, blueprint_id, tag)
            if "images" in req_data:
                image_sql.replace_images_for_blueprint(
                    cursor, blueprint_id, req_data["images"]
                )
            data["tags"] = [
                tag["tag"] for tag in tag_sql.get_tags(cursor, blueprint_id)
            ]
            data["images"] = list(
                image_sql.get_images_for_blueprint(cursor, blueprint_id)
            )
            return jsonify(data)


def delete_blueprint(blueprint_id):
    _validate_uuid(blueprint_id)

    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            try:
                tag_sql.delete_all_blueprint_tags(cursor, blueprint_id)
            except NotFound:
                pass
            rows = blueprint_sql.delete_blueprint(cursor, blueprint_id)
            if rows != 0:
                return make_response("", 204)
            else:
                abort(404)


def download_blueprint(blueprint_id):
    _validate_uuid(blueprint_id)

    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            bp = blueprint_sql.get_blueprint_by_id(cursor, blueprint_id)
            url = _get_signed_urls(bp)
            if url is None:
                abort(404)
            return redirect(url)


def _get_signed_urls(bp: dict):
    if current_app.config["CLOUDFLARE_ENDPOINT"] is None:
        return

    s3_client = boto3.client(
        "s3",
        endpoint_url=current_app.config["CLOUDFLARE_ENDPOINT"],
        aws_access_key_id=current_app.config["CLOUDFLARE_ACCESS_KEY_ID"],
        aws_secret_access_key=current_app.config["CLOUDFLARE_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
    )

    if bp["storage_address"] is None:
        return
    if bp["file_name"] is None:
        return
    parsed_url = urlparse(bp["storage_address"])
    key = parsed_url.path.lstrip("/")

    url = s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": "openforge-models",
            "Key": key,
            "ResponseContentDisposition": f'attachment; filename="{bp["file_name"]}"',
        },
        ExpiresIn=3600,  # 1 hour
    )
    return url


def get_blueprint_thumbnail_variants(blueprint_id):
    """Get thumbnail sprite sheet information for a blueprint.

    Returns sprite sheet URL, grid layout, angle metadata, and default angle.
    Handles models with legacy single thumbnails gracefully.
    """
    _validate_uuid(blueprint_id)

    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            thumbnail = _get_blueprint_thumbnail(cursor, blueprint_id)
            if not thumbnail:
                return jsonify({"error": "No thumbnail found for blueprint"}), 404

            # Check if this is a sprite sheet or legacy single thumbnail
            sprite_metadata = thumbnail.get("sprite_metadata")

            if sprite_metadata:
                # Return sprite sheet information
                return (
                    jsonify(
                        {
                            "type": "sprite",
                            "sprite_url": thumbnail["image_url"],
                            "grid_rows": sprite_metadata["grid_rows"],
                            "grid_cols": sprite_metadata["grid_cols"],
                            "tile_size": sprite_metadata["tile_size"],
                            "angles": sprite_metadata["angles"],
                            "default_angle": sprite_metadata.get("default_angle", 0),
                        }
                    ),
                    200,
                )
            else:
                # Return legacy single thumbnail information
                return (
                    jsonify(
                        {
                            "type": "single",
                            "thumbnail_url": thumbnail["image_url"],
                        }
                    ),
                    200,
                )


def set_blueprint_default_angle(blueprint_id):
    """Set the default camera angle for a blueprint's thumbnail sprite.

    Admin-only endpoint. Updates the default_angle in sprite_metadata.
    """
    _validate_uuid(blueprint_id)

    # Validate request body
    if not request.json or "default_angle" not in request.json:
        return jsonify({"error": "default_angle is required"}), 400

    default_angle = request.json["default_angle"]

    # Validate type
    if not isinstance(default_angle, int):
        return jsonify({"error": "default_angle must be an integer"}), 400

    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            thumbnail = _get_blueprint_thumbnail(cursor, blueprint_id)
            if not thumbnail:
                return jsonify({"error": "No thumbnail found for blueprint"}), 404

            # Check if this has sprite_metadata
            if not thumbnail.get("sprite_metadata"):
                return (
                    jsonify(
                        {
                            "error": (
                                "Blueprint uses legacy single thumbnail, "
                                "not a sprite sheet"
                            )
                        }
                    ),
                    400,
                )

            sprite_metadata = thumbnail["sprite_metadata"]

            # Validate angle index against actual sprite metadata
            max_angle = len(sprite_metadata.get("angles", [])) - 1
            if default_angle < 0 or default_angle > max_angle:
                return (
                    jsonify(
                        {
                            "error": (
                                f"default_angle must be between 0 and {max_angle} "
                                f"for this sprite"
                            )
                        }
                    ),
                    400,
                )

            # Update the default_angle in sprite_metadata
            sprite_metadata = sprite_metadata.copy()
            sprite_metadata["default_angle"] = default_angle

            # Update the image in database
            updated_image = image_sql.update_image(
                cursor, thumbnail["id"], {"sprite_metadata": sprite_metadata}
            )

            return (
                jsonify(
                    {
                        "message": "Default angle updated successfully",
                        "default_angle": default_angle,
                        "sprite_metadata": updated_image["sprite_metadata"],
                    }
                ),
                200,
            )
