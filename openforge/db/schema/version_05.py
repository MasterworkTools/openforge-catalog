from psycopg import cursor, sql

from openforge.db.schema import SchemaBase, SchemaVersionDecorator


@SchemaVersionDecorator(5)
class SchemaVersion5(SchemaBase):
    def up_impl(self, curs: cursor):
        self.create_tag_descriptions(curs)
        self.create_tag_descriptions_index(curs)

    def down_impl(self, curs: cursor):
        self.drop_tag_descriptions_index(curs)
        self.drop_tag_descriptions(curs)

    def create_tag_descriptions(self, curs: cursor):
        query = sql.SQL(
            """
CREATE TABLE tag_descriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tag TEXT ARRAY NOT NULL UNIQUE,
  description TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""
        )
        curs.execute(query)
        print("  created tag_descriptions")

    def create_tag_descriptions_index(self, curs: cursor):
        query = sql.SQL(
            """
CREATE INDEX idx_tag_descriptions_tag
  ON tag_descriptions
    USING BTREE (tag)
"""
        )
        curs.execute(query)
        print("  created tag_descriptions_index")

    def drop_tag_descriptions(self, curs: cursor):
        query = sql.SQL("DROP TABLE tag_descriptions")
        curs.execute(query)
        print("  dropped tag_descriptions")

    def drop_tag_descriptions_index(self, curs: cursor):
        query = sql.SQL(
            """
DROP INDEX IF EXISTS idx_tag_descriptions_tag
"""
        )
        curs.execute(query)
        print("  dropped tag_descriptions_index")
