import os
import uuid

import pytest
from psycopg.rows import dict_row

import openforge.db.sql.tag_descriptions as tag_description_sql
from openforge.app.index import app as flask_app


@pytest.fixture
def client(test_db):
    flask_app.config["TESTING"] = True
    flask_app.db = test_db
    flask_app.config["API_TOKEN"] = os.environ["API_TOKEN"]
    with flask_app.test_client() as client:
        yield client


@pytest.fixture
def auth_client(client):
    client.environ_base["HTTP_AUTHORIZATION"] = os.environ["API_TOKEN"]
    return client


def create_test_tag_description(test_db, tag=None, description=None):
    if tag is None:
        tag = ["foo", "bar"]
    if description is None:
        description = "Test description"
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            return tag_description_sql.insert_tag_description(curs, tag, description)


def test_get_tag_descriptions(client, test_db):
    tag_desc = create_test_tag_description(test_db)
    response = client.get("/api/tag-descriptions")
    assert response.status_code == 200
    assert len(response.json) == 1
    assert "foo|bar" in response.json
    assert response.json["foo|bar"] == tag_desc["description"]


def test_create_tag_description(auth_client, test_db):
    data = {"tag": "foo|bar", "description": "Test description"}
    response = auth_client.post("/api/tag-descriptions", json=data)
    assert response.status_code == 201
    assert response.json["tag"] == "foo|bar"
    assert response.json["description"] == data["description"]


def test_create_tag_description_unauthorized(client, test_db):
    data = {"tag": ["foo", "bar"], "description": "Test description"}
    response = client.post("/api/tag-descriptions", json=data)
    assert response.status_code == 401


def test_get_tag_description_by_id(client, test_db):
    tag_desc = create_test_tag_description(test_db)
    response = client.get(f"/api/tag-descriptions/{tag_desc['id']}")
    assert response.status_code == 200
    assert response.json["id"] == str(tag_desc["id"])
    assert response.json["tag"] == tag_desc["tag"]
    assert response.json["description"] == tag_desc["description"]


def test_get_tag_description_by_id_not_found(client, test_db):
    response = client.get(f"/api/tag-descriptions/{uuid.uuid4()}")
    assert response.status_code == 404


def test_update_tag_description(auth_client, test_db):
    tag_desc = create_test_tag_description(test_db)
    data = {"description": "Updated description"}
    response = auth_client.patch(f"/api/tag-descriptions/{tag_desc['id']}", json=data)
    assert response.status_code == 200
    assert response.json["description"] == data["description"]


def test_update_tag_description_unauthorized(client, test_db):
    tag_desc = create_test_tag_description(test_db)
    data = {"description": "Updated description"}
    response = client.patch(f"/api/tag-descriptions/{tag_desc['id']}", json=data)
    assert response.status_code == 401


def test_delete_tag_description(auth_client, test_db):
    tag_desc = create_test_tag_description(test_db)
    response = auth_client.delete(f"/api/tag-descriptions/{tag_desc['id']}")
    assert response.status_code == 204


def test_delete_tag_description_unauthorized(client, test_db):
    tag_desc = create_test_tag_description(test_db)
    response = client.delete(f"/api/tag-descriptions/{tag_desc['id']}")
    assert response.status_code == 401


def test_get_tag_description_by_tag(client, test_db):
    # Create parent tag
    parent = create_test_tag_description(
        test_db, tag=["foo"], description="Parent description"
    )
    # Create child tag
    child = create_test_tag_description(
        test_db, tag=["foo", "bar"], description="Child description"
    )

    # Test parent tag query
    response = client.get("/api/tag/foo/description")
    assert response.status_code == 200
    assert len(response.json) == 2
    assert any(
        r["tag"] == parent["tag"] and r["description"] == parent["description"]
        for r in response.json
    )
    assert any(
        r["tag"] == child["tag"] and r["description"] == child["description"]
        for r in response.json
    )

    # Test child tag query
    response = client.get("/api/tag/foo|bar/description")
    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0]["tag"] == child["tag"]
    assert response.json[0]["description"] == child["description"]


def test_update_tag_description_by_tag(auth_client, test_db):
    # Create parent tag
    create_test_tag_description(test_db, tag=["foo"], description="Parent description")
    # Create child tag
    child = create_test_tag_description(
        test_db, tag=["foo", "bar"], description="Child description"
    )

    # Update parent tag
    data = {"description": "Updated parent description"}
    response = auth_client.patch("/api/tag/foo/description", json=data)
    assert response.status_code == 200
    assert response.json["description"] == data["description"]

    # Verify child tag unchanged
    response = auth_client.get(f"/api/tag-descriptions/{child['id']}")
    assert response.json["description"] == child["description"]


def test_update_tag_description_by_tag_unauthorized(client, test_db):
    create_test_tag_description(test_db, tag=["foo"])
    data = {"description": "Updated description"}
    response = client.patch("/api/tag/foo/description", json=data)
    assert response.status_code == 401


def test_delete_tag_description_by_tag(auth_client, test_db):
    # Create parent tag
    parent = create_test_tag_description(
        test_db, tag=["foo"], description="Parent description"
    )
    # Create child tag
    child = create_test_tag_description(
        test_db, tag=["foo", "bar"], description="Child description"
    )

    # Delete parent tag
    response = auth_client.delete("/api/tag/foo/description")
    assert response.status_code == 204

    # Verify parent tag deleted
    response = auth_client.get(f"/api/tag-descriptions/{parent['id']}")
    assert response.status_code == 404

    # Verify child tag unchanged
    response = auth_client.get(f"/api/tag-descriptions/{child['id']}")
    assert response.status_code == 200
    assert response.json["description"] == child["description"]


def test_delete_tag_description_by_tag_unauthorized(client, test_db):
    create_test_tag_description(test_db, tag=["foo"])
    response = client.delete("/api/tag/foo/description")
    assert response.status_code == 401
