"""
Incremental fixtures loading for OpenForge database.

This module provides functionality for incremental loading of fixture data,
comparing with existing database records and only updating what has changed.
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from psycopg import connection, cursor
from psycopg.rows import dict_row

import openforge.db.sql.blueprints as blueprint_sql
import openforge.db.sql.images as image_sql
import openforge.db.sql.tags as tag_sql
from openforge.data.transformers import DeprecatedEntryTransformer
from openforge.db.sql.tag_utils import array_to_tag, process_tag

from .utils import get_words, munge_blueprint, write_output


def _parse_timestamp(timestamp) -> Optional[datetime]:
    """Parse timestamp into datetime object, handling various formats.

    Args:
        timestamp: Timestamp as string, datetime object, or other format

    Returns:
        datetime object if parsing successful, None otherwise
    """
    if timestamp is None:
        return None

    # If already a datetime object, return it
    if isinstance(timestamp, datetime):
        return timestamp

    # Convert to string for parsing
    timestamp_str = str(timestamp)

    try:
        # Try parsing as ISO format first (handles timezone info)
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        # Normalize to UTC if timezone info is present
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        try:
            # Try parsing with space separator (common format without timezone)
            dt = datetime.fromisoformat(timestamp_str.replace(" ", "T"))
            return dt
        except ValueError:
            # If all parsing fails, return None
            return None


def _dropped_successor(bp: Dict) -> str:
    """The successor a revival discards, named so the link leaves a record."""
    successor = bp.get("successor_id")
    return f" (dropped successor {successor})" if successor else ""


class ComparisonResult:
    """Result of comparing fixture data with existing database records."""

    def __init__(self):
        self.added = []  # New blueprints
        self.modified = []  # Updated blueprints
        self.deprecated = []  # Deprecated blueprints
        self.consolidated = []  # Path consolidation updates
        # Candidates the apply step declined to tombstone, which is what makes
        # `applied_deprecations` reconcilable against `deprecated`. None until
        # it runs, for the same reason the count is.
        self.declined_deprecations = None
        self.errors = []  # Processing errors
        self.version_changes = {}  # Map of deprecated blueprint ID to new fixture item
        # How many of `deprecated` the apply step tombstoned. None until it runs.
        self.applied_deprecations = None

    def has_changes(self) -> bool:
        """Check if there are any changes to apply."""
        return bool(self.added or self.modified or self.deprecated or self.consolidated)

    def _deprecated_part(self) -> str:
        """The deprecated figure, as what was applied once an apply has run.

        The apply step declines to tombstone a row it renamed in place, so the
        proposal is right only for a dry run.
        """
        if self.applied_deprecations is None:
            return f"{len(self.deprecated)} deprecated"

        part = f"{self.applied_deprecations} deprecated"
        if self.applied_deprecations < len(self.deprecated):
            left = len(self.deprecated) - self.applied_deprecations
            part += f" ({left} left in place)"
        return part

    def summary(self) -> str:
        """Get a summary of changes."""
        parts = []
        if self.added:
            parts.append(f"{len(self.added)} added")
        if self.modified:
            parts.append(f"{len(self.modified)} modified")
        if self.deprecated:
            parts.append(self._deprecated_part())
        if self.consolidated:
            parts.append(f"{len(self.consolidated)} consolidated")
        if self.errors:
            parts.append(f"{len(self.errors)} errors")

        return ", ".join(parts) if parts else "no changes"


class IncrementalFixturesLoader:
    """Handles incremental loading of fixture data."""

    def __init__(self, conn: connection, verbose: bool = False):
        """Initialize incremental fixtures loader.

        Args:
            conn: Database connection
            verbose: Whether to output debug messages
        """
        self.conn = conn
        self.verbose = verbose
        self.transformer = DeprecatedEntryTransformer()
        self.fixture_subset_path = None  # Will be set when processing fixture data
        self.fixture_namespace = None  # Set alongside it, from the same paths
        self.current_fixture_files = (
            set()
        )  # Will be populated when processing fixture data
        self.current_fixture_md5s = {}  # The same paths, with their content
        # Blueprint IDs that were renamed in this load — used to skip the
        # subsequent deprecation step so a renamed row isn't tombstoned and
        # stripped of tags/images. Per-apply state: populated in
        # `_handle_addition`'s rename branch and reset at the top of
        # `_apply_changes_with_cursor` so it doesn't leak between fixtures
        # when one loader instance processes a directory.
        self._renamed_blueprint_ids = set()
        # Rows this load proposes to deprecate, so a duplicate can tell an
        # inheritance from a theft. Populated before additions are applied.
        self._deprecation_candidates = set()

    def _load_existing_blueprints(self, curs: cursor = None) -> Dict[str, Dict]:
        """Load existing blueprints from database for comparison.

        Args:
            curs: Optional cursor to use (for transaction context)

        Returns:
            Dictionary mapping full_name to blueprint data with tags and images loaded
        """
        # Use provided cursor or create new one
        if curs is not None:
            blueprints = blueprint_sql.get_non_deprecated_blueprints(curs)
        else:
            with self.conn.cursor(row_factory=dict_row) as curs:
                blueprints = blueprint_sql.get_non_deprecated_blueprints(curs)

        # Get all blueprint IDs for batch loading
        blueprint_ids = [bp["id"] for bp in blueprints]

        # Batch load all tags and images
        with self.conn.cursor(row_factory=dict_row) as curs:
            all_tags = tag_sql.get_tags_for_blueprints(curs, blueprint_ids)
            all_images = image_sql.get_images_for_blueprints(curs, blueprint_ids)

        # Group tags by blueprint_id
        tags_by_blueprint = {}
        for tag in all_tags:
            bp_id = tag["blueprint_id"]
            if bp_id not in tags_by_blueprint:
                tags_by_blueprint[bp_id] = []
            tags_by_blueprint[bp_id].append(tag["tag"])

        # Group images by blueprint_id
        images_by_blueprint = {}
        for image in all_images:
            bp_id = image["blueprint_id"]
            if bp_id not in images_by_blueprint:
                images_by_blueprint[bp_id] = []
            # Remove blueprint_id from image dict to match expected format
            image_copy = {k: v for k, v in image.items() if k != "blueprint_id"}
            images_by_blueprint[bp_id].append(image_copy)

        # Create final mapping
        blueprint_map = {}
        for bp in blueprints:
            full_name = bp.get("full_name")
            if full_name:
                # File-based blueprint - use full_name as key
                bp["tags"] = tags_by_blueprint.get(bp["id"], [])
                bp["images"] = images_by_blueprint.get(bp["id"], [])
                blueprint_map[full_name] = bp
            elif bp.get("blueprint_type") == "blueprint":
                # Configuration blueprint - use blueprint_name as key
                blueprint_name = bp.get("blueprint_name")
                if blueprint_name:
                    bp["tags"] = tags_by_blueprint.get(bp["id"], [])
                    bp["images"] = images_by_blueprint.get(bp["id"], [])
                    blueprint_map[blueprint_name] = bp

        if self.verbose:
            msg = (
                f"Loaded {len(blueprint_map)} existing blueprints "
                f"with tags and images\n"
            )
            write_output(msg)

        return blueprint_map

    def _find_deprecated_blueprint(self, full_name: str) -> Optional[Dict]:
        """Find a deprecated blueprint by full_name.

        Args:
            full_name: Full name of the blueprint to find

        Returns:
            Deprecated blueprint data if found, None otherwise
        """
        with self.conn.cursor(row_factory=dict_row) as curs:
            query = """
                SELECT id, blueprint_name, blueprint_type, config, file_md5, file_size,
                       file_name, full_name, file_modified_at, storage_address,
                       consolidated_paths, deprecated, successor_id,
                       created_at, updated_at
                FROM blueprints
                WHERE full_name = %s AND deprecated = true
                ORDER BY created_at DESC
                LIMIT 1
            """
            curs.execute(query, (full_name,))
            result = curs.fetchone()

            if result:
                # Load tags and images for the deprecated blueprint
                blueprint_id = result["id"]

                # Get tags
                tags = tag_sql.get_tags(curs, blueprint_id)
                result["tags"] = [tag["tag"] for tag in tags]

                # Get images
                images = image_sql.get_images_for_blueprint(curs, blueprint_id)
                result["images"] = list(images)

                return result

            return None

    def _detect_fixture_subset_path(self, fixture_data: List[Dict]) -> str:
        """Detect the common subset path from fixture data.

        Args:
            fixture_data: List of blueprint fixture objects

        Returns:
            Common path prefix for all files in the fixture
        """
        if not fixture_data:
            return ""

        # Get all full_name values from file-based blueprints
        full_names = []
        for item in fixture_data:
            if "file_metadata" in item and not item.get("deprecated", False):
                full_names.append(item["file_metadata"]["full_name"])

        if not full_names:
            return ""

        # Find common prefix
        paths = [name.split("/") for name in full_names]
        if not paths:
            return ""

        min_len = min(len(path) for path in paths)

        common_parts = []
        for i in range(min_len):
            if all(path[i] == paths[0][i] for path in paths):
                common_parts.append(paths[0][i])
            else:
                break

        # For single files, return the directory path (exclude the filename)
        if len(full_names) == 1:
            path_parts = full_names[0].split("/")
            if len(path_parts) > 1:
                return "/".join(path_parts[:-1])
            else:
                return ""

        return "/".join(common_parts)

    def _get_fixture_namespace(self, fixture_data: List[Dict]) -> Optional[str]:
        """Determine the namespace/category of this fixture based on file paths.

        Args:
            fixture_data: List of blueprint fixture objects

        Returns:
            Namespace string (e.g., 'dungeon_stone', 'cave') or None
        """
        # Look for common patterns in full_name paths
        namespaces = set()
        for item in fixture_data:
            if "file_metadata" in item and not item.get("deprecated", False):
                full_name = item["file_metadata"]["full_name"]
                # Extract namespace from path
                # (e.g., "tiles/dungeon_stone/..." -> "dungeon_stone")
                parts = full_name.split("/")
                if len(parts) >= 2 and parts[0] == "tiles":
                    namespaces.add(parts[1])

        # If we have a consistent namespace, return it
        if len(namespaces) == 1:
            return namespaces.pop()
        return None

    def _in_deprecation_sweep(self, full_name: str) -> bool:
        """Whether this load's missing-file sweep can deprecate that row.

        With a namespace the sweep reaches only rows beneath it, and the
        trailing slash matters: `cave` must not claim `cavern`. Without one the
        sweep falls back to deprecating anything absent from the fixture, so
        every row is in reach.
        """
        if not self.fixture_namespace:
            return True
        return full_name.startswith(f"tiles/{self.fixture_namespace}/")

    def _find_missing_blueprints(
        self,
        fixture_data: List[Dict],
        existing_blueprints: Dict[str, Dict],
    ) -> List[Dict]:
        """Find blueprints that exist in the database but are missing from fixture.

        Args:
            fixture_data: List of blueprint fixture objects
            existing_blueprints: Dict of existing blueprints from database

        Returns:
            List of existing blueprints that should be marked as deprecated
        """
        # Get all full_names from the fixture
        fixture_full_names = set()
        for item in fixture_data:
            if "file_metadata" in item and not item.get("deprecated", False):
                fixture_full_names.add(item["file_metadata"]["full_name"])

        # Find existing blueprints that match this fixture's namespace
        # but aren't in the fixture
        missing = []
        for full_name, bp in existing_blueprints.items():
            if self._in_deprecation_sweep(full_name):
                if full_name not in fixture_full_names:
                    missing.append(bp)

        return missing

    def compare_fixture_data(
        self,
        fixture_data: List[Dict],
        curs: cursor = None,
        skip_load_existing: bool = False,
    ) -> ComparisonResult:
        """Compare fixture data with existing database records.

        Args:
            fixture_data: List of blueprint fixture objects
            curs: Optional cursor to use (for transaction context)
            skip_load_existing: If True, skip loading existing blueprints (for testing)

        Returns:
            ComparisonResult with changes detected
        """
        # Detect and store the fixture's subset path
        self.fixture_subset_path = self._detect_fixture_subset_path(fixture_data)
        if self.verbose:
            write_output(
                f"DEBUG: Detected fixture subset path: '{self.fixture_subset_path}'\n"
            )

        # Build a set of all current filenames in the fixture
        self.current_fixture_files = set()
        self.current_fixture_md5s = {}
        for item in fixture_data:
            if "file_metadata" in item and not item.get("deprecated", False):
                self.current_fixture_files.add(item["file_metadata"]["full_name"])
                self.current_fixture_md5s[item["file_metadata"]["full_name"]] = item[
                    "file_metadata"
                ]["md5"]

        # Load existing blueprints within transaction context
        # (unless skipped for testing)
        if skip_load_existing:
            # Use existing blueprints that were set up for testing
            existing_blueprints = self.existing_blueprints
        elif curs is not None:
            existing_blueprints = self._load_existing_blueprints(curs)
        else:
            # Fallback for standalone usage
            existing_blueprints = self._load_existing_blueprints()

        result = ComparisonResult()

        # Determine the namespace of this fixture
        fixture_namespace = self._get_fixture_namespace(fixture_data)
        self.fixture_namespace = fixture_namespace

        for fixture_item in fixture_data:
            self._compare_single_item(fixture_item, result, existing_blueprints)

        # Build a set of fixture blueprint keys for comparison
        fixture_keys = set()
        for item in fixture_data:
            if "file_metadata" in item and not item.get("deprecated", False):
                fixture_keys.add(item["file_metadata"]["full_name"])
            elif not item.get("deprecated", False):
                # Configuration blueprint
                blueprint_name = item.get("name")
                if blueprint_name:
                    fixture_keys.add(blueprint_name)

        # Check if this fixture contains any file-based blueprints
        has_file_blueprints = any(
            "file_metadata" in item and not item.get("deprecated", False)
            for item in fixture_data
        )

        # Only perform deprecation logic if the fixture contains file-based blueprints
        if has_file_blueprints:
            # Find deprecated blueprints (only for specific namespace if detected)
            if fixture_namespace:
                # Find blueprints that exist in DB for this namespace
                # but are missing from fixture
                missing_blueprints = self._find_missing_blueprints(
                    fixture_data, existing_blueprints
                )
                for missing_bp in missing_blueprints:
                    if not missing_bp.get("deprecated"):
                        result.deprecated.append(missing_bp)
            else:
                # Legacy behavior: deprecate any non-deprecated blueprint not in fixture
                # But only if this fixture actually contains file-based blueprints
                for bp_key, existing_bp in existing_blueprints.items():
                    if bp_key not in fixture_keys and not existing_bp.get("deprecated"):
                        # Only deprecate file-based blueprints
                        if existing_bp.get("blueprint_type") == "model":
                            result.deprecated.append(existing_bp)

        return result

    def _compare_single_item(
        self,
        fixture_item: Dict,
        result: ComparisonResult,
        existing_blueprints: Dict[str, Dict],
    ):
        """Compare a single fixture item with existing data."""
        # Skip deprecated entries from fixtures - they should not be added
        # as active blueprints
        if fixture_item.get("deprecated", False):
            if self.verbose:
                name = fixture_item.get("file_metadata", {}).get("full_name", "unknown")
                write_output(f"SKIPPED (deprecated in fixture): {name}\n")
            return

        # Handle non-file-based blueprints (type "blueprint")
        # that don't have file_metadata
        if "file_metadata" not in fixture_item:
            # For non-file-based blueprints, use the name as the identifier
            blueprint_name = fixture_item.get("name")
            if not blueprint_name:
                if self.verbose:
                    write_output(
                        "DEBUG: Skipping blueprint without name or file_metadata\n"
                    )
                return

            # Check if this configuration blueprint already exists
            existing_bp = existing_blueprints.get(blueprint_name)

            if existing_bp is None:
                # New configuration blueprint
                result.added.append(fixture_item)
                if self.verbose:
                    write_output(f"ADDED CONFIG: {blueprint_name}\n")
            else:
                # Check if configuration blueprint has changes
                if self._has_config_changes(fixture_item, existing_bp):
                    result.modified.append(fixture_item)
                    if self.verbose:
                        write_output(f"MODIFIED CONFIG: {blueprint_name}\n")
            return

        # Handle file-based blueprints (type "model") with file_metadata
        full_name = fixture_item["file_metadata"]["full_name"]
        md5 = fixture_item["file_metadata"]["md5"]

        existing_bp = existing_blueprints.get(full_name)

        # Before the MD5 fallback, which would read a consolidated duplicate as
        # a rename.
        if existing_bp is None and self._is_consolidated(
            full_name, md5, existing_blueprints, result
        ):
            return

        # If not found by full_name, check if a blueprint exists with the same MD5
        # This handles cases where files are renamed or have reordered components
        if existing_bp is None and md5:
            for bp in existing_blueprints.values():
                if bp.get("file_md5") == md5:
                    existing_bp = bp
                    if self.verbose:
                        write_output(
                            f"DEBUG: Found existing blueprint by MD5 for {full_name}\n"
                            f"  Existing path: {bp['full_name']}\n"
                        )
                    break

        if existing_bp is None:
            # New file
            result.added.append(fixture_item)
            # Always show what was added
            write_output(f"ADDED: {full_name}\n")
        else:
            # Existing file found - check if it's a rename or modification
            # If the full_name is different, this is a rename
            if full_name != existing_bp["full_name"]:
                # This is a rename - add as new so it goes through the rename logic
                result.added.append(fixture_item)
                if self.verbose:
                    write_output(
                        f"ADDED (renamed): {full_name}\n"
                        f"  (was: {existing_bp['full_name']})\n"
                    )
            # First check if MD5 is different - if so, this is a new version,
            # not a modification
            elif md5 != existing_bp["file_md5"]:
                # file_md5 is the identity, so new bytes arrive as a new row
                # and the row they replace has to be deprecated — one live row
                # per path.
                result.added.append(fixture_item)
                result.deprecated.append(existing_bp)
                write_output(
                    f"SUPERSEDED: {full_name} "
                    f"(MD5: {existing_bp['file_md5']} -> {md5})\n"
                )
            elif self._has_significant_changes(fixture_item, existing_bp):
                # Same MD5 but other changes (tags, config, etc.)
                result.modified.append(fixture_item)
                if self.verbose:
                    write_output(f"MODIFIED: {full_name}\n")

    def _is_consolidated(
        self,
        full_name: str,
        md5: str,
        existing_blueprints: Dict[str, Dict],
        result: ComparisonResult,
    ) -> bool:
        """Whether this path duplicates a blueprint that outlives this load.

        The content has to still agree, and the holder has to be one this load
        will not deprecate. A path this declines goes on to ordinary
        comparison; what happens to it there is not this function's promise.

        Every holder is considered, because a path can be listed by more than
        one row and only some of them qualify. Records a prune into `result`
        for a holder whose content has diverged.
        """
        for bp in existing_blueprints.values():
            if full_name not in (bp.get("consolidated_paths") or []):
                continue
            if bp.get("file_md5") != md5:
                # Listed, but the bytes differ: the holder no longer matches
                # this path, whatever becomes of it below.
                result.consolidated.append(
                    {"blueprint_id": bp["id"], "remove_path": full_name}
                )
                continue
            if not self._outlives_this_load(bp):
                continue
            holder = bp["full_name"]
            if self.verbose:
                write_output(
                    f"DEBUG: Skipping {full_name} - already in "
                    f"consolidated_paths of {holder}\n"
                )
            return True
        return False

    def _has_config_changes(self, fixture_item: Dict, existing_bp: Dict) -> bool:
        """Check if configuration blueprint has changes compared to existing blueprint.

        Args:
            fixture_item: New fixture item
            existing_bp: Existing blueprint from database

        Returns:
            True if configuration has changed
        """
        blueprint_name = fixture_item.get("name", "")

        # Check tags (compare as sets to handle unordered nature)
        existing_tags = set(existing_bp.get("tags", []))
        new_tags = set(fixture_item.get("tags", []))
        if existing_tags != new_tags:
            if self.verbose:
                write_output(
                    f"DEBUG: Tags changed for config blueprint {blueprint_name}\n"
                )
                write_output(f"  Existing: {sorted(existing_tags)}\n")
                write_output(f"  New: {sorted(new_tags)}\n")
            return True

        # Check config
        existing_config = existing_bp.get("blueprint_config", {})
        new_config = fixture_item.get("config", {})
        if existing_config != new_config:
            if self.verbose:
                write_output(
                    f"DEBUG: Config changed for config blueprint {blueprint_name}\n"
                )
                write_output(f"  Existing: {existing_config}\n")
                write_output(f"  New: {new_config}\n")
            return True

        return False

    def _has_significant_changes(self, fixture_item: Dict, existing_bp: Dict) -> bool:
        """Check if fixture item has significant changes.

        Compares fixture item to existing blueprint.
        """
        full_name = fixture_item["file_metadata"]["full_name"]

        # MD5 changes never reach here: the comparison treats them as a new
        # version before this runs.

        # Check modification time using robust datetime comparison
        existing_modified = existing_bp["file_modified_at"]
        new_modified = fixture_item["file_metadata"]["file_modified_at"]

        if existing_modified and new_modified:
            # Parse both timestamps into datetime objects
            existing_dt = _parse_timestamp(existing_modified)
            new_dt = _parse_timestamp(new_modified)

            # Fail fast if timestamp parsing fails
            if existing_dt is None:
                raise ValueError(
                    f"Failed to parse existing timestamp for {full_name}: "
                    f"{existing_modified}"
                )
            if new_dt is None:
                raise ValueError(
                    f"Failed to parse new timestamp for {full_name}: {new_modified}"
                )

            # Compare datetime objects
            if existing_dt != new_dt:
                if self.verbose:
                    write_output(
                        f"DEBUG: Modified time changed for {full_name}: "
                        f"{existing_bp['file_modified_at']} -> "
                        f"{fixture_item['file_metadata']['file_modified_at']}\n"
                    )
                return True

        # Check size
        if fixture_item["file_metadata"]["size"] != existing_bp["file_size"]:
            if self.verbose:
                write_output(
                    f"DEBUG: Size changed for {full_name}: "
                    f"{existing_bp['file_size']} -> "
                    f"{fixture_item['file_metadata']['size']}\n"
                )
            return True

        # Check tags (compare as sets to handle unordered nature)
        # Both existing_bp tags and fixture_item tags are pipe-delimited strings
        existing_tags = set(existing_bp.get("tags", []))
        new_tags = set(fixture_item.get("tags", []))
        if existing_tags != new_tags:
            if self.verbose:
                write_output(f"DEBUG: Tags changed for {full_name}\n")
                write_output(f"  Existing: {sorted(existing_tags)}\n")
                write_output(f"  New: {sorted(new_tags)}\n")
            return True

        # Check images (compare as sets to handle unordered nature).
        # Whole image dicts are compared, sprite_metadata included, so
        # a re-rendered sprite counts as a change.
        #
        # image_type is excluded because only one side can ever have
        # it. The fixture format has no field for it — none of the
        # 8,720 images in openforge/db/fixtures/blueprints/*.json
        # carries one — and the insert path could not honour it if it
        # did: insert_image_for_blueprint forwards name, url and
        # sprite metadata only, so insert_image's "thumbnail" default
        # always wins. Comparing it could therefore only ever produce
        # a false "changed", and the repair that followed would retype
        # a documentation row through that same default.
        #
        # What would invalidate this: a fixture format that states an
        # image type, or an insert path that forwards one. Either
        # makes the two sides comparable and this exclusion a blind
        # spot. See openforge_catalog-q3o, which replaces it — the
        # scanner should compare only the images it owns rather than
        # ignore the field that says who owns them.
        def comparable_image(img):
            return {
                k: v
                for k, v in img.items()
                if k not in ("created_at", "updated_at", "id", "image_type")
            }

        existing_images = set(
            json.dumps(comparable_image(img), sort_keys=True)
            for img in existing_bp.get("images", [])
        )
        new_images = set(
            json.dumps(comparable_image(img), sort_keys=True)
            for img in fixture_item.get("images", [])
        )
        if existing_images != new_images:
            if self.verbose:
                write_output(f"DEBUG: Images changed for {full_name}\n")
                write_output(f"  Existing: {sorted(existing_images)}\n")
                write_output(f"  New: {sorted(new_images)}\n")
            return True

        # Check config
        existing_config = existing_bp.get("blueprint_config", {})
        new_config = fixture_item.get("config", {})
        if existing_config != new_config:
            if self.verbose:
                write_output(f"DEBUG: Config changed for {full_name}\n")
                write_output(f"  Existing: {existing_config}\n")
                write_output(f"  New: {new_config}\n")
            return True

        return False

    def apply_incremental_changes(
        self,
        changes: ComparisonResult,
        dry_run: bool = False,
        curs: cursor = None,
        filename: str = None,
    ):
        """Apply incremental changes to database.

        Args:
            changes: ComparisonResult with changes to apply
            dry_run: If True, don't actually apply changes
            curs: Optional cursor to use (for transaction context)
        """
        if dry_run:
            if self.verbose:
                write_output(f"DRY RUN: Would apply {changes.summary()}\n")
            return

        # Use provided cursor or create new one
        if curs is not None:
            # Use the provided cursor (from outer transaction context)
            self._apply_changes_with_cursor(curs, changes)
        else:
            # Create new cursor context (fallback for standalone usage)
            with self.conn.cursor(row_factory=dict_row) as curs:
                self._apply_changes_with_cursor(curs, changes)

        # Always show the summary of what was applied
        if filename:
            write_output(f"{filename}: Applied {changes.summary()}\n")
        else:
            write_output(f"Applied {changes.summary()}\n")

    def _apply_changes_with_cursor(self, curs: cursor, changes: ComparisonResult):
        """Apply changes using the provided cursor."""
        # Load existing blueprints for modification handling
        existing_blueprints = self._load_existing_blueprints(curs)

        # Reset rename tracking for this load.
        self._renamed_blueprint_ids = set()
        self._deprecation_candidates = {bp["id"] for bp in changes.deprecated}
        changes.applied_deprecations = 0
        changes.declined_deprecations = []

        # A superseded row has to go before the row that supersedes it: both sit
        # at one path, and only one live row per path is allowed. A row missing
        # from the fixture is the opposite — it has to stay until the additions
        # have run, so a surviving duplicate can inherit it instead. Which is
        # which is the same test _is_rename makes: the superseded path is in
        # this fixture, the missing one is not.
        superseded, vacated = [], []
        for deprecated_bp in changes.deprecated:
            if deprecated_bp.get("full_name") in self.current_fixture_files:
                superseded.append(deprecated_bp)
            else:
                vacated.append(deprecated_bp)

        self._apply_deprecations(curs, superseded, changes, warn_stranded=False)

        for new_item in changes.added:
            self._handle_addition(curs, new_item)

        # An addition can revive a row the phase above tombstoned, and a rename
        # is the only thing that undoes one. Without this the count claims a
        # deprecation that is live again by the time the transaction commits.
        self._uncount_revived(superseded, changes)
        self._warn_stranded_superseded(superseded)

        # The rest: rows whose file left the fixture, which the additions above
        # may have claimed by rename.
        self._apply_deprecations(curs, vacated, changes)

        # Process modifications
        for modified_item in changes.modified:
            self._handle_modification(curs, modified_item, existing_blueprints)

        # Process consolidations
        for consolidated_item in changes.consolidated:
            self._handle_consolidation(curs, consolidated_item)

        # Post-process: Link deprecated blueprints to successors by file path
        self._link_deprecated_to_successors(curs)

    def _uncount_revived(self, candidates: List[Dict], changes: ComparisonResult):
        """Take back the tombstones an addition brought back to life.

        Every candidate here was applied rather than declined: the only decline
        left is a row already renamed in this load, and nothing is renamed until
        the additions run.
        """
        for bp in candidates:
            if bp.get("id") in self._renamed_blueprint_ids:
                changes.applied_deprecations -= 1
                changes.declined_deprecations.append(bp)

    def _apply_deprecations(
        self,
        curs: cursor,
        candidates: List[Dict],
        changes: ComparisonResult,
        warn_stranded: bool = True,
    ):
        """Tombstone what can be tombstoned, and record what was declined."""
        for deprecated_bp in candidates:
            if self._handle_deprecation(curs, deprecated_bp, warn_stranded):
                changes.applied_deprecations += 1
            else:
                changes.declined_deprecations.append(deprecated_bp)

    def _warn_stranded(self, bp: Dict):
        """Said out loud because no one function can tell: the duplicates
        listed here may be surviving in another fixture this run has already
        loaded, or has yet to, and tombstoning their only row leaves them with
        none.

        A path this fixture lists is not one of them — it has an addition of
        its own coming, which will inherit the row or insert its own.
        """
        orphans = [
            path
            for path in (bp.get("consolidated_paths") or [])
            if path not in self.current_fixture_files
        ]
        if orphans:
            write_output(
                f"WARNING: deprecating {bp.get('full_name')}, which "
                f"other paths were consolidated into: "
                f"{', '.join(orphans)}\n"
            )

    def _warn_stranded_superseded(self, superseded: List[Dict]):
        """The same warning, once the additions have decided who survived.

        A superseded row is usually revived by the addition for one of its
        duplicates, which inherits it under that path. Warning before the
        additions run names a row that is about to be live again.
        """
        for bp in superseded:
            if bp.get("id") not in self._renamed_blueprint_ids:
                self._warn_stranded(bp)

    def _handle_deprecation(
        self, curs: cursor, deprecated_bp: Dict, warn_stranded: bool = True
    ) -> bool:
        """Handle deprecation of an existing blueprint.

        Args:
            curs: Database cursor
            deprecated_bp: Blueprint to deprecate

        Returns:
            Whether the row was tombstoned; False when it was deliberately left
            in place.
        """
        # If this blueprint was renamed in this same load, the row was
        # already updated in place. Deprecating it now would tombstone the
        # live row and strip its freshly-inserted tags/images.
        if deprecated_bp.get("id") in self._renamed_blueprint_ids:
            if self.verbose:
                write_output(
                    f"Skipping deprecation of blueprint {deprecated_bp['id']} "
                    f"(renamed in this load)\n"
                )
            return False

        blueprint_id = deprecated_bp["id"]

        if warn_stranded:
            self._warn_stranded(deprecated_bp)

        # Remove tags and images for deprecated blueprint
        tag_sql.delete_all_blueprint_tags(curs, blueprint_id)
        image_sql.delete_images_for_blueprint(curs, blueprint_id)

        # _link_deprecated_to_successors sets successors; an existing successor_id
        # is changelog history and is left alone.
        blueprint_sql.mark_blueprint_deprecated(curs, blueprint_id)

        if self.verbose:
            if deprecated_bp.get("successor_id") is not None:
                write_output(
                    f"Deprecated blueprint {blueprint_id} "
                    f"(preserved existing successor_id: "
                    f"{deprecated_bp.get('successor_id')})\n"
                )
            else:
                write_output(
                    f"Deprecated blueprint {blueprint_id} and removed tags/images\n"
                )

        return True

    def _outlives_this_load(self, bp: Dict) -> bool:
        """Whether this load leaves that row live under the path it has.

        A path the fixture still lists survives only if the content matches:
        different bytes at the same path replace the row rather than update it.
        A path the fixture has dropped survives only if this load's sweep
        cannot reach it.
        """
        full_name = bp["full_name"]
        listed_md5 = self.current_fixture_md5s.get(full_name)
        if listed_md5 is not None:
            return listed_md5 == bp.get("file_md5")
        return not self._in_deprecation_sweep(full_name)

    def _is_rename(self, bp: Dict, new_full_name: str) -> bool:
        """Whether this path should take over an existing row, not just join it.

        The bytes already match: the caller arrives here only because the
        insert was rescued on this item's MD5. What is left to establish is
        that the row is going away, so this path inherits it instead of
        stealing it from a file that is still there.
        """
        existing_full_name = bp["full_name"]
        # A tombstone is not still there, whatever the fixture lists.
        still_there = existing_full_name in self.current_fixture_files
        if still_there and not bp.get("deprecated"):
            return False

        if new_full_name in (bp.get("consolidated_paths") or []):
            # A listed duplicate inherits a row this load is losing, and only
            # that. Absence from current_fixture_files does not prove the row
            # is going: that set holds one fixture file, and a holder in
            # another is simply elsewhere.
            return bp.get("deprecated") or bp["id"] in self._deprecation_candidates

        if not self.fixture_subset_path:
            return False
        subtree = self.fixture_subset_path + "/"
        return existing_full_name.startswith(subtree) and new_full_name.startswith(
            subtree
        )

    def _handle_addition(self, curs: cursor, new_item: Dict):
        """Handle addition of a new blueprint."""
        # Convert fixture format to database format
        bp_data = self._munge_blueprint(new_item)

        # Insert new blueprint
        bp = blueprint_sql.insert_blueprint(
            curs, bp_data, rescue_md5_conflict=True, words=self._get_words(new_item)
        )

        if bp:
            # Handle file-based blueprints with MD5 conflict checking
            if "file_metadata" in new_item:
                # Check if the returned blueprint matches our fixture data
                # This handles the case where there's an MD5 conflict
                # with a different file
                if bp["full_name"] != new_item["file_metadata"]["full_name"]:
                    # The returned blueprint is different from what we're trying to add
                    # This means there's an MD5 conflict with a different file
                    # We should add the new path to consolidated_paths
                    # Check if this is a rename within the same fixture
                    existing_full_name = bp["full_name"]
                    new_full_name = new_item["file_metadata"]["full_name"]

                    is_rename = self._is_rename(bp, new_full_name)

                    if is_rename:
                        # This is a rename within the fixture
                        # Update the main entry's full_name instead of
                        # adding to consolidated_paths
                        if self.verbose:
                            write_output(
                                "DEBUG: File rename within same fixture detected\n"
                            )
                            write_output(f"  Old path: {existing_full_name}\n")
                            write_output(f"  New path: {new_full_name}\n")
                            write_output(
                                "  Updating main entry's full_name instead of "
                                "adding to consolidated_paths\n"
                            )

                        # Update the blueprint's full_name to the new path.
                        # Also resync blueprint_name + search_text and clear
                        # deprecated, since the underlying file is the same
                        # bytes under a new name.
                        new_file_name = os.path.basename(new_full_name)
                        words = self._get_words(new_item)
                        search_text = blueprint_sql.blueprint_search_text(
                            {"blueprint_name": new_file_name}, words
                        )
                        update_data = {
                            "full_name": new_full_name,
                            "file_name": new_file_name,
                            "blueprint_name": new_file_name,
                            "search_text": search_text,
                            "deprecated": False,
                            # The row is this item now, so the fields a later
                            # comparison reads have to be this item's. An
                            # inherited mtime makes the next load of an
                            # unchanged fixture report a modification, and a
                            # modification resets consolidated_paths.
                            "file_size": bp_data["file_size"],
                            "file_modified_at": bp_data["file_modified_at"],
                            "blueprint_config": bp_data["blueprint_config"],
                            # This row is live again, so it is the current
                            # version and succeeds nothing. A live row that
                            # keeps a successor sends the chain reader off it.
                            "successor_id": None,
                            # The row now owns this path, so it is no longer
                            # one of the row's duplicates.
                            "consolidated_paths": [
                                path
                                for path in (bp.get("consolidated_paths") or [])
                                if path != new_full_name
                            ],
                        }
                        blueprint_sql.update_blueprint(curs, bp["id"], update_data)
                        # Mark this id as renamed so a later deprecation step
                        # in the same load won't tombstone it.
                        self._renamed_blueprint_ids.add(bp["id"])

                        # Also update tags and images from the new fixture data
                        # First remove old tags and images
                        tag_sql.delete_all_blueprint_tags(curs, bp["id"])
                        image_sql.delete_images_for_blueprint(curs, bp["id"])

                        # Then add new tags and images
                        for tag in new_item.get("tags", []):

                            def insert_tag_to_db(tag_array):
                                tag_sql.insert_tag(
                                    curs, bp["id"], array_to_tag(tag_array)
                                )

                            process_tag(tag, insert_tag_to_db)

                        for image in new_item.get("images", []):
                            image_sql.insert_image_for_blueprint(curs, bp["id"], image)

                        write_output(
                            f"RENAMED: {existing_full_name} -> {new_full_name}"
                            f"{_dropped_successor(bp)}\n"
                        )

                        # Return the updated blueprint
                        return bp

                    # Files are from different fixtures - add to consolidated_paths
                    if self.verbose:
                        write_output(
                            f"DEBUG: MD5 conflict detected for "
                            f"{new_item['file_metadata']['full_name']}\n"
                        )
                        write_output(f"  Existing blueprint: {bp['full_name']}\n")
                        write_output(
                            f"  New blueprint: "
                            f"{new_item['file_metadata']['full_name']}\n"
                        )
                        write_output(
                            f"  Adding to consolidated_paths for blueprint {bp['id']}\n"
                        )

                    # Add the new path to consolidated_paths
                    existing_paths = bp.get("consolidated_paths") or []
                    new_path = new_item["file_metadata"]["full_name"]
                    if new_path not in existing_paths:
                        existing_paths.append(new_path)
                        # Update the blueprint with the new consolidated_paths
                        update_data = {"consolidated_paths": existing_paths}
                        blueprint_sql.update_blueprint(curs, bp["id"], update_data)
                        write_output(f"CONSOLIDATED: {new_path} -> {bp['full_name']}\n")
                else:
                    # The file is back under the name it had, so the row is
                    # too: nothing else in the loader clears this flag without
                    # the path changing. Tags and images are resynced rather
                    # than added to, since deprecating the row stripped them.
                    if bp.get("deprecated"):
                        # successor_id goes with the tombstone: the chain
                        # follower starts at a live row and then walks the
                        # pointer unconditionally, so a live row that keeps one
                        # answers with the wrong blueprint, or cycles.
                        blueprint_sql.update_blueprint(
                            curs,
                            bp["id"],
                            {
                                "deprecated": False,
                                "successor_id": None,
                                # The row is this item now, so the fields a
                                # later comparison reads have to be this
                                # item's. An inherited mtime or config makes
                                # the next load of an unchanged fixture report
                                # a modification, and a modification resets
                                # consolidated_paths.
                                "file_size": bp_data["file_size"],
                                "file_modified_at": bp_data["file_modified_at"],
                                "blueprint_config": bp_data["blueprint_config"],
                            },
                        )
                        tag_sql.delete_all_blueprint_tags(curs, bp["id"])
                        image_sql.delete_images_for_blueprint(curs, bp["id"])
                        write_output(
                            f"RESTORED: {bp['full_name']}{_dropped_successor(bp)}\n"
                        )

                    # Normal case - insert tags and images for new blueprint
                    for tag in new_item.get("tags", []):

                        def insert_tag_to_db(tag_array):
                            tag_sql.insert_tag(curs, bp["id"], array_to_tag(tag_array))

                        process_tag(tag, insert_tag_to_db)

                    for image in new_item.get("images", []):
                        image_sql.insert_image_for_blueprint(curs, bp["id"], image)

                    if self.verbose:
                        write_output(f"Added blueprint {bp['id']}\n")
            else:
                # Configuration blueprint - insert tags and images
                for tag in new_item.get("tags", []):

                    def insert_tag_to_db(tag_array):
                        tag_sql.insert_tag(curs, bp["id"], array_to_tag(tag_array))

                    process_tag(tag, insert_tag_to_db)

                for image in new_item.get("images", []):
                    image_sql.insert_image_for_blueprint(curs, bp["id"], image)

                if self.verbose:
                    write_output(f"Added configuration blueprint {bp['id']}\n")
        else:
            if self.verbose:
                write_output("Added blueprint skipped\n")

        return bp

    def _handle_modification(
        self, curs: cursor, modified_item: Dict, existing_blueprints: Dict[str, Dict]
    ):
        """Handle modification of an existing blueprint."""
        if "file_metadata" in modified_item:
            # File-based blueprint
            full_name = modified_item["file_metadata"]["full_name"]
            existing_bp = existing_blueprints.get(full_name)
        else:
            # Configuration blueprint
            blueprint_name = modified_item.get("name")
            existing_bp = existing_blueprints.get(blueprint_name)

        if not existing_bp:
            # Shouldn't happen, but handle gracefully
            self._handle_addition(curs, modified_item)
            return

        blueprint_id = existing_bp["id"]

        # Update blueprint data. Recompute search_text alongside the column
        # update because tag changes are a common modify trigger and tag
        # words feed into search_text — without this, search_text drifts
        # whenever tags are edited.
        bp_data = self._munge_blueprint(modified_item)
        bp_data["search_text"] = blueprint_sql.blueprint_search_text(
            bp_data, self._get_words(modified_item)
        )
        blueprint_sql.update_blueprint(curs, blueprint_id, bp_data)

        # Update tags (delete old, insert new)
        tag_sql.delete_all_blueprint_tags(curs, blueprint_id)
        for tag in modified_item.get("tags", []):

            def insert_tag_to_db(tag_array):
                tag_sql.insert_tag(curs, blueprint_id, array_to_tag(tag_array))

            process_tag(tag, insert_tag_to_db)

        # Update images (delete old, insert new)
        image_sql.delete_images_for_blueprint(curs, blueprint_id)
        for image in modified_item.get("images", []):
            image_sql.insert_image_for_blueprint(curs, blueprint_id, image)

        if self.verbose:
            blueprint_name = existing_bp.get("blueprint_name", "unknown")
            write_output(f"Modified blueprint {blueprint_id} ({blueprint_name})\n")

    def _handle_consolidation(self, curs: cursor, consolidated_item: Dict):
        """Drop a path a row can no longer claim.

        A duplicate whose content diverged would otherwise stay listed by the
        row it used to match while also holding a row of its own.
        """
        blueprint_id = consolidated_item["blueprint_id"]
        remove_path = consolidated_item["remove_path"]

        bp = blueprint_sql.get_blueprint_by_id(curs, blueprint_id)
        listed = bp.get("consolidated_paths") or []
        remaining = [p for p in listed if p != remove_path]
        if len(remaining) == len(listed):
            return

        blueprint_sql.update_blueprint(
            curs, blueprint_id, {"consolidated_paths": remaining}
        )
        write_output(f"UNCONSOLIDATED: {remove_path} <- {bp['full_name']}\n")

    def _link_deprecated_to_successors(self, curs: cursor):
        """Link deprecated blueprints to successors by file path.

        For every deprecated blueprint that doesn't have a successor_id,
        find a non-deprecated blueprint with the same file path and link them.
        """
        # Get all deprecated blueprints without successor_id
        query = """
            SELECT id, full_name, file_md5, successor_id
            FROM blueprints
            WHERE deprecated = true
            AND successor_id IS NULL
        """
        curs.execute(query)
        deprecated_blueprints = curs.fetchall()

        if not deprecated_blueprints:
            return

        if self.verbose:
            write_output(
                f"DEBUG: Found {len(deprecated_blueprints)} deprecated "
                f"blueprints without successor_id\n"
            )

        for deprecated_bp in deprecated_blueprints:
            full_name = deprecated_bp["full_name"]
            if not full_name:
                continue  # Skip blueprints without full_name

            # Find non-deprecated blueprint with same file path
            query = """
                SELECT id, file_md5
                FROM blueprints
                WHERE deprecated = false
                AND full_name = %s
                ORDER BY created_at DESC
                LIMIT 1
            """
            curs.execute(query, (full_name,))
            successor_bp = curs.fetchone()

            if successor_bp:
                # Link the deprecated blueprint to the successor
                blueprint_sql.mark_blueprint_deprecated(
                    curs, deprecated_bp["id"], successor_bp["id"]
                )
                if self.verbose:
                    write_output(
                        f"LINKED: {full_name} "
                        f"(deprecated: {deprecated_bp['file_md5']} -> "
                        f"successor: {successor_bp['file_md5']})\n"
                    )
            else:
                if self.verbose:
                    write_output(
                        f"DEBUG: No successor found for deprecated "
                        f"blueprint {full_name}\n"
                    )

    def _munge_blueprint(self, data: dict) -> dict:
        """Convert fixture format to database format."""
        return munge_blueprint(data)

    def _get_words(self, data: dict) -> list[str]:
        """Extract search words from blueprint data."""
        return get_words(data)

    def transform_deprecated_entries(self, fixtures: List[Dict]) -> List[Dict]:
        """Transform deprecated entries to current schema format.

        This should be called before schema validation to ensure all
        deprecated entries conform to the current fixture format.

        Args:
            fixtures: List of fixture objects

        Returns:
            List of fixtures with deprecated entries transformed
        """
        return self.transformer.transform_list(fixtures)
