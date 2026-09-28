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

    The list is what the entry page renders, so it carries what a card
    shows — title, summary, illustration — rather than every step of
    every guide. `image` is null for a guide that has no illustration
    yet, which the card has to survive: a guide is authorable without
    one and the field is not required.
    """
    query = sql.SQL(
        """
SELECT id, guide_key,
       document->>'title' AS title,
       document->>'summary' AS summary,
       hero_image,
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


def upsert_guide(curs: cursor, document: dict, hero_image: str | None = None) -> dict:
    """Write a guide, keyed by the key inside it.

    Nothing supplies `guide_key`: the column is generated from
    `document->>'key'`, so the two cannot disagree no matter what a
    caller does.

    `hero_image` is beside the document rather than in it — see
    `version_19` — and defaults to None because most callers are tests
    and the API that resolves a guide, none of which have a picture to
    say anything about. It is written on conflict like the document, so
    re-loading a fixture whose illustration changed updates it; a
    re-load that omits it clears it, which is what "the fixture is the
    authored state" means everywhere else in the loader.
    """
    query = sql.SQL(
        """
INSERT INTO guides (document, hero_image)
  VALUES ({document}, {hero_image})
  ON CONFLICT (guide_key) DO UPDATE SET
    document = EXCLUDED.document,
    hero_image = EXCLUDED.hero_image,
    updated_at = CURRENT_TIMESTAMP
  RETURNING id, guide_key, document, hero_image, created_at, updated_at
"""
    ).format(
        document=sql.Literal(Jsonb(document)),
        hero_image=sql.Literal(hero_image),
    )
    curs.execute(query)
    return dict(curs.fetchone())


def delete_all_guides(curs: cursor) -> bool:
    query = sql.SQL("TRUNCATE guides CASCADE")
    curs.execute(query)
    return True
