"""
Tests for incremental fixtures loading functionality.
"""

from unittest.mock import Mock, patch

import pytest

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
        """Test compare_fixture_data with version change (MD5 different)."""
        mock_loader.existing_blueprints = {
            "version_change.stl": create_mock_blueprint("version_change.stl", "old789")
        }

        fixture_data = [create_mock_fixture_item("version_change.stl", "new789")]

        result = mock_loader.compare_fixture_data(fixture_data, skip_load_existing=True)

        # Version changes now only create a new addition
        # (deprecation is handled in post-processing)
        assert len(result.added) == 1
        assert result.added[0]["file_metadata"]["full_name"] == "version_change.stl"
        assert len(result.modified) == 0
        assert len(result.deprecated) == 0  # Deprecation is handled in post-processing

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
        mock_loader.existing_blueprints = {
            "existing.stl": create_mock_blueprint("existing.stl", "abc123"),
            "modified.stl": create_mock_blueprint(
                "modified.stl", "def456", tags=[["old", "tag"]]
            ),
            "version_change.stl": create_mock_blueprint("version_change.stl", "old789"),
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

        assert len(result.deprecated) == 0  # Deprecation is handled in post-processing

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
            loader._handle_deprecation(Mock(), deprecated_bp)

        # The skip path means none of the deprecation side-effects fire.
        mark_dep.assert_not_called()
        del_tags.assert_not_called()
        del_imgs.assert_not_called()

    def test_apply_changes_resets_renamed_ids_per_load(self):
        """_renamed_blueprint_ids must reset at the top of each apply so
        state from one fixture doesn't leak into the next."""
        loader = self._rename_loader()
        loader._renamed_blueprint_ids.add("stale-id-from-prior-load")

        empty_changes = ComparisonResult()

        # _link_deprecated_to_successors runs at the end and calls
        # cursor.fetchall(); make it return an empty list.
        cursor = Mock()
        cursor.fetchall = Mock(return_value=[])

        with patch.object(loader, "_load_existing_blueprints", return_value={}):
            loader._apply_changes_with_cursor(cursor, empty_changes)

        assert loader._renamed_blueprint_ids == set()
