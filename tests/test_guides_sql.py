from pathlib import Path

import pytest
import yaml
from psycopg.rows import dict_row
from werkzeug.exceptions import NotFound

import openforge.db.sql.guides as guide_sql
from openforge.db.fixtures import load_fixtures, load_guide_fixture


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
            result = guide_sql.upsert_guide(curs, "wall", a_guide())

            assert result["guide_key"] == "wall"
            assert result["document"]["steps"][0]["key"] == "method"


def test_upsert_replaces_an_existing_guide(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, "wall", a_guide())
            guide_sql.upsert_guide(
                curs, "wall", a_guide(title="How do I make a better wall?")
            )

            guides = guide_sql.get_all_guides(curs)
            assert len(guides) == 1
            assert guides[0]["title"] == "How do I make a better wall?"


def test_get_guide_by_key_returns_the_document(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, "wall", a_guide())

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
            guide_sql.upsert_guide(curs, "wall", a_guide())
            guide_sql.upsert_guide(
                curs, "corner", a_guide(key="corner", title="Corners")
            )

            guides = guide_sql.get_all_guides(curs)

            assert [g["guide_key"] for g in guides] == ["corner", "wall"]
            assert guides[0]["title"] == "Corners"
            assert guides[1]["summary"] == "Three ways."
            assert "document" not in guides[0]


def test_delete_all_guides_empties_the_table(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, "wall", a_guide())

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
            guide_sql.upsert_guide(curs, "gone", a_guide(key="gone"))
        conn.commit()

        load_fixtures(
            conn,
            "",
            [write_guide_fixture(tmp_path, a_guide())],
            incremental=False,
        )
        with conn.cursor(row_factory=dict_row) as curs:
            assert [g["guide_key"] for g in guide_sql.get_all_guides(curs)] == ["wall"]
