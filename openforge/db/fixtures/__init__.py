import json
from importlib import resources as impresources
from pathlib import Path

from psycopg import connection, cursor
from psycopg.rows import dict_row
from yaml import safe_load

import openforge.db.sql.blueprints as blueprint_sql
import openforge.db.sql.images as image_sql
import openforge.db.sql.tag_descriptions as tag_description_sql
import openforge.db.sql.tags as tag_sql
import openforge.db.sql.tags_documentation as tag_documentation_sql
from openforge.db.sql.tag_utils import array_to_tag, process_tag, tag_to_array
from openforge.openapi import validate_schema


def find_fixtures(dir: str):
    if dir:
        return find_fixtures_directory(dir)
    else:
        return find_fixtures_package()


def _collect_fixtures_from_subdir(base_path, subdir_name, file_list):
    """Helper function to collect fixture files from a subdirectory.

    Args:
        base_path: Base path containing the subdirectory
        subdir_name: Name of the subdirectory to search
        file_list: List to append found files to
    """
    subdir = base_path / subdir_name
    if subdir.exists():
        for f in subdir.iterdir():
            if str(f).endswith(".json") or str(f).endswith(".yaml"):
                file_list.append(f)


def find_fixtures_package():
    import openforge.db.fixtures as fixtures

    ffiles = []
    fixtures_path = impresources.files(fixtures)

    # Load fixtures from subdirectories
    _collect_fixtures_from_subdir(fixtures_path, "blueprints", ffiles)
    _collect_fixtures_from_subdir(fixtures_path, "tag_descriptions", ffiles)
    _collect_fixtures_from_subdir(fixtures_path, "tag_documentation", ffiles)

    return ffiles


def find_fixtures_directory(dir: str):
    ffiles = []
    dir_path = Path(dir)

    # Load fixtures from subdirectories
    _collect_fixtures_from_subdir(dir_path, "blueprints", ffiles)
    _collect_fixtures_from_subdir(dir_path, "tag_descriptions", ffiles)
    _collect_fixtures_from_subdir(dir_path, "tag_documentation", ffiles)

    return ffiles


def clear_db(curs: cursor):
    tag_sql.delete_all_tags(curs)
    blueprint_sql.delete_all_blueprints(curs)
    image_sql.delete_all_images(curs)
    tag_description_sql.delete_all_tag_descriptions(curs)


def is_blueprint_fixture(data):
    """Validate data against the blueprint fixture schema."""
    validate_schema("blueprint.fixture.json", data)


def is_tag_description_fixture(data):
    """Validate data against the tag description fixture schema."""
    validate_schema("tag_description.fixture.json", data)


def is_tag_documentation_fixture(data):
    """Validate data against the tag documentation fixture schema."""
    # Tag documentation uses the same structure as tag descriptions
    # but with additional fields for document content
    if not isinstance(data, dict):
        raise ValueError("Tag documentation fixture must be a dictionary")
    return True


def _get_fixture_type(file_path):
    """Determine fixture type based on file path.

    Args:
        file_path: Path to the fixture file

    Returns:
        str: 'blueprint', 'tag_description', or 'tag_documentation'
    """
    file_path_str = str(file_path)
    if "tag_documentation" in file_path_str:
        return "tag_documentation"
    elif "tag_descriptions" in file_path_str:
        return "tag_description"
    elif "blueprints" in file_path_str:
        return "blueprint"
    else:
        # Fallback: assume blueprint for backward compatibility
        return "blueprint"


def load_fixtures(
    conn: connection,
    alt: str,
    files: list = None,
    incremental: bool = True,
    dry_run: bool = False,
    verbose: bool = False,
):
    ffiles = files if files is not None else find_fixtures(alt)

    if incremental:
        # Import here to avoid circular imports
        from .incremental import IncrementalFixturesLoader

        loader = IncrementalFixturesLoader(conn, verbose=verbose)
        for f in ffiles:
            data = _load_data(f, verbose=verbose)
            fixture_type = _get_fixture_type(f)

            if fixture_type == "blueprint":
                # Validate blueprint fixture
                try:
                    is_blueprint_fixture(data)
                    # Use transaction to ensure all-or-nothing behavior
                    with conn.transaction():
                        with conn.cursor(row_factory=dict_row) as curs:
                            changes = loader.compare_fixture_data(data, curs=curs)
                            if dry_run:
                                print_comparison_results(changes)
                            else:
                                loader.apply_incremental_changes(
                                    changes, curs=curs, filename=f.name
                                )
                except Exception as e:
                    raise e
            elif fixture_type == "tag_description":
                # Validate tag description fixture
                try:
                    is_tag_description_fixture(data)
                    # Handle tag descriptions in incremental mode
                    with conn.transaction():
                        with conn.cursor(row_factory=dict_row) as curs:
                            if dry_run:
                                write_output(
                                    f"DRY RUN: Would load tag description "
                                    f"fixture: {f}\n"
                                )
                            else:
                                count = load_tag_description_fixture(curs, data)
                                write_output(
                                    f"{f.name}: Applied {count} tag descriptions\n"
                                )
                                if verbose:
                                    write_output(
                                        f"Loaded tag description fixture: {f}\n"
                                    )
                except Exception as e:
                    raise e
            elif fixture_type == "tag_documentation":
                # Validate tag documentation fixture
                try:
                    is_tag_documentation_fixture(data)
                    # Handle tag documentation in incremental mode
                    with conn.transaction():
                        with conn.cursor(row_factory=dict_row) as curs:
                            if dry_run:
                                write_output(
                                    f"DRY RUN: Would load tag documentation "
                                    f"fixture: {f}\n"
                                )
                            else:
                                count = load_tag_documentation_fixture(curs, data)
                                msg = (
                                    f"{f.name}: Applied {count} tag documentation "
                                    f"entries\n"
                                )
                                write_output(msg)
                                if verbose:
                                    write_output(
                                        f"Loaded tag documentation fixture: {f}\n"
                                    )
                except Exception as e:
                    raise e
            else:
                raise ValueError(f"Unknown fixture type for file: {f}")
    else:
        # Existing full replacement logic
        with conn.cursor(row_factory=dict_row) as curs:
            # Use transaction to ensure all-or-nothing behavior
            with conn.transaction():
                clear_db(curs)
                for f in ffiles:
                    data = _load_data(f, verbose=verbose)
                    fixture_type = _get_fixture_type(f)

                    if fixture_type == "blueprint":
                        # Validate blueprint fixture
                        try:
                            is_blueprint_fixture(data)
                            for rec in data:
                                load_blueprint_fixture(curs, rec)
                        except Exception as e:
                            raise e
                    elif fixture_type == "tag_description":
                        # Validate tag description fixture
                        try:
                            is_tag_description_fixture(data)
                            count = load_tag_description_fixture(curs, data)
                            write_output(
                                f"{f.name}: Applied {count} tag descriptions\n"
                            )
                        except Exception as e:
                            raise e
                    elif fixture_type == "tag_documentation":
                        # Validate tag documentation fixture
                        try:
                            is_tag_documentation_fixture(data)
                            count = load_tag_documentation_fixture(curs, data)
                            write_output(
                                f"{f.name}: Applied {count} tag documentation entries\n"
                            )
                        except Exception as e:
                            raise e
                    else:
                        raise ValueError(f"Unknown fixture type for file: {f}")


def _load_data(f, verbose=False):
    if verbose:
        write_output(f"Loading {f}\n")
    with open(f, "r") as fh:
        if str(f).endswith(".json"):
            return json.load(fh)
        elif str(f).endswith(".yaml"):
            return safe_load(fh)
        raise ValueError(f"Unsupported file type: {f}")


from .utils import get_words, munge_blueprint, write_output  # noqa: E402


def _munge_blueprint(data: dict):
    return munge_blueprint(data)


def _get_words(data: dict):
    return get_words(data)


def load_blueprint_fixture(curs: cursor, data: dict):
    try:
        bp_data = _munge_blueprint(data)
        bp = blueprint_sql.insert_blueprint(
            curs, bp_data, rescue_md5_conflict=True, words=_get_words(data)
        )
        if bp is None:
            return  # Skip this record if it's a duplicate
        for tag in data["tags"]:

            def insert_tag_to_db(tag_array):
                tag_sql.insert_tag(curs, bp["id"], array_to_tag(tag_array))

            process_tag(tag, insert_tag_to_db)
        for image in data.get("images", []):
            image_sql.insert_image_for_blueprint(curs, bp["id"], _munge_image(image))
    except Exception:
        from pprint import pprint

        print("\nFailed record:")
        pprint(data)
        raise


def load_tag_description_fixture(curs: cursor, data: dict):
    count = 0
    for tag, description in data.items():
        tag_arr = tag_to_array(tag)
        tag_description_sql.upsert_tag_description(curs, tag_arr, description)
        count += 1
    return count


def load_tag_documentation_fixture(curs: cursor, data: dict):
    """Load tag documentation from fixture data.

    Args:
        curs: Database cursor
        data: Dict mapping tag strings to lists of documentation entries

    Returns:
        int: Number of documentation entries loaded
    """
    count = 0
    for tag, documents in data.items():
        tag_arr = tag_to_array(tag)

        # Each tag can have multiple documentation entries
        for doc in documents:
            # Create documentation entry
            tag_documentation_sql.create_tag_documentation(
                curs,
                tag_arr,
                doc["document"],
                doc.get("document_type", "instructions"),
                doc.get("is_live", True),
            )
            count += 1

    return count


def _munge_image(image: dict):
    # placeholder for additional work if needed
    return image


def print_comparison_results(changes):
    """Print comparison results in a user-friendly format."""
    print("\nComparison Results:")
    print(f"  Added: {len(changes.added)}")
    print(f"  Modified: {len(changes.modified)}")
    print(f"  Deprecated: {len(changes.deprecated)}")
    print(f"  Consolidated: {len(changes.consolidated)}")
    print(f"  Errors: {len(changes.errors)}")

    if changes.added:
        print("\nAdded blueprints:")
        for item in changes.added:
            if "file_metadata" in item:
                name = item.get("file_metadata", {}).get("full_name", "unknown")
            else:
                name = item.get("name", "unknown")
            print(f"  - {name}")

    if changes.modified:
        print("\nModified blueprints:")
        for item in changes.modified:
            if "file_metadata" in item:
                name = item.get("file_metadata", {}).get("full_name", "unknown")
            else:
                name = item.get("name", "unknown")
            print(f"  - {name}")

    if changes.deprecated:
        print("\nDeprecated blueprints:")
        for item in changes.deprecated:
            name = item.get("full_name", "unknown")
            print(f"  - {name}")

    if changes.errors:
        print("\nErrors:")
        for error in changes.errors:
            print(f"  - {error}")
