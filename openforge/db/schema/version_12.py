"""Version 12: Add is_live flag to documentation tables

- Add is_live column to blueprint_documentation table
- Add is_live column to tag_documentation table
- Set existing documentation as live by default
- Add indexes for performance
"""

from psycopg import cursor, sql

from openforge.db.schema import SchemaBase, SchemaVersionDecorator


@SchemaVersionDecorator(12)
class SchemaVersion12(SchemaBase):
    def up_impl(self, curs: cursor):
        self.add_is_live_to_blueprint_documentation(curs)
        self.add_is_live_to_tag_documentation(curs)
        self.create_documentation_indexes(curs)
        self.update_changelog_history_function(curs)
        self.create_find_current_version_function(curs)

    def down_impl(self, curs: cursor):
        self.drop_find_current_version_function(curs)
        self.revert_changelog_history_function(curs)
        self.drop_documentation_indexes(curs)
        self.remove_is_live_from_tag_documentation(curs)
        self.remove_is_live_from_blueprint_documentation(curs)

    def add_is_live_to_blueprint_documentation(self, curs: cursor):
        # Add is_live column to blueprint_documentation table
        query = sql.SQL(
            """
ALTER TABLE blueprint_documentation
ADD COLUMN is_live boolean NOT NULL DEFAULT false
"""
        )
        curs.execute(query)
        print("  added is_live column to blueprint_documentation table")

        # Set the most recent document of each type per blueprint as live
        query = sql.SQL(
            """
WITH latest_docs AS (
    SELECT DISTINCT ON (blueprint_id, document_type) id
    FROM blueprint_documentation
    ORDER BY blueprint_id, document_type, created_at DESC
)
UPDATE blueprint_documentation
SET is_live = true
WHERE id IN (SELECT id FROM latest_docs)
"""
        )
        curs.execute(query)
        print(f"  set {curs.rowcount} most recent documents as live")

    def add_is_live_to_tag_documentation(self, curs: cursor):
        # Add is_live column to tag_documentation table
        query = sql.SQL(
            """
ALTER TABLE tag_documentation
ADD COLUMN is_live boolean NOT NULL DEFAULT false
"""
        )
        curs.execute(query)
        print("  added is_live column to tag_documentation table")

        # Set the most recent document of each type per tag as live
        query = sql.SQL(
            """
WITH latest_docs AS (
    SELECT DISTINCT ON (tag, document_type) id
    FROM tag_documentation
    ORDER BY tag, document_type, created_at DESC
)
UPDATE tag_documentation
SET is_live = true
WHERE id IN (SELECT id FROM latest_docs)
"""
        )
        curs.execute(query)
        print(f"  set {curs.rowcount} most recent tag documents as live")

    def create_documentation_indexes(self, curs: cursor):
        # Create composite indexes for better performance on common queries
        # These indexes support filtering by blueprint_id/tag + document_type + is_live
        query = sql.SQL(
            """
CREATE INDEX idx_blueprint_documentation_composite
ON blueprint_documentation(blueprint_id, document_type, is_live)
"""
        )
        curs.execute(query)
        print("  created idx_blueprint_documentation_composite index")

        query = sql.SQL(
            """
CREATE INDEX idx_tag_documentation_composite
ON tag_documentation(tag, document_type, is_live)
"""
        )
        curs.execute(query)
        print("  created idx_tag_documentation_composite index")

        # Create unique indexes to enforce business rule:
        # only one live instructions document per blueprint/tag
        # This prevents data integrity issues that the frontend currently
        # handles defensively
        query = sql.SQL(
            """
CREATE UNIQUE INDEX idx_blueprint_documentation_unique_live_instructions
ON blueprint_documentation (blueprint_id, document_type)
WHERE is_live = true AND document_type = 'instructions'
"""
        )
        curs.execute(query)
        print("  created idx_blueprint_documentation_unique_live_instructions index")

        query = sql.SQL(
            """
CREATE UNIQUE INDEX idx_tag_documentation_unique_live_instructions
ON tag_documentation (tag, document_type)
WHERE is_live = true AND document_type = 'instructions'
"""
        )
        curs.execute(query)
        print("  created idx_tag_documentation_unique_live_instructions index")

    def drop_documentation_indexes(self, curs: cursor):
        query = sql.SQL("DROP INDEX IF EXISTS idx_tag_documentation_composite")
        curs.execute(query)
        print("  dropped idx_tag_documentation_composite index")

        query = sql.SQL("DROP INDEX IF EXISTS idx_blueprint_documentation_composite")
        curs.execute(query)
        print("  dropped idx_blueprint_documentation_composite index")

        query = sql.SQL(
            "DROP INDEX IF EXISTS idx_tag_documentation_unique_live_instructions"
        )
        curs.execute(query)
        print("  dropped idx_tag_documentation_unique_live_instructions index")

        query = sql.SQL(
            "DROP INDEX IF EXISTS idx_blueprint_documentation_unique_live_instructions"
        )
        curs.execute(query)
        print("  dropped idx_blueprint_documentation_unique_live_instructions index")

    def remove_is_live_from_tag_documentation(self, curs: cursor):
        query = sql.SQL("ALTER TABLE tag_documentation DROP COLUMN IF EXISTS is_live")
        curs.execute(query)
        print("  dropped is_live column from tag_documentation table")

    def remove_is_live_from_blueprint_documentation(self, curs: cursor):
        query = sql.SQL(
            "ALTER TABLE blueprint_documentation DROP COLUMN IF EXISTS is_live"
        )
        curs.execute(query)
        print("  dropped is_live column from blueprint_documentation table")

    def update_changelog_history_function(self, curs: cursor):
        """Update the changelog history function.

        Show proper messages for missing changelogs.
        """
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
    WITH RECURSIVE full_chain AS (
        -- First, find the root (first version) by following predecessor chain backwards
        WITH RECURSIVE predecessor_chain AS (
            -- Start with the current blueprint
            SELECT
                b.id,
                b.blueprint_name,
                b.successor_id,
                b.deprecated,
                0 as depth
            FROM blueprints b
            WHERE b.id = p_blueprint_id

            UNION ALL

            -- Follow predecessor chain backwards
            SELECT
                b.id,
                b.blueprint_name,
                b.successor_id,
                b.deprecated,
                pc.depth + 1
            FROM blueprints b
            INNER JOIN predecessor_chain pc ON b.successor_id = pc.id
            WHERE pc.depth < p_max_depth
        )
        SELECT
            b.id,
            b.blueprint_name,
            b.successor_id,
            b.created_at,
            0 as depth,  -- Root always starts at depth 0
            b.deprecated
        FROM predecessor_chain pc
        INNER JOIN blueprints b ON pc.id = b.id
        WHERE pc.depth = (
            SELECT MAX(pc2.depth) FROM predecessor_chain pc2
        )

        UNION ALL

        -- Then follow successor chain forward from the root
        SELECT
            b.id,
            b.blueprint_name,
            b.successor_id,
            b.created_at,
            fc.depth + 1,
            b.deprecated
        FROM blueprints b
        INNER JOIN full_chain fc ON b.id = fc.successor_id
        WHERE fc.depth < p_max_depth AND fc.successor_id IS NOT NULL
    )
    SELECT
        fc.id,
        fc.blueprint_name,
        bd.document as changelog,
        fc.created_at::timestamptz,
        fc.depth,
        fc.successor_id,
        fc.deprecated
    FROM full_chain fc
    LEFT JOIN blueprint_documentation bd ON fc.id = bd.blueprint_id
        AND bd.document_type = 'changelog'
    ORDER BY fc.depth ASC, fc.created_at DESC NULLS LAST;
END;
$$ LANGUAGE plpgsql
"""
        )
        curs.execute(query)
        print(
            "  updated get_blueprint_changelog_history function to handle "
            "missing changelogs properly"
        )

    def revert_changelog_history_function(self, curs: cursor):
        """Revert the changelog history function to version 11 state."""
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
    WITH RECURSIVE full_chain AS (
        -- First, find the root (first version) by following predecessor chain backwards
        WITH RECURSIVE predecessor_chain AS (
            -- Start with the current blueprint
            SELECT
                b.id,
                b.blueprint_name,
                b.successor_id,
                b.deprecated,
                0 as depth
            FROM blueprints b
            WHERE b.id = p_blueprint_id

            UNION ALL

            -- Follow predecessor chain backwards
            SELECT
                b.id,
                b.blueprint_name,
                b.successor_id,
                b.deprecated,
                pc.depth + 1
            FROM blueprints b
            INNER JOIN predecessor_chain pc ON b.successor_id = pc.id
            WHERE pc.depth < p_max_depth
        )
        SELECT
            b.id,
            b.blueprint_name,
            b.successor_id,
            b.created_at,
            pc.depth as depth,
            b.deprecated
        FROM predecessor_chain pc
        INNER JOIN blueprints b ON pc.id = b.id
        WHERE pc.depth = (
            SELECT MAX(pc2.depth) FROM predecessor_chain pc2
        )

        UNION ALL

        -- Then follow successor chain forward from the root
        SELECT
            b.id,
            b.blueprint_name,
            b.successor_id,
            b.created_at,
            fc.depth + 1,
            b.deprecated
        FROM blueprints b
        INNER JOIN full_chain fc ON b.id = fc.successor_id
        WHERE fc.depth < p_max_depth AND fc.successor_id IS NOT NULL
    )
    SELECT
        fc.id,
        fc.blueprint_name,
        CASE
            WHEN fc.depth = 0 AND bd.document IS NULL THEN 'Initial version'
            ELSE bd.document
        END as changelog,
        fc.created_at::timestamptz,
        fc.depth,
        fc.successor_id,
        fc.deprecated
    FROM full_chain fc
    LEFT JOIN blueprint_documentation bd ON fc.id = bd.blueprint_id
        AND bd.document_type = 'changelog'
    ORDER BY fc.depth ASC, fc.created_at DESC NULLS LAST;
END;
$$ LANGUAGE plpgsql
"""
        )
        curs.execute(query)
        print("  reverted get_blueprint_changelog_history function to version 11 state")

    def create_find_current_version_function(self, curs: cursor):
        """Create function to find the current version of a blueprint.

        Follows successor chain.
        """
        query = sql.SQL(
            """
CREATE OR REPLACE FUNCTION find_current_version_by_md5(
    p_md5 text
) RETURNS uuid AS $$
DECLARE
    v_current_id uuid;
    v_next_id uuid;
    v_max_iterations integer := 100; -- Prevent infinite loops
    v_iteration integer := 0;
BEGIN
    -- Find the initial blueprint by MD5
    SELECT id INTO v_current_id
    FROM blueprints
    WHERE file_md5 = p_md5
    AND NOT deprecated  -- Start with non-deprecated if multiple exist
    ORDER BY created_at DESC
    LIMIT 1;

    -- If no non-deprecated found, try deprecated
    IF v_current_id IS NULL THEN
        SELECT id INTO v_current_id
        FROM blueprints
        WHERE file_md5 = p_md5
        ORDER BY created_at DESC
        LIMIT 1;
    END IF;

    -- If still not found, return NULL
    IF v_current_id IS NULL THEN
        RETURN NULL;
    END IF;

    -- Follow the successor chain to find the current version
    LOOP
        v_iteration := v_iteration + 1;

        -- Prevent infinite loops
        IF v_iteration > v_max_iterations THEN
            RAISE EXCEPTION 'Maximum iterations reached following successor chain';
        END IF;

        -- Check if there's a successor
        SELECT successor_id INTO v_next_id
        FROM blueprints
        WHERE id = v_current_id;

        -- If no successor, we've found the current version
        IF v_next_id IS NULL THEN
            RETURN v_current_id;
        END IF;

        -- Move to the successor
        v_current_id := v_next_id;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION find_current_version_by_id(
    p_blueprint_id uuid
) RETURNS uuid AS $$
DECLARE
    v_current_id uuid;
    v_next_id uuid;
    v_max_iterations integer := 100; -- Prevent infinite loops
    v_iteration integer := 0;
BEGIN
    v_current_id := p_blueprint_id;

    -- Follow the successor chain to find the current version
    LOOP
        v_iteration := v_iteration + 1;

        -- Prevent infinite loops
        IF v_iteration > v_max_iterations THEN
            RAISE EXCEPTION 'Maximum iterations reached following successor chain';
        END IF;

        -- Check if there's a successor
        SELECT successor_id INTO v_next_id
        FROM blueprints
        WHERE id = v_current_id;

        -- If no successor, we've found the current version
        IF v_next_id IS NULL THEN
            RETURN v_current_id;
        END IF;

        -- Move to the successor
        v_current_id := v_next_id;
    END LOOP;
END;
$$ LANGUAGE plpgsql;
"""
        )
        curs.execute(query)
        print(
            "  created find_current_version_by_md5 and "
            "find_current_version_by_id functions"
        )

    def drop_find_current_version_function(self, curs: cursor):
        """Drop the find current version functions."""
        query = sql.SQL(
            """
DROP FUNCTION IF EXISTS find_current_version_by_md5(text);
DROP FUNCTION IF EXISTS find_current_version_by_id(uuid);
"""
        )
        curs.execute(query)
        print("  dropped find_current_version functions")
