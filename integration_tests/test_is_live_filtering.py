"""Test is_live filtering functionality."""

import pytest

from integration_tests.test_blueprint_documentation import TestBlueprintDocumentation


class TestIsLiveFiltering(TestBlueprintDocumentation):
    """Test that is_live filtering works correctly."""

    @pytest.fixture(autouse=True)
    def cleanup_documentation(self, api_client):
        """Clean up created documentation after each test."""
        # Track created documentation IDs
        self.created_doc_ids = []

        # Run the test
        yield

        # Clean up after test
        for doc_id in self.created_doc_ids:
            for blueprint_id in [getattr(self, "_test_blueprint_id", None)]:
                if blueprint_id:
                    try:
                        api_client.delete(
                            f"/api/blueprints/{blueprint_id}/documentation/{doc_id}"
                        )
                    except Exception:
                        pass  # Ignore cleanup errors

    def test_all_documentation_only_returns_live_docs(
        self, api_client, test_blueprint_id
    ):
        """Test that all-documentation endpoint only returns live documentation."""
        # Store blueprint ID for cleanup
        self._test_blueprint_id = test_blueprint_id

        # Create a live documentation
        live_doc = {
            "document": "This is live documentation for testing",
            "document_type": "instructions",
            "is_live": True,
        }

        response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=live_doc
        )
        assert response.status_code == 201
        live_doc_id = response.json()["documentation"]["id"]
        self.created_doc_ids.append(live_doc_id)

        # Create a non-live documentation
        draft_doc = {
            "document": "This is draft documentation for testing",
            "document_type": "instructions",
            "is_live": False,
        }

        response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=draft_doc
        )
        assert response.status_code == 201
        draft_doc_id = response.json()["documentation"]["id"]
        self.created_doc_ids.append(draft_doc_id)

        # Get all documentation (should only return live docs)
        response = api_client.get(
            f"/api/blueprints/{test_blueprint_id}/all-documentation"
        )
        assert response.status_code == 200

        data = response.json()
        blueprint_docs = data["blueprint_documentation"]

        # Check that our live document is in the results
        live_docs = [doc for doc in blueprint_docs if doc["id"] == live_doc_id]
        assert len(live_docs) == 1, f"Live document {live_doc_id} should be in results"
        assert live_docs[0]["is_live"], "Live document should have is_live=True"
        assert "This is live documentation for testing" in live_docs[0]["document"]

        # Check that our draft document is NOT in the results
        draft_ids = [doc["id"] for doc in blueprint_docs]
        assert (
            draft_doc_id not in draft_ids
        ), f"Draft document {draft_doc_id} should not be in results"

    def test_changelogs_always_live(self, api_client, test_blueprint_id):
        """Test that changelogs are always saved as live regardless of is_live."""
        # Store blueprint ID for cleanup
        self._test_blueprint_id = test_blueprint_id

        # Try to create a changelog with is_live=False
        changelog_doc = {
            "document": "This is a changelog entry",
            "document_type": "changelog",
            "is_live": False,  # This should be ignored
        }

        response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=changelog_doc
        )
        assert response.status_code == 201

        # Verify it was saved as live
        created_doc = response.json()["documentation"]
        self.created_doc_ids.append(created_doc["id"])
        assert created_doc["is_live"]
        assert created_doc["document_type"] == "changelog"

    def test_changelog_update_always_live(self, api_client, test_blueprint_id):
        """Test that updating a changelog with is_live=false still makes it live."""
        # Store blueprint ID for cleanup
        self._test_blueprint_id = test_blueprint_id

        # First create a changelog
        changelog_doc = {
            "document": "This is a changelog entry for update test",
            "document_type": "changelog",
            "is_live": True,
        }

        response = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=changelog_doc
        )
        assert response.status_code == 201
        doc_id = response.json()["documentation"]["id"]
        self.created_doc_ids.append(doc_id)

        # Now try to update it with is_live=false but without document_type
        update_data = {
            "document": "This is an updated changelog entry",
            "is_live": False,  # This should be ignored for changelogs
        }

        response = api_client.patch(
            f"/api/blueprints/{test_blueprint_id}/documentation/{doc_id}",
            data=update_data,
        )
        assert response.status_code == 200

        # Verify it was still saved as live
        updated_doc = response.json()["documentation"]
        assert updated_doc[
            "is_live"
        ], "Changelog should always be live even when is_live=false is sent"
        assert updated_doc["document_type"] == "changelog"
        assert "This is an updated changelog entry" in updated_doc["document"]

    def test_publish_workflow(self, api_client, test_blueprint_id):
        """Test that publishing a document marks others as non-live."""
        # Store blueprint ID for cleanup
        self._test_blueprint_id = test_blueprint_id

        # Create two instruction documents
        doc1 = {
            "document": "First instruction document for publish test",
            "document_type": "instructions",
            "is_live": False,
        }

        doc2 = {
            "document": "Second instruction document for publish test",
            "document_type": "instructions",
            "is_live": False,
        }

        response1 = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=doc1
        )
        assert response1.status_code == 201
        doc1_id = response1.json()["documentation"]["id"]
        self.created_doc_ids.append(doc1_id)

        response2 = api_client.post(
            f"/api/blueprints/{test_blueprint_id}/documentation", data=doc2
        )
        assert response2.status_code == 201
        doc2_id = response2.json()["documentation"]["id"]
        self.created_doc_ids.append(doc2_id)

        # Publish the first document
        publish_data = {
            "document": "First instruction document for publish test (updated)",
            "document_type": "instructions",
            "is_live": True,
        }

        response = api_client.patch(
            f"/api/blueprints/{test_blueprint_id}/documentation/{doc1_id}",
            data=publish_data,
        )
        assert response.status_code == 200

        # Get all documentation - should only show the published one
        response = api_client.get(
            f"/api/blueprints/{test_blueprint_id}/all-documentation"
        )
        assert response.status_code == 200

        data = response.json()
        blueprint_docs = data["blueprint_documentation"]

        # Should only have the published documentation
        our_instruction_docs = [
            doc for doc in blueprint_docs if doc["id"] in [doc1_id, doc2_id]
        ]
        assert (
            len(our_instruction_docs) == 1
        ), f"Should only have one of our test docs, got {len(our_instruction_docs)}"
        assert our_instruction_docs[0]["id"] == doc1_id, "Should have the published doc"
        assert our_instruction_docs[0]["is_live"], "Published doc should be live"
        assert (
            "First instruction document for publish test (updated)"
            in our_instruction_docs[0]["document"]
        )
