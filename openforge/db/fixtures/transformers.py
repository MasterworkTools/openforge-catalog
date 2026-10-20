"""
Transformers for updating deprecated fixture entries to current schema.

These transformers are applied to deprecated entries before schema validation
to ensure they conform to the current fixture format.
"""

from typing import Any, Dict, List


class TagArrayToPipeTransformer:
    """Transform tag arrays to pipe-delimited format."""

    def test(self, fixture: Dict[str, Any]) -> bool:
        """Test if transformation is needed."""
        if not fixture.get("deprecated", False):
            return False

        tags = fixture.get("tags", [])
        if not tags:
            return False

        # Check if tags field itself is not a list (invalid format)
        if not isinstance(tags, list):
            return True

        # Check if any tags are in array format or invalid format
        for tag in tags:
            if isinstance(tag, list):
                return True
            elif not isinstance(tag, str):
                # Invalid format - needs transformation (will raise error)
                return True
        return False

    def apply(self, fixture: Dict[str, Any]) -> Dict[str, Any]:
        """Apply transformation to convert array tags to pipe format."""
        if not self.test(fixture):
            return fixture

        result = fixture.copy()
        tags = result.get("tags", [])

        # Check if tags field itself is not a list (invalid format)
        if not isinstance(tags, list):
            raise ValueError(
                f"Invalid tags format: {tags}. Expected list, got {type(tags)}"
            )

        transformed_tags = []

        for tag in tags:
            if isinstance(tag, list):
                # Convert array to pipe-delimited string
                transformed_tags.append("|".join(str(item) for item in tag))
            elif isinstance(tag, str):
                # Already in correct format, keep as is
                transformed_tags.append(tag)
            else:
                # Invalid tag format
                raise ValueError(
                    f"Invalid tag format: {tag}. Expected list or string, "
                    f"got {type(tag)}"
                )

        result["tags"] = transformed_tags
        return result


class TimestampFieldTransformer:
    """Transform timestamp fields to current schema."""

    def test(self, fixture: Dict[str, Any]) -> bool:
        """Test if transformation is needed."""
        if not fixture.get("deprecated", False):
            return False

        file_metadata = fixture.get("file_metadata", {})

        # Check if we have old timestamp fields
        has_changed = "changed" in file_metadata
        has_modified = "modified" in file_metadata
        has_file_modified_at = "file_modified_at" in file_metadata

        return has_changed or has_modified or not has_file_modified_at

    def apply(self, fixture: Dict[str, Any]) -> Dict[str, Any]:
        """Apply transformation to update timestamp fields."""
        if not self.test(fixture):
            return fixture

        result = fixture.copy()
        file_metadata = result.get("file_metadata", {}).copy()

        # Remove 'changed' field if it exists
        if "changed" in file_metadata:
            del file_metadata["changed"]

        # Rename 'modified' to 'file_modified_at' if it exists
        if "modified" in file_metadata:
            file_metadata["file_modified_at"] = file_metadata.pop("modified")

        # Ensure we have file_modified_at (use a default if neither existed)
        if "file_modified_at" not in file_metadata:
            file_metadata["file_modified_at"] = "2020-01-01T00:00:00+00:00"

        result["file_metadata"] = file_metadata
        return result


class DeprecatedEntryTransformer:
    """Main transformer that applies all transformations to deprecated entries."""

    def __init__(self):
        self.transformers = [
            TagArrayToPipeTransformer(),
            TimestampFieldTransformer(),
        ]

    def transform(self, fixture: Dict[str, Any]) -> Dict[str, Any]:
        """Apply all transformations to a deprecated fixture entry."""
        if not fixture.get("deprecated", False):
            return fixture

        result = fixture
        for transformer in self.transformers:
            try:
                result = transformer.apply(result)
            except Exception as e:
                raise Exception(
                    f"Transformer {transformer.__class__.__name__} failed: {e}. "
                    f"Fixture: {fixture}"
                ) from e

        return result

    def transform_list(self, fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply transformations to a list of fixtures."""
        return [self.transform(fixture) for fixture in fixtures]
