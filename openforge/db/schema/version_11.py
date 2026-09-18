from psycopg import sql

from openforge.db.schema import SchemaBase, SchemaVersionDecorator


@SchemaVersionDecorator(11)
class SchemaVersion11(SchemaBase):
    """Update changelog history function.

    Include all versions with default messages.
    """

    def up_impl(self, curs):
        """Update the changelog history function to include all versions."""
        self.update_changelog_history_function(curs)

    def down_impl(self, curs):
        """Revert the changelog history function to previous version."""
        self.revert_changelog_history_function(curs)

    def update_changelog_history_function(self, curs):
        """Update the changelog history function to include all versions."""
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
        print(
            "  updated get_blueprint_changelog_history function to include all versions"
        )

    def revert_changelog_history_function(self, curs):
        """Revert the changelog history function to previous version."""
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
            bd.document,
            bd.created_at,
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
            bd.document,
            bd.created_at,
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
        print("  reverted get_blueprint_changelog_history function to previous version")
