import uuid

import pytest
from psycopg.rows import dict_row
from werkzeug.exceptions import NotFound

import openforge.db.sql.blueprints as blueprint_sql

from .test_helpers import assert_blueprint_matches, create_test_blueprint


def test_create_blueprint(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            blueprint = create_test_blueprint()
            result = blueprint_sql.insert_blueprint(curs, blueprint)
            assert_blueprint_matches(result, blueprint)

            blueprints = blueprint_sql.get_all_blueprints(curs)
            assert len(blueprints) == 1
            assert_blueprint_matches(blueprints[0], blueprint)


def test_get_blueprint_by_id(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            blueprint = create_test_blueprint()
            created = blueprint_sql.insert_blueprint(curs, blueprint)

            result = blueprint_sql.get_blueprint_by_id(curs, created["id"])
            assert_blueprint_matches(result, blueprint)

            with pytest.raises(NotFound):
                blueprint_sql.get_blueprint_by_id(
                    curs, uuid.UUID("00000000-0000-0000-0000-000000000000")
                )


def test_get_blueprint_by_md5(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            blueprint = create_test_blueprint(file_md5="test_md5")
            blueprint_sql.insert_blueprint(curs, blueprint)

            result = blueprint_sql.get_blueprint_by_md5(curs, blueprint["file_md5"])
            assert_blueprint_matches(result, blueprint)

            with pytest.raises(NotFound):
                blueprint_sql.get_blueprint_by_md5(curs, "nonexistent_md5")


def test_update_blueprint(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            blueprint = create_test_blueprint()
            created = blueprint_sql.insert_blueprint(curs, blueprint)

            update_data = {
                "blueprint_name": "updated_blueprint",
                "blueprint_config": {"updated": "config"},
            }

            result = blueprint_sql.update_blueprint(curs, created["id"], update_data)
            assert result["blueprint_name"] == update_data["blueprint_name"]
            assert result["blueprint_config"] == update_data["blueprint_config"]

            with pytest.raises(NotFound):
                blueprint_sql.update_blueprint(
                    curs, uuid.UUID("00000000-0000-0000-0000-000000000000"), update_data
                )


def test_delete_blueprint(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            blueprint = create_test_blueprint()
            created = blueprint_sql.insert_blueprint(curs, blueprint)

            rows = blueprint_sql.delete_blueprint(curs, created["id"])
            assert rows == 1

            with pytest.raises(NotFound):
                blueprint_sql.get_blueprint_by_id(curs, created["id"])


def test_delete_all_blueprints(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            blueprints = [
                create_test_blueprint(blueprint_name=f"test_blueprint_{i}")
                for i in range(3)
            ]

            for bp in blueprints:
                blueprint_sql.insert_blueprint(curs, bp)

            blueprint_sql.delete_all_blueprints(curs)

            curs.execute("SELECT COUNT(*) FROM blueprints")
            count = curs.fetchone()["count"]
            assert count == 0


def test_md5_conflict(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            blueprint1 = create_test_blueprint(file_md5="test_md5")
            created1 = blueprint_sql.insert_blueprint(curs, blueprint1)

            blueprint2 = create_test_blueprint(
                blueprint_name="test_blueprint_2", file_md5="test_md5"
            )
            with pytest.raises(Exception) as exc_info:
                blueprint_sql.insert_blueprint(curs, blueprint2)
            assert "duplicate key value violates unique constraint" in str(
                exc_info.value
            )
            conn.rollback()

            created2 = blueprint_sql.insert_blueprint(
                curs, blueprint2, rescue_md5_conflict=True
            )
            assert created2["file_md5"] == created1["file_md5"]
