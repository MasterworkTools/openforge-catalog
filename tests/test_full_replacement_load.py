import json
from pathlib import Path

import pytest
from jsonschema import ValidationError
from psycopg.rows import dict_row

from openforge.db.fixtures import load_fixtures

MD5 = "0123456789abcdef0123456789abcdef"
OLD = "tiles/ds/corner/ds#corner+left,wall.2x.openforge.stl"
NEW = "tiles/ds/corner/ds#corner+right,wall.2x.openforge.stl"


def a_record(full_name: str, side: str, deprecated: bool = False) -> dict:
    rec = {
        "type": "model",
        "file_metadata": {
            "file": Path(full_name).name,
            "full_name": full_name,
            "md5": MD5,
            "size": 1000,
            "file_modified_at": "2020-01-01T12:00:00",
        },
        "tags": ["shape|corner", f"shape|corner|{side}"],
        "images": [],
        "metadata": False,
    }
    if deprecated:
        rec["deprecated"] = True
    return rec


def write_fixture(tmp_path: Path, name: str, records: list) -> Path:
    path = tmp_path / "blueprints" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(records))
    return path


def rows_for_md5(conn) -> list:
    with conn.cursor(row_factory=dict_row) as curs:
        curs.execute(
            """
            SELECT b.full_name, b.deprecated,
                   array_agg(array_to_string(t.tag, '|') ORDER BY t.tag) AS tags
            FROM blueprints b JOIN tags t ON t.blueprint_id = b.id
            WHERE b.file_md5 = %s
            GROUP BY b.full_name, b.deprecated
            """,
            (MD5,),
        )
        return curs.fetchall()


@pytest.mark.parametrize("deprecated_first", [True, False])
def test_a_renamed_file_loads_under_its_new_name_with_only_its_own_tags(
    test_db, tmp_path, deprecated_first
):
    """The fixture keeps the old path as a deprecated record with the same
    bytes. Whichever comes first, the live record must be the one loaded."""
    old, new = a_record(OLD, "left", deprecated=True), a_record(NEW, "right")
    records = [old, new] if deprecated_first else [new, old]
    with test_db.connection() as conn:
        load_fixtures(
            conn, "", [write_fixture(tmp_path, "ds.json", records)], incremental=False
        )

        assert rows_for_md5(conn) == [
            {
                "full_name": NEW,
                "deprecated": False,
                "tags": ["shape|corner", "shape|corner|right"],
            }
        ]


def test_the_live_record_can_be_in_another_fixture(test_db, tmp_path):
    files = [
        write_fixture(tmp_path, "a.json", [a_record(OLD, "left", deprecated=True)]),
        write_fixture(tmp_path, "b.json", [a_record(NEW, "right")]),
    ]
    with test_db.connection() as conn:
        load_fixtures(conn, "", files, incremental=False)

        assert [(r["full_name"], r["deprecated"]) for r in rows_for_md5(conn)] == [
            (NEW, False)
        ]


def test_a_deprecated_record_with_no_live_twin_still_loads(test_db, tmp_path):
    """Retired files keep their tombstone in a freshly built database."""
    retired = a_record(OLD, "left", deprecated=True)
    with test_db.connection() as conn:
        load_fixtures(
            conn, "", [write_fixture(tmp_path, "ds.json", [retired])], incremental=False
        )

        assert [(r["full_name"], r["deprecated"]) for r in rows_for_md5(conn)] == [
            (OLD, True)
        ]


def test_records_without_file_metadata_load_alongside_a_rename(test_db, tmp_path):
    compositions = [
        {"type": "blueprint", "name": "live composition", "tags": []},
        {
            "type": "blueprint",
            "name": "old composition",
            "tags": [],
            "deprecated": True,
        },
    ]
    records = [a_record(OLD, "left", deprecated=True), a_record(NEW, "right")]
    with test_db.connection() as conn:
        load_fixtures(
            conn,
            "",
            [write_fixture(tmp_path, "ds.json", compositions + records)],
            incremental=False,
        )
        with conn.cursor(row_factory=dict_row) as curs:
            curs.execute(
                "SELECT blueprint_name, deprecated FROM blueprints"
                " WHERE file_md5 IS NULL ORDER BY blueprint_name"
            )
            assert curs.fetchall() == [
                {"blueprint_name": "live composition", "deprecated": False},
                {"blueprint_name": "old composition", "deprecated": True},
            ]
        assert [r["full_name"] for r in rows_for_md5(conn)] == [NEW]


def test_a_record_missing_its_md5_fails_with_the_record_named(
    test_db, tmp_path, capsys
):
    broken = a_record(NEW, "right")
    del broken["file_metadata"]["md5"]
    with test_db.connection() as conn:
        with pytest.raises(KeyError):
            load_fixtures(
                conn,
                "",
                [write_fixture(tmp_path, "ds.json", [broken])],
                incremental=False,
            )
    assert "Failed record" in capsys.readouterr().out


def test_a_malformed_file_is_refused_by_the_schema(test_db, tmp_path):
    broken = a_record(NEW, "right")
    broken["file_metadata"] = NEW
    with test_db.connection() as conn:
        with pytest.raises(ValidationError):
            load_fixtures(
                conn,
                "",
                [write_fixture(tmp_path, "ds.json", [broken])],
                incremental=False,
            )
