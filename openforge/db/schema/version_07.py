"""Version 07: Restructure documentation system

- Drop old documentation table entirely
- Remove changelog field from blueprints table
- Create new blueprint_documentation table with document and document_type fields
- Create documentation_type_enum for extensibility
"""

from psycopg import cursor, sql

from openforge.db.schema import SchemaBase, SchemaVersionDecorator


@SchemaVersionDecorator(7)
class SchemaVersion7(SchemaBase):
    def up_impl(self, curs: cursor):
        self.create_update_updated_at_function(curs)
        self.drop_old_documentation(curs)
        self.drop_old_blueprint_documentation(curs)
        self.create_documentation_type_enum(curs)
        self.create_blueprint_documentation(curs)
        self.create_blueprint_documentation_indexes(curs)

    def down_impl(self, curs: cursor):
        self.drop_blueprint_documentation_indexes(curs)
        self.drop_blueprint_documentation(curs)
        self.drop_documentation_type_enum(curs)
        self.recreate_old_documentation(curs)
        self.recreate_old_blueprint_documentation(curs)
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

    def drop_old_documentation(self, curs: cursor):
        query = sql.SQL("DROP TABLE IF EXISTS documentation CASCADE")
        curs.execute(query)
        print("  dropped old documentation table")

    def drop_old_blueprint_documentation(self, curs: cursor):
        query = sql.SQL("DROP TABLE IF EXISTS blueprint_documentation CASCADE")
        curs.execute(query)
        print("  dropped old blueprint_documentation table")

    def create_documentation_type_enum(self, curs: cursor):
        query = sql.SQL(
            """
CREATE TYPE documentation_type_enum AS ENUM ('changelog')
"""
        )
        curs.execute(query)
        print("  created documentation_type_enum")

    def create_blueprint_documentation(self, curs: cursor):
        query = sql.SQL(
            """
CREATE TABLE blueprint_documentation (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    blueprint_id uuid NOT NULL REFERENCES blueprints(id) ON DELETE CASCADE,
    document text NOT NULL,
    document_type documentation_type_enum NOT NULL DEFAULT 'changelog',
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
)
"""
        )
        curs.execute(query)
        print("  created blueprint_documentation table")

    def create_blueprint_documentation_indexes(self, curs: cursor):
        # Index for blueprint_id
        query = sql.SQL(
            """
CREATE INDEX idx_blueprint_documentation_blueprint_id
  ON blueprint_documentation(blueprint_id)
"""
        )
        curs.execute(query)
        print("  created idx_blueprint_documentation_blueprint_id index")

        # Index for document_type
        query = sql.SQL(
            """
CREATE INDEX idx_blueprint_documentation_type
  ON blueprint_documentation(document_type)
"""
        )
        curs.execute(query)
        print("  created idx_blueprint_documentation_type index")

        # Trigger for automatic updated_at timestamp updates
        query = sql.SQL(
            """
CREATE TRIGGER update_blueprint_documentation_updated_at
  BEFORE UPDATE ON blueprint_documentation
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
"""
        )
        curs.execute(query)
        print("  created blueprint_documentation updated_at trigger")

    def drop_blueprint_documentation_indexes(self, curs: cursor):
        query = sql.SQL("DROP INDEX IF EXISTS idx_blueprint_documentation_blueprint_id")
        curs.execute(query)
        print("  dropped idx_blueprint_documentation_blueprint_id index")

        query = sql.SQL("DROP INDEX IF EXISTS idx_blueprint_documentation_type")
        curs.execute(query)
        print("  dropped idx_blueprint_documentation_type index")

        query = sql.SQL(
            "DROP TRIGGER IF EXISTS update_blueprint_documentation_updated_at "
            "ON blueprint_documentation"
        )
        curs.execute(query)
        print("  dropped blueprint_documentation updated_at trigger")

    def drop_blueprint_documentation(self, curs: cursor):
        query = sql.SQL("DROP TABLE IF EXISTS blueprint_documentation CASCADE")
        curs.execute(query)
        print("  dropped blueprint_documentation table")

    def drop_documentation_type_enum(self, curs: cursor):
        query = sql.SQL("DROP TYPE IF EXISTS documentation_type_enum")
        curs.execute(query)
        print("  dropped documentation_type_enum")

    def recreate_old_blueprint_documentation(self, curs: cursor):
        query = sql.SQL(
            """
CREATE TABLE IF NOT EXISTS blueprint_documentation (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            blueprint_id uuid NOT NULL REFERENCES blueprints(id),
            documentation_id uuid NOT NULL REFERENCES documentation(id),
            created_at timestamp DEFAULT now(),
            updated_at timestamp DEFAULT now()
        )
"""
        )
        curs.execute(query)
        print("  recreated old blueprint_documentation table")

    def recreate_old_documentation(self, curs: cursor):
        query = sql.SQL(
            """
CREATE TABLE IF NOT EXISTS documentation (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            document text NOT NULL,
            documentation_type text NOT NULL DEFAULT 'instruction',
            created_at timestamp DEFAULT now(),
            updated_at timestamp DEFAULT now()
        )
"""
        )
        curs.execute(query)
        print("  recreated old documentation table")
