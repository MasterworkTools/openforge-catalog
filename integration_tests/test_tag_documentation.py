"""
Pytest tests for Tag Documentation API endpoints.
"""

from .test_constants import TEST_DOCUMENT_TEMPLATES


class TestTagDocumentation:
    """Test tag documentation endpoints."""

    def test_get_tag_documentation(self, api_client, test_tag_documentation):
        """Test GET /api/tags/{tag_array}/documentation."""
        # Test with a tag that should have documentation (if test data exists)
        response = api_client.get("/api/tags/texture/dungeon_stone/documentation")

        # If test data exists, should return 200 with data
        # If no test data exists, should return 404
        if response.status_code == 200:
            data = response.json()
            assert "documentation" in data
            assert isinstance(data["documentation"], list)
            assert len(data["documentation"]) >= 1

            # Check that the documentation is for the correct tag
            for doc in data["documentation"]:
                assert doc["tag"] == "texture|dungeon_stone"
        else:
            assert response.status_code == 404

    def test_get_tag_documentation_empty(self, api_client):
        """Test GET for tag with no documentation."""
        response = api_client.get("/api/tags/nonexistent/tag/documentation")

        assert response.status_code == 404

    def test_create_tag_documentation(self, api_client, cleanup_test_data):
        """Test POST /api/tags/{tag_array}/documentation."""
        test_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["instructions"],
            "document_type": "instructions",
        }

        response = api_client.post("/api/tags/test/tag/documentation", data=test_doc)

        assert response.status_code == 201
        data = response.json()
        assert "documentation" in data
        assert data["documentation"]["document"] == test_doc["document"]
        assert data["documentation"]["document_type"] == test_doc["document_type"]
        assert data["documentation"]["tag"] == "test|tag"
        assert "id" in data["documentation"]

        # Track the created ID for cleanup
        cleanup_test_data["tag_doc_ids"].append(data["documentation"]["id"])

    def test_update_tag_documentation(self, api_client, cleanup_test_data):
        """Test PATCH /api/tags/{tag_array}/documentation/{doc_id}."""
        # First create a document
        test_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["instructions"],
            "document_type": "instructions",
        }

        create_response = api_client.post(
            "/api/tags/test/tag/documentation", data=test_doc
        )
        assert create_response.status_code == 201
        doc_id = create_response.json()["documentation"]["id"]

        # Track the created ID for cleanup
        cleanup_test_data["tag_doc_ids"].append(doc_id)

        # Now update it
        update_doc = {
            "document": "Updated tag documentation entry",
            "document_type": "instructions",
        }

        response = api_client.patch(
            f"/api/tags/test/tag/documentation/{doc_id}", data=update_doc
        )

        assert response.status_code == 200
        data = response.json()
        assert "documentation" in data
        assert data["documentation"]["document"] == update_doc["document"]
        assert data["documentation"]["id"] == doc_id
        assert data["documentation"]["tag"] == "test|tag"

    def test_delete_tag_documentation(self, api_client, cleanup_test_data):
        """Test DELETE /api/tags/{tag_array}/documentation/{doc_id}."""
        # First create a document
        test_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["delete"],
            "document_type": "instructions",
        }

        create_response = api_client.post(
            "/api/tags/test/tag/documentation", data=test_doc
        )
        assert create_response.status_code == 201
        doc_id = create_response.json()["documentation"]["id"]

        # Track the created ID for cleanup (in case deletion fails)
        cleanup_test_data["tag_doc_ids"].append(doc_id)

        # Now delete it
        response = api_client.delete(f"/api/tags/test/tag/documentation/{doc_id}")

        assert response.status_code == 204

        # Remove from cleanup list since it was successfully deleted
        cleanup_test_data["tag_doc_ids"].remove(doc_id)

    def test_create_tag_documentation_requires_auth(self, api_client_no_auth):
        """Test that creating tag documentation requires authentication."""
        test_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["auth"],
            "document_type": "instructions",
        }

        response = api_client_no_auth.post(
            "/api/tags/test/tag/documentation", data=test_doc
        )

        assert response.status_code == 401

    def test_update_tag_documentation_requires_auth(self, api_client_no_auth):
        """Test that updating tag documentation requires authentication."""
        update_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["update"],
            "document_type": "instructions",
        }

        response = api_client_no_auth.patch(
            "/api/tags/test/tag/documentation/test-id", data=update_doc
        )

        assert response.status_code == 401

    def test_delete_tag_documentation_requires_auth(self, api_client_no_auth):
        """Test that deleting tag documentation requires authentication."""
        response = api_client_no_auth.delete("/api/tags/test/tag/documentation/test-id")

        assert response.status_code == 401

    def test_invalid_tag_format(self, api_client):
        """Test handling of invalid tag format."""
        # Test with invalid tag format
        response = api_client.get("/api/tags/invalid-tag-format/documentation")

        # Invalid tag format should return 400 - tag must have at least 2 components
        assert response.status_code == 400

    def test_nonexistent_tag_documentation_id(self, api_client):
        """Test updating/deleting non-existent tag documentation."""
        # Test update
        update_doc = {
            "document": TEST_DOCUMENT_TEMPLATES["update"],
            "document_type": "instructions",
        }

        response = api_client.patch(
            "/api/tags/test/tag/documentation/00000000-0000-0000-0000-000000000001",
            data=update_doc,
        )
        assert response.status_code == 404

        # Test delete
        response = api_client.delete(
            "/api/tags/test/tag/documentation/00000000-0000-0000-0000-000000000001"
        )
        assert response.status_code == 404

    def test_multiple_tag_documentation(
        self, api_client, test_tag_documentation, cleanup_test_data
    ):
        """Test that only one live instructions document can exist per tag."""
        # Create first live document
        test_doc1 = {
            "document": TEST_DOCUMENT_TEMPLATES["multiple_1"],
            "document_type": "instructions",
            "is_live": True,
        }

        response1 = api_client.post(
            "/api/tags/multiple/test/documentation", data=test_doc1
        )
        assert response1.status_code == 201

        # Create second live document - this should make the first one non-live
        test_doc2 = {
            "document": TEST_DOCUMENT_TEMPLATES["multiple_2"],
            "document_type": "instructions",
            "is_live": True,
        }

        response2 = api_client.post(
            "/api/tags/multiple/test/documentation", data=test_doc2
        )
        assert response2.status_code == 201

        # Verify both documents exist, but only one is live
        get_response = api_client.get("/api/tags/multiple/test/documentation")
        assert get_response.status_code == 200
        data = get_response.json()
        assert len(data["documentation"]) >= 2

        # Count live documents - should be exactly 1
        live_docs = [doc for doc in data["documentation"] if doc["is_live"]]
        assert len(live_docs) == 1

        # Track created IDs for cleanup
        doc1_id = response1.json()["documentation"]["id"]
        doc2_id = response2.json()["documentation"]["id"]
        cleanup_test_data["tag_doc_ids"].extend([doc1_id, doc2_id])

    def test_tag_documentation_types(self, api_client, cleanup_test_data):
        """Test different document types for tag documentation."""
        # Tags only support "instructions" type according to implementation plan
        test_docs = [{"document": "Test instructions", "document_type": "instructions"}]

        for test_doc in test_docs:
            response = api_client.post(
                "/api/tags/test/types/documentation", data=test_doc
            )
            assert response.status_code == 201
            data = response.json()
            assert data["documentation"]["document_type"] == test_doc["document_type"]

            # Track the created ID for cleanup
            cleanup_test_data["tag_doc_ids"].append(data["documentation"]["id"])

        # Test that changelog type is rejected for tags
        invalid_doc = {"document": "Test changelog", "document_type": "changelog"}
        response = api_client.post(
            "/api/tags/test/types/documentation", data=invalid_doc
        )
        assert response.status_code == 400

    def test_tag_documentation_ordering(self, api_client, test_tag_documentation):
        """Test that tag documentation is returned in correct order (newest first)."""
        response = api_client.get("/api/tags/texture/dungeon_stone/documentation")

        assert response.status_code == 200
        data = response.json()

        if len(data["documentation"]) >= 2:
            # Check that documents are ordered by created_at DESC
            docs = data["documentation"]
            for i in range(len(docs) - 1):
                assert docs[i]["created_at"] >= docs[i + 1]["created_at"]
