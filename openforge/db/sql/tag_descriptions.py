import uuid

from psycopg import sql
from werkzeug.exceptions import NotFound

from .tag_utils import convert_tag_dict, tag_to_array


def get_all_tag_descriptions(curs):
    query = sql.SQL(
        """
SELECT id, tag, description, created_at, updated_at
  FROM tag_descriptions
  ORDER BY tag
"""
    )
    curs.execute(query)
    return [convert_tag_dict(dict(row)) for row in curs.fetchall()]


def get_tag_description_by_id(curs, tag_description_id: uuid.UUID):
    query = sql.SQL(
        """
SELECT id, tag, description, created_at, updated_at
  FROM tag_descriptions
  WHERE id = {id}
"""
    ).format(id=sql.Literal(tag_description_id))
    curs.execute(query)
    result = curs.fetchone()
    if not result:
        raise NotFound("Tag description not found")
    return convert_tag_dict(dict(result))


def get_tag_description_by_tag(curs, tag):
    """Get tag descriptions by tag, including child tags (prefix match)."""
    tag_arr = tag_to_array(tag)
    n = len(tag_arr)
    query = sql.SQL(
        """
        SELECT id, tag, description, created_at, updated_at
        FROM tag_descriptions
        WHERE tag[1:{n}] = {prefix}
        ORDER BY array_length(tag, 1), tag
        """
    ).format(n=sql.Literal(n), prefix=sql.Literal(tag_arr))
    curs.execute(query)
    return [convert_tag_dict(dict(row)) for row in curs.fetchall()]


def insert_tag_description(curs, tag: list[str], description: str):
    query = sql.SQL(
        """
INSERT INTO tag_descriptions (tag, description)
  VALUES ({tag}, {description})
  RETURNING id, tag, description, created_at, updated_at
"""
    ).format(tag=sql.Literal(tag), description=sql.Literal(description))
    curs.execute(query)
    return convert_tag_dict(dict(curs.fetchone()))


def upsert_tag_description(curs, tag: list[str], description: str):
    """Insert tag description or update if it already exists."""
    query = sql.SQL(
        """
INSERT INTO tag_descriptions (tag, description)
  VALUES ({tag}, {description})
  ON CONFLICT (tag) DO UPDATE SET
    description = EXCLUDED.description,
    updated_at = CURRENT_TIMESTAMP
  RETURNING id, tag, description, created_at, updated_at
"""
    ).format(tag=sql.Literal(tag), description=sql.Literal(description))
    curs.execute(query)
    return convert_tag_dict(dict(curs.fetchone()))


def update_tag_description(curs, tag_description_id: uuid.UUID, description: str):
    query = sql.SQL(
        """
UPDATE tag_descriptions
  SET description = {description},
      updated_at = CURRENT_TIMESTAMP
  WHERE id = {tag_description_id}
  RETURNING id, tag, description, created_at, updated_at
"""
    ).format(
        description=sql.Literal(description),
        tag_description_id=sql.Literal(tag_description_id),
    )
    curs.execute(query)
    result = curs.fetchone()
    if not result:
        raise NotFound("Tag description not found")
    return convert_tag_dict(dict(result))


def update_tag_description_by_tag(curs, tag, description: str):
    tag_arr = tag_to_array(tag)
    clauses = [
        sql.SQL("array_length(tag, 1) = {n}").format(n=sql.Literal(len(tag_arr)))
    ]
    for i, val in enumerate(tag_arr):
        clauses.append(
            sql.SQL("tag[{i}] = {val}").format(
                i=sql.Literal(i + 1), val=sql.Literal(val)
            )
        )
    where_clause = sql.SQL(" AND ").join(clauses)
    query = sql.SQL(
        """
UPDATE tag_descriptions
  SET description = {description},
      updated_at = CURRENT_TIMESTAMP
  WHERE {where_clause}
  RETURNING id, tag, description, created_at, updated_at
"""
    ).format(where_clause=where_clause, description=sql.Literal(description))
    curs.execute(query)
    result = curs.fetchone()
    if not result:
        raise NotFound("Tag description not found")
    return convert_tag_dict(dict(result))


def delete_tag_description(curs, tag_description_id: uuid.UUID):
    query = sql.SQL(
        """
DELETE FROM tag_descriptions
  WHERE id = {tag_description_id}
  RETURNING id
"""
    ).format(tag_description_id=sql.Literal(tag_description_id))
    curs.execute(query)
    result = curs.fetchone()
    if not result:
        raise NotFound("Tag description not found")
    return dict(result)


def delete_tag_description_by_tag(curs, tag):
    tag_arr = tag_to_array(tag)
    clauses = [
        sql.SQL("array_length(tag, 1) = {n}").format(n=sql.Literal(len(tag_arr)))
    ]
    for i, val in enumerate(tag_arr):
        clauses.append(
            sql.SQL("tag[{i}] = {val}").format(
                i=sql.Literal(i + 1), val=sql.Literal(val)
            )
        )
    where_clause = sql.SQL(" AND ").join(clauses)
    query = sql.SQL(
        """
DELETE FROM tag_descriptions
  WHERE {where_clause}
  RETURNING id
"""
    ).format(where_clause=where_clause)
    curs.execute(query)
    result = curs.fetchone()
    if not result:
        raise NotFound("Tag description not found")
    return dict(result)


def delete_all_tag_descriptions(curs) -> bool:
    query = sql.SQL("TRUNCATE tag_descriptions CASCADE")
    curs.execute(query)
    return True
