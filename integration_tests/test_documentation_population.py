"""
Integration test to populate the database with documentation data for frontend testing.
This test creates blueprint documentation, tag documentation, and uploads images.
"""

import base64
import json
import os
from pathlib import Path

import pytest

from .test_constants import TEST_DATA_PREFIX


class TestDocumentationPopulation:
    """Test class for populating documentation data.

    Note: This test class does not use db_transaction fixture because it has
    conditional cleanup logic based on KEEP_TEST_DATA environment variable.
    When KEEP_TEST_DATA=true, the test data is preserved for manual testing.
    """

    def test_populate_blueprint_documentation(self, api_client, test_blueprint_id):
        """Test creating blueprint documentation."""

        # Use the test blueprint ID directly instead of hardcoded MD5
        blueprint_id = test_blueprint_id
        print(f"Using test blueprint: {blueprint_id}")

        # Create blueprint documentation
        doc_data = {
            "document": (
                f"{TEST_DATA_PREFIX} This is test blueprint documentation.\n\n"
                "## Assembly Instructions\n\n"
                "1. Print all parts\n"
                "2. Clean up supports\n"
                "3. Assemble according to diagram\n\n"
                "## Printing Tips\n\n"
                "- Use 0.2mm layer height\n"
                "- 20% infill recommended\n"
                "- Support material may be needed"
            ),
            "document_type": "instructions",
        }

        response = api_client.post(
            f"/api/blueprints/{blueprint_id}/documentation", data=doc_data
        )
        assert (
            response.status_code == 201
        ), f"Failed to create blueprint documentation: {response.text}"
        doc = response.json()

        print(f"Created blueprint documentation: {doc.get('id', 'NO_ID')}")
        print(f"Response: {doc}")

        # Keep the data if KEEP_TEST_DATA is set
        if os.environ.get("KEEP_TEST_DATA") == "true":
            print("Keeping test data as KEEP_TEST_DATA=true")
        else:
            # Clean up
            doc_id = doc.get("id")
            if doc_id:
                response = api_client.delete(
                    f"/api/blueprints/{blueprint_id}/documentation/{doc_id}"
                )
                assert response.status_code == 204

    def test_populate_tag_documentation(self, api_client):
        """Test creating tag documentation."""

        # Create documentation for component|full_pillar|torch
        torch_doc_data = {
            "document": (
                f"{TEST_DATA_PREFIX} ## Torch Component Documentation\n\n"
                "This is a full pillar torch component.\n\n"
                "### Usage\n\n"
                "- Attach to walls or pillars\n"
                "- Provides lighting in dungeons\n"
                "- Compatible with standard mounting systems\n\n"
                "![Torch Example](torch_test.png)\n\n"
                "### Specifications\n\n"
                "- Height: 15cm\n"
                "- Base diameter: 3cm\n"
                "- Material: PLA recommended"
            ),
            "document_type": "instructions",
        }

        response = api_client.post(
            "/api/tags/component/full_pillar/torch/documentation", data=torch_doc_data
        )
        assert (
            response.status_code == 201
        ), f"Failed to create torch documentation: {response.text}"
        torch_doc = response.json()

        print(f"Created torch documentation: {torch_doc.get('id', 'NO_ID')}")
        print(f"Response: {torch_doc}")

        # Create documentation for texture|dungeon_stone
        stone_doc_data = {
            "document": (
                f"{TEST_DATA_PREFIX} ## Dungeon Stone Texture\n\n"
                "This texture provides a realistic stone appearance for "
                "dungeon environments.\n\n"
                "### Application\n\n"
                "- Use on walls and floors\n"
                "- Compatible with various stone types\n"
                "- Weather-resistant finish\n\n"
                "### Color Variations\n\n"
                "- Dark gray (default)\n"
                "- Light gray\n"
                "- Brown stone\n"
                "- Moss-covered variants"
            ),
            "document_type": "instructions",
        }

        response = api_client.post(
            "/api/tags/texture/dungeon_stone/documentation", data=stone_doc_data
        )
        assert (
            response.status_code == 201
        ), f"Failed to create stone documentation: {response.text}"
        stone_doc = response.json()

        print(f"Created stone documentation: {stone_doc.get('id', 'NO_ID')}")
        print(f"Response: {stone_doc}")

        # Keep the data if KEEP_TEST_DATA is set
        if os.environ.get("KEEP_TEST_DATA") == "true":
            print("Keeping test data as KEEP_TEST_DATA=true")
        else:
            # Clean up
            torch_doc_id = torch_doc.get("id")
            if torch_doc_id:
                response = api_client.delete(
                    f"/api/tags/component/full_pillar/torch/documentation/{torch_doc_id}"
                )
                assert response.status_code == 204

            stone_doc_id = stone_doc.get("id")
            if stone_doc_id:
                response = api_client.delete(
                    f"/api/tags/texture/dungeon_stone/documentation/{stone_doc_id}"
                )
                assert response.status_code == 204

    def test_upload_image(self, api_client):
        """Test uploading an image for documentation."""

        # For integration tests against live server, credentials handled by server
        # The server should have the Cloudflare R2 credentials in its .env file

        # Create a test image file
        test_image_path = Path(__file__).parent / "test_data" / "torch_test.png"
        test_image_path.parent.mkdir(exist_ok=True)

        # Create a simple test image (1x1 pixel PNG)
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )
        test_image_path.write_bytes(png_data)

        try:
            # Upload image with metadata
            metadata = {"image_name": "torch_test", "blueprint_ids": []}

            with open(test_image_path, "rb") as f:
                files = {"file": ("torch_test.png", f, "image/png")}
                data = {"metadata": json.dumps(metadata)}

                response = api_client.post("/api/images", data=data, files=files)
                print(
                    f"Image upload response: {response.status_code} - {response.text}"
                )
                assert (
                    response.status_code == 201
                ), f"Failed to upload image: {response.text}"
                image = response.json()

                print(f"Uploaded image: {image['id']} - {image['image_url']}")

                # Keep the data if KEEP_TEST_DATA is set
                if os.environ.get("KEEP_TEST_DATA") == "true":
                    print("Keeping test image as KEEP_TEST_DATA=true")
                else:
                    # Clean up
                    image_id = image.get("id")
                    if image_id:
                        response = api_client.delete(f"/api/images/{image_id}")
                        assert response.status_code == 204

        finally:
            # Clean up test file
            if test_image_path.exists():
                test_image_path.unlink()

    def test_populate_changelog(self, api_client):
        """Test creating/updating changelog for deprecated blueprint."""

        # First, create a successor relationship between two blueprints
        # Get any two blueprints
        response = api_client.get("/api/blueprints")
        assert response.status_code == 200
        blueprints = response.json()
        assert len(blueprints) >= 2, "Need at least 2 blueprints for this test"

        # Use the first as deprecated and second as successor
        deprecated_blueprint = blueprints[0]
        successor_blueprint = blueprints[1]

        # Update the first blueprint to be deprecated and point to successor
        update_data = {"deprecated": True, "successor_id": successor_blueprint["id"]}
        response = api_client.patch(
            f"/api/blueprints/{deprecated_blueprint['id']}", data=update_data
        )
        assert (
            response.status_code == 200
        ), f"Failed to update blueprint: {response.text}"

        # Now we have a deprecated blueprint with a successor
        successor_id = successor_blueprint["id"]

        response = api_client.get(f"/api/blueprints/{successor_id}")
        status = response.status_code
        print(f"Successor blueprint lookup response: {status} - {response.text}")
        assert (
            response.status_code == 200
        ), f"Failed to get successor blueprint: {response.text}"

        # Check if changelog already exists
        response = api_client.get(f"/api/blueprints/{successor_id}/documentation")
        print(
            f"Documentation lookup response: {response.status_code} - {response.text}"
        )

        if response.status_code == 404:
            # No documentation exists yet, create new changelog
            # Even on 404, the response should have the consistent structure
            response_data = response.json()
            existing_docs = response_data["documentation"]

            changelog_data = {
                "document": "Manifold repair",
                "document_type": "changelog",
            }

            response = api_client.post(
                f"/api/blueprints/{successor_id}/documentation", data=changelog_data
            )
            assert (
                response.status_code == 201
            ), f"Failed to create changelog: {response.text}"
            new_doc = response.json()

            print(f"Created changelog: {new_doc.get('id', 'NO_ID')}")
            print(f"Response: {new_doc}")
            return

        assert (
            response.status_code == 200
        ), f"Failed to get documentation: {response.text}"
        response_data = response.json()
        existing_docs = response_data["documentation"]

        changelog_doc = None
        for doc in existing_docs:
            if doc["document_type"] == "changelog":
                changelog_doc = doc
                break

        if changelog_doc:
            # Update existing changelog
            update_data = {"document": "Manifold repair"}

            response = api_client.patch(
                f"/api/blueprints/{successor_id}/documentation/{changelog_doc['id']}",
                data=update_data,
            )
            assert (
                response.status_code == 200
            ), f"Failed to update changelog: {response.text}"
            updated_doc = response.json()

            print(f"Updated changelog: {updated_doc.get('id', 'NO_ID')}")
            print(f"Response: {updated_doc}")
        else:
            # Create new changelog
            changelog_data = {
                "document": "Manifold repair",
                "document_type": "changelog",
            }

            response = api_client.post(
                f"/api/blueprints/{successor_id}/documentation", data=changelog_data
            )
            assert (
                response.status_code == 201
            ), f"Failed to create changelog: {response.text}"
            new_doc = response.json()

            print(f"Created changelog: {new_doc.get('id', 'NO_ID')}")
            print(f"Response: {new_doc}")

        # Keep the data if KEEP_TEST_DATA is set
        if os.environ.get("KEEP_TEST_DATA") == "true":
            print("Keeping changelog data as KEEP_TEST_DATA=true")
        # Note: We don't clean up changelogs as they represent real data


if __name__ == "__main__":
    # Allow running this test directly for manual data population
    pytest.main([__file__, "-v", "-s"])
