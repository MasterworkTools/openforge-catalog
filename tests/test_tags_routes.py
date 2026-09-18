import logging
import os

import pytest
from psycopg.rows import dict_row

import openforge.db.sql.blueprints as blueprint_sql
import openforge.db.sql.tags as tag_sql
from openforge.app.index import app as flask_app

from .test_helpers import create_test_blueprint, setup_test_data

logger = logging.getLogger(__name__)


@pytest.fixture
def client(test_db):
    flask_app.config["TESTING"] = True
    flask_app.db = test_db
    flask_app.config["API_TOKEN"] = os.environ["API_TOKEN"]
    with flask_app.test_client() as client:
        yield client


def create_blueprint_with_tags(test_db, tags=None, blueprint_type="model"):
    blueprint = setup_test_data(
        test_db,
        create_test_blueprint(blueprint_type=blueprint_type),
        blueprint_sql.insert_blueprint,
    )
    if tags:
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                for tag in tags:
                    tag_sql.insert_tag(curs, blueprint["id"], tag)
                conn.commit()
    return blueprint


def test_get_blueprint_tags(auth_client, test_db):
    tags = ["foo|bar", "baz|qux"]
    blueprint = create_blueprint_with_tags(test_db, tags)
    resp = auth_client.get(f"/api/blueprints/{blueprint['id']}/tags")
    assert resp.status_code == 200
    returned_tags = [t["tag"] for t in resp.json]
    for tag in tags:
        assert tag in returned_tags


def test_replace_blueprint_tags(auth_client, test_db):
    blueprint = create_blueprint_with_tags(test_db, ["old|tag"])
    new_tags = ["new|tag1", "new|tag2"]
    resp = auth_client.post(f"/api/blueprints/{blueprint['id']}/tags", json=new_tags)
    assert resp.status_code in (200, 204)
    # Check tags replaced
    resp2 = auth_client.get(f"/api/blueprints/{blueprint['id']}/tags")
    returned_tags = [t["tag"] for t in resp2.json]
    for tag in new_tags:
        assert tag in returned_tags
    assert "old|tag" not in returned_tags


def test_delete_all_blueprint_tags(auth_client, test_db):
    blueprint = create_blueprint_with_tags(test_db, ["foo|bar"])
    resp = auth_client.delete(f"/api/blueprints/{blueprint['id']}/tags")
    assert resp.status_code == 204
    # Should be empty
    resp2 = auth_client.get(f"/api/blueprints/{blueprint['id']}/tags")
    assert resp2.status_code == 200
    assert resp2.json == []


def test_add_and_delete_single_tag(auth_client, test_db):
    blueprint = create_blueprint_with_tags(test_db)
    tag = "single|tag"
    # Add
    resp = auth_client.post(f"/api/blueprints/{blueprint['id']}/tags/{tag}")
    assert resp.status_code == 200
    assert any(t["tag"] == tag for t in resp.json)
    # Delete
    resp2 = auth_client.delete(f"/api/blueprints/{blueprint['id']}/tags/{tag}")
    assert resp2.status_code == 204
    # Confirm gone
    resp3 = auth_client.get(f"/api/blueprints/{blueprint['id']}/tags")
    assert tag not in [t["tag"] for t in resp3.json]


def test_get_blueprint_ids_by_tag(auth_client, test_db):
    tag = "foo|bar"
    blueprint = create_blueprint_with_tags(test_db, [tag])
    resp = auth_client.get(f"/api/blueprints/tags/{tag}")
    assert resp.status_code == 200
    assert str(blueprint["id"]) in [str(bid) for bid in resp.json]


def test_query_tags_basic(auth_client, test_db):
    tag1 = "foo|bar"
    tag2 = "baz|qux"
    bp1 = create_blueprint_with_tags(test_db, [tag1], blueprint_type="model")
    bp2 = create_blueprint_with_tags(test_db, [tag2], blueprint_type="model")
    query = {"accept": [{"tag": tag1}]}
    resp = auth_client.post("/api/blueprints/tags", json=query)
    assert resp.status_code == 200
    ids = [b["id"] for b in resp.json["blueprints"]]
    assert str(bp1["id"]) in ids
    assert str(bp2["id"]) not in ids


def test_query_tags_paging_and_limit(auth_client, test_db):
    tag = "foo|bar"
    # Create 5 blueprints with unique names for proper sorting
    bps = []
    for i in range(5):
        bp = create_test_blueprint(blueprint_type="model")
        bp["blueprint_name"] = f"test_blueprint_{i}"  # Ensure unique names
        bps.append(setup_test_data(test_db, bp, blueprint_sql.insert_blueprint))
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                tag_sql.insert_tag(curs, bps[-1]["id"], tag)
                conn.commit()

    logger.info("\nCreated blueprints:")
    for bp in bps:
        logger.info(f"ID: {bp['id']}, Name: {bp['blueprint_name']}")

    query = {"require": [{"tag": tag}]}
    resp = auth_client.post("/api/blueprints/tags?limit=2", json=query)
    assert resp.status_code == 200
    assert len(resp.json["blueprints"]) == 2

    logger.info("\nFirst page blueprints:")
    for bp in resp.json["blueprints"]:
        logger.info(f"ID: {bp['id']}, Name: {bp['blueprint_name']}")

    next_token = resp.json["paging"]["next_token"]
    logger.info(f"\nNext token: {next_token}")

    resp2 = auth_client.post(
        f"/api/blueprints/tags?limit=2&next={next_token}", json=query
    )
    assert resp2.status_code == 200
    assert len(resp2.json["blueprints"]) == 2

    logger.info("\nSecond page blueprints:")
    for bp in resp2.json["blueprints"]:
        logger.info(f"ID: {bp['id']}, Name: {bp['blueprint_name']}")


def test_query_tags_search(auth_client, test_db):
    tag = "foo|bar"
    bp = create_blueprint_with_tags(test_db, [tag], blueprint_type="model")
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            curs.execute(
                "UPDATE blueprints SET search_text = %s WHERE id = %s",
                ("uniquesearchterm", bp["id"]),
            )
            conn.commit()
    query = {"accept": [{"tag": tag}]}
    resp = auth_client.post("/api/blueprints/tags?search=uniquesearchterm", json=query)
    assert resp.status_code == 200
    ids = [b["id"] for b in resp.json["blueprints"]]
    assert str(bp["id"]) in ids


def test_invalid_and_unauthorized_requests(client, auth_client, test_db):
    blueprint = create_blueprint_with_tags(test_db, ["foo|bar"])
    # Test that the app accepts any tag format
    resp = auth_client.post(
        f"/api/blueprints/{blueprint['id']}/tags", json=["invalid|tag|format"]
    )
    assert resp.status_code == 200
