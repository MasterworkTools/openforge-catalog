"""Version 08: Create openscad_source table

- Create new openscad_source table for OpenSCAD file references
- Add proper foreign key relationship to blueprints
- Add indexes for performance
"""

from psycopg import cursor, sql

from openforge.db.schema import SchemaBase, SchemaVersionDecorator


@SchemaVersionDecorator(8)
class SchemaVersion8(SchemaBase):
    def up_impl(self, curs: cursor):
        self.create_update_updated_at_function(curs)
        self.create_openscad_source(curs)
        self.create_openscad_source_index(curs)
        self.create_openscad_source_trigger(curs)

    def down_impl(self, curs: cursor):
        self.drop_openscad_source_trigger(curs)
        self.drop_openscad_source_index(curs)
        self.drop_openscad_source(curs)
        # Note: Don't drop update_updated_at_function
        # as it might be used by other tables

    def create_update_updated_at_function(self, curs: cursor):
        query = sql.SQL(
            """
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""
        )
        curs.execute(query)
        print("  created update_updated_at_column function")

    def drop_update_updated_at_function(self, curs: cursor):
        query = sql.SQL("DROP FUNCTION IF EXISTS update_updated_at_column()")
        curs.execute(query)
        print("  dropped update_updated_at_column function")

    def create_openscad_source(self, curs: cursor):
        query = sql.SQL(
            """
CREATE TABLE openscad_source (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    blueprint_id uuid NOT NULL REFERENCES blueprints(id) ON DELETE CASCADE,
    openscad text NOT NULL,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
)
"""
        )
        curs.execute(query)
        print("  created openscad_source table")

    def create_openscad_source_index(self, curs: cursor):
        query = sql.SQL(
            """
CREATE INDEX idx_openscad_source_blueprint_id
  ON openscad_source(blueprint_id)
"""
        )
        curs.execute(query)
        print("  created idx_openscad_source_blueprint_id index")

    def create_openscad_source_trigger(self, curs: cursor):
        query = sql.SQL(
            """
CREATE TRIGGER update_openscad_source_updated_at
  BEFORE UPDATE ON openscad_source
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
"""
        )
        curs.execute(query)
        print("  created openscad_source updated_at trigger")

    def drop_openscad_source_trigger(self, curs: cursor):
        query = sql.SQL(
            "DROP TRIGGER IF EXISTS update_openscad_source_updated_at "
            "ON openscad_source"
        )
        curs.execute(query)
        print("  dropped openscad_source updated_at trigger")

    def drop_openscad_source_index(self, curs: cursor):
        query = sql.SQL("DROP INDEX IF EXISTS idx_openscad_source_blueprint_id")
        curs.execute(query)
        print("  dropped idx_openscad_source_blueprint_id index")

    def drop_openscad_source(self, curs: cursor):
        query = sql.SQL("DROP TABLE IF EXISTS openscad_source CASCADE")
        curs.execute(query)
        print("  dropped openscad_source table")
