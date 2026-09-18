"""Version 10: Phase 2 Documentation System Implementation

- Add image_type support to images table
- Create tag_documentation table following blueprint_documentation pattern
- Create sessions table for admin authentication
- Create SQL functions for documentation operations
"""

from psycopg import cursor, sql

from openforge.db.schema import SchemaBase, SchemaVersionDecorator


@SchemaVersionDecorator(10)
class SchemaVersion10(SchemaBase):
    def up_impl(self, curs: cursor):
        self.add_image_type_support(curs)
        self.create_tag_documentation_table(curs)
        self.create_sessions_table(curs)
        self.migrate_existing_images(curs)
        self.create_documentation_functions(curs)

    def down_impl(self, curs: cursor):
        self.drop_documentation_functions(curs)
        self.drop_sessions_table(curs)
        self.drop_tag_documentation_table(curs)
        self.remove_image_type_support(curs)

    def add_image_type_support(self, curs: cursor):
        # Create image_type_enum
        query = sql.SQL(
            """
CREATE TYPE image_type_enum AS ENUM ('thumbnail', 'documentation')
"""
        )
        curs.execute(query)
        print("  created image_type_enum")

        # Add image_type column to images table
        query = sql.SQL(
            """
ALTER TABLE images ADD COLUMN image_type image_type_enum NOT NULL DEFAULT 'thumbnail'
"""
        )
        curs.execute(query)
        print("  added image_type column to images table")

        # Create index for performance
        query = sql.SQL(
            """
CREATE INDEX idx_images_type ON images(image_type)
"""
        )
        curs.execute(query)
        print("  created idx_images_type index")

    def create_tag_documentation_table(self, curs: cursor):
        query = sql.SQL(
            """
CREATE TABLE tag_documentation (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tag text[] NOT NULL,
    document text NOT NULL,
    document_type documentation_type_enum NOT NULL DEFAULT 'instructions',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
)
"""
        )
        curs.execute(query)
        print("  created tag_documentation table")

        # Indexes for performance
        query = sql.SQL(
            """
CREATE INDEX idx_tag_documentation_tag ON tag_documentation USING GIN(tag)
"""
        )
        curs.execute(query)
        print("  created idx_tag_documentation_tag index")

        query = sql.SQL(
            """
CREATE INDEX idx_tag_documentation_type ON tag_documentation(document_type)
"""
        )
        curs.execute(query)
        print("  created idx_tag_documentation_type index")

        # Trigger for automatic updated_at timestamp updates
        query = sql.SQL(
            """
CREATE TRIGGER update_tag_documentation_updated_at
  BEFORE UPDATE ON tag_documentation
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
"""
        )
        curs.execute(query)
        print("  created tag_documentation updated_at trigger")

    def create_sessions_table(self, curs: cursor):
        query = sql.SQL(
            """
CREATE TABLE sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_token_hash text NOT NULL UNIQUE,
    created_at timestamptz DEFAULT now(),
    expires_at timestamptz NOT NULL,
    last_used_at timestamptz NOT NULL DEFAULT now()
)
"""
        )
        curs.execute(query)
        print("  created sessions table")

        # Indexes for performance
        query = sql.SQL(
            """
CREATE INDEX idx_sessions_token ON sessions(session_token_hash)
"""
        )
        curs.execute(query)
        print("  created idx_sessions_token index")

        query = sql.SQL(
            """
CREATE INDEX idx_sessions_expires ON sessions(expires_at)
"""
        )
        curs.execute(query)
        print("  created idx_sessions_expires index")

        # Trigger function to update last_used_at column
        # (only if more than 1 hour has passed)
        query = sql.SQL(
            """
CREATE OR REPLACE FUNCTION update_last_used_at_column()
RETURNS TRIGGER AS $$
BEGIN
    IF EXTRACT(EPOCH FROM (now() - OLD.last_used_at)) > 3600 THEN
        NEW.last_used_at := now();
    ELSE
        NEW.last_used_at := OLD.last_used_at;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""
        )
        curs.execute(query)
        print("  created update_last_used_at_column function")

        # Trigger for automatic last_used_at updates on UPDATE
        query = sql.SQL(
            """
CREATE TRIGGER update_sessions_last_used
  BEFORE UPDATE ON sessions
  FOR EACH ROW EXECUTE FUNCTION update_last_used_at_column()
"""
        )
        curs.execute(query)
        print("  created sessions last_used_at trigger")

    def create_documentation_functions(self, curs: cursor):
        # Function to get changelog history recursively
        query = sql.SQL(
            """
CREATE OR REPLACE FUNCTION get_blueprint_changelog_history(
    p_blueprint_id uuid,
    p_max_depth integer DEFAULT 10
) RETURNS TABLE (
    blueprint_id uuid,
    blueprint_name text,
    changelog text,
    created_at timestamptz,
    depth integer,
    successor_id uuid,
    deprecated boolean
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE changelog_chain AS (
        -- Start with the current blueprint
        SELECT
            b.id,
            b.blueprint_name,
            b.successor_id,
            COALESCE(bd.document, 'Initial version') as document,
            COALESCE(bd.created_at, b.created_at) as created_at,
            0 as depth,
            b.deprecated
        FROM blueprints b
        LEFT JOIN blueprint_documentation bd ON b.id = bd.blueprint_id
            AND bd.document_type = 'changelog'
        WHERE b.id = p_blueprint_id

        UNION ALL

        -- Follow successor chain
        SELECT
            b.id,
            b.blueprint_name,
            b.successor_id,
            COALESCE(bd.document, 'Initial version') as document,
            COALESCE(bd.created_at, b.created_at) as created_at,
            cc.depth + 1,
            b.deprecated
        FROM blueprints b
        LEFT JOIN blueprint_documentation bd ON b.id = bd.blueprint_id
            AND bd.document_type = 'changelog'
        INNER JOIN changelog_chain cc ON b.id = cc.successor_id
        WHERE cc.depth < p_max_depth AND cc.successor_id IS NOT NULL
    )
    SELECT
        cc.id,
        cc.blueprint_name,
        cc.document,
        cc.created_at::timestamptz,
        cc.depth,
        cc.successor_id,
        cc.deprecated
    FROM changelog_chain cc
    ORDER BY depth ASC, created_at DESC NULLS LAST;
END;
$$ LANGUAGE plpgsql
"""
        )
        curs.execute(query)
        print("  created get_blueprint_changelog_history function")

    def migrate_existing_images(self, curs: cursor):
        # All existing images are automatically set to 'thumbnail' type
        # due to the NOT NULL DEFAULT 'thumbnail' constraint
        print("  existing images automatically migrated to 'thumbnail' type")

    def drop_documentation_functions(self, curs: cursor):
        query = sql.SQL(
            "DROP FUNCTION IF EXISTS get_blueprint_changelog_history(uuid, integer)"
        )
        curs.execute(query)
        print("  dropped get_blueprint_changelog_history function")

    def drop_sessions_table(self, curs: cursor):
        query = sql.SQL("DROP TRIGGER IF EXISTS update_sessions_last_used ON sessions")
        curs.execute(query)
        print("  dropped sessions last_used_at trigger")

        query = sql.SQL("DROP FUNCTION IF EXISTS update_last_used_at_column()")
        curs.execute(query)
        print("  dropped update_last_used_at_column function")

        query = sql.SQL("DROP INDEX IF EXISTS idx_sessions_expires")
        curs.execute(query)
        print("  dropped idx_sessions_expires index")

        query = sql.SQL("DROP INDEX IF EXISTS idx_sessions_token")
        curs.execute(query)
        print("  dropped idx_sessions_token index")

        query = sql.SQL("DROP TABLE IF EXISTS sessions CASCADE")
        curs.execute(query)
        print("  dropped sessions table")

    def drop_tag_documentation_table(self, curs: cursor):
        query = sql.SQL(
            "DROP TRIGGER IF EXISTS update_tag_documentation_updated_at "
            "ON tag_documentation"
        )
        curs.execute(query)
        print("  dropped tag_documentation updated_at trigger")

        query = sql.SQL("DROP INDEX IF EXISTS idx_tag_documentation_type")
        curs.execute(query)
        print("  dropped idx_tag_documentation_type index")

        query = sql.SQL("DROP INDEX IF EXISTS idx_tag_documentation_tag")
        curs.execute(query)
        print("  dropped idx_tag_documentation_tag index")

        query = sql.SQL("DROP TABLE IF EXISTS tag_documentation CASCADE")
        curs.execute(query)
        print("  dropped tag_documentation table")

    def remove_image_type_support(self, curs: cursor):
        query = sql.SQL("DROP INDEX IF EXISTS idx_images_type")
        curs.execute(query)
        print("  dropped idx_images_type index")

        query = sql.SQL("ALTER TABLE images DROP COLUMN IF EXISTS image_type")
        curs.execute(query)
        print("  dropped image_type column from images table")

        query = sql.SQL("DROP TYPE IF EXISTS image_type_enum")
        curs.execute(query)
        print("  dropped image_type_enum")
