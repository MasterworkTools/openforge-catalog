"""Version 13: Enable pg_trgm extension for future search optimizations

- Enable pg_trgm extension for trigram search support
- Note: GIN index on tags would require immutable function wrapper for array_to_string
"""

from psycopg import cursor, sql

from openforge.db.schema import SchemaBase, SchemaVersionDecorator


@SchemaVersionDecorator(13)
class SchemaVersion13(SchemaBase):
    def up_impl(self, curs: cursor) -> None:
        """Apply the database changes."""
        # Enable the pg_trgm extension for future search optimizations
        query = sql.SQL("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        curs.execute(query)
        print("  ensured pg_trgm extension is enabled")

        # Note: A GIN index on tags would require creating an immutable wrapper function
        # for array_to_string, which is beyond the scope of this migration.
        # The pg_trgm extension is now available for other text search optimizations.

    def down_impl(self, curs: cursor) -> None:
        """Revert the database changes."""
        # Note: We don't drop pg_trgm extension as other parts of the system
        # might use it
        # and it's generally safe to leave extensions enabled
        pass
