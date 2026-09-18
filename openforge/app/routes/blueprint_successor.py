import logging
import uuid

from flask import current_app, jsonify
from psycopg.rows import dict_row
from werkzeug.exceptions import NotFound

import openforge.db.sql.blueprint_documentation as blueprint_doc_sql
import openforge.db.sql.blueprints as blueprint_sql

logger = logging.getLogger(__name__)


def disconnect_successor(blueprint_id: str):
    """Disconnect a successor relationship and mark associated changelogs as non-live.

    This endpoint:
    1. Sets the successor_id to null on the deprecated blueprint
    2. Updates any changelog documentation on the successor to is_live=false
    """
    try:
        blueprint_uuid = uuid.UUID(blueprint_id)
    except ValueError:
        return jsonify({"error": "Invalid blueprint ID format"}), 400

    with current_app.db.connection() as conn:
        with conn.transaction():
            with conn.cursor(row_factory=dict_row) as cursor:
                # First, get the blueprint to find its successor
                try:
                    blueprint = blueprint_sql.get_blueprint_by_id(
                        cursor, blueprint_uuid
                    )
                except NotFound:
                    return jsonify({"error": "Blueprint not found"}), 404

                if not blueprint.get("successor_id"):
                    return jsonify({"error": "Blueprint has no successor"}), 400

                successor_id = blueprint["successor_id"]

                # Set any changelog documentation on the successor to is_live=false
                try:
                    rowcount = blueprint_doc_sql.set_changelogs_non_live(
                        cursor, successor_id
                    )
                    if rowcount > 0:
                        logger.info(
                            f"Set {rowcount} changelog(s) to is_live=false "
                            f"for successor {successor_id}"
                        )
                except Exception as e:
                    logger.error(
                        f"Unexpected error updating changelog: {e}", exc_info=True
                    )
                    # Continue even if changelog update fails

                # Remove the successor relationship
                updated_blueprint = blueprint_sql.update_blueprint(
                    cursor, blueprint_uuid, {"successor_id": None}
                )

                return jsonify({"success": True, "blueprint": updated_blueprint})
