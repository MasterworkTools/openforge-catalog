"""Test that incremental fixtures prevent duplicate deprecated entries per MD5."""

from unittest.mock import MagicMock

from openforge.db.fixtures.incremental import IncrementalFixturesLoader


class TestDuplicateDeprecationPrevention:
    """Test prevention of duplicate deprecated entries with same MD5."""

    def test_prevents_duplicate_deprecated_entries_by_md5(self):
        """Test that we don't create multiple deprecated entries for the same MD5."""
        # Create a mock connection
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs

        # Create loader
        loader = IncrementalFixturesLoader(mock_conn, verbose=True)

        # Mock to return an existing deprecated entry
        existing_deprecated = {
            "id": "deprecated-123",
            "blueprint_name": "old_file.stl",
            "file_md5": "abc123",
            "deprecated": True,
            "tags": [],
            "images": [],
        }
        loader._find_deprecated_blueprint_by_md5 = MagicMock(
            return_value=existing_deprecated
        )

        # Blueprint to deprecate (same MD5 as existing deprecated)
        blueprint_to_deprecate = {
            "id": "active-456",
            "blueprint_name": "new_file.stl",
            "file_md5": "abc123",  # Same MD5 as existing deprecated
            "deprecated": False,
        }

        # Call _handle_deprecation
        loader._handle_deprecation(mock_curs, blueprint_to_deprecate)

        # Verify that we checked for existing deprecated entry
        loader._find_deprecated_blueprint_by_md5.assert_called_once_with("abc123")

        # Verify that we did NOT mark the blueprint as deprecated
        # (no database operations should have been called)
        assert not mock_curs.execute.called

    def test_creates_deprecated_entry_when_no_duplicate_exists(self):
        """Test that we create deprecated entry when no duplicate MD5 exists."""
        # Create a mock connection
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs

        # Create loader
        loader = IncrementalFixturesLoader(mock_conn, verbose=False)

        # Mock to return None (no existing deprecated)
        loader._find_deprecated_blueprint_by_md5 = MagicMock(return_value=None)

        # Blueprint to deprecate
        blueprint_to_deprecate = {
            "id": "active-456",
            "blueprint_name": "file.stl",
            "file_md5": "abc123",
            "deprecated": False,
        }

        # Mock the SQL module functions
        import openforge.db.sql.blueprints as blueprint_sql
        import openforge.db.sql.images as image_sql
        import openforge.db.sql.tags as tag_sql

        # Save original functions
        orig_delete_tags = tag_sql.delete_all_blueprint_tags
        orig_delete_images = image_sql.delete_images_for_blueprint
        orig_mark_deprecated = blueprint_sql.mark_blueprint_deprecated

        try:
            tag_sql.delete_all_blueprint_tags = MagicMock()
            image_sql.delete_images_for_blueprint = MagicMock()
            blueprint_sql.mark_blueprint_deprecated = MagicMock()

            # Call _handle_deprecation
            loader._handle_deprecation(mock_curs, blueprint_to_deprecate)

            # Verify that we checked for existing deprecated entry
            loader._find_deprecated_blueprint_by_md5.assert_called_once_with("abc123")

            # Verify that we DID mark the blueprint as deprecated
            tag_sql.delete_all_blueprint_tags.assert_called_once_with(
                mock_curs, "active-456"
            )
            image_sql.delete_images_for_blueprint.assert_called_once_with(
                mock_curs, "active-456"
            )
            blueprint_sql.mark_blueprint_deprecated.assert_called_once_with(
                mock_curs, "active-456"
            )
        finally:
            # Restore original functions
            tag_sql.delete_all_blueprint_tags = orig_delete_tags
            image_sql.delete_images_for_blueprint = orig_delete_images
            blueprint_sql.mark_blueprint_deprecated = orig_mark_deprecated

    def test_compare_fixture_data_skips_duplicate_deprecated_in_legacy_mode(self):
        """Test that duplicate deprecated entries are skipped in legacy mode."""
        # Create a mock connection
        mock_conn = MagicMock()
        mock_curs = MagicMock()

        # Create loader
        loader = IncrementalFixturesLoader(mock_conn, verbose=False)

        # Mock existing blueprints (one that would be deprecated)
        existing_blueprints = {
            "old_file.stl": {
                "id": "active-123",
                "full_name": "old_file.stl",
                "file_md5": "abc123",
                "blueprint_type": "model",
                "deprecated": False,
                "tags": [],
                "images": [],
            }
        }

        # Mock _load_existing_blueprints to return our test data
        loader._load_existing_blueprints = MagicMock(return_value=existing_blueprints)

        # Mock find_deprecated_blueprint_by_md5 to simulate existing deprecated entry
        existing_deprecated = {
            "id": "deprecated-999",
            "file_md5": "abc123",
            "deprecated": True,
        }
        loader._find_deprecated_blueprint_by_md5 = MagicMock(
            return_value=existing_deprecated
        )

        # Fixture data with at least one file-based blueprint
        # This is needed to trigger the deprecation logic
        # Use a different path to avoid namespace detection
        fixture_data = [
            {
                "file_metadata": {
                    "full_name": "some_other_file.stl",
                    "md5": "def456",
                },
                "name": "Some Other File",
                "blueprint_type": "model",
                "deprecated": False,
            }
        ]

        # Call compare_fixture_data
        result = loader.compare_fixture_data(fixture_data, curs=mock_curs)

        # Verify that no blueprints were marked for deprecation
        # (because one with the same MD5 already exists)
        assert len(result.deprecated) == 0

        # Verify we checked for existing deprecated
        loader._find_deprecated_blueprint_by_md5.assert_called_once_with("abc123")
