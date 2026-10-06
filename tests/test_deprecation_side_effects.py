"""What _handle_deprecation does to the row it tombstones.

`UNIQUE (file_md5)` is table-wide, so one live and one deprecated row cannot
share an MD5 — there is nothing to guard against, only the tombstone itself to
assert.
"""

from unittest.mock import MagicMock, patch

from openforge.db.fixtures.incremental import IncrementalFixturesLoader


class TestDeprecationSideEffects:
    """A tombstoned row loses its tags and images and gains the flag."""

    def test_tombstoning_strips_tags_and_images(self):
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs

        loader = IncrementalFixturesLoader(mock_conn, verbose=False)

        blueprint_to_deprecate = {
            "id": "active-456",
            "blueprint_name": "file.stl",
            "file_md5": "abc123",
            "deprecated": False,
        }

        with (
            patch(
                "openforge.db.fixtures.incremental.tag_sql.delete_all_blueprint_tags"
            ) as del_tags,
            patch(
                "openforge.db.fixtures.incremental.image_sql"
                ".delete_images_for_blueprint"
            ) as del_imgs,
            patch(
                "openforge.db.fixtures.incremental.blueprint_sql"
                ".mark_blueprint_deprecated"
            ) as mark_dep,
        ):
            applied = loader._handle_deprecation(mock_curs, blueprint_to_deprecate)

        assert applied is True
        del_tags.assert_called_once_with(mock_curs, "active-456")
        del_imgs.assert_called_once_with(mock_curs, "active-456")
        # Two arguments: a successor is _link_deprecated_to_successors' job.
        mark_dep.assert_called_once_with(mock_curs, "active-456")
