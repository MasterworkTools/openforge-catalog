"""Guide documents: the inverse of a blueprint.

A guide names a thing someone wants to build and the roles it is made
of; see docs/design/guided-builds.md. The document is stored whole as
JSONB and validated before it is written, so these functions do no
munging beyond looking a guide up by its key.
"""

from psycopg import cursor, sql
from psycopg.types.json import Jsonb
from werkzeug.exceptions import NotFound


def get_all_guides(curs: cursor) -> list[dict]:
    """List guides without their documents.

    The list is what a landing page renders, so it carries only the
    title and summary rather than every step of every guide.
    """
    query = sql.SQL(
        """
SELECT id, guide_key,
       document->>'title' AS title,
       document->>'summary' AS summary,
       created_at, updated_at
  FROM guides
  ORDER BY guide_key
"""
    )
    curs.execute(query)
    return [dict(row) for row in curs.fetchall()]


def get_guide_by_key(curs: cursor, guide_key: str) -> dict:
    query = sql.SQL(
        """
SELECT id, guide_key, document, created_at, updated_at
  FROM guides
  WHERE guide_key = {guide_key}
"""
    ).format(guide_key=sql.Literal(guide_key))
    curs.execute(query)
    result = curs.fetchone()
    if not result:
        raise NotFound(f"Guide not found: {guide_key}")
    return dict(result)


def upsert_guide(curs: cursor, document: dict) -> dict:
    """Write a guide, keyed by the key inside it.

    The column and `document->>'key'` cannot drift apart because the
    caller never gets to say what the key is.
    """
    guide_key = document["key"]
    query = sql.SQL(
        """
INSERT INTO guides (guide_key, document)
  VALUES ({guide_key}, {document})
  ON CONFLICT (guide_key) DO UPDATE SET
    document = EXCLUDED.document,
    updated_at = CURRENT_TIMESTAMP
  RETURNING id, guide_key, document, created_at, updated_at
"""
    ).format(
        guide_key=sql.Literal(guide_key),
        document=sql.Literal(Jsonb(document)),
    )
    curs.execute(query)
    return dict(curs.fetchone())


def delete_all_guides(curs: cursor) -> bool:
    query = sql.SQL("TRUNCATE guides CASCADE")
    curs.execute(query)
    return True
