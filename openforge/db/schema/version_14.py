from psycopg import cursor, sql

from openforge.db.schema import SchemaBase, SchemaVersionDecorator


@SchemaVersionDecorator(14)
class SchemaVersion14(SchemaBase):
    def up_impl(self, curs: cursor):
        """Add indexes for tag search performance."""
        # Create a GIN index directly on the tag array for array operations
        query = sql.SQL(
            """
CREATE INDEX IF NOT EXISTS idx_tags_array_gin
ON tags USING gin (tag)
"""
        )
        curs.execute(query)
        print("  created idx_tags_array_gin index for array operations")

        # Create an index on blueprint_id for faster joins
        query = sql.SQL(
            """
CREATE INDEX IF NOT EXISTS idx_tags_blueprint_id
ON tags (blueprint_id)
"""
        )
        curs.execute(query)
        print("  created idx_tags_blueprint_id index for joins")

    def down_impl(self, curs: cursor):
        """Remove indexes."""
        query = sql.SQL("DROP INDEX IF EXISTS idx_tags_array_gin")
        curs.execute(query)
        print("  dropped idx_tags_array_gin index")

        query = sql.SQL("DROP INDEX IF EXISTS idx_tags_blueprint_id")
        curs.execute(query)
        print("  dropped idx_tags_blueprint_id index")
