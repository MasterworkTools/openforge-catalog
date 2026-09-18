import uuid

import pytest
from psycopg.rows import dict_row
from werkzeug.exceptions import NotFound

import openforge.db.sql.blueprints as blueprint_sql
import openforge.db.sql.images as image_sql

from .test_helpers import assert_image_matches, create_test_blueprint, create_test_image


def test_create_image(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            # Create test image
            image = create_test_image()
            result = image_sql.insert_image(curs, **image)
            assert_image_matches(result, image)

            # Verify it exists
            images = image_sql.get_all_images(curs)
            assert len(images) == 1
            assert_image_matches(images[0], image)


def test_get_image_by_id(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            # Create test image
            image = create_test_image()
            created = image_sql.insert_image(curs, **image)

            # Get by ID
            result = image_sql.get_image_by_id(curs, created["id"])
            assert_image_matches(result, image)

            # Test not found
            result = image_sql.get_image_by_id(
                curs, uuid.UUID("00000000-0000-0000-0000-000000000000")
            )
            assert result is None


def test_update_image(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            # Create test image
            image = create_test_image()
            created = image_sql.insert_image(curs, **image)

            # Update image
            update_data = {
                "image_name": "updated_image",
                "image_url": "http://test.com/updated.jpg",
            }

            result = image_sql.update_image(curs, created["id"], update_data)
            assert result["image_name"] == update_data["image_name"]
            assert result["image_url"] == update_data["image_url"]

            # Test not found
            with pytest.raises(NotFound):
                image_sql.update_image(
                    curs, uuid.UUID("00000000-0000-0000-0000-000000000000"), update_data
                )


def test_delete_image(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            # Create test image
            image = create_test_image()
            created = image_sql.insert_image(curs, **image)

            # Delete image
            rows = image_sql.delete_image(curs, created["id"])
            assert rows == 1

            # Verify it's gone
            result = image_sql.get_image_by_id(curs, created["id"])
            assert result is None


def test_delete_all_images(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            # Create multiple images
            images = [create_test_image(image_name=f"test_image_{i}") for i in range(3)]

            for img in images:
                image_sql.insert_image(curs, **img)

            # Delete all
            image_sql.delete_all_images(curs)

            # Verify no images exist
            curs.execute("SELECT COUNT(*) FROM images")
            count = curs.fetchone()["count"]
            assert count == 0


def test_image_blueprint_associations(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            # Create test image
            image = create_test_image()
            created_image = image_sql.insert_image(curs, **image)

            # Create test blueprint
            blueprint = create_test_blueprint()
            created_blueprint = blueprint_sql.insert_blueprint(curs, blueprint)

            # Associate image with blueprint
            image_sql.insert_blueprint_image(
                curs, created_blueprint["id"], created_image["id"]
            )

            # Test get blueprints for image
            blueprint_ids = image_sql.get_blueprints_ids_for_image(
                curs, created_image["id"]
            )
            assert len(blueprint_ids) == 1
            assert blueprint_ids[0] == created_blueprint["id"]

            # Test replace blueprints
            new_blueprint = create_test_blueprint(blueprint_name="new_blueprint")
            created_new_blueprint = blueprint_sql.insert_blueprint(curs, new_blueprint)
            image_sql.replace_blueprints_for_image(
                curs, created_image["id"], [created_new_blueprint["id"]]
            )
            blueprint_ids = image_sql.get_blueprints_ids_for_image(
                curs, created_image["id"]
            )
            assert len(blueprint_ids) == 1
            assert blueprint_ids[0] == created_new_blueprint["id"]


def test_image_duplicate_url(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            # Create first image
            image1 = create_test_image()
            created1 = image_sql.insert_image(curs, **image1)

            # Create second image with same URL
            image2 = create_test_image(image_name="different_name")
            created2 = image_sql.insert_image(curs, **image2)

            # Should return the existing image
            assert created2["id"] == created1["id"]
            assert created2["image_url"] == created1["image_url"]
