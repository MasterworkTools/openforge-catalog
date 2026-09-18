import uuid

import pytest
from psycopg.rows import dict_row
from werkzeug.exceptions import NotFound

import openforge.db.sql.tag_descriptions as tag_description_sql


def test_create_tag_description(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            tag = ["foo", "bar"]
            description = "Test description"
            result = tag_description_sql.insert_tag_description(curs, tag, description)
            assert result["tag"] == "foo|bar"


def test_get_tag_description_by_id(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            tag = ["foo", "bar"]
            description = "Test description"
            created = tag_description_sql.insert_tag_description(curs, tag, description)

            result = tag_description_sql.get_tag_description_by_id(curs, created["id"])
            assert result["tag"] == "foo|bar"

            with pytest.raises(NotFound):
                tag_description_sql.get_tag_description_by_id(
                    curs, uuid.UUID("00000000-0000-0000-0000-000000000000")
                )


def test_get_tag_description_by_tag(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            # Create parent tag
            parent_tag = ["foo"]
            parent_desc = "Parent description"
            tag_description_sql.insert_tag_description(curs, parent_tag, parent_desc)

            # Create child tag
            child_tag = ["foo", "bar"]
            child_desc = "Child description"
            tag_description_sql.insert_tag_description(curs, child_tag, child_desc)

            # Test parent tag query
            results = tag_description_sql.get_tag_description_by_tag(curs, "foo")
            assert len(results) == 2
            assert any(
                r["tag"] == "foo" and r["description"] == parent_desc for r in results
            )
            assert any(
                r["tag"] == "foo|bar" and r["description"] == child_desc
                for r in results
            )

            # Test child tag query
            results = tag_description_sql.get_tag_description_by_tag(curs, "foo|bar")
            assert len(results) == 1
            assert results[0]["tag"] == "foo|bar"
            assert results[0]["description"] == child_desc


def test_update_tag_description(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            tag = ["foo", "bar"]
            description = "Test description"
            created = tag_description_sql.insert_tag_description(curs, tag, description)

            new_description = "Updated description"
            result = tag_description_sql.update_tag_description(
                curs, created["id"], new_description
            )
            assert result["description"] == new_description

            with pytest.raises(NotFound):
                tag_description_sql.update_tag_description(
                    curs,
                    uuid.UUID("00000000-0000-0000-0000-000000000000"),
                    new_description,
                )


def test_update_tag_description_by_tag(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            # Create parent tag
            parent_tag = ["foo"]
            parent_desc = "Parent description"
            tag_description_sql.insert_tag_description(curs, parent_tag, parent_desc)

            # Create child tag
            child_tag = ["foo", "bar"]
            child_desc = "Child description"
            child = tag_description_sql.insert_tag_description(
                curs, child_tag, child_desc
            )

            # Update parent tag
            new_parent_desc = "Updated parent description"
            result = tag_description_sql.update_tag_description_by_tag(
                curs, "foo", new_parent_desc
            )
            assert result["description"] == new_parent_desc

            # Verify child tag unchanged
            result = tag_description_sql.get_tag_description_by_id(curs, child["id"])
            assert result["description"] == child_desc


def test_delete_tag_description(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            tag = ["foo", "bar"]
            description = "Test description"
            created = tag_description_sql.insert_tag_description(curs, tag, description)

            result = tag_description_sql.delete_tag_description(curs, created["id"])
            assert result["id"] == created["id"]

            with pytest.raises(NotFound):
                tag_description_sql.get_tag_description_by_id(curs, created["id"])


def test_delete_tag_description_by_tag(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            # Create parent tag
            parent_tag = ["foo"]
            parent_desc = "Parent description"
            parent = tag_description_sql.insert_tag_description(
                curs, parent_tag, parent_desc
            )

            # Create child tag
            child_tag = ["foo", "bar"]
            child_desc = "Child description"
            child = tag_description_sql.insert_tag_description(
                curs, child_tag, child_desc
            )

            # Delete parent tag
            result = tag_description_sql.delete_tag_description_by_tag(curs, "foo")
            assert result["id"] == parent["id"]

            # Verify parent tag deleted
            with pytest.raises(NotFound):
                tag_description_sql.get_tag_description_by_id(curs, parent["id"])

            # Verify child tag unchanged
            result = tag_description_sql.get_tag_description_by_id(curs, child["id"])
            assert result["description"] == child_desc
