"""Integration tests for the documentation system."""

import pytest

from openforge.db.sql.tag_utils import array_to_tag, tag_to_array


class TestTagUtilities:
    """Test tag utility functions."""

    def test_tag_to_array_string(self):
        """Test converting pipe-delimited string to array."""
        result = tag_to_array("texture|dungeon_stone")
        assert result == ["texture", "dungeon_stone"]

    def test_tag_to_array_list(self):
        """Test converting list to array (no change)."""
        result = tag_to_array(["texture", "dungeon_stone"])
        assert result == ["texture", "dungeon_stone"]

    def test_array_to_tag(self):
        """Test converting array to pipe-delimited string."""
        result = array_to_tag(["texture", "dungeon_stone"])
        assert result == "texture|dungeon_stone"


class TestDocumentationSchemas:
    """Test that documentation schemas are properly defined."""

    def test_blueprint_documentation_schema_exists(self):
        """Test that blueprint documentation schema file exists."""
        import os

        schema_path = "openforge/openapi/schemas/blueprint_documentation.yaml"
        assert os.path.exists(schema_path), f"Schema file not found: {schema_path}"

    def test_tag_documentation_schema_exists(self):
        """Test that tag documentation schema file exists."""
        import os

        schema_path = "openforge/openapi/schemas/tag_documentation.yaml"
        assert os.path.exists(schema_path), f"Schema file not found: {schema_path}"

    def test_openapi_includes_documentation_schemas(self):
        """Test that main OpenAPI file includes documentation schemas."""
        import os

        openapi_path = "openforge/openapi/schemas/openapi.yaml"
        assert os.path.exists(openapi_path), f"OpenAPI file not found: {openapi_path}"

        with open(openapi_path, "r") as f:
            content = f.read()
            # Check that documentation schemas are referenced
            assert "BlueprintDocumentation:" in content
            assert "TagDocumentation:" in content
            assert "ChangelogHistory:" in content


class TestDocumentationImports:
    """Test that documentation modules can be imported."""

    def test_blueprint_documentation_import(self):
        """Test importing blueprint documentation module."""
        try:
            import openforge.db.sql.blueprint_documentation  # noqa: F401

            assert True, "Blueprint documentation module imported successfully"
        except ImportError as e:
            pytest.fail(f"Failed to import blueprint documentation module: {e}")

    def test_tags_documentation_import(self):
        """Test importing tags documentation module."""
        try:
            import openforge.db.sql.tags_documentation  # noqa: F401

            assert True, "Tags documentation module imported successfully"
        except ImportError as e:
            pytest.fail(f"Failed to import tags documentation module: {e}")

    def test_documentation_routes_import(self):
        """Test importing documentation route modules."""
        try:
            import openforge.app.routes.blueprint_documentation  # noqa: F401
            import openforge.app.routes.tags_documentation  # noqa: F401

            assert True, "Documentation route modules imported successfully"
        except ImportError as e:
            pytest.fail(f"Failed to import documentation route modules: {e}")
