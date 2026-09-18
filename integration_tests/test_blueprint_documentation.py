"""
Pytest tests for Blueprint Documentation API endpoints.
"""

import uuid

from .test_constants import TEST_DOCUMENT_TEMPLATES


class TestBlueprintDocumentation:
    """Test blueprint documentation endpoints."""

    def test_get_blueprint_documentation(self, api_client, test_blueprint_id):
        """Test GET /api/blueprints/{blueprint_id}/documentation."""
        response = api_client.get(f"/api/blueprints/{test_blueprint_id}/documentation")

        assert response.status_code == 200
        data = response.json()
        assert "documentation" in data
        assert isinstance(data["documentation"], list)

    def test_create_blueprint_documentation(
        self, api_client, test_blueprint_id, cleanup_test_data
    ):
        """Test POST /api/blueprints/{blueprint_id}/documentation."""
        test_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["changelog"],
            "document_type": "changelog",
        }

        response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=test_doc
        )

        assert response.status_code == 201
        data = response.json()
        assert "documentation" in data
        assert data["documentation"]["document"] == test_doc["document"]
        assert data["documentation"]["document_type"] == test_doc["document_type"]
        assert "id" in data["documentation"]

        # Track the created ID for cleanup
        cleanup_test_data["blueprint_doc_ids"].append(data["documentation"]["id"])

    def test_update_blueprint_documentation(
        self, api_client, test_blueprint_id, cleanup_test_data
    ):
        """Test PATCH /api/blueprints/{blueprint_id}/documentation/{doc_id}."""
        # First create a document
        test_doc = {
            "document": "Test changelog entry for update",
            "document_type": "changelog",
        }

        create_response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=test_doc
        )
        assert create_response.status_code == 201
        doc_id = create_response.json()["documentation"]["id"]

        # Track the created ID for cleanup
        cleanup_test_data["blueprint_doc_ids"].append(doc_id)

        # Now update it
        update_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["update"],
            "document_type": "changelog",
        }

        response = api_client.patch(
            f"/api/blueprints/{test_blueprint_id}/documentation/{doc_id}",
            data=update_doc,
        )

        assert response.status_code == 200
        data = response.json()
        assert "documentation" in data
        assert data["documentation"]["document"] == update_doc["document"]
        assert data["documentation"]["id"] == doc_id

    def test_delete_blueprint_documentation(
        self, api_client, test_blueprint_id, cleanup_test_data
    ):
        """Test DELETE /api/blueprints/{blueprint_id}/documentation/{doc_id}."""
        # First create a document
        test_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["delete"],
            "document_type": "changelog",
        }

        create_response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=test_doc
        )
        assert create_response.status_code == 201
        doc_id = create_response.json()["documentation"]["id"]

        # Track the created ID for cleanup (in case deletion fails)
        cleanup_test_data["blueprint_doc_ids"].append(doc_id)

        # Now delete it
        response = api_client.delete(
            f"/api/blueprints/{test_blueprint_id}/documentation/{doc_id}"
        )

        assert response.status_code == 204

        # Remove from cleanup list since it was successfully deleted
        cleanup_test_data["blueprint_doc_ids"].remove(doc_id)

    def test_get_changelog_history(self, api_client, test_blueprint_id):
        """Test GET /api/blueprints/{blueprint_id}/changelog-history."""
        response = api_client.get(
            f"/api/blueprints/{test_blueprint_id}/changelog-history"
        )

        assert response.status_code == 200
        data = response.json()
        assert "changelogs" in data
        assert isinstance(data["changelogs"], list)
        assert "has_more" in data
        assert "total_count" in data

    def test_get_all_documentation(self, api_client, test_blueprint_id):
        """Test GET /api/blueprints/{blueprint_id}/all-documentation."""
        response = api_client.get(
            f"/api/blueprints/{test_blueprint_id}/all-documentation"
        )

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        required_fields = [
            "blueprint_id",
            "blueprint_name",
            "blueprint_documentation",
            "changelog_history",
            "tag_documentation",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Check data types
        assert isinstance(data["blueprint_documentation"], list)
        assert isinstance(data["changelog_history"], dict)
        assert isinstance(data["tag_documentation"], dict)
        assert "changelogs" in data["changelog_history"]
        assert isinstance(data["changelog_history"]["changelogs"], list)

    def test_create_blueprint_documentation_requires_auth(
        self, api_client_no_auth, test_blueprint_id
    ):
        """Test that creating blueprint documentation requires authentication."""
        test_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["auth"],
            "document_type": "changelog",
        }

        response = api_client_no_auth.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=test_doc
        )

        assert response.status_code == 401

    def test_update_blueprint_documentation_requires_auth(
        self, api_client_no_auth, test_blueprint_id
    ):
        """Test that updating blueprint documentation requires authentication."""
        update_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["update"],
            "document_type": "changelog",
        }

        response = api_client_no_auth.patch(
            f"/api/blueprints/{test_blueprint_id}/documentation/test-id",
            data=update_doc,
        )

        assert response.status_code == 401

    def test_delete_blueprint_documentation_requires_auth(
        self, api_client_no_auth, test_blueprint_id
    ):
        """Test that deleting blueprint documentation requires authentication."""
        response = api_client_no_auth.delete(
            f"/api/blueprints/{test_blueprint_id}/documentation/test-id"
        )

        assert response.status_code == 401

    def test_invalid_blueprint_id(self, api_client):
        """Test handling of invalid blueprint ID."""
        response = api_client.get("/api/blueprints/invalid-uuid/documentation")

        assert response.status_code == 400

    def test_nonexistent_blueprint_documentation(self, api_client):
        """Test getting documentation for a blueprint that has none."""
        # Create a new blueprint specifically for this test
        test_blueprint = {
            "blueprint_name": f"test_no_docs_{uuid.uuid4().hex[:8]}",
            "blueprint_type": "model",
            "file_md5": "test_md5_no_docs",
            "file_size": 1234,
            "file_name": "test_no_docs.stl",
            "full_name": "Test Blueprint With No Docs",
        }

        create_response = api_client.post("/api/blueprints", data=test_blueprint)
        assert create_response.status_code == 201
        blueprint_id = create_response.json()["id"]

        # Now test getting documentation for this blueprint (should be empty)
        # According to API standard, this should return 404 for empty collections
        response = api_client.get(f"/api/blueprints/{blueprint_id}/documentation")

        assert response.status_code == 404
        data = response.json()
        assert "documentation" in data
        assert isinstance(data["documentation"], list)
        assert len(data["documentation"]) == 0

        # Clean up
        api_client.delete(f"/api/blueprints/{blueprint_id}")

    def test_nonexistent_documentation_id(self, api_client, test_blueprint_id):
        """Test updating/deleting non-existent documentation."""
        # Test update
        update_doc = {
            "document": "Updated changelog entry",
            "document_type": "changelog",
        }

        response = api_client.patch(
            f"/api/blueprints/{test_blueprint_id}/documentation/00000000-0000-0000-0000-000000000001",
            data=update_doc,
        )
        assert response.status_code == 404

        # Test delete
        response = api_client.delete(
            f"/api/blueprints/{test_blueprint_id}/documentation/00000000-0000-0000-0000-000000000001"
        )
        assert response.status_code == 404
