from psycopg.rows import dict_row

import openforge.db.sql.blueprints as blueprint_sql
import openforge.db.sql.tags as tag_sql

from .test_helpers import create_test_blueprint


def test_insert_and_get_tag(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint()
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag = tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            assert tag["tag"] == "foo|bar"
            assert tag["blueprint_id"] == inserted_bp["id"]


def test_get_tags_for_blueprint(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint()
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            tags = tag_sql.get_tags(curs, inserted_bp["id"])
            assert len(tags) == 1
            assert tags[0]["tag"] == "foo|bar"


def test_insert_duplicate_tag(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint()
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag1 = tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            tag2 = tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            assert tag1["id"] == tag2["id"]


def test_delete_tag(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint()
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            rows = tag_sql.delete_tag(curs, inserted_bp["id"], "foo|bar")
            assert rows == 1
            tags = tag_sql.get_tags(curs, inserted_bp["id"])
            assert len(tags) == 0


def test_delete_all_blueprint_tags(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint()
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            tag_sql.insert_tag(curs, inserted_bp["id"], "baz|qux")
            rows = tag_sql.delete_all_blueprint_tags(curs, inserted_bp["id"])
            assert rows == 2
            tags = tag_sql.get_tags(curs, inserted_bp["id"])
            assert len(tags) == 0


def test_delete_all_tags(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp1 = create_test_blueprint()
            bp2 = create_test_blueprint()
            inserted_bp1 = blueprint_sql.insert_blueprint(curs, bp1)
            inserted_bp2 = blueprint_sql.insert_blueprint(curs, bp2)
            tag_sql.insert_tag(curs, inserted_bp1["id"], "foo|bar")
            tag_sql.insert_tag(curs, inserted_bp2["id"], "foo|bar")
            rows = tag_sql.delete_all_tags(curs)
            assert rows == 2
            tags = tag_sql.get_tags(curs, inserted_bp1["id"])
            assert len(tags) == 0


def test_get_blueprint_ids_by_tag(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp1 = create_test_blueprint()
            bp2 = create_test_blueprint()
            inserted_bp1 = blueprint_sql.insert_blueprint(curs, bp1)
            inserted_bp2 = blueprint_sql.insert_blueprint(curs, bp2)
            tag_sql.insert_tag(curs, inserted_bp1["id"], "foo|bar")
            tag_sql.insert_tag(curs, inserted_bp2["id"], "foo|bar")
            ids = tag_sql.get_blueprint_ids_by_tag(curs, "foo|bar")
            assert len(ids) == 2
            assert inserted_bp1["id"] in ids
            assert inserted_bp2["id"] in ids


def test_tag_search_blueprints(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint(blueprint_type="model")
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            results = tag_sql.tag_search_blueprints(
                curs, ["foo|bar"], [], [], None, None, 20, True, False, None
            )
            assert len(results) == 1
            assert results[0]["id"] == inserted_bp["id"]


def test_tag_search_tags(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint(blueprint_type="model")
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            results = tag_sql.tag_search_tags(
                curs, ["foo|bar"], [], [], None, None, 20, True, False, None
            )
            assert len(results) == 1
            assert results[0]["tag"] == ["foo", "bar"]


def test_tag_search_blueprint_images(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint()
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            results = tag_sql.tag_search_blueprint_images(
                curs, ["foo|bar"], [], [], None, None, 20, True, False, None
            )
            assert len(results) == 0


def test_tag_search_blueprint_count(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint(blueprint_type="model")
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            count = tag_sql.tag_search_blueprint_count(
                curs, ["foo|bar"], [], [], True, False, None
            )
            assert count == 1


def test_tag_search_tag_count(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            bp = create_test_blueprint(blueprint_type="model")
            inserted_bp = blueprint_sql.insert_blueprint(curs, bp)
            tag_sql.insert_tag(curs, inserted_bp["id"], "foo|bar")
            count = tag_sql.tag_search_tag_count(
                curs, ["foo|bar"], [], [], True, False, None
            )
            assert count[0]["tag"] == ["foo", "bar"]
            assert count[0]["tag_count"] == 1
