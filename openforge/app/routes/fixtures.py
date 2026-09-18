"""Admin routes for fixture loading via API."""

import json
from functools import wraps
from typing import Any, Callable, Dict, List

from flask import current_app, g, jsonify, request
from psycopg.rows import dict_row
from yaml import YAMLError, safe_load

from openforge.db.fixtures import (
    is_blueprint_fixture,
    is_tag_description_fixture,
    is_tag_documentation_fixture,
    print_comparison_results,
)
from openforge.db.fixtures import (
    load_tag_description_fixture as _load_tag_description_data,
)
from openforge.db.fixtures import (
    load_tag_documentation_fixture as _load_tag_documentation_data,
)
from openforge.db.fixtures.incremental import IncrementalFixturesLoader
from openforge.db.fixtures.utils import write_output


class OutputLogger:
    """Simple output logger for capturing fixture loading output.

    This logger is set in Flask's g context and used by the write_output()
    helper function in openforge.db.fixtures.utils. This approach allows
    the same fixture loading code to work in both CLI mode (prints to stderr)
    and API mode (captures output for response).
    """

    def __init__(self):
        self.output: List[str] = []

    def write(self, message: str):
        """Capture a log message."""
        if message and message != "\n":
            self.output.append(message.rstrip())


def fixture_endpoint(f: Callable) -> Callable:
    """Decorator for fixture loading endpoints.

    Handles common setup (query params, output logger, data parsing) and
    error handling for all fixture loading endpoints.

    The decorated function receives: (data, dry_run, verbose) parameters.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Parse query parameters
            dry_run = request.args.get("dry_run", "false").lower() == "true"
            verbose = request.args.get("verbose", "false").lower() == "true"

            # Set up output logger
            g.output_logger = OutputLogger()

            # Parse fixture data
            data, error = _parse_fixture_data()
            if error:
                return error

            # Call the actual endpoint function with parsed data
            return f(data, dry_run, verbose, *args, **kwargs)

        except Exception as e:
            current_app.logger.exception(f"Unexpected error in {f.__name__}")
            output = g.output_logger.output if hasattr(g, "output_logger") else []
            return jsonify({"success": False, "error": str(e), "output": output}), 500

    return decorated_function


def _parse_fixture_data():
    """Parse fixture data from request body.

    Returns:
        Parsed data or error response tuple
    """
    raw_data = request.get_data(as_text=True)
    if not raw_data:
        return None, (
            jsonify({"success": False, "error": "No fixture data provided"}),
            400,
        )

    # Parse the data - try JSON first, then YAML
    try:
        content_type = request.content_type or ""
        if "yaml" in content_type or "yml" in content_type:
            data = safe_load(raw_data)
        else:
            # Default to JSON, with YAML fallback
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                data = safe_load(raw_data)
    except (json.JSONDecodeError, YAMLError) as e:
        return None, (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to parse fixture data: {str(e)}",
                    "output": g.output_logger.output
                    if hasattr(g, "output_logger")
                    else [],
                }
            ),
            400,
        )

    return data, None


def _process_fixture(data: Any, fixture_type: str, dry_run: bool, verbose: bool):
    """Common fixture processing logic.

    Args:
        data: Parsed fixture data
        fixture_type: Expected fixture type
        dry_run: If True, preview changes only
        verbose: If True, enable debug output

    Returns:
        JSON response tuple
    """
    if verbose:
        write_output(f"Processing fixture type: {fixture_type}\n")

    try:
        with current_app.db.connection() as conn:
            with conn.transaction():
                with conn.cursor(row_factory=dict_row) as curs:
                    if fixture_type == "blueprint":
                        result = _process_blueprint_fixture(
                            data, curs, dry_run, verbose
                        )
                    elif fixture_type == "tag_description":
                        result = _process_tag_description_fixture(
                            data, curs, dry_run, verbose
                        )
                    elif fixture_type == "tag_documentation":
                        result = _process_tag_documentation_fixture(
                            data, curs, dry_run, verbose
                        )
                    else:
                        raise ValueError(f"Unknown fixture type: {fixture_type}")

                    result["output"] = g.output_logger.output
                    result["success"] = True

                    return jsonify(result), 200

    except Exception as e:
        current_app.logger.exception("Error processing fixture")
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "output": g.output_logger.output,
                }
            ),
            500,
        )


@fixture_endpoint
def load_fixture(data, dry_run, verbose):
    """Load a fixture file via API upload with auto-detection."""
    fixture_type = _get_fixture_type_from_data(data)
    return _process_fixture(data, fixture_type, dry_run, verbose)


@fixture_endpoint
def load_blueprint_fixture(data, dry_run, verbose):
    """Load a blueprint fixture file via API upload."""
    # Validate it's a blueprint fixture
    try:
        is_blueprint_fixture(data)
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Invalid blueprint fixture: {str(e)}",
                    "output": g.output_logger.output,
                }
            ),
            400,
        )

    return _process_fixture(data, "blueprint", dry_run, verbose)


@fixture_endpoint
def load_tag_description_fixture(data, dry_run, verbose):
    """Load a tag description fixture file via API upload."""
    # Validate it's a tag description fixture
    try:
        is_tag_description_fixture(data)
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Invalid tag description fixture: {str(e)}",
                    "output": g.output_logger.output,
                }
            ),
            400,
        )

    return _process_fixture(data, "tag_description", dry_run, verbose)


@fixture_endpoint
def load_tag_documentation_fixture(data, dry_run, verbose):
    """Load a tag documentation fixture file via API upload."""
    # Validate it's a tag documentation fixture
    try:
        is_tag_documentation_fixture(data)
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Invalid tag documentation fixture: {str(e)}",
                    "output": g.output_logger.output,
                }
            ),
            400,
        )

    return _process_fixture(data, "tag_documentation", dry_run, verbose)


def _get_fixture_type_from_data(data: Any) -> str:
    """Determine fixture type from data structure.

    Args:
        data: Parsed fixture data

    Returns:
        'blueprint', 'tag_description', or 'tag_documentation'

    Raises:
        ValueError: If the fixture type cannot be determined.
    """
    if isinstance(data, list):
        # Blueprints are lists of blueprint objects.
        return "blueprint"

    if isinstance(data, dict):
        # Dictionaries can be tag_description or tag_documentation.
        # We can distinguish them by checking the type of their values.
        first_value = next(iter(data.values()), None)
        if isinstance(first_value, list):
            # Tag documentation values are lists of documents.
            return "tag_documentation"
        else:
            # Tag description values are strings. This also handles empty dicts.
            return "tag_description"

    raise ValueError(
        f"Cannot determine fixture type for data of type {type(data).__name__}"
    )


def _process_blueprint_fixture(
    data: List[Dict], curs, dry_run: bool, verbose: bool
) -> Dict:
    """Process a blueprint fixture.

    Args:
        data: List of blueprint fixture objects
        curs: Database cursor
        dry_run: If True, don't apply changes
        verbose: If True, output debug information

    Returns:
        Dictionary with comparison results
    """
    # Validate blueprint fixture
    is_blueprint_fixture(data)

    # Use incremental loader
    loader = IncrementalFixturesLoader(curs.connection, verbose=verbose)
    changes = loader.compare_fixture_data(data, curs=curs)

    if dry_run:
        write_output("DRY RUN: Changes would be:\n")
        print_comparison_results(changes)
    else:
        loader.apply_incremental_changes(changes, curs=curs)

    return {
        "added": [_format_item(item) for item in changes.added],
        "modified": [_format_item(item) for item in changes.modified],
        "deprecated": [_format_item(item) for item in changes.deprecated],
        "consolidated": [_format_item(item) for item in changes.consolidated],
        "errors": changes.errors,
    }


def _process_tag_description_fixture(
    data: Dict, curs, dry_run: bool, verbose: bool
) -> Dict:
    """Process a tag description fixture.

    Args:
        data: Dict of tag->description mappings
        curs: Database cursor
        dry_run: If True, don't apply changes
        verbose: If True, output debug information

    Returns:
        Dictionary with results
    """
    # Validate tag description fixture
    is_tag_description_fixture(data)

    if dry_run:
        write_output(f"DRY RUN: Would load {len(data)} tag descriptions\n")
    else:
        count = _load_tag_description_data(curs, data)
        write_output(f"Applied {count} tag descriptions\n")

    return {
        "added": [],
        "modified": [{"name": key} for key in data.keys()],
        "deprecated": [],
        "consolidated": [],
        "errors": [],
    }


def _process_tag_documentation_fixture(
    data: Dict, curs, dry_run: bool, verbose: bool
) -> Dict:
    """Process a tag documentation fixture.

    Args:
        data: Dict of tag->documentation entries mappings
        curs: Database cursor
        dry_run: If True, don't apply changes
        verbose: If True, output debug information

    Returns:
        Dictionary with results
    """
    # Validate tag documentation fixture
    is_tag_documentation_fixture(data)

    if dry_run:
        total_docs = sum(len(docs) for docs in data.values())
        write_output(f"DRY RUN: Would load {total_docs} tag documentation entries\n")
    else:
        count = _load_tag_documentation_data(curs, data)
        write_output(f"Applied {count} tag documentation entries\n")

    return {
        "added": [],
        "modified": [{"name": key} for key in data.keys()],
        "deprecated": [],
        "consolidated": [],
        "errors": [],
    }


def _format_item(item: Dict) -> Dict:
    """Format an item for API response.

    Args:
        item: Item from comparison results

    Returns:
        Formatted item with relevant fields
    """
    if "file_metadata" in item:
        return {
            "full_name": item["file_metadata"]["full_name"],
            "md5": item["file_metadata"]["md5"],
            "size": item["file_metadata"]["size"],
        }
    elif "full_name" in item:
        return {
            "full_name": item.get("full_name"),
            "md5": item.get("file_md5"),
            "size": item.get("file_size"),
        }
    else:
        return {"name": item.get("name", "unknown")}
