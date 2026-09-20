"""Version 18: guides table

- Create guides table: one row per guide document — the inverted
  blueprint that answers "how do I make a wall?" by naming the parts
  that make the thing, rather than the slots a part accepts.

The whole document lives in a single JSONB column. Guides are authored
as data (repo fixtures loaded by bin/fixtures, see
docs/design/guided-builds.md), the loader validates them against
openforge/openapi/schemas/guide.yaml before they land, and the only
thing the application looks a guide up by is its key. Columns per field
would buy nothing and would mean a migration every time the guide format
grows a key.
"""

from psycopg import cursor, sql

from openforge.db.schema import SchemaBase, SchemaVersionDecorator


@SchemaVersionDecorator(18)
class SchemaVersion18(SchemaBase):
    def up_impl(self, curs: cursor):
        self.create_guides(curs)

    def down_impl(self, curs: cursor):
        self.drop_guides(curs)

    def create_guides(self, curs: cursor):
        query = sql.SQL(
            """
CREATE TABLE guides (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  guide_key TEXT NOT NULL,
  document JSONB NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (guide_key)
)
"""
        )
        curs.execute(query)
        print("  created guides")

    def drop_guides(self, curs: cursor):
        query = sql.SQL("DROP TABLE guides")
        curs.execute(query)
        print("  dropped guides")
