"""Version 09: Extend documentation_type_enum

- Extend documentation_type_enum to include 'instructions'
"""

from psycopg import cursor, sql

from openforge.db.schema import SchemaBase, SchemaVersionDecorator


@SchemaVersionDecorator(9)
class SchemaVersion9(SchemaBase):
    def up_impl(self, curs: cursor):
        self.extend_documentation_type_enum(curs)

    def down_impl(self, curs: cursor):
        # Note: PostgreSQL doesn't support dropping ENUM values
        # The 'instructions' value will remain in documentation_type_enum
        # This is acceptable as it doesn't break existing functionality
        pass

    def extend_documentation_type_enum(self, curs: cursor):
        # Check if 'instructions' already exists in the enum
        query = sql.SQL(
            """
SELECT EXISTS (
    SELECT 1 FROM pg_enum
    WHERE enumtypid = 'documentation_type_enum'::regtype
    AND enumlabel = 'instructions'
)
"""
        )
        curs.execute(query)
        exists = curs.fetchone()[0]

        if not exists:
            query = sql.SQL(
                """
ALTER TYPE documentation_type_enum ADD VALUE 'instructions'
"""
            )
            curs.execute(query)
            print("  extended documentation_type_enum with 'instructions'")
        else:
            print("  'instructions' already exists in documentation_type_enum")
