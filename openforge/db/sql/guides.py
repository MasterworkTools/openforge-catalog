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
    every guide.

    `hero_image` is a column rather than a field of the document, so it
    is selected rather than projected out of the JSONB — see
    `version_19`. Null for a guide nobody has photographed, which the
    card has to survive, and the only query that returns it:
    `get_guide_by_key` deliberately does not, which `upsert_guide`'s
    docstring warns a writer about.
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
    `version_19`. It is written on conflict like the document, so
    re-loading a fixture whose illustration changed updates it; a
    re-load that omits it clears it, which is what "the fixture is the
    authored state" means everywhere else in the loader.

    The default is for tests. `load_guide_fixture` is the only caller
    outside them and always passes it, and no route writes a guide at
    all, so nothing clears a picture today.

    **A writer must read `hero_image` from somewhere other than
    `get_guide_by_key`.** That query selects the document and not this
    column, so read-modify-write through it loses the URL: the row comes
    back without a picture, and writing it back clears one. Before the
    column existed the round trip was lossless because the URL rode
    inside the document. The guide editor in `openforge_catalog-kcm` is
    exactly the caller that will do this, and it is the reason the
    constraint is written here, in the function that would silently
    honour it, rather than left to be rediscovered.
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
