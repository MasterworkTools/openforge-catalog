"""Schema-semantics tests for the thingiverse sync-state tables (version 17)."""

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

import openforge.db.sql.blueprints as blueprint_sql
import openforge.db.sql.images as image_sql

from .test_helpers import create_test_blueprint


def insert_thing(curs, name="Test Thing", thing_id=None, status="draft"):
    curs.execute(
        sql.SQL(
            "INSERT INTO thingiverse_things (name, thing_id, status) "
            "VALUES (%s, %s, %s) RETURNING *"
        ),
        (name, thing_id, status),
    )
    return curs.fetchone()


def insert_file(curs, thing_row_id, **overrides):
    fields = {
        "thingiverse_thing_id": thing_row_id,
        "file_type": "model",
        "blueprint_id": None,
        "image_id": None,
        "local_path": None,
        "local_md5": None,
        "local_sha256": None,
        "remote_file_id": None,
        "remote_file_name": None,
        "remote_hash": None,
    }
    fields.update(overrides)
    columns = list(fields.keys())
    curs.execute(
        sql.SQL("INSERT INTO thingiverse_files ({}) VALUES ({}) RETURNING *").format(
            sql.SQL(", ").join(sql.Identifier(c) for c in columns),
            sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        ),
        list(fields.values()),
    )
    return curs.fetchone()


def test_thing_round_trip(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            thing = insert_thing(curs, name="Cut Stone Walls", thing_id=12345)
            assert thing["status"] == "draft"
            assert thing["thing_id"] == 12345
            assert thing["created_at"] is not None


def test_thing_id_unique_but_nullable(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            # drafts have no remote id yet; multiple NULLs must coexist
            insert_thing(curs, name="Draft A")
            insert_thing(curs, name="Draft B")
            insert_thing(curs, name="Published", thing_id=99)
            with pytest.raises(psycopg.errors.UniqueViolation):
                insert_thing(curs, name="Duplicate", thing_id=99)


def test_file_requires_a_local_source(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            thing = insert_thing(curs)
            with pytest.raises(psycopg.errors.CheckViolation):
                insert_file(curs, thing["id"])  # no blueprint/image/path


def test_file_accepts_each_local_source_kind(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            blueprint = blueprint_sql.insert_blueprint(curs, create_test_blueprint())
            thing = insert_thing(curs)

            by_blueprint = insert_file(
                curs, thing["id"], blueprint_id=blueprint["id"], local_md5="abc123"
            )
            assert by_blueprint["file_type"] == "model"

            by_path = insert_file(
                curs, thing["id"], file_type="zip", local_path="/out/set.zip"
            )
            assert by_path["local_path"] == "/out/set.zip"

            image = image_sql.insert_image(
                curs, "gallery_shot", "http://test.com/shot.jpg"
            )
            by_image = insert_file(
                curs, thing["id"], file_type="image", image_id=image["id"]
            )
            assert by_image["image_id"] == image["id"]


def test_deleting_thing_cascades_to_files(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            thing = insert_thing(curs)
            insert_file(curs, thing["id"], local_path="/out/a.stl")
            curs.execute(
                sql.SQL("DELETE FROM thingiverse_things WHERE id = %s"),
                (thing["id"],),
            )
            curs.execute(sql.SQL("SELECT count(*) AS n FROM thingiverse_files"))
            assert curs.fetchone()["n"] == 0


def test_deleting_referenced_blueprint_is_restricted(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            blueprint = blueprint_sql.insert_blueprint(curs, create_test_blueprint())
            thing = insert_thing(curs)
            insert_file(curs, thing["id"], blueprint_id=blueprint["id"])
            # RESTRICT raises RestrictViolation (23001) on newer Postgres,
            # ForeignKeyViolation (23503) on older — accept either
            with pytest.raises(
                (
                    psycopg.errors.ForeignKeyViolation,
                    psycopg.errors.RestrictViolation,
                )
            ):
                curs.execute(
                    sql.SQL("DELETE FROM blueprints WHERE id = %s"),
                    (blueprint["id"],),
                )


def test_deleting_referenced_image_is_restricted(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            image = image_sql.insert_image(
                curs, "gallery_shot", "http://test.com/shot.jpg"
            )
            thing = insert_thing(curs)
            insert_file(curs, thing["id"], file_type="image", image_id=image["id"])
            with pytest.raises(
                (
                    psycopg.errors.ForeignKeyViolation,
                    psycopg.errors.RestrictViolation,
                )
            ):
                curs.execute(
                    sql.SQL("DELETE FROM images WHERE id = %s"), (image["id"],)
                )


def test_thing_id_unique_on_update(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            insert_thing(curs, name="Existing", thing_id=99)
            draft = insert_thing(curs, name="Draft")
            with pytest.raises(psycopg.errors.UniqueViolation):
                curs.execute(
                    sql.SQL(
                        "UPDATE thingiverse_things SET thing_id = 99 WHERE id = %s"
                    ),
                    (draft["id"],),
                )


def test_file_check_enforced_on_update(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            thing = insert_thing(curs)
            row = insert_file(curs, thing["id"], local_path="/out/a.stl")
            with pytest.raises(psycopg.errors.CheckViolation):
                curs.execute(
                    sql.SQL(
                        "UPDATE thingiverse_files SET local_path = NULL WHERE id = %s"
                    ),
                    (row["id"],),
                )


def test_duplicate_source_in_same_thing_rejected(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            blueprint = blueprint_sql.insert_blueprint(curs, create_test_blueprint())
            thing = insert_thing(curs)
            insert_file(curs, thing["id"], blueprint_id=blueprint["id"])
            with pytest.raises(psycopg.errors.UniqueViolation):
                insert_file(curs, thing["id"], blueprint_id=blueprint["id"])


def test_duplicate_image_in_same_thing_rejected(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            image = image_sql.insert_image(
                curs, "gallery_shot", "http://test.com/shot.jpg"
            )
            thing = insert_thing(curs)
            insert_file(curs, thing["id"], file_type="image", image_id=image["id"])
            with pytest.raises(psycopg.errors.UniqueViolation):
                insert_file(curs, thing["id"], file_type="image", image_id=image["id"])


def test_duplicate_path_in_same_thing_rejected(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            thing = insert_thing(curs)
            insert_file(curs, thing["id"], file_type="zip", local_path="/out/a.zip")
            with pytest.raises(psycopg.errors.UniqueViolation):
                insert_file(curs, thing["id"], file_type="zip", local_path="/out/a.zip")


def test_same_source_allowed_in_different_things(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            blueprint = blueprint_sql.insert_blueprint(curs, create_test_blueprint())
            thing_a = insert_thing(curs, name="Set A")
            thing_b = insert_thing(curs, name="Set B")
            insert_file(curs, thing_a["id"], blueprint_id=blueprint["id"])
            # a blueprint may legitimately ship in more than one thing
            insert_file(curs, thing_b["id"], blueprint_id=blueprint["id"])


def test_file_type_enum_rejects_unknown_values(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            thing = insert_thing(curs)
            with pytest.raises(psycopg.errors.InvalidTextRepresentation):
                insert_file(curs, thing["id"], file_type="hologram", local_path="/x")


def test_thing_status_enum_rejects_unknown_values(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            with pytest.raises(psycopg.errors.InvalidTextRepresentation):
                insert_thing(curs, status="imaginary")
