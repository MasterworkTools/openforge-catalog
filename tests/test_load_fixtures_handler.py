"""The fixture-loading Lambda's handler.

The handler's job is not "run the loader" — `bin/fixtures` already did that.
It is to decide, from a load nobody watched, whether a release may proceed.
So the tests here are mostly about what it refuses: a fixture name that
matches nothing, a package with no fixtures in it, and a load that left a
path the fixtures still list with no way to answer for it.

Loading the real 45 fixtures takes minutes, so the tests that need a load
point the handler at a small set of files it builds itself.
"""

import json

import pytest
from psycopg.rows import dict_row

from openforge.app import load_fixtures as handler


def _item(path, md5, deprecated=False):
    item = {
        "type": "model",
        "file_metadata": {
            "full_name": path,
            "file": path.split("/")[-1],
            "md5": md5,
            "size": 1000,
            "file_modified_at": "2020-01-01T12:00:00",
        },
        "tags": ["shape|floor"],
        "images": [],
        "config": {},
    }
    if deprecated:
        item["deprecated"] = True
    return item


@pytest.fixture
def blueprint_fixture(tmp_path):
    """A fixtures tree shaped the way the real one is.

    `_expected_paths` keys off the parent directory being `blueprints`, so a
    flat temporary file would be skipped and every assertion about missing
    paths would pass vacuously.
    """

    def write(items, name="small.json"):
        blueprints = tmp_path / "blueprints"
        blueprints.mkdir(exist_ok=True)
        f = blueprints / name
        f.write_text(json.dumps(items))
        return f

    return write


def test_a_named_fixture_that_matches_nothing_is_refused():
    """Loading everything, or nothing, would both look like success."""
    with pytest.raises(RuntimeError) as exc:
        handler._fixture_files("not-a-fixture.json")

    # The message lists what there was, so the operator does not have to guess.
    assert "no fixture named" in str(exc.value)
    assert "bases.json" in str(exc.value)


def test_a_named_fixture_narrows_to_exactly_that_file():
    assert [f.name for f in handler._fixture_files("cave.json")] == ["cave.json"]


def test_no_fixtures_at_all_reads_as_a_packaging_fault(monkeypatch):
    """A build that pruned the fixtures must not report a clean load."""
    monkeypatch.setattr(handler, "find_fixtures", lambda _: [])

    with pytest.raises(RuntimeError) as exc:
        handler._fixture_files(None)

    assert "packaging fault" in str(exc.value)


def test_expected_paths_skips_what_the_fixture_marks_deprecated(blueprint_fixture):
    """That flag asks for no live row, so the path is not owed one."""
    f = blueprint_fixture(
        [
            _item("tiles/h/live.stl", "M_live"),
            _item("tiles/h/retired.stl", "M_retired", deprecated=True),
        ]
    )

    assert handler._expected_paths([f]) == {"tiles/h/live.stl"}


def test_a_load_reports_what_moved_and_not_the_files_it_read(
    test_db, blueprint_fixture, monkeypatch
):
    """`files` counts what was read; `applied` only what changed."""
    f = blueprint_fixture([_item("tiles/h/a.stl", "M_a")])
    monkeypatch.setattr(handler, "find_fixtures", lambda _: [f])
    monkeypatch.setattr(handler, "PgDB", lambda *a, **k: test_db)

    first = handler.lambda_handler({}, None)
    assert first["ok"] is True
    assert first["files"] == 1
    assert first["blueprints_changed"] is True
    assert first["applied"][0]["added"] == 1

    # The property the deploy depends on: loading the same data again is a
    # no-op, so a release that changed no data says so.
    second = handler.lambda_handler({}, None)
    assert second["ok"] is True
    assert second["blueprints_changed"] is False
    assert second["applied"] == []


def test_a_path_left_unanswerable_fails_the_load(
    test_db, blueprint_fixture, monkeypatch
):
    """The failure this gate exists for, and the one that looks healthy.

    A load that drops a path returns an ordinary payload — the catalog simply
    has no way to answer for a file the fixtures still list. Simulated by
    tombstoning the row after the load, which is the shape the real incident
    took: a load left 76 paths with their only row deprecated.
    """
    f = blueprint_fixture([_item("tiles/h/a.stl", "M_a")])
    monkeypatch.setattr(handler, "find_fixtures", lambda _: [f])
    monkeypatch.setattr(handler, "PgDB", lambda *a, **k: test_db)

    real_load = handler.load_fixtures

    def load_then_lose(conn, alt, files):
        results = real_load(conn, alt, files)
        with conn.cursor(row_factory=dict_row) as curs:
            curs.execute(
                "UPDATE blueprints SET deprecated = true"
                " WHERE full_name = 'tiles/h/a.stl'"
            )
        conn.commit()
        return results

    monkeypatch.setattr(handler, "load_fixtures", load_then_lose)

    with pytest.raises(RuntimeError) as exc:
        handler.lambda_handler({}, None)

    assert "neither a live row nor listed by one" in str(exc.value)
    assert "tiles/h/a.stl" in str(exc.value)


def test_a_duplicate_counts_as_answerable(test_db, blueprint_fixture, monkeypatch):
    """A path a live row speaks for is answerable without a row of its own.

    Two fixture entries sharing an MD5 produce one row listing the other
    path, which is the normal state for roughly 349 catalog paths — so a
    gate that demanded a row each would fail every real load.
    """
    f = blueprint_fixture(
        [_item("tiles/h/a.stl", "M_same"), _item("tiles/h/b.stl", "M_same")]
    )
    monkeypatch.setattr(handler, "find_fixtures", lambda _: [f])
    monkeypatch.setattr(handler, "PgDB", lambda *a, **k: test_db)

    result = handler.lambda_handler({}, None)

    assert result["ok"] is True
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            curs.execute("SELECT count(*) AS n FROM blueprints WHERE NOT deprecated")
            assert curs.fetchone()["n"] == 1
