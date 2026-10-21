from psycopg import cursor, sql

from openforge.db.schema import SchemaBase, SchemaVersionDecorator


@SchemaVersionDecorator(15)
class SchemaVersion15(SchemaBase):
    def up_impl(self, curs: cursor):
        """Add user authentication tables."""
        # Create patreon_tier_enum type
        query = sql.SQL(
            """
CREATE TYPE patreon_tier_enum AS ENUM ('Bronze', 'Silver', 'Gold', 'Platinum')
"""
        )
        curs.execute(query)
        print("  created patreon_tier_enum type")

        # Create users table
        query = sql.SQL(
            """
CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL UNIQUE,
    role text NOT NULL DEFAULT 'user',
    patreon_tier patreon_tier_enum,
    blocked boolean DEFAULT false,
    blocked_at timestamp,
    blocked_reason text,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
)
"""
        )
        curs.execute(query)
        print("  created users table")

        # Create user_identities table
        query = sql.SQL(
            """
CREATE TABLE user_identities (
    provider text NOT NULL,
    provider_id text NOT NULL,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (provider, provider_id)
)
"""
        )
        curs.execute(query)
        print("  created user_identities table")

        # Create index on user_identities.user_id
        query = sql.SQL(
            """
CREATE INDEX idx_user_identities_user_id ON user_identities(user_id)
"""
        )
        curs.execute(query)
        print("  created idx_user_identities_user_id index")

        # Create index on users.email
        query = sql.SQL(
            """
CREATE INDEX idx_users_email ON users(email)
"""
        )
        curs.execute(query)
        print("  created idx_users_email index")

        # Create index on users.patreon_tier
        query = sql.SQL(
            """
CREATE INDEX idx_users_patreon_tier ON users(patreon_tier)
"""
        )
        curs.execute(query)
        print("  created idx_users_patreon_tier index")

        # Add created_by and updated_by to blueprints table
        query = sql.SQL(
            """
ALTER TABLE blueprints
ADD COLUMN created_by uuid REFERENCES users(id) ON DELETE SET NULL,
ADD COLUMN updated_by uuid REFERENCES users(id) ON DELETE SET NULL
"""
        )
        curs.execute(query)
        print("  added created_by and updated_by to blueprints table")

        # Add created_by and updated_by to tags table
        query = sql.SQL(
            """
ALTER TABLE tags
ADD COLUMN created_by uuid REFERENCES users(id) ON DELETE SET NULL,
ADD COLUMN updated_by uuid REFERENCES users(id) ON DELETE SET NULL
"""
        )
        curs.execute(query)
        print("  added created_by and updated_by to tags table")

        # Add created_by and updated_by to tag_descriptions table
        query = sql.SQL(
            """
ALTER TABLE tag_descriptions
ADD COLUMN created_by uuid REFERENCES users(id) ON DELETE SET NULL,
ADD COLUMN updated_by uuid REFERENCES users(id) ON DELETE SET NULL
"""
        )
        curs.execute(query)
        print("  added created_by and updated_by to tag_descriptions table")

        # Add created_by and updated_by to images table
        query = sql.SQL(
            """
ALTER TABLE images
ADD COLUMN created_by uuid REFERENCES users(id) ON DELETE SET NULL,
ADD COLUMN updated_by uuid REFERENCES users(id) ON DELETE SET NULL
"""
        )
        curs.execute(query)
        print("  added created_by and updated_by to images table")

        # Create updated_at trigger function if it doesn't exist
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
        print("  created update_updated_at_column trigger function")

        # Create trigger for users table
        query = sql.SQL(
            """
CREATE TRIGGER update_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
"""
        )
        curs.execute(query)
        print("  created update_users_updated_at trigger")

        # Create trigger for user_identities table
        query = sql.SQL(
            """
CREATE TRIGGER update_user_identities_updated_at
BEFORE UPDATE ON user_identities
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
"""
        )
        curs.execute(query)
        print("  created update_user_identities_updated_at trigger")

        # Add user_id column to sessions table
        query = sql.SQL(
            """
ALTER TABLE sessions
ADD COLUMN user_id uuid REFERENCES users(id) ON DELETE CASCADE
"""
        )
        curs.execute(query)
        print("  added user_id to sessions table")

        # Create index on user_id for performance
        query = sql.SQL(
            """
CREATE INDEX idx_sessions_user_id ON sessions(user_id)
"""
        )
        curs.execute(query)
        print("  created idx_sessions_user_id index")

    def down_impl(self, curs: cursor):
        """Remove user authentication tables."""
        # Drop sessions indexes and columns first
        query = sql.SQL("DROP INDEX IF EXISTS idx_sessions_user_id")
        curs.execute(query)
        print("  dropped idx_sessions_user_id index")

        query = sql.SQL("ALTER TABLE sessions DROP COLUMN IF EXISTS user_id")
        curs.execute(query)
        print("  removed user_id from sessions table")

        # Drop triggers first
        query = sql.SQL(
            "DROP TRIGGER IF EXISTS "
            "update_user_identities_updated_at ON user_identities"
        )
        curs.execute(query)
        print("  dropped update_user_identities_updated_at trigger")

        query = sql.SQL("DROP TRIGGER IF EXISTS update_users_updated_at ON users")
        curs.execute(query)
        print("  dropped update_users_updated_at trigger")

        # Remove created_by and updated_by columns
        query = sql.SQL(
            "ALTER TABLE images DROP COLUMN IF EXISTS created_by, "
            "DROP COLUMN IF EXISTS updated_by"
        )
        curs.execute(query)
        print("  removed created_by and updated_by from images table")

        query = sql.SQL(
            "ALTER TABLE tag_descriptions DROP COLUMN IF EXISTS created_by, "
            "DROP COLUMN IF EXISTS updated_by"
        )
        curs.execute(query)
        print("  removed created_by and updated_by from tag_descriptions table")

        query = sql.SQL(
            "ALTER TABLE tags DROP COLUMN IF EXISTS created_by, "
            "DROP COLUMN IF EXISTS updated_by"
        )
        curs.execute(query)
        print("  removed created_by and updated_by from tags table")

        query = sql.SQL(
            "ALTER TABLE blueprints DROP COLUMN IF EXISTS created_by, "
            "DROP COLUMN IF EXISTS updated_by"
        )
        curs.execute(query)
        print("  removed created_by and updated_by from blueprints table")

        # Drop indexes
        query = sql.SQL("DROP INDEX IF EXISTS idx_users_patreon_tier")
        curs.execute(query)
        print("  dropped idx_users_patreon_tier index")

        query = sql.SQL("DROP INDEX IF EXISTS idx_users_email")
        curs.execute(query)
        print("  dropped idx_users_email index")

        query = sql.SQL("DROP INDEX IF EXISTS idx_user_identities_user_id")
        curs.execute(query)
        print("  dropped idx_user_identities_user_id index")

        # Drop tables
        query = sql.SQL("DROP TABLE IF EXISTS user_identities")
        curs.execute(query)
        print("  dropped user_identities table")

        query = sql.SQL("DROP TABLE IF EXISTS users")
        curs.execute(query)
        print("  dropped users table")

        # Drop enum type
        query = sql.SQL("DROP TYPE IF EXISTS patreon_tier_enum")
        curs.execute(query)
        print("  dropped patreon_tier_enum type")
