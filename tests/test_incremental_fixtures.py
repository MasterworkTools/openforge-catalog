"""
Tests for incremental fixtures loading functionality.
"""

from unittest.mock import ANY, Mock, patch

import pytest
from psycopg.rows import dict_row

from openforge.db.fixtures.incremental import (
    ComparisonResult,
    IncrementalFixturesLoader,
)


def create_mock_connection():
    """Create a mock database connection that supports the required methods."""
    mock_conn = Mock()

    # Mock cursor that supports context manager
    mock_cursor = Mock()
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)
    mock_cursor.fetchall = Mock(return_value=[])
    mock_cursor.fetchone = Mock(return_value=None)

    # Mock connection that returns the cursor
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.transaction = Mock()
    mock_conn.transaction.__enter__ = Mock(return_value=mock_conn.transaction)
    mock_conn.transaction.__exit__ = Mock(return_value=None)
    mock_conn.commit = Mock()

    return mock_conn


def create_mock_blueprint(full_name, md5, tags=None, images=None):
    """Create a mock blueprint for testing.

    Note: Database blueprints return pipe-delimited string tags, not arrays.
    """
    # Convert array tags to pipe-delimited strings to match database format
    if tags:
        db_tags = []
        for tag in tags:
            if isinstance(tag, list):
                db_tags.append("|".join(str(t) for t in tag))
            else:
                db_tags.append(str(tag))
    else:
        db_tags = []

    return {
        "id": f"test-{md5[:8]}",
        "full_name": full_name,
        "file_md5": md5,
        "file_size": 1000,
        "file_modified_at": "2020-01-01T12:00:00",
        "blueprint_config": {},
        "tags": db_tags,
        "images": images or [],
    }


def create_mock_fixture_item(full_name, md5, tags=None, images=None):
    """Create a mock fixture item for testing.

    Note: Fixture items use pipe-delimited strings for tags, not arrays.
    """
    # Convert array tags to pipe-delimited strings to match real fixture format
    if tags:
        fixture_tags = []
        for tag in tags:
            if isinstance(tag, list):
                fixture_tags.append("|".join(str(t) for t in tag))
            else:
                fixture_tags.append(str(tag))
    else:
        fixture_tags = []

    return {
        "type": "model",
        "file_metadata": {
            "full_name": full_name,
            "md5": md5,
            "size": 1000,
            "file_modified_at": "2020-01-01T12:00:00",
        },
        "tags": fixture_tags,
        "images": images or [],
        "config": {},
    }


class TestIncrementalFixturesLoader:
    """Test cases for IncrementalFixturesLoader class."""

    @pytest.fixture
    def mock_loader(self):
        """Create a mock loader for testing."""
        mock_conn = create_mock_connection()
        loader = IncrementalFixturesLoader(mock_conn, verbose=True)
        # Override the existing blueprints to avoid database calls
        loader.existing_blueprints = {}
        return loader

    def test_has_significant_changes_no_changes(self, mock_loader):
        """Test _has_significant_changes with no changes."""
        existing = create_mock_blueprint("test.stl", "abc123")
        fixture = create_mock_fixture_item("test.stl", "abc123")

        result = mock_loader._has_significant_changes(fixture, existing)
        assert not result, f"Expected no changes, got {result}"

    def test_has_significant_changes_md5_change(self, mock_loader):
        """Test _has_significant_changes with MD5 change.

        Note: MD5 changes are now handled in _compare_single_item before calling
        _has_significant_changes, so this test now verifies that MD5 changes
        are NOT detected in _has_significant_changes.
        """
        existing = create_mock_blueprint("test.stl", "abc123")
        fixture = create_mock_fixture_item("test.stl", "def456")

        result = mock_loader._has_significant_changes(fixture, existing)
        assert not result, (
            f"Expected no changes for MD5 change in _has_significant_changes, "
            f"got {result}"
        )

    def test_has_significant_changes_tags_change(self, mock_loader):
        """Test _has_significant_changes with tags change."""
        existing = create_mock_blueprint("test.stl", "abc123")
        fixture = create_mock_fixture_item("test.stl", "abc123", tags=[["new", "tag"]])

        result = mock_loader._has_significant_changes(fixture, existing)
        assert result, f"Expected changes for tags change, got {result}"

    def test_has_significant_changes_images_change(self, mock_loader):
        """Test _has_significant_changes with images change."""
        existing = create_mock_blueprint("test.stl", "abc123")
        fixture = create_mock_fixture_item("test.stl", "abc123")
        fixture["images"] = [{"image_name": "thumbnail", "image_url": "test.jpg"}]

        result = mock_loader._has_significant_changes(fixture, existing)
        assert result, f"Expected changes for images change, got {result}"

    def test_has_significant_changes_sprite_metadata_change(self, mock_loader):
        """Test _has_significant_changes detects sprite_metadata addition."""
        # Existing blueprint has image without sprite_metadata
        existing = create_mock_blueprint(
            "test.stl",
            "abc123",
            images=[{"image_name": "thumbnail", "image_url": "test.png"}],
        )

        # Fixture has same image but with sprite_metadata added
        fixture = create_mock_fixture_item("test.stl", "abc123")
        fixture["images"] = [
            {
                "image_name": "thumbnail",
                "image_url": "test.png",
                "sprite_metadata": {
                    "grid_rows": 2,
                    "grid_cols": 5,
                    "tile_size": 512,
                    "angles": [{"index": 0, "name": "front", "camera_pos": [0, -4, 2]}],
                    "default_angle": 0,
                },
            }
        ]

        result = mock_loader._has_significant_changes(fixture, existing)
        assert result, "Expected changes when sprite_metadata is added to image"

    def test_has_significant_changes_sprite_metadata_unchanged(self, mock_loader):
        """The same sprite on both sides is not a change.

        Every fixture image carries sprite_metadata — all 8,720 of
        them — so if the database side lacks it, every blueprint with
        an image reports as changed on every scan and has its images
        deleted and reinserted. That is what happened while the batch
        query that loads the existing side omitted the column.

        This test hands itself both sides, so it pins the comparison
        and nothing else — put `image_type` back into it and this
        fails. It does not reach the query the bug was in; that seam
        is pinned from the other side, by the projection-parity test
        in `tests/test_images_sql.py`.
        """
        sprite = {
            "grid_rows": 2,
            "grid_cols": 5,
            "tile_size": 512,
            "angles": [{"index": 0, "name": "front", "camera_pos": [0, -4, 2]}],
            "default_angle": 0,
        }
        image = {
            "image_name": "thumbnail",
            "image_url": "test.png",
            "sprite_metadata": sprite,
        }
        # The database side also carries the type it assigned, which
        # the fixture never states.
        existing = create_mock_blueprint(
            "test.stl", "abc123", images=[{**image, "image_type": "thumbnail"}]
        )
        fixture = create_mock_fixture_item("test.stl", "abc123")
        fixture["images"] = [image]

        assert not mock_loader._has_significant_changes(fixture, existing)

    def test_has_significant_changes_config_change(self, mock_loader):
        """Test _has_significant_changes with config change."""
        existing = create_mock_blueprint("test.stl", "abc123")
        fixture = create_mock_fixture_item("test.stl", "abc123")
        fixture["config"] = {"new": "value"}

        result = mock_loader._has_significant_changes(fixture, existing)
        assert result, f"Expected changes for config change, got {result}"

    def test_has_significant_changes_tag_format_comparison(self, mock_loader):
        """Test _has_significant_changes with proper tag format comparison.

        This test verifies that the comparison correctly handles:
        - Database tags: arrays like [['shape', 'floor']]
        - Fixture tags: pipe-delimited strings like ['shape|floor']
        """
        # Database blueprint with array tags
        existing = create_mock_blueprint(
            "test.stl", "abc123", tags=[["shape", "floor"], ["material", "stone"]]
        )

        # Fixture with pipe-delimited tags (same content)
        fixture = create_mock_fixture_item(
            "test.stl", "abc123", tags=[["shape", "floor"], ["material", "stone"]]
        )

        # Should detect no changes since tags are equivalent
        result = mock_loader._has_significant_changes(fixture, existing)
        assert not result, f"Expected no changes for equivalent tags, got {result}"

        # Test with different tags
        fixture_different = create_mock_fixture_item(
            "test.stl", "abc123", tags=[["shape", "wall"], ["material", "stone"]]
        )
        result = mock_loader._has_significant_changes(fixture_different, existing)
        assert result, f"Expected changes for different tags, got {result}"

    def test_compare_fixture_data_new_file(self, mock_loader):
        """Test compare_fixture_data with new file."""
        fixture_data = [create_mock_fixture_item("new.stl", "new123")]

        result = mock_loader.compare_fixture_data(fixture_data, skip_load_existing=True)

        assert len(result.added) == 1
        assert result.added[0]["file_metadata"]["full_name"] == "new.stl"
        assert len(result.modified) == 0
        assert len(result.deprecated) == 0

    def test_compare_fixture_data_existing_file_no_changes(self, mock_loader):
        """Test compare_fixture_data with existing file and no changes."""
        mock_loader.existing_blueprints = {
            "existing.stl": create_mock_blueprint("existing.stl", "abc123")
        }

        fixture_data = [create_mock_fixture_item("existing.stl", "abc123")]

        result = mock_loader.compare_fixture_data(fixture_data, skip_load_existing=True)

        assert len(result.added) == 0
        assert len(result.modified) == 0
        assert len(result.deprecated) == 0

    def test_compare_fixture_data_modified_file(self, mock_loader):
        """Test compare_fixture_data with modified file."""
        mock_loader.existing_blueprints = {
            "modified.stl": create_mock_blueprint(
                "modified.stl",
                "def456",
                tags=[["old", "tag"]],
                images=[{"image_name": "old", "image_url": "old.jpg"}],
            )
        }

        fixture_data = [
            create_mock_fixture_item(
                "modified.stl",
                "def456",
                tags=[["new", "tag"]],
                images=[{"image_name": "new", "image_url": "new.jpg"}],
            )
        ]

        result = mock_loader.compare_fixture_data(fixture_data, skip_load_existing=True)

        assert len(result.added) == 0
        assert len(result.modified) == 1
        assert result.modified[0]["file_metadata"]["full_name"] == "modified.stl"
        assert len(result.deprecated) == 0

    def test_compare_fixture_data_version_change(self, mock_loader):
        """An edited file is a new row, and the row it replaces is superseded.

        file_md5 is the identity, so the new bytes cannot update the old row in
        place. Leaving the old row live puts two of them at one path, and the
        loader then compares against whichever is older.
        """
        superseded = create_mock_blueprint("version_change.stl", "old789")
        mock_loader.existing_blueprints = {"version_change.stl": superseded}

        fixture_data = [create_mock_fixture_item("version_change.stl", "new789")]

        with patch("openforge.db.fixtures.incremental.write_output") as out:
            result = mock_loader.compare_fixture_data(
                fixture_data, skip_load_existing=True
            )

        assert len(result.added) == 1
        assert result.added[0]["file_metadata"]["full_name"] == "version_change.stl"
        assert len(result.modified) == 0
        # The superseded row is a deprecation candidate; the post-pass links it
        # to the new row, which it finds by the path they share.
        assert result.deprecated == [superseded]
        # Said at default verbosity: this retires a row.
        said = "".join(c.args[0] for c in out.call_args_list)
        assert "SUPERSEDED" in said and "version_change.stl" in said

    def test_compare_fixture_data_shared_md5_already_consolidated(self, mock_loader):
        """A path held in another blueprint's consolidated_paths is not a rename.

        Both files are byte-identical, so the MD5 fallback finds the row the
        duplicate was consolidated into. Reported as a rename, that repeats on
        every load and the loader never settles.
        """
        bystander = create_mock_blueprint("tiles/plain/2x2.magnetic.stl", "other111")
        bystander["consolidated_paths"] = ["tiles/plain/2x2.magnetic,openlock.stl"]
        kept = create_mock_blueprint("tiles/plain/1x1.magnetic+flex.stl", "same999")
        kept["consolidated_paths"] = ["tiles/plain/1x1.magnetic+flex,openlock.stl"]
        # Non-owner first, so finding the owner cannot depend on dict order.
        mock_loader.existing_blueprints = {
            bystander["full_name"]: bystander,
            kept["full_name"]: kept,
        }

        fixture_data = [
            # Present, so the sweep has no reason to deprecate it.
            create_mock_fixture_item("tiles/plain/2x2.magnetic.stl", "other111"),
            create_mock_fixture_item("tiles/plain/1x1.magnetic+flex.stl", "same999"),
            create_mock_fixture_item(
                "tiles/plain/1x1.magnetic+flex,openlock.stl", "same999"
            ),
        ]

        result = mock_loader.compare_fixture_data(fixture_data, skip_load_existing=True)

        assert len(result.added) == 0
        assert len(result.modified) == 0
        assert len(result.deprecated) == 0

    def test_compare_fixture_data_shared_md5_unrecorded_is_a_rename(self, mock_loader):
        """An MD5 match at a path nobody consolidated is still a rename.

        The row holds an unrelated consolidated path, so only a membership test
        can tell this path is not one of them.
        """
        existing = create_mock_blueprint("tiles/plain/old/path.stl", "same999")
        existing["consolidated_paths"] = ["tiles/plain/some/other/dup.stl"]
        mock_loader.existing_blueprints = {existing["full_name"]: existing}

        fixture_data = [create_mock_fixture_item("tiles/plain/new/path.stl", "same999")]

        result = mock_loader.compare_fixture_data(fixture_data, skip_load_existing=True)

        assert len(result.added) == 1
        assert (
            result.added[0]["file_metadata"]["full_name"] == "tiles/plain/new/path.stl"
        )
        assert len(result.modified) == 0

    def test_compare_fixture_data_consolidated_holder_left_the_fixture(
        self, mock_loader
    ):
        """A duplicate whose canonical path is gone has to take the row over.

        The holder is absent from this fixture, so it becomes a deprecation
        candidate. Skipping its surviving duplicate would tombstone the piece
        while its file is still on disk.
        """
        holder = create_mock_blueprint("tiles/x/a.stl", "same999")
        holder["consolidated_paths"] = ["tiles/x/b.stl"]
        mock_loader.existing_blueprints = {holder["full_name"]: holder}

        fixture_data = [create_mock_fixture_item("tiles/x/b.stl", "same999")]

        result = mock_loader.compare_fixture_data(fixture_data, skip_load_existing=True)

        assert len(result.added) == 1
        assert result.added[0]["file_metadata"]["full_name"] == "tiles/x/b.stl"

    def test_compare_fixture_data_consolidated_content_diverged(self, mock_loader):
        """An edited duplicate is its own file again, not a skip.

        consolidated_paths is only ever appended to, so a path still listed
        after its content changed would otherwise never reach the catalog.
        """
        holder = create_mock_blueprint("tiles/x/a.stl", "same999")
        holder["consolidated_paths"] = ["tiles/x/b.stl"]
        mock_loader.existing_blueprints = {holder["full_name"]: holder}

        fixture_data = [
            create_mock_fixture_item("tiles/x/a.stl", "same999"),
            create_mock_fixture_item("tiles/x/b.stl", "edited222"),
        ]

        result = mock_loader.compare_fixture_data(fixture_data, skip_load_existing=True)

        added = [i["file_metadata"]["full_name"] for i in result.added]
        assert added == ["tiles/x/b.stl"]
        # The holder still lists a path whose bytes have moved on, so the apply
        # is told to stop it claiming one it no longer matches.
        assert result.consolidated == [
            {"blueprint_id": holder["id"], "remove_path": "tiles/x/b.stl"}
        ]

    def test_compare_fixture_data_consolidated_holder_in_another_fixture(
        self, mock_loader
    ):
        """A holder outside this fixture's namespace is not this load's business.

        consolidated_paths is written precisely when two files come from
        different fixtures, so this is the common case rather than an edge one.
        The holder is absent from this fixture's file list, but the missing-file
        sweep cannot reach it either, so it survives and this path stays a
        duplicate.
        """
        # dungeon_stone+ruined is a real namespace that dungeon_stone is a
        # prefix of, so the trailing slash in the sweep's prefix is what keeps
        # this holder out of a dungeon_stone load's reach.
        holder = create_mock_blueprint(
            "tiles/dungeon_stone+ruined/brazier.stl", "same999"
        )
        holder["consolidated_paths"] = ["tiles/dungeon_stone/brazier.stl"]
        mock_loader.existing_blueprints = {holder["full_name"]: holder}

        fixture_data = [
            create_mock_fixture_item("tiles/dungeon_stone/brazier.stl", "same999")
        ]

        result = mock_loader.compare_fixture_data(fixture_data, skip_load_existing=True)

        assert len(result.added) == 0
        assert len(result.modified) == 0
        assert result.deprecated == []

    def test_compare_fixture_data_consolidated_checks_every_holder(self, mock_loader):
        """One row listing the path does not settle it when another also does.

        Both rows list the duplicate; only the second still matches its content.
        Answering from the first row alone makes the verdict depend on row
        order, which is the non-settling load this guard exists to stop.
        """
        stale = create_mock_blueprint("tiles/x/stale.stl", "old111")
        stale["consolidated_paths"] = ["tiles/x/dup.stl"]
        owner = create_mock_blueprint("tiles/x/owner.stl", "same999")
        owner["consolidated_paths"] = ["tiles/x/dup.stl"]
        mock_loader.existing_blueprints = {
            stale["full_name"]: stale,
            owner["full_name"]: owner,
        }

        fixture_data = [
            create_mock_fixture_item("tiles/x/stale.stl", "old111"),
            create_mock_fixture_item("tiles/x/owner.stl", "same999"),
            create_mock_fixture_item("tiles/x/dup.stl", "same999"),
        ]

        result = mock_loader.compare_fixture_data(fixture_data, skip_load_existing=True)

        assert len(result.added) == 0
        assert len(result.modified) == 0
        # The stale holder is told to stop claiming a path it no longer matches,
        # even though a later holder does.
        assert result.consolidated == [
            {"blueprint_id": stale["id"], "remove_path": "tiles/x/dup.stl"}
        ]

    def test_compare_fixture_data_row_listing_its_own_path_is_still_compared(
        self, mock_loader
    ):
        """A row can end up holding its own path, and must not skip itself.

        The rename branch does not prune consolidated_paths, so a row moved onto
        a path it had consolidated keeps pointing at itself. Its own changes
        still have to be seen.
        """
        row = create_mock_blueprint("tiles/x/b.stl", "same999", tags=["shape|floor"])
        row["consolidated_paths"] = ["tiles/x/b.stl"]
        mock_loader.existing_blueprints = {row["full_name"]: row}

        fixture_data = [
            create_mock_fixture_item(
                "tiles/x/b.stl", "same999", tags=["shape|floor", "size|width|2"]
            )
        ]

        result = mock_loader.compare_fixture_data(fixture_data, skip_load_existing=True)

        assert len(result.modified) == 1
        assert len(result.added) == 0

    def test_compare_fixture_data_no_namespace_sweeps_everything(self, mock_loader):
        """With no namespace the sweep is catalog-wide, so no holder is safe.

        A fixture spanning two namespaces yields none, and the loader then
        deprecates any model row absent from it. A holder certified as
        surviving on that basis would be tombstoned by the same load, taking
        the duplicate's only row with it.
        """
        holder = create_mock_blueprint("tiles/cut-stone/brazier.stl", "same999")
        holder["consolidated_paths"] = ["tiles/dungeon_stone/brazier.stl"]
        holder["blueprint_type"] = "model"
        mock_loader.existing_blueprints = {holder["full_name"]: holder}

        # Two namespaces, so _get_fixture_namespace cannot pick one.
        fixture_data = [
            create_mock_fixture_item("tiles/dungeon_stone/brazier.stl", "same999"),
            create_mock_fixture_item("tiles/towne/wall.stl", "other222"),
        ]

        result = mock_loader.compare_fixture_data(fixture_data, skip_load_existing=True)

        assert mock_loader.fixture_namespace is None
        # The holder is swept, so the duplicate has to become its own row.
        assert holder in result.deprecated
        added = [i["file_metadata"]["full_name"] for i in result.added]
        assert "tiles/dungeon_stone/brazier.stl" in added

    def test_compare_fixture_data_config_blueprint_new(self, mock_loader):
        """Test compare_fixture_data with new configuration blueprint."""
        fixture_data = [
            {
                "type": "blueprint",
                "name": "Test Config Blueprint",
                "tags": ["test|config"],
                "config": {"test": "value"},
            }
        ]

        result = mock_loader.compare_fixture_data(fixture_data, skip_load_existing=True)

        assert len(result.added) == 1
        assert result.added[0]["name"] == "Test Config Blueprint"
        assert len(result.modified) == 0
        assert len(result.deprecated) == 0

    def test_compare_fixture_data_config_blueprint_existing_no_changes(
        self, mock_loader
    ):
        """Test compare_fixture_data with existing configuration blueprint
        and no changes."""
        mock_loader.existing_blueprints = {
            "Test Config Blueprint": {
                "id": "test-config-123",
                "blueprint_name": "Test Config Blueprint",
                "blueprint_type": "blueprint",
                "blueprint_config": {"test": "value"},
                "tags": ["test|config"],
                "images": [],
            }
        }

        fixture_data = [
            {
                "type": "blueprint",
                "name": "Test Config Blueprint",
                "tags": ["test|config"],
                "config": {"test": "value"},
            }
        ]

        result = mock_loader.compare_fixture_data(fixture_data, skip_load_existing=True)

        assert len(result.added) == 0
        assert len(result.modified) == 0
        assert len(result.deprecated) == 0

    def test_compare_fixture_data_config_blueprint_modified(self, mock_loader):
        """Test compare_fixture_data with modified configuration blueprint."""
        mock_loader.existing_blueprints = {
            "Test Config Blueprint": {
                "id": "test-config-123",
                "blueprint_name": "Test Config Blueprint",
                "blueprint_type": "blueprint",
                "blueprint_config": {"old": "value"},
                "tags": ["old|tag"],
                "images": [],
            }
        }

        fixture_data = [
            {
                "type": "blueprint",
                "name": "Test Config Blueprint",
                "tags": ["new|tag"],
                "config": {"new": "value"},
            }
        ]

        result = mock_loader.compare_fixture_data(fixture_data, skip_load_existing=True)

        assert len(result.added) == 0
        assert len(result.modified) == 1
        assert result.modified[0]["name"] == "Test Config Blueprint"
        assert len(result.deprecated) == 0

    def test_has_config_changes_no_changes(self, mock_loader):
        """Test _has_config_changes with no changes."""
        existing = {
            "blueprint_name": "Test Config",
            "blueprint_config": {"test": "value"},
            "tags": ["test|tag"],
        }

        fixture = {
            "name": "Test Config",
            "config": {"test": "value"},
            "tags": ["test|tag"],
        }

        result = mock_loader._has_config_changes(fixture, existing)
        assert not result, f"Expected no changes, got {result}"

    def test_has_config_changes_tags_change(self, mock_loader):
        """Test _has_config_changes with tags change."""
        existing = {
            "blueprint_name": "Test Config",
            "blueprint_config": {"test": "value"},
            "tags": ["old|tag"],
        }

        fixture = {
            "name": "Test Config",
            "config": {"test": "value"},
            "tags": ["new|tag"],
        }

        result = mock_loader._has_config_changes(fixture, existing)
        assert result, f"Expected changes for tags change, got {result}"

    def test_has_config_changes_config_change(self, mock_loader):
        """Test _has_config_changes with config change."""
        existing = {
            "blueprint_name": "Test Config",
            "blueprint_config": {"old": "value"},
            "tags": ["test|tag"],
        }

        fixture = {
            "name": "Test Config",
            "config": {"new": "value"},
            "tags": ["test|tag"],
        }

        result = mock_loader._has_config_changes(fixture, existing)
        assert result, f"Expected changes for config change, got {result}"

    def test_compare_fixture_data_mixed_changes(self, mock_loader):
        """Test compare_fixture_data with mixed changes."""
        superseded = create_mock_blueprint("version_change.stl", "old789")
        mock_loader.existing_blueprints = {
            "existing.stl": create_mock_blueprint("existing.stl", "abc123"),
            "modified.stl": create_mock_blueprint(
                "modified.stl", "def456", tags=[["old", "tag"]]
            ),
            "version_change.stl": superseded,
        }

        fixture_data = [
            create_mock_fixture_item("new.stl", "new123"),  # New file
            create_mock_fixture_item("existing.stl", "abc123"),  # No changes
            create_mock_fixture_item(
                "modified.stl", "def456", tags=[["new", "tag"]]
            ),  # Modified
            create_mock_fixture_item("version_change.stl", "new789"),  # Version change
        ]

        result = mock_loader.compare_fixture_data(fixture_data, skip_load_existing=True)

        # Verify results
        assert len(result.added) == 2  # new.stl + version_change.stl
        added_names = [item["file_metadata"]["full_name"] for item in result.added]
        assert "new.stl" in added_names
        assert "version_change.stl" in added_names

        assert len(result.modified) == 1
        assert result.modified[0]["file_metadata"]["full_name"] == "modified.stl"

        # Only the edited file's old row; the unchanged and modified ones stay.
        assert result.deprecated == [superseded]

    def test_munge_blueprint(self, mock_loader):
        """Test _munge_blueprint method."""
        fixture_item = {
            "type": "model",
            "name": "test_blueprint",
            "config": {"test": "value"},
            "deprecated": False,
            "successor_id": None,
            "consolidated_paths": [],
            "file_metadata": {
                "file": "test.stl",
                "md5": "abc123",
                "size": 1000,
                "full_name": "test.stl",
                "file_modified_at": "2020-01-01T12:00:00",
                "storage_address": "https://example.com/test.stl",
            },
        }

        result = mock_loader._munge_blueprint(fixture_item)

        # Verify the conversion
        assert result["blueprint_type"] == "model"
        assert result["blueprint_name"] == "test_blueprint"
        assert result["blueprint_config"] == {"test": "value"}
        assert result["file_md5"] == "abc123"
        assert result["file_size"] == 1000
        assert result["file_name"] == "test.stl"
        assert result["full_name"] == "test.stl"
        # Note: openscad_source and changelog fields are no longer extracted
        # as they are not stored in the blueprints table

    def test_get_words(self, mock_loader):
        """Test _get_words method."""
        data = {"tags": [["shape", "floor"], ["size", "width", 1], ["texture", "cave"]]}

        words = mock_loader._get_words(data)

        # Should extract all words from tags
        expected_words = {"shape", "floor", "size", "width", "1", "texture", "cave"}
        assert set(words) == expected_words

    def test_comparison_result_summary(self):
        """Test ComparisonResult summary method."""
        result = ComparisonResult()

        # Test empty result
        assert result.summary() == "no changes"
        assert not result.has_changes()

        # Test with changes
        result.added = [{"name": "test1"}]
        result.modified = [{"name": "test2"}]
        result.deprecated = [{"name": "test3"}]

        summary = result.summary()
        assert "1 added" in summary
        assert "1 modified" in summary
        assert "1 deprecated" in summary
        assert result.has_changes()

    # ------------------------------------------------------------------
    # Rename-within-same-fixture regression tests
    # ------------------------------------------------------------------
    # These tests pin down the bug where renaming a file in Dropbox
    # (same MD5, new full_name) corrupted the DB row: blueprint_name and
    # search_text went stale, the row got tombstoned in the same load,
    # and tags/images were deleted.

    def _rename_loader(self):
        """Build a loader primed for the same-fixture rename branch."""
        mock_conn = create_mock_connection()
        loader = IncrementalFixturesLoader(mock_conn, verbose=False)
        # Trigger the is_rename=True branch in _handle_addition: both
        # paths must share the subset path, and the existing path must
        # not be in the current fixture files set.
        loader.fixture_subset_path = "tiles/aztlan"
        loader.current_fixture_files = {
            "tiles/aztlan/floors/floor/openforge/aztlan#floor.1x1.openforge.stl"
        }
        return loader

    def test_rename_resyncs_blueprint_name_and_clears_deprecated(self):
        """Rename branch must resync blueprint_name + search_text and
        clear deprecated, not just full_name/file_name."""
        loader = self._rename_loader()

        # Existing DB row uses the old (typo'd) name; insert returns it
        # as the rescued md5 conflict.
        existing_bp = {
            "id": "bp-1",
            "full_name": (
                "tiles/aztlan/floors/floor/openforge/atzlan#floor.1x1.openforge.stl"
            ),
        }

        new_item = create_mock_fixture_item(
            "tiles/aztlan/floors/floor/openforge/aztlan#floor.1x1.openforge.stl",
            "md5-shared",
            tags=[["texture", "aztlan"], ["shape", "floor"]],
        )
        # _munge_blueprint reads file_metadata["file"]; create_mock_fixture_item
        # omits it, so add the basename here.
        new_item["file_metadata"]["file"] = "aztlan#floor.1x1.openforge.stl"

        captured = {}

        def fake_update(curs, blueprint_id, data):
            captured["id"] = blueprint_id
            captured["data"] = data

        with (
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.insert_blueprint",
                return_value=existing_bp,
            ),
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.update_blueprint",
                side_effect=fake_update,
            ),
            patch(
                "openforge.db.fixtures.incremental.tag_sql.delete_all_blueprint_tags"
            ),
            patch("openforge.db.fixtures.incremental.tag_sql.insert_tag"),
            patch(
                "openforge.db.fixtures.incremental.image_sql"
                ".delete_images_for_blueprint"
            ),
            patch(
                "openforge.db.fixtures.incremental.image_sql.insert_image_for_blueprint"
            ),
        ):
            loader._handle_addition(Mock(), new_item)

        # The rename id is tracked so the deprecation step skips it.
        assert "bp-1" in loader._renamed_blueprint_ids
        # All four corruption-prone fields must be in the update payload.
        assert captured["data"]["full_name"] == (
            "tiles/aztlan/floors/floor/openforge/aztlan#floor.1x1.openforge.stl"
        )
        assert captured["data"]["file_name"] == "aztlan#floor.1x1.openforge.stl"
        assert captured["data"]["blueprint_name"] == ("aztlan#floor.1x1.openforge.stl")
        assert captured["data"]["deprecated"] is False
        # search_text reflects the new name and tag words, not the old.
        search_text = captured["data"]["search_text"]
        assert "aztlan" in search_text.split()
        assert "atzlan" not in search_text.split()
        assert "floor" in search_text.split()

    def test_handle_addition_takes_over_a_row_outside_the_subtree(self):
        """A duplicate takes the row over even when the holder is above it.

        The fixture's subtree is the common prefix of its own paths, so it
        deepens when the holder's file is deleted — the same deletion that
        makes the holder a deprecation candidate. Refusing the takeover on
        that basis tombstones the row and leaves the surviving file with none.
        """
        loader = IncrementalFixturesLoader(create_mock_connection(), verbose=False)
        loader.fixture_subset_path = "tiles/catacombs/thick_wall/loculus"
        loader.current_fixture_files = {"tiles/catacombs/thick_wall/loculus/b.stl"}

        # The rescued row sits above the subtree and already lists the new path.
        existing_bp = {
            "id": "bp-1",
            "full_name": "tiles/catacombs/thick_wall/a.stl",
            "consolidated_paths": ["tiles/catacombs/thick_wall/loculus/b.stl"],
        }

        # The same deletion also makes the holder a deprecation candidate,
        # which is what entitles this path to inherit its row.
        loader._deprecation_candidates = {"bp-1"}

        new_item = create_mock_fixture_item(
            "tiles/catacombs/thick_wall/loculus/b.stl", "md5-shared"
        )
        new_item["file_metadata"]["file"] = "b.stl"

        updates = []

        with (
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.insert_blueprint",
                return_value=existing_bp,
            ),
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.update_blueprint",
                side_effect=lambda curs, bid, data: updates.append(data),
            ),
            patch(
                "openforge.db.fixtures.incremental.tag_sql.delete_all_blueprint_tags"
            ),
            patch("openforge.db.fixtures.incremental.tag_sql.insert_tag"),
            patch(
                "openforge.db.fixtures.incremental.image_sql"
                ".delete_images_for_blueprint"
            ),
            patch(
                "openforge.db.fixtures.incremental.image_sql.insert_image_for_blueprint"
            ),
            patch("openforge.db.fixtures.incremental.write_output") as out,
        ):
            loader._handle_addition(Mock(), new_item)

        # Said at default verbosity: this relocates a row and replaces its
        # tags and images, and the loader is not verbose here.
        said = "".join(c.args[0] for c in out.call_args_list)
        assert "tiles/catacombs/thick_wall/a.stl" in said
        assert "tiles/catacombs/thick_wall/loculus/b.stl" in said

        # One write, not an accumulation of two.
        assert len(updates) == 1
        payload = updates[0]
        assert payload["full_name"] == "tiles/catacombs/thick_wall/loculus/b.stl"
        assert payload["file_name"] == "b.stl"
        assert payload["blueprint_name"] == "b.stl"
        # The row may have been a tombstone; it is live again under this path.
        assert payload["deprecated"] is False
        # And it no longer lists the path it now owns.
        assert payload["consolidated_paths"] == []
        # The row is this item now, so every field a later comparison or a
        # reader comes to is this item's, not the one it inherited.
        assert payload["file_size"] == new_item["file_metadata"]["size"]
        assert (
            payload["file_modified_at"] == new_item["file_metadata"]["file_modified_at"]
        )
        assert payload["blueprint_config"] == new_item["config"]
        # Tracked, so the deprecation step in the same apply declines the row.
        assert "bp-1" in loader._renamed_blueprint_ids

    def test_handle_addition_clears_the_successor_when_it_revives_by_rename(self):
        """The takeover revives a tombstone, so it drops the successor too.

        _handle_deprecation deliberately preserves successor_id when it
        tombstones a row, so the field is routinely set on exactly the rows
        this branch brings back. A live row that keeps one sends the
        version-chain reader off it, or closes a cycle with the row that
        replaced it.
        """
        loader = IncrementalFixturesLoader(create_mock_connection(), verbose=False)
        loader.fixture_subset_path = "tiles/sewers"
        loader.current_fixture_files = {"tiles/sewers/b.stl"}

        # Deprecated holder, linked to whatever replaced it while it was away.
        tombstone = {
            "id": "bp-1",
            "full_name": "tiles/catacombs/a.stl",
            "deprecated": True,
            "successor_id": "bp-successor",
            "consolidated_paths": ["tiles/sewers/b.stl"],
        }

        new_item = create_mock_fixture_item("tiles/sewers/b.stl", "md5-shared")
        new_item["file_metadata"]["file"] = "b.stl"

        updates = []

        with (
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.insert_blueprint",
                return_value=tombstone,
            ),
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.update_blueprint",
                side_effect=lambda curs, bid, data: updates.append(data),
            ),
            patch(
                "openforge.db.fixtures.incremental.tag_sql.delete_all_blueprint_tags"
            ),
            patch("openforge.db.fixtures.incremental.tag_sql.insert_tag"),
            patch(
                "openforge.db.fixtures.incremental.image_sql"
                ".delete_images_for_blueprint"
            ),
            patch(
                "openforge.db.fixtures.incremental.image_sql.insert_image_for_blueprint"
            ),
            patch("openforge.db.fixtures.incremental.write_output") as out,
        ):
            loader._handle_addition(Mock(), new_item)

        assert len(updates) == 1
        assert updates[0]["full_name"] == "tiles/sewers/b.stl"
        assert updates[0]["deprecated"] is False
        assert updates[0]["successor_id"] is None
        # The discarded link is named rather than vanishing.
        assert "bp-successor" in "".join(c.args[0] for c in out.call_args_list)

    def test_handle_consolidation_drops_only_the_named_path(self):
        """Pruning one stale listing leaves the row's other duplicates alone."""
        loader = IncrementalFixturesLoader(create_mock_connection(), verbose=False)

        holder = {
            "id": "bp-1",
            "full_name": "tiles/x/a.stl",
            "consolidated_paths": ["tiles/x/gone.stl", "tiles/x/still.stl"],
        }

        updates = []

        with (
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.get_blueprint_by_id",
                return_value=holder,
            ),
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.update_blueprint",
                side_effect=lambda curs, bid, data: updates.append(data),
            ),
            patch("openforge.db.fixtures.incremental.write_output") as out,
        ):
            loader._handle_consolidation(
                Mock(), {"blueprint_id": "bp-1", "remove_path": "tiles/x/gone.stl"}
            )

        assert updates == [{"consolidated_paths": ["tiles/x/still.stl"]}]
        said = "".join(c.args[0] for c in out.call_args_list)
        assert "tiles/x/gone.stl" in said

    def test_handle_consolidation_writes_nothing_when_the_path_is_absent(self):
        """A path the row never listed is not a change to make."""
        loader = IncrementalFixturesLoader(create_mock_connection(), verbose=False)

        holder = {
            "id": "bp-1",
            "full_name": "tiles/x/a.stl",
            "consolidated_paths": ["tiles/x/still.stl"],
        }

        with (
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.get_blueprint_by_id",
                return_value=holder,
            ),
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.update_blueprint"
            ) as upd,
            patch("openforge.db.fixtures.incremental.write_output") as out,
        ):
            loader._handle_consolidation(
                Mock(), {"blueprint_id": "bp-1", "remove_path": "tiles/x/never.stl"}
            )

        upd.assert_not_called()
        out.assert_not_called()

    def test_handle_addition_leaves_a_live_row_alone(self):
        """A fresh duplicate of a file still in the fixture joins, never steals.

        Two identical files, both present, the second not yet listed: this is
        the ordinary consolidation case and the only thing standing between it
        and the rename branch. Taking the row over here would rewrite a live
        blueprint's name and delete the tags and images of a file nobody
        touched.
        """
        loader = IncrementalFixturesLoader(create_mock_connection(), verbose=False)
        loader.fixture_subset_path = "tiles/plain"
        loader.current_fixture_files = {"tiles/plain/a.stl", "tiles/plain/b.stl"}

        live_bp = {
            "id": "bp-1",
            "full_name": "tiles/plain/a.stl",
            "consolidated_paths": [],
        }

        new_item = create_mock_fixture_item("tiles/plain/b.stl", "md5-shared")
        new_item["file_metadata"]["file"] = "b.stl"

        updates = []

        with (
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.insert_blueprint",
                return_value=live_bp,
            ),
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.update_blueprint",
                side_effect=lambda curs, bid, data: updates.append(data),
            ),
            patch(
                "openforge.db.fixtures.incremental.tag_sql.delete_all_blueprint_tags"
            ) as del_tags,
            patch("openforge.db.fixtures.incremental.tag_sql.insert_tag"),
            patch(
                "openforge.db.fixtures.incremental.image_sql"
                ".delete_images_for_blueprint"
            ) as del_imgs,
            patch(
                "openforge.db.fixtures.incremental.image_sql.insert_image_for_blueprint"
            ),
            patch("openforge.db.fixtures.incremental.write_output") as out,
        ):
            loader._handle_addition(Mock(), new_item)

        # Consolidated, not renamed: the live row keeps its identity.
        assert updates == [{"consolidated_paths": ["tiles/plain/b.stl"]}]
        # An append is a state change, so it is said at default verbosity.
        said = "".join(c.args[0] for c in out.call_args_list)
        assert "tiles/plain/b.stl" in said and "tiles/plain/a.stl" in said
        assert "bp-1" not in loader._renamed_blueprint_ids
        # The untouched file's tags and images survive.
        del_tags.assert_not_called()
        del_imgs.assert_not_called()

    def test_apply_collects_candidates_before_applying_additions(self):
        """The candidate set has to exist before additions consult it.

        A duplicate inherits a row only when this load is deprecating it, so
        the set is built from changes.deprecated at the top of the apply. Built
        late, one fixture's takeovers would be judged against the previous
        fixture's candidates, which is the per-load leak the rename set beside
        it already guards against.
        """
        loader = IncrementalFixturesLoader(create_mock_connection(), verbose=False)
        loader.fixture_subset_path = "tiles/catacombs/thick_wall/loculus"
        loader.current_fixture_files = {"tiles/catacombs/thick_wall/loculus/b.stl"}

        holder = {
            "id": "bp-1",
            "full_name": "tiles/catacombs/thick_wall/a.stl",
            "file_md5": "md5-shared",
            "consolidated_paths": ["tiles/catacombs/thick_wall/loculus/b.stl"],
        }

        new_item = create_mock_fixture_item(
            "tiles/catacombs/thick_wall/loculus/b.stl", "md5-shared"
        )
        new_item["file_metadata"]["file"] = "b.stl"

        # The holder is declined because the addition takes its row over; the
        # second candidate has nothing to inherit it, so it is tombstoned. One
        # of each, through paths the loader can actually reach.
        doomed = {
            "id": "bp-2",
            "full_name": "tiles/catacombs/gone.stl",
            "file_md5": "md5-gone",
            # Tombstoning this strands the path listed here, which is the one
            # thing the deprecation step says out loud.
            "consolidated_paths": ["tiles/catacombs/stranded.stl"],
        }

        changes = ComparisonResult()
        changes.added = [new_item]
        changes.deprecated = [holder, doomed]

        cursor = Mock()
        cursor.fetchall = Mock(return_value=[])
        updates = []

        with (
            patch.object(loader, "_load_existing_blueprints", return_value={}),
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.insert_blueprint",
                return_value=holder,
            ),
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.update_blueprint",
                side_effect=lambda curs, bid, data: updates.append(data),
            ),
            patch(
                "openforge.db.fixtures.incremental.tag_sql.delete_all_blueprint_tags"
            ),
            patch("openforge.db.fixtures.incremental.tag_sql.insert_tag"),
            patch(
                "openforge.db.fixtures.incremental.image_sql"
                ".delete_images_for_blueprint"
            ),
            patch(
                "openforge.db.fixtures.incremental.image_sql.insert_image_for_blueprint"
            ),
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql"
                ".mark_blueprint_deprecated"
            ) as mark_dep,
            patch("openforge.db.fixtures.incremental.write_output") as out,
        ):
            loader._apply_changes_with_cursor(cursor, changes)

        said = "".join(c.args[0] for c in out.call_args_list)
        assert "tiles/catacombs/stranded.stl" in said

        # The takeover happened, which it can only do if the holder was a
        # known candidate while the addition was being applied.
        assert len(updates) == 1
        assert updates[0]["full_name"] == "tiles/catacombs/thick_wall/loculus/b.stl"
        assert "bp-1" in loader._renamed_blueprint_ids
        # The inherited row is spared and the other is tombstoned, so one
        # apply shows both outcomes.
        mark_dep.assert_called_once_with(ANY, "bp-2")
        assert changes.applied_deprecations == 1
        assert changes.declined_deprecations == [holder]
        assert changes.summary() == "1 added, 1 deprecated (1 left in place)"

    def test_is_rename_declines_a_listed_path_when_the_holder_survives(self):
        """A listed duplicate inherits a row that is going, and only that.

        The holder lives in another fixture file, so it is absent from this
        load's file set for a reason that has nothing to do with deletion. It
        is not deprecated and this load does not propose to deprecate it, so
        the row is not going anywhere and the path must stay a duplicate.
        """
        loader = IncrementalFixturesLoader(create_mock_connection(), verbose=False)
        loader.fixture_subset_path = "tiles/sewers"
        loader.current_fixture_files = {"tiles/sewers/b.stl"}

        bp = {
            "id": "bp-live",
            "full_name": "tiles/catacombs/a.stl",
            "consolidated_paths": ["tiles/sewers/b.stl"],
            "deprecated": False,
        }

        assert loader._is_rename(bp, "tiles/sewers/b.stl") is False

    def test_is_rename_takes_over_a_tombstoned_holder(self):
        """A deprecated holder is already gone, so its row can be revived.

        This is the only route by which a duplicate stranded by an earlier
        load gets a row again, and it reaches across namespaces because a
        tombstone is invisible to the consolidation gate.
        """
        loader = IncrementalFixturesLoader(create_mock_connection(), verbose=False)
        loader.fixture_subset_path = "tiles/sewers"
        loader.current_fixture_files = {"tiles/sewers/b.stl"}

        bp = {
            "id": "bp-dead",
            "full_name": "tiles/catacombs/a.stl",
            "consolidated_paths": ["tiles/sewers/b.stl"],
            "deprecated": True,
        }

        assert loader._is_rename(bp, "tiles/sewers/b.stl") is True

    def test_is_rename_needs_both_paths_in_the_subtree(self):
        """One path inside and one outside is not a rename within a fixture."""
        loader = IncrementalFixturesLoader(create_mock_connection(), verbose=False)
        loader.fixture_subset_path = "tiles/plain/floors"
        loader.current_fixture_files = {"tiles/plain/floors/new.stl"}

        # Holder inside the subtree, new path outside it.
        inside_holder = {"id": "bp-1", "full_name": "tiles/plain/floors/old.stl"}
        assert loader._is_rename(inside_holder, "tiles/plain/walls/new.stl") is False

        # Holder outside the subtree, new path inside it.
        outside_holder = {"id": "bp-2", "full_name": "tiles/plain/walls/old.stl"}
        assert loader._is_rename(outside_holder, "tiles/plain/floors/new.stl") is False

    def test_is_rename_subtree_stops_at_a_path_boundary(self):
        """`cave` must not claim `cavern`, which is a real namespace pair."""
        loader = IncrementalFixturesLoader(create_mock_connection(), verbose=False)
        loader.fixture_subset_path = "tiles/cave"
        loader.current_fixture_files = {"tiles/cavern/new.stl"}

        bp = {"id": "bp-1", "full_name": "tiles/cavern/old.stl"}

        assert loader._is_rename(bp, "tiles/cavern/new.stl") is False

    def test_is_rename_declines_without_a_subtree(self):
        """No detected subtree means no basis for calling a move a rename."""
        loader = IncrementalFixturesLoader(create_mock_connection(), verbose=False)
        loader.fixture_subset_path = None
        loader.current_fixture_files = {"tiles/plain/new.stl"}

        bp = {"id": "bp-1", "full_name": "tiles/plain/old.stl"}

        assert loader._is_rename(bp, "tiles/plain/new.stl") is False

    def test_handle_addition_revives_a_tombstone_at_the_same_path(self):
        """A file restored under its own name brings its row back with it.

        The rename branch is the only other place the flag is cleared, and it
        needs the path to change. Without this, a deleted-then-restored file
        has its tags rewritten onto a tombstone on every load while the output
        reports adding it.
        """
        loader = IncrementalFixturesLoader(create_mock_connection(), verbose=False)
        loader.fixture_subset_path = "tiles/plain"
        loader.current_fixture_files = {"tiles/plain/a.stl"}

        # Rescued by MD5; already at this path, so it can only be a tombstone.
        tombstone = {
            "id": "bp-1",
            "full_name": "tiles/plain/a.stl",
            "deprecated": True,
            "successor_id": "bp-replacement",
        }

        new_item = create_mock_fixture_item(
            "tiles/plain/a.stl",
            "md5-shared",
            tags=[["shape", "floor"]],
            images=[{"image_url": "https://example.test/a.png"}],
        )
        new_item["file_metadata"]["file"] = "a.stl"
        new_item["config"] = {"parts": ["pillar"]}

        updates = []
        events = []

        with (
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.insert_blueprint",
                return_value=tombstone,
            ),
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.update_blueprint",
                side_effect=lambda curs, bid, data: updates.append(data),
            ),
            patch(
                "openforge.db.fixtures.incremental.tag_sql.delete_all_blueprint_tags",
                side_effect=lambda *a: events.append("del_tags"),
            ),
            patch(
                "openforge.db.fixtures.incremental.tag_sql.insert_tag",
                side_effect=lambda *a: events.append("ins_tag"),
            ),
            patch(
                "openforge.db.fixtures.incremental.image_sql"
                ".delete_images_for_blueprint",
                side_effect=lambda *a: events.append("del_imgs"),
            ),
            patch(
                "openforge.db.fixtures.incremental.image_sql.insert_image_for_blueprint",
                side_effect=lambda *a: events.append("ins_img"),
            ),
            patch("openforge.db.fixtures.incremental.write_output") as out,
        ):
            loader._handle_addition(Mock(), new_item)

        # The successor goes with the tombstone: a live row that keeps one
        # sends the version-chain reader off to the wrong blueprint.
        (payload,) = updates
        assert payload["deprecated"] is False
        assert payload["successor_id"] is None
        # The row is this item now, so the fields a later comparison reads
        # have to be this item's rather than the tombstone's.
        assert payload["file_size"] == new_item["file_metadata"]["size"]
        assert (
            payload["file_modified_at"] == new_item["file_metadata"]["file_modified_at"]
        )
        assert payload["blueprint_config"] == new_item["config"]
        said = "".join(c.args[0] for c in out.call_args_list)
        # The discarded link is named here too, not only on a rename.
        assert "bp-replacement" in said
        # The resync has to precede the inserts, or the row comes back with
        # nothing on it.
        assert events == ["del_tags", "del_imgs", "ins_tag", "ins_img"]
        # Said at default verbosity.
        assert "tiles/plain/a.stl" in said

    def test_revival_says_nothing_about_a_successor_there_was_not(self):
        """The dropped-successor note belongs to rows that had one."""
        loader = IncrementalFixturesLoader(create_mock_connection(), verbose=False)
        loader.fixture_subset_path = "tiles/plain"
        loader.current_fixture_files = {"tiles/plain/a.stl"}

        tombstone = {
            "id": "bp-1",
            "full_name": "tiles/plain/a.stl",
            "deprecated": True,
            "successor_id": None,
        }

        new_item = create_mock_fixture_item("tiles/plain/a.stl", "md5-shared")
        new_item["file_metadata"]["file"] = "a.stl"

        with (
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.insert_blueprint",
                return_value=tombstone,
            ),
            patch("openforge.db.fixtures.incremental.blueprint_sql.update_blueprint"),
            patch(
                "openforge.db.fixtures.incremental.tag_sql.delete_all_blueprint_tags"
            ),
            patch("openforge.db.fixtures.incremental.tag_sql.insert_tag"),
            patch(
                "openforge.db.fixtures.incremental.image_sql"
                ".delete_images_for_blueprint"
            ),
            patch(
                "openforge.db.fixtures.incremental.image_sql.insert_image_for_blueprint"
            ),
            patch("openforge.db.fixtures.incremental.write_output") as out,
        ):
            loader._handle_addition(Mock(), new_item)

        said = "".join(c.args[0] for c in out.call_args_list)
        assert "RESTORED" in said
        assert "dropped successor" not in said

    def test_handle_addition_does_not_touch_a_live_row_at_the_same_path(self):
        """An ordinary insert is not a revival, so nothing is rewritten."""
        loader = IncrementalFixturesLoader(create_mock_connection(), verbose=False)
        loader.fixture_subset_path = "tiles/plain"
        loader.current_fixture_files = {"tiles/plain/a.stl"}

        fresh = {
            "id": "bp-1",
            "full_name": "tiles/plain/a.stl",
            "deprecated": False,
            "successor_id": None,
        }

        new_item = create_mock_fixture_item("tiles/plain/a.stl", "md5-new")
        new_item["file_metadata"]["file"] = "a.stl"

        updates = []

        with (
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.insert_blueprint",
                return_value=fresh,
            ),
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql.update_blueprint",
                side_effect=lambda curs, bid, data: updates.append(data),
            ),
            patch(
                "openforge.db.fixtures.incremental.tag_sql.delete_all_blueprint_tags"
            ) as del_tags,
            patch("openforge.db.fixtures.incremental.tag_sql.insert_tag"),
            patch(
                "openforge.db.fixtures.incremental.image_sql"
                ".delete_images_for_blueprint"
            ) as del_imgs,
            patch(
                "openforge.db.fixtures.incremental.image_sql.insert_image_for_blueprint"
            ),
        ):
            loader._handle_addition(Mock(), new_item)

        assert updates == []
        del_tags.assert_not_called()
        del_imgs.assert_not_called()

    def test_renamed_id_skips_deprecation(self):
        """A bp id added to _renamed_blueprint_ids during a load must
        not be re-deprecated by _handle_deprecation in the same load."""
        loader = self._rename_loader()
        loader._renamed_blueprint_ids.add("bp-1")

        deprecated_bp = {"id": "bp-1", "file_md5": "md5-shared"}

        with (
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql"
                ".mark_blueprint_deprecated"
            ) as mark_dep,
            patch(
                "openforge.db.fixtures.incremental.tag_sql.delete_all_blueprint_tags"
            ) as del_tags,
            patch(
                "openforge.db.fixtures.incremental.image_sql"
                ".delete_images_for_blueprint"
            ) as del_imgs,
        ):
            applied = loader._handle_deprecation(Mock(), deprecated_bp)

        # The caller counts this return, so a decline has to report one.
        assert applied is False
        # The skip path means none of the deprecation side-effects fire.
        mark_dep.assert_not_called()
        del_tags.assert_not_called()
        del_imgs.assert_not_called()

    def test_summary_reports_what_was_applied_not_what_was_proposed(self):
        """A load that renamed every row in place deprecated none of them."""
        result = ComparisonResult()
        result.added = [{}] * 236
        result.modified = [{}] * 3
        result.deprecated = [{}] * 236

        assert result.summary() == "236 added, 3 modified, 236 deprecated"

        result.applied_deprecations = 0
        assert result.summary() == (
            "236 added, 3 modified, 0 deprecated (236 left in place)"
        )

    def test_summary_reports_a_partial_deprecation(self):
        """Some applied and some declined names both figures."""
        result = ComparisonResult()
        result.deprecated = [{}] * 10

        result.applied_deprecations = 4
        assert result.summary() == "4 deprecated (6 left in place)"

    def test_summary_says_nothing_was_left_when_all_were_applied(self):
        """The ordinary load: every candidate tombstoned, no trailing clause."""
        result = ComparisonResult()
        result.deprecated = [{}] * 10

        result.applied_deprecations = 10
        assert result.summary() == "10 deprecated"

    def test_apply_changes_resets_per_load_counters(self):
        """Per-apply state must reset at the top so one fixture cannot
        inflate the next: a loader instance serves a whole directory."""
        loader = self._rename_loader()
        loader._renamed_blueprint_ids.add("stale-id-from-prior-load")

        loader._deprecation_candidates = {"stale-candidate"}

        empty_changes = ComparisonResult()
        empty_changes.applied_deprecations = 5
        empty_changes.declined_deprecations = [{"id": "stale-declined"}]

        # _link_deprecated_to_successors runs at the end and calls
        # cursor.fetchall(); make it return an empty list.
        cursor = Mock()
        cursor.fetchall = Mock(return_value=[])

        with patch.object(loader, "_load_existing_blueprints", return_value={}):
            loader._apply_changes_with_cursor(cursor, empty_changes)

        assert loader._renamed_blueprint_ids == set()
        assert loader._deprecation_candidates == set()
        assert empty_changes.applied_deprecations == 0
        assert empty_changes.declined_deprecations == []


class TestEditThenLoadAgainstTheDatabase:
    """The loader has to survive its own output against the real schema.

    Every other test here mocks the SQL layer, so the one thing none of them
    can see is a constraint. An edited file supersedes a row at the same path,
    and only one live row per path is allowed, so the order the apply writes in
    is load-bearing rather than incidental.
    """

    PATH = "tiles/plain/edit_me.stl"

    def _item_at(self, path, md5):
        item = self._item(md5)
        item["file_metadata"]["full_name"] = path
        item["file_metadata"]["file"] = path.split("/")[-1]
        return item

    def _item(self, md5):
        return {
            "type": "model",
            "file_metadata": {
                "full_name": self.PATH,
                "file": "edit_me.stl",
                "md5": md5,
                "size": 1000,
                "file_modified_at": "2020-01-01T12:00:00",
            },
            "tags": ["shape|floor"],
            "images": [],
            "config": {},
        }

    def _load(self, test_db, md5):
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                loader = IncrementalFixturesLoader(conn, verbose=False)
                changes = loader.compare_fixture_data([self._item(md5)], curs=curs)
                loader.apply_incremental_changes(changes, curs=curs)
            conn.commit()

    def test_editing_a_file_leaves_one_live_row_linked_to_its_predecessor(
        self, test_db
    ):
        self._load(test_db, "md5-before")
        self._load(test_db, "md5-after")

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute(
                    "SELECT id, file_md5, deprecated, successor_id"
                    "  FROM blueprints WHERE full_name = %s"
                    " ORDER BY created_at",
                    (self.PATH,),
                )
                rows = curs.fetchall()

        assert len(rows) == 2
        old, new = rows
        assert old["file_md5"] == "md5-before"
        assert old["deprecated"] is True
        assert new["file_md5"] == "md5-after"
        assert new["deprecated"] is False
        # The tombstone points at what replaced it, which is what the catalog
        # follows to answer for the old bytes.
        assert old["successor_id"] == new["id"]

    def test_editing_a_holder_does_not_orphan_its_duplicate(self, test_db):
        """A path consolidated into an edited row has to end up with a row.

        The holder is superseded, so the row that carried both paths becomes a
        tombstone. The duplicate's bytes are unchanged, so it inherits that
        tombstone under its own path rather than losing its only
        representation — and a second load has nothing left to do.
        """
        holder, dupe = "tiles/a/p.stl", "tiles/a/q.stl"

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute(
                    "INSERT INTO blueprints (blueprint_name, blueprint_type,"
                    " full_name, file_md5, file_name, config, consolidated_paths)"
                    " VALUES ('p.stl','model',%s,'M_old','p.stl','{}',%s)",
                    (holder, [dupe]),
                )
            conn.commit()

        def load():
            with test_db.connection() as conn:
                with conn.cursor(row_factory=dict_row) as curs:
                    loader = IncrementalFixturesLoader(conn, verbose=False)
                    data = [
                        self._item_at(holder, "M_new"),
                        self._item_at(dupe, "M_old"),
                    ]
                    changes = loader.compare_fixture_data(data, curs=curs)
                    loader.apply_incremental_changes(changes, curs=curs)
                conn.commit()

        def live_paths():
            with test_db.connection() as conn:
                with conn.cursor(row_factory=dict_row) as curs:
                    curs.execute(
                        "SELECT full_name, file_md5 FROM blueprints"
                        " WHERE NOT deprecated AND full_name IS NOT NULL"
                        " ORDER BY full_name"
                    )
                    return [(r["full_name"], r["file_md5"]) for r in curs.fetchall()]

        load()
        assert live_paths() == [(holder, "M_new"), (dupe, "M_old")]

        # And it settles: a second identical load changes nothing.
        load()
        assert live_paths() == [(holder, "M_new"), (dupe, "M_old")]

    def test_every_live_fixture_path_is_answerable_after_a_load(self, test_db):
        """The property a load exists to establish, stated positively.

        A path is answerable if a live row holds it or a live row lists it as
        a duplicate. An entry the fixture itself marks deprecated is excluded:
        asking for no live row is the whole point of that flag, and exactly
        one path in the catalog is in that position.
        """
        plain = "tiles/inv/plain.stl"
        holder, twin = "tiles/inv/holder.stl", "tiles/inv/twin.stl"
        retired = "tiles/inv/retired.stl"

        items = [
            self._item_at(plain, "M_plain"),
            self._item_at(holder, "M_shared"),
            self._item_at(twin, "M_shared"),
            self._item_at(retired, "M_retired"),
        ]
        items[3]["deprecated"] = True

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute("TRUNCATE blueprints CASCADE")
            conn.commit()

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                loader = IncrementalFixturesLoader(conn, verbose=False)
                changes = loader.compare_fixture_data(items, curs=curs)
                loader.apply_incremental_changes(changes, curs=curs)
            conn.commit()

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute(
                    "SELECT full_name, consolidated_paths FROM blueprints"
                    " WHERE NOT deprecated AND full_name IS NOT NULL"
                )
                live = curs.fetchall()

        answerable = {r["full_name"] for r in live}
        for row in live:
            answerable |= set(row["consolidated_paths"] or [])

        expected = {
            item["file_metadata"]["full_name"]
            for item in items
            if not item.get("deprecated")
        }
        assert expected <= answerable, expected - answerable
        # And the retired one is genuinely absent rather than quietly live.
        assert retired not in answerable

    def test_a_revived_row_drops_duplicates_that_diverged(self, test_db):
        """A revived row must not claim a path that now has its own row.

        The prune that normally removes a diverged duplicate only sees live
        rows, so a holder tombstoned earlier in the same directory load is
        invisible to it and comes back carrying a listing that is no longer
        true.
        """
        holder = "tiles/alpha/h.stl"
        kept, diverged = "tiles/beta/p.stl", "tiles/beta/q.stl"

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute("TRUNCATE blueprints CASCADE")
                curs.execute(
                    "INSERT INTO blueprints (blueprint_name, blueprint_type,"
                    " full_name, file_md5, file_name, config, consolidated_paths,"
                    " deprecated)"
                    " VALUES ('h.stl','model',%s,'M_x','h.stl','{}',%s,true)",
                    (holder, [kept, diverged]),
                )
            conn.commit()

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                loader = IncrementalFixturesLoader(conn, verbose=False)
                changes = loader.compare_fixture_data(
                    [self._item_at(kept, "M_x"), self._item_at(diverged, "M_z")],
                    curs=curs,
                )
                loader.apply_incremental_changes(changes, curs=curs)
            conn.commit()

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute(
                    "SELECT full_name, file_md5, consolidated_paths FROM blueprints"
                    " WHERE NOT deprecated ORDER BY full_name"
                )
                live = curs.fetchall()

        by_path = {r["full_name"]: r for r in live}
        # The tombstone was inherited under the path that kept its bytes, and
        # the diverged path got a row of its own.
        assert by_path[kept]["file_md5"] == "M_x"
        assert by_path[diverged]["file_md5"] == "M_z"
        # No live row speaks for a path that another live row owns.
        owned = set(by_path)
        for row in live:
            assert not (set(row["consolidated_paths"] or []) & owned)

    def test_a_tombstone_is_linked_to_the_row_that_claimed_its_path(self, test_db):
        """An edit whose new bytes already exist elsewhere still leaves a trail.

        The replacement never becomes a row of its own: it is rescued onto the
        row that already holds those bytes, which then lists this path as a
        duplicate. Nothing holds the path any more, so a link by path finds
        nothing and a lookup by the old MD5 would stop on the tombstone.
        """
        edited, twin = "tiles/a/p.stl", "tiles/a/q.stl"

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute("TRUNCATE blueprints CASCADE")
                for path, md5, name in (
                    (edited, "M_old", "p.stl"),
                    (twin, "M_new", "q.stl"),
                ):
                    curs.execute(
                        "INSERT INTO blueprints (blueprint_name, blueprint_type,"
                        " full_name, file_md5, file_name, config)"
                        " VALUES (%s,'model',%s,%s,%s,'{}')",
                        (name, path, md5, name),
                    )
            conn.commit()

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                loader = IncrementalFixturesLoader(conn, verbose=False)
                changes = loader.compare_fixture_data(
                    [self._item_at(edited, "M_new"), self._item_at(twin, "M_new")],
                    curs=curs,
                )
                loader.apply_incremental_changes(changes, curs=curs)
            conn.commit()

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute(
                    "SELECT id, file_md5, deprecated, successor_id, full_name,"
                    " consolidated_paths FROM blueprints ORDER BY file_md5"
                )
                rows = {r["file_md5"]: r for r in curs.fetchall()}

        old, new = rows["M_old"], rows["M_new"]
        assert old["deprecated"] is True
        # The row that took the path over is the one the chain has to reach.
        assert old["successor_id"] == new["id"]
        assert new["deprecated"] is False
        assert edited in (new["consolidated_paths"] or [])

    def test_a_file_moved_across_fixtures_inherits_the_tombstone(self, test_db):
        """A tombstone is inheritable wherever it lies.

        The subtree test guards a live row's path, and a tombstone has no path
        to guard. Declining the inheritance appends this live file's path to
        the dead row instead, which leaves the file with no live row at all
        and reports it as added.
        """
        old_path, new_path = "tiles/old/moved.stl", "tiles/new/moved.stl"

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute("TRUNCATE blueprints CASCADE")
                curs.execute(
                    "INSERT INTO blueprints (blueprint_name, blueprint_type,"
                    " full_name, file_md5, file_name, config, deprecated)"
                    " VALUES ('moved.stl','model',%s,'M_moved','moved.stl','{}',true)",
                    (old_path,),
                )
            conn.commit()

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                loader = IncrementalFixturesLoader(conn, verbose=False)
                changes = loader.compare_fixture_data(
                    [self._item_at(new_path, "M_moved")], curs=curs
                )
                loader.apply_incremental_changes(changes, curs=curs)
            conn.commit()

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute(
                    "SELECT full_name, consolidated_paths FROM blueprints"
                    " WHERE NOT deprecated"
                )
                live = curs.fetchall()
                curs.execute("SELECT count(*) AS n FROM blueprints")
                total = curs.fetchone()["n"]

        # The file has a row of its own, and it is the one that already held
        # these bytes rather than a second row beside it.
        assert [r["full_name"] for r in live] == [new_path]
        assert total == 1
        assert not (live[0]["consolidated_paths"] or [])

    def test_a_modification_keeps_the_duplicates_the_row_speaks_for(self, test_db):
        """The listing is this loader's bookkeeping, and no fixture declares it.

        The munge defaults the key to empty and the update writes any key it
        is given, so sending it on a modification drops every path the row
        holds — and those paths have no row of their own to fall back on.
        """
        holder, dupe = "tiles/a/p.stl", "tiles/a/q.stl"

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute("TRUNCATE blueprints CASCADE")
                # An mtime the fixture disagrees with, so the load reports a
                # modification rather than no change.
                curs.execute(
                    "INSERT INTO blueprints (blueprint_name, blueprint_type,"
                    " full_name, file_md5, file_name, config, consolidated_paths,"
                    " file_modified_at)"
                    " VALUES ('p.stl','model',%s,'M_same','p.stl','{}',%s,"
                    " '2019-01-01 00:00:00')",
                    (holder, [dupe]),
                )
            conn.commit()

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                loader = IncrementalFixturesLoader(conn, verbose=False)
                changes = loader.compare_fixture_data(
                    [self._item_at(holder, "M_same")], curs=curs
                )
                assert len(changes.modified) == 1
                loader.apply_incremental_changes(changes, curs=curs)
            conn.commit()

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute(
                    "SELECT consolidated_paths FROM blueprints WHERE full_name = %s",
                    (holder,),
                )
                assert curs.fetchone()["consolidated_paths"] == [dupe]

    def test_the_stranding_warning_waits_for_the_additions(self, test_db):
        """The warning has to describe what happened, not what was attempted.

        Superseding a holder tombstones the row that listed its duplicates,
        but the additions that follow usually revive it under one of them.
        Warned before they run, every ordinary edit of a holder names paths
        that are about to be fine.
        """
        holder, dupe = "tiles/a/p.stl", "tiles/a/q.stl"
        elsewhere = "tiles/b/r.stl"

        def seed(listed=None):
            with test_db.connection() as conn:
                with conn.cursor(row_factory=dict_row) as curs:
                    curs.execute("TRUNCATE blueprints CASCADE")
                    curs.execute(
                        "INSERT INTO blueprints (blueprint_name, blueprint_type,"
                        " full_name, file_md5, file_name, config,"
                        " consolidated_paths)"
                        " VALUES ('p.stl','model',%s,'M_old','p.stl','{}',%s)",
                        (holder, listed if listed is not None else [dupe]),
                    )
                conn.commit()

        def load(data):
            with (
                patch("openforge.db.fixtures.incremental.write_output") as out,
                test_db.connection() as conn,
            ):
                with conn.cursor(row_factory=dict_row) as curs:
                    loader = IncrementalFixturesLoader(conn, verbose=False)
                    changes = loader.compare_fixture_data(data, curs=curs)
                    loader.apply_incremental_changes(changes, curs=curs)
                conn.commit()
            return "".join(c.args[0] for c in out.call_args_list)

        # The duplicate is in the fixture, so it inherits the tombstone and
        # nothing is stranded.
        seed()
        said = load([self._item_at(holder, "M_new"), self._item_at(dupe, "M_old")])
        assert "consolidated into" not in said

        # Re-exported together, so nothing is renamed and the suppression
        # above cannot fire — but the duplicate is still listed, so it has an
        # addition of its own and is not stranded either.
        seed()
        said = load([self._item_at(holder, "M_new"), self._item_at(dupe, "M_new")])
        assert "consolidated into" not in said

        # A path in another fixture cannot be checked against this one, so the
        # suppression has to come from the row surviving: it is live at the
        # duplicate's path and still lists the far one.
        seed([dupe, elsewhere])
        said = load([self._item_at(holder, "M_new"), self._item_at(dupe, "M_old")])
        assert "consolidated into" not in said

        # The duplicate is gone from the fixture, so the tombstone really does
        # take its only row with it, and that still has to be said.
        seed()
        said = load([self._item_at(holder, "M_new")])
        assert "consolidated into" in said
        assert dupe in said

    def test_editing_one_file_while_another_takes_its_bytes(self, test_db):
        """Edit a file and rename a second onto the bytes it gave up.

        The ordinary workflow, and the only load where the superseded phase,
        the takeover and the index all fire together: `old.stl` is superseded,
        so its row becomes a tombstone still holding the original MD5, and
        `new.stl` carries exactly those bytes and has to inherit it.
        """
        old_path, new_path = "tiles/plain/old.stl", "tiles/plain/new.stl"

        def load(items):
            with test_db.connection() as conn:
                with conn.cursor(row_factory=dict_row) as curs:
                    loader = IncrementalFixturesLoader(conn, verbose=False)
                    changes = loader.compare_fixture_data(items, curs=curs)
                    loader.apply_incremental_changes(changes, curs=curs)
                conn.commit()

        def live():
            with test_db.connection() as conn:
                with conn.cursor(row_factory=dict_row) as curs:
                    curs.execute(
                        "SELECT full_name, file_md5 FROM blueprints"
                        " WHERE NOT deprecated AND full_name IS NOT NULL"
                        " ORDER BY full_name"
                    )
                    return [(r["full_name"], r["file_md5"]) for r in curs.fetchall()]

        load([self._item_at(old_path, "X")])
        load([self._item_at(old_path, "Y"), self._item_at(new_path, "X")])

        assert live() == [(new_path, "X"), (old_path, "Y")]
        # And it settles.
        load([self._item_at(old_path, "Y"), self._item_at(new_path, "X")])
        assert live() == [(new_path, "X"), (old_path, "Y")]

    def test_an_inherited_row_stops_reporting_changes(self, test_db):
        """The row is the new item now, so its fields have to be the new item's.

        An inherited modification time makes the next load of an unchanged
        fixture report a modification, and a modification resets
        consolidated_paths — so the holder's other duplicates lose every
        representation for a load. Real duplicate groups disagree on mtime, so
        this is the common case rather than a contrived one.
        """
        holder, dupe = "tiles/a/holder.stl", "tiles/a/dupe.stl"

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute(
                    "INSERT INTO blueprints (blueprint_name, blueprint_type,"
                    " full_name, file_md5, file_name, config, consolidated_paths,"
                    " file_modified_at)"
                    " VALUES ('holder.stl','model',%s,'M_old','holder.stl','{}',%s,"
                    " '2020-01-01T00:00:00')",
                    (holder, [dupe]),
                )
            conn.commit()

        def load():
            with test_db.connection() as conn:
                with conn.cursor(row_factory=dict_row) as curs:
                    loader = IncrementalFixturesLoader(conn, verbose=False)
                    data = [
                        self._item_at(holder, "M_new"),
                        self._item_at(dupe, "M_old"),
                    ]
                    changes = loader.compare_fixture_data(data, curs=curs)
                    loader.apply_incremental_changes(changes, curs=curs)
                conn.commit()
                return changes

        load()
        settled = load()

        # Nothing changed on disk, so nothing is reported.
        assert len(settled.added) == 0
        assert len(settled.modified) == 0
        assert len(settled.deprecated) == 0

    def test_a_revived_row_is_not_reported_as_deprecated(self, test_db):
        """The superseded phase runs before the only thing that undoes it.

        Editing a file and renaming another onto its old bytes tombstones the
        first row and then revives it under the new path, so nothing ends up
        deprecated. A count taken before the additions says otherwise, which is
        the same false report this series began with.
        """
        old_path, new_path = "tiles/plain/old.stl", "tiles/plain/new.stl"

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                loader = IncrementalFixturesLoader(conn, verbose=False)
                first = loader.compare_fixture_data(
                    [self._item_at(old_path, "X")], curs=curs
                )
                loader.apply_incremental_changes(first, curs=curs)
            conn.commit()

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                loader = IncrementalFixturesLoader(conn, verbose=False)
                changes = loader.compare_fixture_data(
                    [self._item_at(old_path, "Y"), self._item_at(new_path, "X")],
                    curs=curs,
                )
                # The old row is a candidate: its path is staying, its bytes are not.
                assert len(changes.deprecated) == 1
                loader.apply_incremental_changes(changes, curs=curs)
            conn.commit()

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute("SELECT count(*) AS n FROM blueprints WHERE deprecated")
                tombstones = curs.fetchone()["n"]

        # Nothing is deprecated in the database, so nothing may be reported as
        # deprecated either.
        assert tombstones == 0
        assert changes.applied_deprecations == 0
        assert len(changes.declined_deprecations) == 1
        assert "0 deprecated (1 left in place)" in changes.summary()

    def test_one_loader_does_not_carry_md5s_between_fixture_files(self):
        """load_fixtures reuses one loader for every file in the directory.

        So the map of what each path currently holds has to be rebuilt per
        file. Carried over, a path listed in the previous fixture reads as
        unchanged in this one and the row it duplicates is tombstoned under it.
        """
        mock_loader = IncrementalFixturesLoader(create_mock_connection(), verbose=False)
        mock_loader.existing_blueprints = {}
        mock_loader.compare_fixture_data(
            [create_mock_fixture_item("tiles/a/first.stl", "md5-first")],
            skip_load_existing=True,
        )
        assert mock_loader.current_fixture_md5s == {"tiles/a/first.stl": "md5-first"}

        mock_loader.compare_fixture_data(
            [create_mock_fixture_item("tiles/b/second.stl", "md5-second")],
            skip_load_existing=True,
        )
        assert mock_loader.current_fixture_md5s == {"tiles/b/second.stl": "md5-second"}
        assert mock_loader.current_fixture_files == {"tiles/b/second.stl"}

    def test_loading_the_same_bytes_twice_changes_nothing(self, test_db):
        self._load(test_db, "md5-stable")
        self._load(test_db, "md5-stable")

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute(
                    "SELECT count(*) AS n FROM blueprints WHERE full_name = %s",
                    (self.PATH,),
                )
                assert curs.fetchone()["n"] == 1
