"""Version 16: Add sprite sheet support to images table

- Add sprite_metadata JSONB column to images table
- Support for multi-angle thumbnail sprite sheets
- Nullable for backward compatibility with legacy single thumbnails
- Stores grid layout, camera positions, and default angle
"""

from psycopg import cursor, sql

from openforge.db.schema import SchemaBase, SchemaVersionDecorator


@SchemaVersionDecorator(16)
class SchemaVersion16(SchemaBase):
    def up_impl(self, curs: cursor):
        self.add_sprite_metadata_column(curs)

    def down_impl(self, curs: cursor):
        self.remove_sprite_metadata_column(curs)

    def add_sprite_metadata_column(self, curs: cursor):
        # Add sprite_metadata JSONB column to images table
        query = sql.SQL(
            """
ALTER TABLE images
ADD COLUMN sprite_metadata JSONB
"""
        )
        curs.execute(query)
        print("  added sprite_metadata column to images table")

        # Create GIN index for JSONB queries
        query = sql.SQL(
            """
CREATE INDEX idx_images_sprite_metadata
ON images USING gin (sprite_metadata)
"""
        )
        curs.execute(query)
        print("  created idx_images_sprite_metadata GIN index")

    def remove_sprite_metadata_column(self, curs: cursor):
        query = sql.SQL("DROP INDEX IF EXISTS idx_images_sprite_metadata")
        curs.execute(query)
        print("  dropped idx_images_sprite_metadata index")

        query = sql.SQL("ALTER TABLE images DROP COLUMN IF EXISTS sprite_metadata")
        curs.execute(query)
        print("  dropped sprite_metadata column from images table")
