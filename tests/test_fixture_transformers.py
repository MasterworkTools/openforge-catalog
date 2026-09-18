"""
Unit tests for fixture transformers.
"""

import pytest

from openforge.data.transformers import (
    DeprecatedEntryTransformer,
    TagArrayToPipeTransformer,
    TimestampFieldTransformer,
)


class TestTagArrayToPipeTransformer:
    """Test cases for TagArrayToPipeTransformer."""

    def test_test_no_transformation_needed_not_deprecated(self):
        """Test that non-deprecated entries don't need transformation."""
        transformer = TagArrayToPipeTransformer()
        fixture = {
            "deprecated": False,
            "tags": [["shape", "floor"], ["texture", "stone"]],
        }

        assert not transformer.test(fixture)

    def test_test_no_transformation_needed_no_tags(self):
        """Test that entries without tags don't need transformation."""
        transformer = TagArrayToPipeTransformer()
        fixture = {"deprecated": True, "tags": []}

        assert not transformer.test(fixture)

    def test_test_no_transformation_needed_already_pipe_format(self):
        """Test that entries with pipe format tags don't need transformation."""
        transformer = TagArrayToPipeTransformer()
        fixture = {"deprecated": True, "tags": ["shape|floor", "texture|stone"]}

        assert not transformer.test(fixture)

    def test_test_transformation_needed_array_tags(self):
        """Test that entries with array tags need transformation."""
        transformer = TagArrayToPipeTransformer()
        fixture = {
            "deprecated": True,
            "tags": [["shape", "floor"], ["texture", "stone"]],
        }

        assert transformer.test(fixture)

    def test_test_transformation_needed_mixed_tags(self):
        """Test that entries with mixed format tags need transformation."""
        transformer = TagArrayToPipeTransformer()
        fixture = {"deprecated": True, "tags": [["shape", "floor"], "texture|stone"]}

        assert transformer.test(fixture)

    def test_apply_no_transformation(self):
        """Test that non-deprecated entries are returned unchanged."""
        transformer = TagArrayToPipeTransformer()
        fixture = {"deprecated": False, "tags": [["shape", "floor"]]}

        result = transformer.apply(fixture)
        assert result == fixture

    def test_apply_converts_array_tags(self):
        """Test that array tags are converted to pipe format."""
        transformer = TagArrayToPipeTransformer()
        fixture = {
            "deprecated": True,
            "tags": [["shape", "floor"], ["texture", "stone"]],
        }

        result = transformer.apply(fixture)

        expected = {"deprecated": True, "tags": ["shape|floor", "texture|stone"]}
        assert result == expected

    def test_apply_preserves_pipe_tags(self):
        """Test that pipe format tags are preserved."""
        transformer = TagArrayToPipeTransformer()
        fixture = {"deprecated": True, "tags": ["shape|floor", "texture|stone"]}

        result = transformer.apply(fixture)
        assert result == fixture

    def test_apply_handles_mixed_tags(self):
        """Test that mixed format tags are handled correctly."""
        transformer = TagArrayToPipeTransformer()
        fixture = {"deprecated": True, "tags": [["shape", "floor"], "texture|stone"]}

        result = transformer.apply(fixture)

        expected = {"deprecated": True, "tags": ["shape|floor", "texture|stone"]}
        assert result == expected

    def test_apply_handles_non_string_items(self):
        """Test that non-string items in arrays are converted to strings."""
        transformer = TagArrayToPipeTransformer()
        fixture = {
            "deprecated": True,
            "tags": [["shape", "floor", 1], ["texture", "stone"]],
        }

        result = transformer.apply(fixture)

        expected = {"deprecated": True, "tags": ["shape|floor|1", "texture|stone"]}
        assert result == expected


class TestTimestampFieldTransformer:
    """Test cases for TimestampFieldTransformer."""

    def test_test_no_transformation_needed_not_deprecated(self):
        """Test that non-deprecated entries don't need transformation."""
        transformer = TimestampFieldTransformer()
        fixture = {
            "deprecated": False,
            "file_metadata": {"changed": "old", "modified": "old"},
        }

        assert not transformer.test(fixture)

    def test_test_no_transformation_needed_current_format(self):
        """Test that entries with current format don't need transformation."""
        transformer = TimestampFieldTransformer()
        fixture = {
            "deprecated": True,
            "file_metadata": {"file_modified_at": "2020-01-01T00:00:00+00:00"},
        }

        assert not transformer.test(fixture)

    def test_test_transformation_needed_has_changed(self):
        """Test that entries with 'changed' field need transformation."""
        transformer = TimestampFieldTransformer()
        fixture = {
            "deprecated": True,
            "file_metadata": {"changed": "old", "file_modified_at": "new"},
        }

        assert transformer.test(fixture)

    def test_test_transformation_needed_has_modified(self):
        """Test that entries with 'modified' field need transformation."""
        transformer = TimestampFieldTransformer()
        fixture = {"deprecated": True, "file_metadata": {"modified": "old"}}

        assert transformer.test(fixture)

    def test_test_transformation_needed_missing_file_modified_at(self):
        """Test that entries missing 'file_modified_at' need transformation."""
        transformer = TimestampFieldTransformer()
        fixture = {"deprecated": True, "file_metadata": {}}

        assert transformer.test(fixture)

    def test_apply_no_transformation(self):
        """Test that non-deprecated entries are returned unchanged."""
        transformer = TimestampFieldTransformer()
        fixture = {
            "deprecated": False,
            "file_metadata": {"changed": "old", "modified": "old"},
        }

        result = transformer.apply(fixture)
        assert result == fixture

    def test_apply_removes_changed_field(self):
        """Test that 'changed' field is removed."""
        transformer = TimestampFieldTransformer()
        fixture = {
            "deprecated": True,
            "file_metadata": {
                "changed": "old",
                "file_modified_at": "2020-01-01T00:00:00+00:00",
            },
        }

        result = transformer.apply(fixture)

        expected = {
            "deprecated": True,
            "file_metadata": {"file_modified_at": "2020-01-01T00:00:00+00:00"},
        }
        assert result == expected

    def test_apply_renames_modified_to_file_modified_at(self):
        """Test that 'modified' is renamed to 'file_modified_at'."""
        transformer = TimestampFieldTransformer()
        fixture = {
            "deprecated": True,
            "file_metadata": {"modified": "2020-01-01T00:00:00+00:00"},
        }

        result = transformer.apply(fixture)

        expected = {
            "deprecated": True,
            "file_metadata": {"file_modified_at": "2020-01-01T00:00:00+00:00"},
        }
        assert result == expected

    def test_apply_adds_default_file_modified_at(self):
        """Test that default 'file_modified_at' is added if missing."""
        transformer = TimestampFieldTransformer()
        fixture = {"deprecated": True, "file_metadata": {}}

        result = transformer.apply(fixture)

        expected = {
            "deprecated": True,
            "file_metadata": {"file_modified_at": "2020-01-01T00:00:00+00:00"},
        }
        assert result == expected

    def test_apply_handles_both_old_fields(self):
        """Test that both old fields are handled correctly."""
        transformer = TimestampFieldTransformer()
        fixture = {
            "deprecated": True,
            "file_metadata": {
                "changed": "old",
                "modified": "2020-01-01T00:00:00+00:00",
            },
        }

        result = transformer.apply(fixture)

        expected = {
            "deprecated": True,
            "file_metadata": {"file_modified_at": "2020-01-01T00:00:00+00:00"},
        }
        assert result == expected


class TestDeprecatedEntryTransformer:
    """Test cases for DeprecatedEntryTransformer."""

    def test_transform_non_deprecated_unchanged(self):
        """Test that non-deprecated entries are returned unchanged."""
        transformer = DeprecatedEntryTransformer()
        fixture = {
            "deprecated": False,
            "tags": [["shape", "floor"]],
            "file_metadata": {"changed": "old", "modified": "old"},
        }

        result = transformer.transform(fixture)
        assert result == fixture

    def test_transform_deprecated_with_old_format(self):
        """Test that deprecated entries with old format are transformed."""
        transformer = DeprecatedEntryTransformer()
        fixture = {
            "deprecated": True,
            "tags": [["shape", "floor"], ["texture", "stone"]],
            "file_metadata": {
                "changed": "old",
                "modified": "2020-01-01T00:00:00+00:00",
            },
        }

        result = transformer.transform(fixture)

        expected = {
            "deprecated": True,
            "tags": ["shape|floor", "texture|stone"],
            "file_metadata": {"file_modified_at": "2020-01-01T00:00:00+00:00"},
        }
        assert result == expected

    def test_transform_list(self):
        """Test that transform_list applies to all fixtures."""
        transformer = DeprecatedEntryTransformer()
        fixtures = [
            {
                "deprecated": False,
                "tags": [["shape", "floor"]],
                "file_metadata": {"changed": "old"},
            },
            {
                "deprecated": True,
                "tags": [["shape", "floor"]],
                "file_metadata": {"modified": "2020-01-01T00:00:00+00:00"},
            },
        ]

        result = transformer.transform_list(fixtures)

        # First fixture should be unchanged
        assert result[0] == fixtures[0]

        # Second fixture should be transformed
        expected = {
            "deprecated": True,
            "tags": ["shape|floor"],
            "file_metadata": {"file_modified_at": "2020-01-01T00:00:00+00:00"},
        }
        assert result[1] == expected

    def test_transform_error_handling(self):
        """Test that errors include fixture details."""
        transformer = DeprecatedEntryTransformer()
        fixture = {
            "deprecated": True,
            "tags": "invalid_tags",  # Should cause error
            "file_metadata": {"modified": "2020-01-01T00:00:00+00:00"},
        }

        with pytest.raises(Exception) as exc_info:
            transformer.transform(fixture)

        assert "TagArrayToPipeTransformer failed" in str(exc_info.value)
        assert "Fixture:" in str(exc_info.value)
        assert str(fixture) in str(exc_info.value)
