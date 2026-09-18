import uuid

from flask import current_app, jsonify, request
from psycopg.errors import InvalidTextRepresentation, OperationalError, ProgrammingError
from psycopg.rows import dict_row
from werkzeug.exceptions import NotFound

import openforge.db.sql.blueprint_documentation as blueprint_doc_sql
import openforge.db.sql.blueprints as blueprint_sql
import openforge.db.sql.tags as tag_sql
import openforge.db.sql.tags_documentation as tags_doc_sql
from openforge.app.utils.pagination import validate_pagination_params
from openforge.app.utils.sanitization import (
    sanitize_documentation_content,
    validate_documentation_content,
)


def _apply_document_type_rules(document_type: str, is_live: bool | None) -> bool | None:
    """Apply business rules based on document type.

    Args:
        document_type: The type of document ('changelog' or 'instructions')
        is_live: The requested live status (can be None for updates)

    Returns:
        The final is_live status after applying rules (None if input was None)
    """
    # Changelogs should always be live
    if document_type == "changelog":
        return True

    # For other document types, use the requested value (including None)
    return is_live


def _verify_documentation_ownership(cursor, doc_uuid, blueprint_id):
    """Verify that documentation belongs to the specified blueprint.

    Args:
        cursor: Database cursor
        doc_uuid: Documentation UUID
        blueprint_id: Blueprint ID string

    Returns:
        dict: Documentation data if ownership is verified

    Raises:
        NotFound: If documentation doesn't exist
        ValueError: If documentation doesn't belong to blueprint
    """
    existing_doc = blueprint_doc_sql.get_blueprint_documentation_by_id(cursor, doc_uuid)
    if str(existing_doc["blueprint_id"]) != blueprint_id:
        raise ValueError("Documentation not found for this blueprint")
    return existing_doc


def get_blueprint_documentation(blueprint_id):
    """Get all documentation for a blueprint."""
    try:
        blueprint_uuid = uuid.UUID(blueprint_id)
    except ValueError:
        return jsonify({"error": "Invalid blueprint ID"}), 400

    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            # First verify the blueprint exists
            try:
                blueprint_sql.get_blueprint_by_id(cursor, blueprint_uuid)
            except NotFound:
                return jsonify({"error": "Blueprint not found"}), 404

            # Then get the documentation (all docs for individual endpoint)
            data = blueprint_doc_sql.get_blueprint_documentation(
                cursor, blueprint_uuid, is_live=None
            )
            if not data:
                return jsonify({"documentation": []}), 404
            return jsonify({"documentation": data})


def get_blueprint_documentation_entry(blueprint_id, doc_id):
    """Get specific documentation entry."""
    try:
        uuid.UUID(blueprint_id)
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        return jsonify({"error": "Invalid ID"}), 400

    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            try:
                data = _verify_documentation_ownership(cursor, doc_uuid, blueprint_id)
                return jsonify({"documentation": data})
            except NotFound:
                return jsonify({"error": "Documentation not found"}), 404
            except ValueError as e:
                return jsonify({"error": str(e)}), 404


def create_blueprint_documentation(blueprint_id):
    """Create new documentation for a blueprint."""
    try:
        blueprint_uuid = uuid.UUID(blueprint_id)
    except ValueError:
        return jsonify({"error": "Invalid blueprint ID"}), 400

    if not request.json:
        return jsonify({"error": "Request body required"}), 400

    document = request.json.get("document")
    document_type = request.json.get("document_type", "changelog")
    is_live = request.json.get("is_live", True)

    if not document or not document.strip():
        return jsonify({"error": "Document content required"}), 400

    if document_type not in ["changelog", "instructions"]:
        return jsonify({"error": "Invalid document type"}), 400

    # Apply document type rules
    is_live = _apply_document_type_rules(document_type, is_live)

    # Validate and sanitize the document content
    try:
        validate_documentation_content(document)
        sanitized_document = sanitize_documentation_content(
            document, allow_markdown=True
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            try:
                data = blueprint_doc_sql.create_blueprint_documentation(
                    cursor, blueprint_uuid, sanitized_document, document_type, is_live
                )

                return jsonify({"documentation": data}), 201
            except Exception as e:
                current_app.logger.error(f"Error creating blueprint documentation: {e}")
                return jsonify({"error": "An internal error occurred"}), 500


def update_blueprint_documentation(blueprint_id, doc_id):
    """Update specific documentation entry."""
    try:
        uuid.UUID(blueprint_id)
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        return jsonify({"error": "Invalid ID"}), 400

    if not request.json:
        return jsonify({"error": "Request body required"}), 400

    document = request.json.get("document")
    document_type = request.json.get("document_type")
    is_live = request.json.get("is_live")

    if not document or not document.strip():
        return jsonify({"error": "Document content required"}), 400

    if document_type and document_type not in ["changelog", "instructions"]:
        return jsonify({"error": "Invalid document type"}), 400

    # Validate and sanitize the document content
    try:
        validate_documentation_content(document)
        sanitized_document = sanitize_documentation_content(
            document, allow_markdown=True
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            try:
                # First verify the documentation belongs to the specified blueprint
                # and get existing doc
                existing_doc = _verify_documentation_ownership(
                    cursor, doc_uuid, blueprint_id
                )

                # Determine the final document_type (from request or existing doc)
                final_document_type = document_type or existing_doc["document_type"]

                # Apply document type rules using the final document_type
                is_live = _apply_document_type_rules(final_document_type, is_live)

                data = blueprint_doc_sql.update_blueprint_documentation(
                    cursor, doc_uuid, sanitized_document, final_document_type, is_live
                )

                return jsonify({"documentation": data})
            except NotFound:
                return jsonify({"error": "Documentation not found"}), 404
            except ValueError as e:
                return jsonify({"error": str(e)}), 404
            except Exception as e:
                current_app.logger.error(f"Error updating blueprint documentation: {e}")
                return jsonify({"error": "An internal error occurred"}), 500


def delete_blueprint_documentation(blueprint_id, doc_id):
    """Delete specific documentation entry."""
    try:
        uuid.UUID(blueprint_id)
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        return jsonify({"error": "Invalid ID"}), 400

    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            try:
                # First verify the documentation belongs to the specified blueprint
                _verify_documentation_ownership(cursor, doc_uuid, blueprint_id)

                blueprint_doc_sql.delete_blueprint_documentation(cursor, doc_uuid)
                return "", 204
            except NotFound:
                return jsonify({"error": "Documentation not found"}), 404
            except ValueError as e:
                return jsonify({"error": str(e)}), 404
            except Exception as e:
                current_app.logger.error(f"Error deleting blueprint documentation: {e}")
                return jsonify({"error": "An internal error occurred"}), 500


def get_blueprint_changelog_history(blueprint_id):
    """Get changelog history for blueprint."""
    try:
        blueprint_uuid = uuid.UUID(blueprint_id)
    except ValueError:
        return jsonify({"error": "Invalid blueprint ID"}), 400

    limit = request.args.get("limit", 10, type=int)
    offset = request.args.get("offset", 0, type=int)

    try:
        limit, offset = validate_pagination_params(limit, offset)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            try:
                data = blueprint_doc_sql.get_blueprint_changelog_history(
                    cursor, blueprint_uuid, limit, offset
                )
                return jsonify(data)
            except Exception as e:
                current_app.logger.error(f"Error getting changelog history: {e}")
                return jsonify({"error": "An internal error occurred"}), 500


def get_blueprint_all_documentation(blueprint_id):
    """Get all documentation for a blueprint.

    Includes blueprint docs, changelog history, and tag docs.
    """
    try:
        blueprint_uuid = uuid.UUID(blueprint_id)
    except ValueError:
        return jsonify({"error": "Invalid blueprint ID"}), 400

    changelog_limit = request.args.get("changelog_limit", 10, type=int)
    changelog_offset = request.args.get("changelog_offset", 0, type=int)

    try:
        changelog_limit, changelog_offset = validate_pagination_params(
            changelog_limit, changelog_offset
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            try:
                # 1. Get blueprint information
                blueprint_data = blueprint_sql.get_blueprint_by_id(
                    cursor, blueprint_uuid
                )

                # 2. Get blueprint documentation (live only for public endpoint)
                blueprint_docs = blueprint_doc_sql.get_blueprint_documentation(
                    cursor, blueprint_uuid, is_live=True
                )

                # 3. Get changelog history
                changelog_data = blueprint_doc_sql.get_blueprint_changelog_history(
                    cursor, blueprint_uuid, changelog_limit, changelog_offset
                )

                # 4. Get blueprint tags
                tag_sql.get_tags(cursor, blueprint_uuid)

                # 5. Get documentation for all tags in a single query
                # (live only for public endpoint)
                try:
                    tag_documentation = (
                        tags_doc_sql.get_tag_documentation_for_blueprint(
                            cursor, blueprint_uuid, is_live=True
                        )
                    )
                except (
                    OperationalError,
                    ProgrammingError,
                    InvalidTextRepresentation,
                ) as e:
                    # If tag documentation fails due to database issues,
                    # continue with empty results
                    current_app.logger.warning(
                        f"Database error getting documentation for blueprint tags: {e}"
                    )
                    tag_documentation = {}

                # Combine all data
                result = {
                    "blueprint_id": str(blueprint_uuid),
                    "blueprint_name": blueprint_data["blueprint_name"],
                    "blueprint_documentation": blueprint_docs,
                    "changelog_history": changelog_data,
                    "tag_documentation": tag_documentation,
                }

                return jsonify(result)

            except NotFound:
                return jsonify({"error": "Blueprint not found"}), 404
            except Exception as e:
                current_app.logger.error(
                    f"Error getting all documentation for blueprint {blueprint_id}: {e}"
                )
                return jsonify({"error": "An internal error occurred"}), 500
