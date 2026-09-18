import uuid

from psycopg import cursor, sql
from psycopg.types.json import Json
from werkzeug.exceptions import NotFound


def get_all_images(curs: cursor) -> list[dict]:
    query = sql.SQL(
        """
SELECT id, image_name, image_url, image_type, created_at, updated_at
  FROM images
  ORDER BY id
"""
    )
    curs.execute(query)
    return curs.fetchall()


def get_documentation_images(curs: cursor) -> list[dict]:
    """Get all documentation type images.

    Returns:
        List of image dictionaries with image_type = 'documentation'
    """
    query = sql.SQL(
        """
SELECT id, image_name, image_url, image_type, created_at, updated_at
  FROM images
  WHERE image_type = 'documentation'
  ORDER BY created_at DESC
"""
    )
    curs.execute(query)
    return curs.fetchall()


def get_all_blueprint_images(curs: cursor) -> list[dict]:
    query = sql.SQL(
        """
SELECT id, blueprint_id, image_id, created_at, updated_at
  FROM blueprint_images
  ORDER BY image_id
"""
    )
    curs.execute(query)
    return curs.fetchall()


def get_images_for_blueprint(curs: cursor, blueprint_id: uuid.UUID) -> dict:
    query = sql.SQL(
        """
SELECT i.id AS id, i.image_name AS image_name, i.image_url AS image_url,
    i.image_type AS image_type, i.sprite_metadata AS sprite_metadata,
    i.created_at AS created_at, i.updated_at AS updated_at
  FROM images i
    JOIN blueprint_images bi ON bi.image_id = i.id
  WHERE bi.blueprint_id = {blueprint_id}
"""
    ).format(blueprint_id=sql.Literal(blueprint_id))
    curs.execute(query)
    return curs.fetchall()


def get_images_for_blueprints(
    curs: cursor, blueprint_ids: list[uuid.UUID]
) -> list[dict]:
    """Get all images for multiple blueprints in a single query.

    Args:
        curs: Database cursor
        blueprint_ids: List of blueprint IDs to get images for

    Returns:
        List of image dictionaries with blueprint_id included
    """
    if not blueprint_ids:
        return []

    query = sql.SQL(
        """
SELECT i.id AS id, i.image_name AS image_name, i.image_url AS image_url,
    i.created_at AS created_at, i.updated_at AS updated_at,
    bi.blueprint_id AS blueprint_id
  FROM images i
    JOIN blueprint_images bi ON bi.image_id = i.id
  WHERE bi.blueprint_id IN ({blueprint_ids})
  ORDER BY bi.blueprint_id, i.image_name
"""
    ).format(
        blueprint_ids=sql.SQL(",").join(sql.Literal(bp_id) for bp_id in blueprint_ids)
    )
    curs.execute(query)
    return curs.fetchall()


def get_image_by_id(curs: cursor, image_id: uuid.UUID) -> dict:
    query = sql.SQL(
        """
SELECT id, image_name, image_url, image_type, sprite_metadata, created_at, updated_at
  FROM images
  WHERE id = {image_id}
"""
    ).format(image_id=sql.Literal(image_id))
    curs.execute(query)
    return curs.fetchone()


def get_images_by_name(curs: cursor, image_name: str) -> list[dict]:
    """Get images by name (exact match).

    Args:
        curs: Database cursor
        image_name: Name of the image to search for

    Returns:
        List of image dictionaries matching the name
    """
    query = sql.SQL(
        """
SELECT id, image_name, image_url, image_type, created_at, updated_at
  FROM images
  WHERE image_name = {image_name}
  ORDER BY created_at DESC
"""
    ).format(image_name=sql.Literal(image_name))
    curs.execute(query)
    return curs.fetchall()


def insert_image(
    curs: cursor,
    image_name: str,
    image_url: str,
    image_type: str = "thumbnail",
    sprite_metadata: dict | None = None,
    **kwargs,
) -> dict:
    query = sql.SQL(
        """
INSERT INTO images (
  image_name, image_url, image_type, sprite_metadata
) VALUES (
  {image_name}, {image_url}, {image_type}, {sprite_metadata}
)
ON CONFLICT (image_url) DO UPDATE SET
  image_name = EXCLUDED.image_name,
  image_type = EXCLUDED.image_type,
  sprite_metadata = EXCLUDED.sprite_metadata
RETURNING id
"""
    ).format(
        image_name=sql.Literal(image_name),
        image_url=sql.Literal(image_url),
        image_type=sql.Literal(image_type),
        sprite_metadata=sql.Literal(Json(sprite_metadata))
        if sprite_metadata
        else sql.SQL("NULL"),
    )
    curs.execute(query)
    return get_image_by_id(curs, curs.fetchone()["id"])


def get_blueprint_image_by_id(curs: cursor, blueprint_image_id: uuid.UUID) -> dict:
    query = sql.SQL(
        """
SELECT id, blueprint_id, image_id, created_at, updated_at
  FROM blueprint_images
  WHERE id = {blueprint_image_id}
"""
    ).format(blueprint_image_id=sql.Literal(blueprint_image_id))
    curs.execute(query)
    return curs.fetchone()


def insert_blueprint_image(
    curs: cursor, blueprint_id: uuid.UUID, image_id: uuid.UUID
) -> dict:
    query = sql.SQL(
        """
WITH new_blueprint_images AS (
  INSERT INTO blueprint_images (
    blueprint_id, image_id
  ) VALUES (
    {blueprint_id}, {image_id}
  ) ON CONFLICT DO NOTHING
  RETURNING id
)
SELECT COALESCE(
  (SELECT id FROM new_blueprint_images),
  (SELECT id FROM blueprint_images
   WHERE blueprint_id = {blueprint_id} AND image_id = {image_id})
) AS id
"""
    ).format(blueprint_id=sql.Literal(blueprint_id), image_id=sql.Literal(image_id))
    curs.execute(query)
    row = curs.fetchone()
    if row:
        return get_blueprint_image_by_id(curs, row["id"])
    return None


def insert_image_for_blueprint(
    curs: cursor, blueprint_id: uuid.UUID, image: dict
) -> dict:
    sprite_metadata = image.get("sprite_metadata")
    inserted_image = insert_image(
        curs,
        image["image_name"],
        image["image_url"],
        sprite_metadata=sprite_metadata,
    )
    insert_blueprint_image(curs, blueprint_id, inserted_image["id"])
    return inserted_image


def replace_images_for_blueprint(
    curs: cursor, blueprint_id: uuid.UUID, images: list[dict]
) -> dict:
    image_ids = []
    try:
        image_ids = delete_images_for_blueprint(curs, blueprint_id)
    except NotFound:
        pass
    for image in images:
        insert_image_for_blueprint(curs, blueprint_id, image)
    if image_ids:  # Only delete if we have IDs to delete
        delete_images_by_ids(curs, image_ids)


def delete_images_for_blueprint(curs: cursor, blueprint_id: uuid.UUID) -> dict:
    query = sql.SQL(
        """
DELETE FROM blueprint_images
  WHERE blueprint_id = {blueprint_id}
  RETURNING image_id
"""
    ).format(blueprint_id=sql.Literal(blueprint_id))
    curs.execute(query)
    rows = curs.fetchall()
    return [row["image_id"] for row in rows]


def get_blueprints_ids_for_image(curs: cursor, image_id: uuid.UUID) -> dict:
    query = sql.SQL(
        """
SELECT blueprint_id
  FROM blueprint_images
  WHERE image_id = {image_id}
"""
    ).format(image_id=sql.Literal(image_id))
    curs.execute(query)
    return [row["blueprint_id"] for row in curs.fetchall()]


def delete_images_by_ids(curs: cursor, image_ids: list[uuid.UUID]) -> dict:
    query = sql.SQL(
        """
DELETE FROM images
  WHERE id IN ({image_ids})
    AND NOT EXISTS (
      SELECT FROM blueprint_images bi
        WHERE  bi.image_id = images.id
    )
"""
    ).format(
        image_ids=sql.SQL(",").join(sql.Literal(image_id) for image_id in image_ids)
    )
    curs.execute(query)
    return curs.rowcount


def delete_all_images(curs: cursor) -> dict:
    query = sql.SQL("TRUNCATE images CASCADE")
    curs.execute(query)
    return curs.rowcount


def delete_image(curs: cursor, image_id: uuid.UUID) -> dict:
    query = sql.SQL(
        """
DELETE FROM blueprint_images
  WHERE image_id = {image_id}
"""
    ).format(image_id=sql.Literal(image_id))
    curs.execute(query)
    query = sql.SQL(
        """
DELETE FROM images
  WHERE id = {image_id}
"""
    ).format(image_id=sql.Literal(image_id))
    curs.execute(query)
    return curs.rowcount


def update_image(curs: cursor, image_id: uuid.UUID, data: dict) -> dict:
    newdata = {}
    newdata.update(data)
    query_list = [
        sql.SQL("UPDATE images"),
        sql.SQL("  SET"),
    ]

    fields = [
        "image_name",
        "image_url",
    ]

    comma = ""
    for field in fields:
        if field in data:
            query_list.append(
                sql.SQL(f"{comma}{field} = " + "{value}").format(value=data[field])
            )
            comma = ", "

    # Handle sprite_metadata separately as it needs Json() wrapper
    if "sprite_metadata" in data:
        query_list.append(
            sql.SQL(f"{comma}sprite_metadata = " + "{sprite_metadata}").format(
                sprite_metadata=sql.Literal(Json(data["sprite_metadata"]))
            )
        )
        comma = ", "

    query_list.append(sql.SQL(f"{comma}updated_at = NOW()"))

    query_list.append(
        sql.SQL("  WHERE id = {image_id}").format(image_id=sql.Literal(image_id))
    )
    query = sql.Composed(query_list)
    curs.execute(query.join("\n"))
    if curs.rowcount > 0:
        return get_image_by_id(curs, image_id)
    else:
        raise NotFound("Image not found")


def replace_blueprints_for_image(
    curs: cursor, image_id: uuid.UUID, blueprint_ids: list[uuid.UUID]
) -> dict:
    query = sql.SQL(
        """
DELETE FROM blueprint_images
  WHERE image_id = {image_id}
"""
    ).format(image_id=sql.Literal(image_id))
    curs.execute(query)
    for blueprint_id in blueprint_ids:
        insert_blueprint_image(curs, blueprint_id, image_id)
