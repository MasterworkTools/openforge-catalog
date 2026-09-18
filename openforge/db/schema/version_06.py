from psycopg import cursor, sql

from openforge.db.schema import SchemaBase, SchemaVersionDecorator


@SchemaVersionDecorator(6)
class SchemaVersion6(SchemaBase):
    def up_impl(self, curs: cursor):
        self.add_phase_1_fields(curs)
        self.create_phase_1_indexes(curs)

    def down_impl(self, curs: cursor):
        self.drop_phase_1_indexes(curs)
        self.drop_phase_1_fields(curs)

    def add_phase_1_fields(self, curs: cursor):
        """Add Phase 1 fields to blueprints table.

        Fields for incremental loading and versioning.
        """

        # Add consolidated_paths array
        query = sql.SQL(
            """
ALTER TABLE blueprints
  ADD COLUMN consolidated_paths TEXT[]
"""
        )
        curs.execute(query)
        print("  added consolidated_paths column")

        # Add deprecated boolean with default false
        query = sql.SQL(
            """
ALTER TABLE blueprints
  ADD COLUMN deprecated BOOLEAN DEFAULT false
"""
        )
        curs.execute(query)
        print("  added deprecated column")

        # Add successor_id UUID (nullable)
        query = sql.SQL(
            """
ALTER TABLE blueprints
  ADD COLUMN successor_id UUID
"""
        )
        curs.execute(query)
        print("  added successor_id column")

    def create_phase_1_indexes(self, curs: cursor):
        """Create indexes for Phase 1 fields for performance."""

        # Index for successor_id
        query = sql.SQL(
            """
CREATE INDEX idx_blueprints_successor
  ON blueprints(successor_id)
"""
        )
        curs.execute(query)
        print("  created idx_blueprints_successor index")

        # Index for file_md5 (if not already exists)
        query = sql.SQL(
            """
CREATE INDEX IF NOT EXISTS idx_blueprints_md5
  ON blueprints(file_md5)
"""
        )
        curs.execute(query)
        print("  created idx_blueprints_md5 index")

    def drop_phase_1_indexes(self, curs: cursor):
        """Drop Phase 1 indexes."""

        query = sql.SQL("DROP INDEX IF EXISTS idx_blueprints_successor")
        curs.execute(query)
        print("  dropped idx_blueprints_successor index")

        query = sql.SQL("DROP INDEX IF EXISTS idx_blueprints_md5")
        curs.execute(query)
        print("  dropped idx_blueprints_md5 index")

    def drop_phase_1_fields(self, curs: cursor):
        """Drop Phase 1 fields from blueprints table."""

        # Drop columns in reverse order
        columns = ["successor_id", "deprecated", "consolidated_paths"]

        for column in columns:
            query = sql.SQL(
                """
ALTER TABLE blueprints
  DROP COLUMN IF EXISTS {column}
"""
            ).format(column=sql.Identifier(column))
            curs.execute(query)
            print(f"  dropped {column} column")
