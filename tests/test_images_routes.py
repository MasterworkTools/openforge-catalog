import pytest

import openforge.db.sql.blueprints as blueprint_sql
import openforge.db.sql.images as image_sql

# Import the Flask app from openforge.app.index
from openforge.app.index import app as flask_app

from .test_helpers import (
    assert_image_matches,
    create_test_blueprint,
    create_test_image,
    setup_test_data,
)


@pytest.fixture
def client(test_db):
    flask_app.config["TESTING"] = True
    flask_app.db = test_db
    with flask_app.test_client() as client:
        yield client


def test_get_images(client):
    resp = client.get("/api/images")
    assert resp.status_code in (200, 404)  # 200 if any, 404 if none


def test_create_image(auth_client):
    image_data = create_test_image()
    response = auth_client.post("/api/images", json=image_data)
    assert response.status_code == 201
    assert_image_matches(response.json, image_data)


def test_get_image_by_id(auth_client, test_db):
    image = setup_test_data(test_db, create_test_image(), image_sql.insert_image)
    response = auth_client.get(f"/api/images/{image['id']}")
    assert response.status_code == 200
    assert str(response.json["id"]) == str(image["id"])


def test_update_image(auth_client, test_db):
    image = setup_test_data(test_db, create_test_image(), image_sql.insert_image)

    # Test updating basic fields
    patch_data = {
        "image_name": "updated_image",
        "image_url": "http://test.com/updated.jpg",
    }
    response = auth_client.patch(f"/api/images/{image['id']}", json=patch_data)
    assert response.status_code == 200
    assert response.json["image_name"] == "updated_image"
    assert response.json["image_url"] == "http://test.com/updated.jpg"

    # Test updating blueprint associations with a real blueprint
    blueprint = setup_test_data(
        test_db, create_test_blueprint(), blueprint_sql.insert_blueprint
    )
    patch_data = {"blueprint_ids": [str(blueprint["id"])]}
    response = auth_client.patch(f"/api/images/{image['id']}", json=patch_data)
    assert response.status_code == 200
    assert response.json["blueprint_ids"] == patch_data["blueprint_ids"]


def test_delete_image(auth_client, test_db):
    image = setup_test_data(test_db, create_test_image(), image_sql.insert_image)
    response = auth_client.delete(f"/api/images/{image['id']}")
    assert response.status_code == 204


def test_create_image_with_blueprints(auth_client, test_db):
    # Create a blueprint first
    blueprint = setup_test_data(
        test_db, create_test_blueprint(), blueprint_sql.insert_blueprint
    )
    image_data = create_test_image(blueprint_ids=[blueprint["id"]])
    response = auth_client.post("/api/images", json=image_data)
    assert response.status_code == 201
    assert str(response.json["blueprint_ids"][0]) == str(blueprint["id"])


def test_unauthorized_access(client, test_db):
    image = setup_test_data(test_db, create_test_image(), image_sql.insert_image)

    # Test unauthorized POST
    response = client.post("/api/images", json=create_test_image())
    assert response.status_code == 401

    # Test unauthorized PATCH
    response = client.patch(
        f"/api/images/{image['id']}", json={"image_name": "unauthorized"}
    )
    assert response.status_code == 401

    # Test unauthorized DELETE
    response = client.delete(f"/api/images/{image['id']}")
    assert response.status_code == 401
