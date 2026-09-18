from psycopg import cursor, sql

from openforge.db.schema import SchemaBase, SchemaVersionDecorator


@SchemaVersionDecorator(4)
class SchemaVersion4(SchemaBase):
    def up_impl(self, curs: cursor):
        self.add_blueprint_search_text(curs)
        self.add_blueprint_search_text_index(curs)

    def down_impl(self, curs: cursor):
        self.drop_blueprint_search_text_index(curs)
        self.drop_blueprint_search_text(curs)

    def add_blueprint_search_text(self, curs: cursor):
        query = sql.SQL(
            """
ALTER TABLE blueprints
  ADD COLUMN search_text TEXT
"""
        )
        curs.execute(query)
        print("  added blueprint_search_text")

    def add_blueprint_search_text_index(self, curs: cursor):
        query = sql.SQL(
            """
CREATE INDEX idx_blueprints_search_text
  ON blueprints
    USING GIN (to_tsvector('english', search_text))
"""
        )
        curs.execute(query)
        print("  added blueprint_search_text_index")

    def drop_blueprint_search_text(self, curs: cursor):
        query = sql.SQL(
            """
ALTER TABLE blueprints
  DROP COLUMN search_text
"""
        )
        curs.execute(query)
        print("  dropped blueprint_search_text")

    def drop_blueprint_search_text_index(self, curs: cursor):
        query = sql.SQL(
            """
DROP INDEX IF EXISTS idx_blueprints_search_text
"""
        )
        curs.execute(query)
        print("  dropped blueprint_search_text_index")
