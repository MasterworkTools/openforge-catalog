"""Shared utilities for fixture processing."""

import sys

from openforge.db.sql.tag_utils import tag_to_array


def write_output(message: str):
    """Write output message - uses Flask g.output_logger if available, otherwise stderr.

    This allows the same code to work in both CLI mode (prints to stderr in real-time)
    and API mode (captures output for response).

    Args:
        message: Message to write
    """
    try:
        from flask import g, has_request_context

        if has_request_context() and hasattr(g, "output_logger"):
            g.output_logger.write(message)
        else:
            sys.stderr.write(message)
    except (ImportError, RuntimeError):
        # Flask not available or no application context - use stderr
        sys.stderr.write(message)


def munge_blueprint(data: dict) -> dict:
    """Convert fixture format to database format.

    This function converts blueprint fixture data from the fixture format
    to the database format used by the blueprint_sql module.

    Args:
        data: Blueprint fixture data in fixture format

    Returns:
        Dictionary in database format
    """
    bp = {}
    bp["blueprint_type"] = data["type"]
    bp["blueprint_name"] = data.get("name")
    bp["blueprint_config"] = data.get("config", {})

    # Phase 1 fields
    bp["deprecated"] = data.get("deprecated", False)
    bp["successor_id"] = data.get("successor_id")
    bp["consolidated_paths"] = data.get("consolidated_paths", [])

    if "file_metadata" in data:
        if not bp["blueprint_name"]:
            bp["blueprint_name"] = data["file_metadata"]["file"]
        bp["file_md5"] = data["file_metadata"]["md5"]
        bp["file_size"] = data["file_metadata"]["size"]
        bp["file_name"] = data["file_metadata"]["file"]
        bp["full_name"] = data["file_metadata"]["full_name"]
        bp["file_modified_at"] = data["file_metadata"]["file_modified_at"]
        bp["storage_address"] = data["file_metadata"].get("storage_address")
    return bp


def get_words(data: dict) -> list[str]:
    """Extract search words from blueprint data.

    Args:
        data: Blueprint fixture data

    Returns:
        List of search words extracted from tags
    """
    words = set()
    for t in data.get("tags", []):
        # Convert tag to array (handles both pipe-delimited strings and arrays)
        tag_array = tag_to_array(t)
        words.update(str(w) for w in tag_array)
    return list(words)
