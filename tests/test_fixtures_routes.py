"""Tests for fixture loading API endpoint."""

import json

import pytest
from yaml import dump as yaml_dump

from openforge.app.index import app as flask_app


@pytest.fixture
def client(test_db):
    """Create a test client with database."""
    flask_app.config["TESTING"] = True
    flask_app.db = test_db
    # Use hardcoded test token for self-contained tests
    flask_app.config["API_TOKEN"] = "test_token"
    with flask_app.test_client() as client:
        yield client


@pytest.fixture
def auth_headers():
    """Get authorization headers with API token."""
    # Use hardcoded test token matching the client fixture
    return {"Authorization": "Bearer test_token"}


# Sample fixture data for testing
SAMPLE_BLUEPRINT_FIXTURE = [
    {
        "type": "model",
        "name": "test_wall",
        "tags": ["texture|dungeon_stone", "shape|wall"],
        "images": [],
        "file_metadata": {
            "file": "test_wall.stl",
            "full_name": "tiles/test/test_wall.stl",
            "md5": "d41d8cd98f00b204e9800998ecf8427e",
            "size": 12345,
            "file_modified_at": "2024-01-01T00:00:00",
            "storage_address": "s3://test/test_wall.stl",
        },
    }
]

SAMPLE_TAG_DESCRIPTION_FIXTURE = {
    "texture|test": "A test texture",
    "shape|test": "A test shape",
}

SAMPLE_TAG_DOCUMENTATION_FIXTURE = {
    "texture|test": [
        {
            "document": "Test documentation content",
            "document_type": "instructions",
            "is_live": True,
        }
    ]
}


class TestFixtureLoadEndpoint:
    """Test the POST /api/admin/fixtures endpoint."""

    def test_load_blueprint_fixture_json(self, client, auth_headers):
        """Test loading a blueprint fixture as JSON."""
        response = client.post(
            "/api/admin/fixtures?dry_run=true",
            data=json.dumps(SAMPLE_BLUEPRINT_FIXTURE),
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "added" in data
        assert "modified" in data
        assert "deprecated" in data
        assert "consolidated" in data
        assert "errors" in data
        assert "output" in data
        assert isinstance(data["output"], list)

    def test_load_blueprint_fixture_yaml(self, client, auth_headers):
        """Test loading a blueprint fixture as YAML."""
        yaml_content = yaml_dump(SAMPLE_BLUEPRINT_FIXTURE)
        response = client.post(
            "/api/admin/fixtures?dry_run=true",
            data=yaml_content,
            headers={**auth_headers, "Content-Type": "application/x-yaml"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "output" in data

    def test_load_tag_description_fixture(self, client, auth_headers):
        """Test loading a tag description fixture."""
        response = client.post(
            "/api/admin/fixtures?dry_run=true",
            data=json.dumps(SAMPLE_TAG_DESCRIPTION_FIXTURE),
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "modified" in data
        # Tag descriptions should show up as modified
        assert len(data["modified"]) > 0
        # Modified items should be objects per API contract
        assert all(isinstance(item, dict) for item in data["modified"])

    def test_load_tag_documentation_fixture(self, client, auth_headers):
        """Test loading a tag documentation fixture."""
        response = client.post(
            "/api/admin/fixtures?dry_run=true",
            data=json.dumps(SAMPLE_TAG_DOCUMENTATION_FIXTURE),
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "modified" in data
        assert len(data["modified"]) > 0
        # Modified items should be objects per API contract
        assert all(isinstance(item, dict) for item in data["modified"])

    def test_dry_run_parameter(self, client, auth_headers):
        """Test that dry_run=true doesn't modify the database."""
        response = client.post(
            "/api/admin/fixtures?dry_run=true",
            data=json.dumps(SAMPLE_BLUEPRINT_FIXTURE),
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        # Check output contains dry run message
        assert any("DRY RUN" in msg for msg in data["output"])

    def test_verbose_parameter(self, client, auth_headers):
        """Test that verbose=true includes debug output."""
        response = client.post(
            "/api/admin/fixtures?dry_run=true&verbose=true",
            data=json.dumps(SAMPLE_BLUEPRINT_FIXTURE),
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        # Verbose mode should include more output
        assert len(data["output"]) > 0
        # Should see processing messages
        assert any("Processing fixture type" in msg for msg in data["output"])

    def test_empty_body_returns_400(self, client, auth_headers):
        """Test that empty request body returns 400."""
        response = client.post(
            "/api/admin/fixtures",
            data="",
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data

    def test_invalid_json_returns_400(self, client, auth_headers):
        """Test that invalid JSON returns 400 (client error)."""
        response = client.post(
            "/api/admin/fixtures",
            data="{invalid json",
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data
        assert "output" in data

    def test_invalid_yaml_returns_400(self, client, auth_headers):
        """Test that invalid YAML returns 400 (client error)."""
        response = client.post(
            "/api/admin/fixtures",
            data="invalid: yaml: content:",
            headers={**auth_headers, "Content-Type": "application/x-yaml"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data

    def test_output_capture(self, client, auth_headers):
        """Test that output is captured in response."""
        response = client.post(
            "/api/admin/fixtures?dry_run=true&verbose=true",
            data=json.dumps(SAMPLE_BLUEPRINT_FIXTURE),
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "output" in data
        assert isinstance(data["output"], list)
        assert len(data["output"]) > 0
        # Output should be strings
        assert all(isinstance(msg, str) for msg in data["output"])

    def test_error_response_includes_output_field(self, client, auth_headers):
        """Test that error responses include output field."""
        # Invalid JSON will trigger a 400 error
        response = client.post(
            "/api/admin/fixtures",
            data="{bad json",
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data
        assert "output" in data
        assert isinstance(data["output"], list)

    def test_content_type_auto_detection(self, client, auth_headers):
        """Test that content type is auto-detected from data structure."""
        # Send JSON without explicit content type
        response = client.post(
            "/api/admin/fixtures?dry_run=true",
            data=json.dumps(SAMPLE_BLUEPRINT_FIXTURE),
            headers=auth_headers,  # No Content-Type header
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True


class TestFixtureTypeDetection:
    """Test fixture type auto-detection logic."""

    def test_detect_blueprint_fixture(self, client, auth_headers):
        """Test that blueprint fixtures are detected correctly."""
        response = client.post(
            "/api/admin/fixtures?dry_run=true&verbose=true",
            data=json.dumps(SAMPLE_BLUEPRINT_FIXTURE),
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.get_json()
        # Verbose mode should show fixture type
        assert any("blueprint" in msg.lower() for msg in data["output"])

    def test_detect_tag_description_fixture(self, client, auth_headers):
        """Test that tag description fixtures are detected correctly."""
        response = client.post(
            "/api/admin/fixtures?dry_run=true",
            data=json.dumps(SAMPLE_TAG_DESCRIPTION_FIXTURE),
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.get_json()
        # Tag descriptions show up as modified
        assert "modified" in data

    def test_detect_tag_documentation_fixture(self, client, auth_headers):
        """Test that tag documentation fixtures are detected correctly."""
        response = client.post(
            "/api/admin/fixtures?dry_run=true",
            data=json.dumps(SAMPLE_TAG_DOCUMENTATION_FIXTURE),
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.get_json()
        # Tag documentation shows up as modified
        assert "modified" in data


class TestTypeSpecificEndpoints:
    """Test type-specific fixture endpoints."""

    def test_blueprints_endpoint_accepts_blueprint(self, client, auth_headers):
        """Test /api/admin/fixtures/blueprints accepts blueprint fixtures."""
        response = client.post(
            "/api/admin/fixtures/blueprints?dry_run=true",
            data=json.dumps(SAMPLE_BLUEPRINT_FIXTURE),
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_blueprints_endpoint_rejects_tag_description(self, client, auth_headers):
        """Test /api/admin/fixtures/blueprints rejects non-blueprint fixtures."""
        response = client.post(
            "/api/admin/fixtures/blueprints?dry_run=true",
            data=json.dumps(SAMPLE_TAG_DESCRIPTION_FIXTURE),
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Invalid blueprint fixture" in data["error"]

    def test_tag_descriptions_endpoint_accepts_tag_description(
        self, client, auth_headers
    ):
        """Test tag-descriptions endpoint accepts tag descriptions."""
        response = client.post(
            "/api/admin/fixtures/tag-descriptions?dry_run=true",
            data=json.dumps(SAMPLE_TAG_DESCRIPTION_FIXTURE),
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_tag_descriptions_endpoint_rejects_blueprint(self, client, auth_headers):
        """Test tag-descriptions endpoint validates fixture type."""
        response = client.post(
            "/api/admin/fixtures/tag-descriptions?dry_run=true",
            data=json.dumps(SAMPLE_BLUEPRINT_FIXTURE),
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Invalid tag description fixture" in data["error"]

    def test_tag_documentation_endpoint_accepts_tag_documentation(
        self, client, auth_headers
    ):
        """Test tag-documentation endpoint accepts tag docs."""
        response = client.post(
            "/api/admin/fixtures/tag-documentation?dry_run=true",
            data=json.dumps(SAMPLE_TAG_DOCUMENTATION_FIXTURE),
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_tag_documentation_endpoint_rejects_blueprint(self, client, auth_headers):
        """Test tag-documentation endpoint validates fixture type."""
        response = client.post(
            "/api/admin/fixtures/tag-documentation?dry_run=true",
            data=json.dumps(SAMPLE_BLUEPRINT_FIXTURE),
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Invalid tag documentation fixture" in data["error"]


class TestResponseFormat:
    """Test response format consistency."""

    def test_success_response_structure(self, client, auth_headers):
        """Test that success responses have consistent structure."""
        response = client.post(
            "/api/admin/fixtures?dry_run=true",
            data=json.dumps(SAMPLE_BLUEPRINT_FIXTURE),
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.get_json()

        # Required fields
        assert "success" in data
        assert data["success"] is True
        assert "added" in data
        assert "modified" in data
        assert "deprecated" in data
        assert "consolidated" in data
        assert "errors" in data
        assert "output" in data

        # Field types
        assert isinstance(data["added"], list)
        assert isinstance(data["modified"], list)
        assert isinstance(data["deprecated"], list)
        assert isinstance(data["consolidated"], list)
        assert isinstance(data["errors"], list)
        assert isinstance(data["output"], list)

    def test_error_response_structure(self, client, auth_headers):
        """Test that error responses have consistent structure."""
        response = client.post(
            "/api/admin/fixtures",
            data="",
            headers={**auth_headers, "Content-Type": "application/json"},
        )

        assert response.status_code == 400
        data = response.get_json()

        # Required fields
        assert "success" in data
        assert data["success"] is False
        assert "error" in data
        assert isinstance(data["error"], str)
