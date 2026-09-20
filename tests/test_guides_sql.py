from pathlib import Path

import psycopg
import pytest
import yaml
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from werkzeug.exceptions import NotFound

import openforge.db.sql.guides as guide_sql
from openforge.db.fixtures import (
    _get_fixture_type,
    find_fixtures_directory,
    load_fixtures,
    load_guide_fixture,
)


def a_guide(key="wall", title="How do I make a wall?", summary="Three ways."):
    return {
        "key": key,
        "title": title,
        "summary": summary,
        "steps": [
            {
                "key": "method",
                "prompt": "How do you want to build it?",
                "options": [
                    {
                        "key": "s2w-modular",
                        "title": "Modular (s2w)",
                        "roles": {"wall": {"require": ["build|s2w"]}},
                    }
                ],
            }
        ],
        "roles": {"wall": {"title": "Wall", "query": {"require": ["shape|wall"]}}},
    }


def test_upsert_stores_the_whole_document(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            result = guide_sql.upsert_guide(curs, a_guide())

            assert result["guide_key"] == "wall"
            assert result["document"]["steps"][0]["key"] == "method"


def test_upsert_replaces_an_existing_guide(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, a_guide())
            guide_sql.upsert_guide(curs, a_guide(title="How do I make a better wall?"))

            guides = guide_sql.get_all_guides(curs)
            assert len(guides) == 1
            assert guides[0]["title"] == "How do I make a better wall?"


def test_get_guide_by_key_returns_the_document(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, a_guide())

            result = guide_sql.get_guide_by_key(curs, "wall")
            assert result["document"]["title"] == "How do I make a wall?"


def test_get_guide_by_key_raises_for_an_unknown_key(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            with pytest.raises(NotFound):
                guide_sql.get_guide_by_key(curs, "nonesuch")


def test_the_list_carries_titles_but_not_documents(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, a_guide())
            guide_sql.upsert_guide(curs, a_guide(key="corner", title="Corners"))

            guides = guide_sql.get_all_guides(curs)

            assert [g["guide_key"] for g in guides] == ["corner", "wall"]
            assert guides[0]["title"] == "Corners"
            assert guides[1]["summary"] == "Three ways."
            assert "document" not in guides[0]


def test_delete_all_guides_empties_the_table(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, a_guide())

            guide_sql.delete_all_guides(curs)

            assert guide_sql.get_all_guides(curs) == []


def test_loading_a_fixture_validates_before_it_writes(test_db):
    broken = a_guide()
    broken["steps"][0]["options"][0]["roles"] = {"plinth": None}

    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            with pytest.raises(ValueError, match="plinth"):
                load_guide_fixture(curs, broken)

            assert guide_sql.get_all_guides(curs) == []


def test_loading_a_fixture_returns_the_key_it_loaded(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            assert load_guide_fixture(curs, a_guide()) == "wall"
            assert len(guide_sql.get_all_guides(curs)) == 1


def write_guide_fixture(tmp_path: Path, guide: dict) -> Path:
    """A guide fixture on disk, in the directory the loader keys on."""
    guides = tmp_path / "guides"
    guides.mkdir(exist_ok=True)
    path = guides / f"{guide['key']}.yaml"
    path.write_text(yaml.safe_dump(guide))
    return path


def test_the_fixtures_command_loads_a_guide_file(test_db, tmp_path):
    path = write_guide_fixture(tmp_path, a_guide())

    with test_db.connection() as conn:
        load_fixtures(conn, "", [path])
        with conn.cursor(row_factory=dict_row) as curs:
            assert (
                guide_sql.get_guide_by_key(curs, "wall")["document"]["title"]
                == "How do I make a wall?"
            )


def test_a_full_replacement_load_clears_guides_first(test_db, tmp_path):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, a_guide(key="gone"))
        conn.commit()

        load_fixtures(
            conn,
            "",
            [write_guide_fixture(tmp_path, a_guide())],
            incremental=False,
        )
        with conn.cursor(row_factory=dict_row) as curs:
            assert [g["guide_key"] for g in guide_sql.get_all_guides(curs)] == ["wall"]


def test_the_key_column_comes_from_the_document(test_db):
    """The column and document->>'key' cannot drift apart.

    Not by convention: guide_key is generated from the document, so
    the database itself refuses a row whose key disagrees with the
    document it belongs to.
    """
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            stored = guide_sql.upsert_guide(curs, a_guide(key="corner"))

            assert stored["guide_key"] == "corner"
            assert stored["document"]["key"] == "corner"


def test_a_document_with_no_key_is_refused(test_db):
    """NOT NULL on the generated column is doing work.

    Without it a keyless document would land under an empty name
    rather than failing, and `upsert_guide` no longer reads
    document["key"], so nothing in Python would catch it either.
    """
    keyless = a_guide()
    del keyless["key"]

    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            with pytest.raises(psycopg.errors.NotNullViolation):
                guide_sql.upsert_guide(curs, keyless)


def test_rewriting_a_document_moves_the_key_with_it(test_db):
    """The stale-key case the generated column exists to prevent.

    An update that rewrites the document cannot leave the old name
    behind, because the column is recomputed rather than stored
    alongside.
    """
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            stored = guide_sql.upsert_guide(curs, a_guide(key="wall"))
            curs.execute(
                "UPDATE guides SET document = %s WHERE id = %s RETURNING guide_key",
                (Jsonb(a_guide(key="renamed")), stored["id"]),
            )

            assert curs.fetchone()["guide_key"] == "renamed"


def test_the_database_refuses_a_key_that_contradicts_the_document(test_db):
    """The invariant belongs to the table, not to one function.

    A later partial update that rewrote the document and left the key
    alone would be rejected here rather than quietly storing a guide
    under the wrong name.
    """
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            with pytest.raises(psycopg.errors.GeneratedAlways):
                curs.execute(
                    "INSERT INTO guides (document, guide_key) VALUES (%s, %s)",
                    (Jsonb(a_guide()), "something-else"),
                )


def test_the_fixtures_command_finds_guides_on_its_own(test_db, tmp_path):
    """Discovery is the only part bin/fixtures actually uses.

    Every other test here hands load_fixtures an explicit path, which
    skips the directory walk entirely — so this one points it at a
    directory instead.
    """
    write_guide_fixture(tmp_path, a_guide())

    found = find_fixtures_directory(str(tmp_path))

    assert [p.name for p in found] == ["wall.yaml"]

    with test_db.connection() as conn:
        load_fixtures(conn, str(tmp_path))
        with conn.cursor(row_factory=dict_row) as curs:
            assert [g["guide_key"] for g in guide_sql.get_all_guides(curs)] == ["wall"]


def test_a_dry_run_still_rejects_a_broken_guide(test_db, tmp_path):
    """A dry run that skipped validation would call it loadable."""
    broken = a_guide()
    broken["steps"][0]["options"][0]["roles"] = {"plinth": None}
    path = write_guide_fixture(tmp_path, broken)

    with test_db.connection() as conn:
        with pytest.raises(ValueError, match="plinth"):
            load_fixtures(conn, "", [path], dry_run=True)


def test_a_rejected_guide_names_the_file_it_came_from(test_db, tmp_path):
    broken = a_guide()
    broken["steps"][0]["options"][0]["roles"] = {"plinth": None}
    path = write_guide_fixture(tmp_path, broken)

    with test_db.connection() as conn:
        with pytest.raises(ValueError, match="wall.yaml"):
            load_fixtures(conn, "", [path])


@pytest.mark.parametrize(
    "path,expected",
    [
        ("openforge/db/fixtures/guides/wall.yaml", "guide"),
        # The case the directory rule exists for: a guide whose
        # filename names another fixture kind.
        ("openforge/db/fixtures/guides/blueprints.s2w.yaml", "guide"),
        ("openforge/db/fixtures/blueprints/dungeon_stone.json", "blueprint"),
        ("openforge/db/fixtures/tag_descriptions/x.yaml", "tag_description"),
        ("openforge/db/fixtures/tag_documentation/x.yaml", "tag_documentation"),
    ],
)
def test_a_fixture_is_typed_by_the_directory_it_sits_in(path, expected):
    assert _get_fixture_type(path) == expected


def test_a_fixture_outside_the_known_directories_is_refused():
    """Guessing would give a blueprint-shaped error for a guide."""
    with pytest.raises(ValueError, match="Cannot tell what kind"):
        _get_fixture_type("/tmp/loose/wall.yaml")
