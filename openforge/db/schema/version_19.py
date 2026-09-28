"""Version 19: a hero image for a guide

- Add guides.hero_image: the card illustration the entry page draws, one
  per guide, as an absolute URL.

A column rather than a field of the JSONB document, which is where it
started. Two reasons, and neither is about the format growing a key —
version 18 argued correctly that per-field columns would mean a migration
every time a guide learns a new kind of question, and that still holds
for everything describing *how to build* the thing.

An illustration is not that. It is a property of how the guide is
presented, it changes for reasons the build logic never sees — a better
render, a repainted model — and when guides are authored in the interface
(openforge_catalog-kcm) changing the picture must not mean rewriting the
document that says how to make a wall. A column can be updated on its
own; a key inside a JSONB blob cannot without writing the whole document
back.

Absolute rather than a path resolved against a configured host, because
production and staging share the object bucket: one URL describes the
object in both environments. Nothing in the app resolves a relative image
path today either — images.image_url is absolute and the frontend uses it
verbatim.

Not a row in `images` with a foreign key, which was the other candidate.
That table exists for the images attached to blueprints, carries
image_type and sprite_metadata that a card illustration has no use for,
and would need a join table or an enum value to say what this one is. One
nullable column is the whole requirement.

TEXT and nullable: a guide is authorable before anyone has rendered it,
and the entry page draws an empty frame for a guide with no picture
rather than refusing to list it.
"""

from psycopg import cursor, sql

from openforge.db.schema import SchemaBase, SchemaVersionDecorator


@SchemaVersionDecorator(19)
class SchemaVersion19(SchemaBase):
    def up_impl(self, curs: cursor):
        self.add_hero_image(curs)

    def down_impl(self, curs: cursor):
        self.drop_hero_image(curs)

    def add_hero_image(self, curs: cursor):
        query = sql.SQL(
            """
ALTER TABLE guides ADD COLUMN hero_image TEXT
"""
        )
        curs.execute(query)
        print("  added guides.hero_image")

    def drop_hero_image(self, curs: cursor):
        query = sql.SQL(
            """
ALTER TABLE guides DROP COLUMN IF EXISTS hero_image
"""
        )
        curs.execute(query)
        print("  dropped guides.hero_image")
