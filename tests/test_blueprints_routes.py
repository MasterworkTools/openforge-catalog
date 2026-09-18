import os
import warnings

import pytest
from psycopg.rows import dict_row

import openforge.db.sql.blueprints as blueprint_sql

# Import the Flask app from openforge.app.index
from openforge.app.index import app as flask_app


@pytest.fixture
def client(test_db):
    flask_app.config["TESTING"] = True
    flask_app.db = test_db
    flask_app.config["API_TOKEN"] = os.environ["API_TOKEN"]
    with flask_app.test_client() as client:
        yield client


# Define test data
test_blueprint_data = {
    "blueprint_name": "Test Blueprint",
    "blueprint_type": "blueprint",
    "blueprint_config": {},
    "file_md5": "d41d8cd98f00b204e9800998ecf8427e",
    "file_name": "test.blueprint",
    "storage_address": "s3://openforge-models/test.blueprint",
}


# Setup test data
def setup_test_data(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            blueprint = blueprint_sql.insert_blueprint(curs, test_blueprint_data)
            conn.commit()
            return blueprint


def test_get_blueprints(client):
    resp = client.get("/api/blueprints")
    assert resp.status_code in (200, 404)  # 200 if any, 404 if none


def test_create_blueprint(auth_client):
    response = auth_client.post("/api/blueprints", json=test_blueprint_data)
    assert response.status_code in [201, 400]
    if response.status_code == 201:
        response.json["id"]
        response.json["file_md5"]


def test_get_blueprint_by_id(auth_client, test_db):
    blueprint = setup_test_data(test_db)
    response = auth_client.get(f"/api/blueprints/{blueprint['id']}")
    assert response.status_code == 200
    assert str(response.json["id"]) == str(blueprint["id"])


def test_get_blueprint_by_md5(auth_client, test_db):
    blueprint = setup_test_data(test_db)
    response = auth_client.get(f"/api/blueprints/md5/{blueprint['file_md5']}")
    assert response.status_code == 200
    assert str(response.json["id"]) == str(blueprint["id"])


def test_update_blueprint(auth_client, test_db):
    blueprint = setup_test_data(test_db)

    # Test updating basic fields
    patch_data = {"blueprint_name": "Updated Blueprint"}
    response = auth_client.patch(f"/api/blueprints/{blueprint['id']}", json=patch_data)
    assert response.status_code == 200
    assert response.json["blueprint_name"] == "Updated Blueprint"

    # Test updating tags
    patch_data = {"tags": ["new|tag1", "new|tag2"]}
    response = auth_client.patch(f"/api/blueprints/{blueprint['id']}", json=patch_data)
    assert response.status_code == 200
    assert set(response.json["tags"]) == {"new|tag1", "new|tag2"}

    # Test updating images
    patch_data = {
        "images": [
            {"image_name": "new_image1", "image_url": "https://example.com/new1.png"},
            {"image_name": "new_image2", "image_url": "https://example.com/new2.png"},
        ]
    }
    response = auth_client.patch(f"/api/blueprints/{blueprint['id']}", json=patch_data)
    assert response.status_code == 200
    assert len(response.json["images"]) == 2
    assert response.json["images"][0]["image_name"] == "new_image1"
    assert response.json["images"][0]["image_url"] == "https://example.com/new1.png"
    assert response.json["images"][1]["image_name"] == "new_image2"
    assert response.json["images"][1]["image_url"] == "https://example.com/new2.png"

    # Test updating both tags and images together
    patch_data = {
        "tags": ["combined|tag"],
        "images": [
            {
                "image_name": "combined_image",
                "image_url": "https://example.com/combined.png",
            }
        ],
    }
    response = auth_client.patch(f"/api/blueprints/{blueprint['id']}", json=patch_data)
    assert response.status_code == 200
    assert set(response.json["tags"]) == {"combined|tag"}
    assert len(response.json["images"]) == 1
    assert response.json["images"][0]["image_name"] == "combined_image"
    assert response.json["images"][0]["image_url"] == "https://example.com/combined.png"


def test_delete_blueprint(auth_client, test_db):
    blueprint = setup_test_data(test_db)
    response = auth_client.delete(f"/api/blueprints/{blueprint['id']}")
    assert response.status_code == 204


def test_download_blueprint(client, test_db):
    # Mock CloudFlare credentials
    client.application.config["CLOUDFLARE_ENDPOINT"] = "https://test.endpoint"
    client.application.config["CLOUDFLARE_ACCESS_KEY_ID"] = "test_key"
    client.application.config["CLOUDFLARE_SECRET_ACCESS_KEY"] = "test_secret"

    blueprint = setup_test_data(test_db)

    # Suppress the specific botocore deprecation warning
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", category=DeprecationWarning, module="botocore"
        )
        resp = client.get(
            f"/api/blueprints/{blueprint['id']}/download",
            headers={"Authorization": "Bearer test_token"},
        )

    assert resp.status_code == 302


def test_create_blueprint_with_tags_and_images(auth_client):
    blueprint_data = {
        "blueprint_name": "basic_bp",
        "blueprint_type": "blueprint",
        "tags": ["tag1|foo", "tag2|bar|baz"],
        "images": [
            {"image_name": "image1", "image_url": "https://example.com/image1.png"},
            {"image_name": "image2", "image_url": "https://example.com/image2.png"},
        ],
    }
    response = auth_client.post("/api/blueprints", json=blueprint_data)
    assert response.status_code == 201
    data = response.json
    assert data["blueprint_name"] == "basic_bp"
    assert data["blueprint_type"] == "blueprint"
    assert set(data["tags"]) == {"tag1|foo", "tag2|bar|baz"}
    assert len(data["images"]) == 2
    assert data["images"][0]["image_name"] == "image1"
    assert data["images"][0]["image_url"] == "https://example.com/image1.png"
    assert data["images"][1]["image_name"] == "image2"
    assert data["images"][1]["image_url"] == "https://example.com/image2.png"
