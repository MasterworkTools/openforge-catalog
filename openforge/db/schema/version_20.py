"""Version 20: one live row per path

- Deprecate every live row but the newest at each full_name, linking it to that
  newest row as its successor.
- Add a partial unique index so it cannot happen again.

Editing a file and rescanning used to leave two live rows at one path. file_md5
is a blueprint's identity and is uniquely constrained, so new bytes arrive as a
new row rather than an update; nothing deprecated the row they replaced, and
there was no constraint on full_name to object. The loader keys its view of the
catalog by full_name and reads the oldest match, so it compared every later load
against the row it had already superseded and reported the file as changed
again, forever.

This migration repairs the rows that state produced, and then makes it
unreachable rather than merely unproduced.

The index is partial on `NOT deprecated` because tombstones are history: a path
accumulates one per edit, and they have to be allowed to share it with the live
row that replaced them. Config blueprints are unaffected either way — they carry
no full_name at all, and Postgres permits many NULLs in a unique index.

The repair picks the survivor by created_at rather than by anything in the
fixtures, because the fixtures are not available to a migration and the newest
row is by construction the one the most recent scan inserted. Ties broken by id
so the choice is deterministic.

Every duplicate is deprecated, with no exception for one that already carries a
successor_id: skipping any would leave it live and the index would then refuse
to build. An existing successor is kept rather than overwritten, since that
pointer is changelog history.

Down drops the index and leaves the deprecations alone. Reviving them would mean
guessing which tombstones this migration created rather than the loader, and a
duplicate live row is the defect, not a state worth restoring.
"""

from psycopg import cursor, sql

from openforge.db.schema import SchemaBase, SchemaVersionDecorator


@SchemaVersionDecorator(20)
class SchemaVersion20(SchemaBase):
    def up_impl(self, curs: cursor):
        self.deprecate_superseded_duplicates(curs)
        self.add_one_live_row_per_path(curs)

    def down_impl(self, curs: cursor):
        self.drop_one_live_row_per_path(curs)

    def deprecate_superseded_duplicates(self, curs: cursor):
        query = sql.SQL(
            """
WITH ranked AS (
  SELECT id, full_name,
         row_number() OVER (
           PARTITION BY full_name ORDER BY created_at DESC, id DESC
         ) AS rank
    FROM blueprints
   WHERE NOT deprecated AND full_name IS NOT NULL
),
survivor AS (
  SELECT full_name, id FROM ranked WHERE rank = 1
)
UPDATE blueprints AS b
   SET deprecated = true,
       successor_id = COALESCE(b.successor_id, survivor.id),
       updated_at = CURRENT_TIMESTAMP
  FROM ranked
  JOIN survivor USING (full_name)
 WHERE b.id = ranked.id
   AND ranked.rank > 1
"""
        )
        curs.execute(query)
        print(f"  deprecated {curs.rowcount} superseded duplicate rows")

    def add_one_live_row_per_path(self, curs: cursor):
        query = sql.SQL(
            """
CREATE UNIQUE INDEX blueprints_live_full_name_key
    ON blueprints (full_name)
 WHERE NOT deprecated
"""
        )
        curs.execute(query)
        print("  added blueprints_live_full_name_key")

    def drop_one_live_row_per_path(self, curs: cursor):
        query = sql.SQL(
            """
DROP INDEX IF EXISTS blueprints_live_full_name_key
"""
        )
        curs.execute(query)
        print("  dropped blueprints_live_full_name_key")
