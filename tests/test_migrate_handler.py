"""The migration Lambda's handler.

The `test_db` fixture has already migrated to head, so "it applies pending
migrations" cannot be observed by simply calling the handler — there is
nothing pending. The tests that need something pending roll a version back
through the migration system itself, so they stay version-agnostic and
exercise the `down_impl` they stand in for.
"""

import logging

import pytest
from psycopg import sql

from openforge.app import migrate
from openforge.db.schema import get_schema_versions


@pytest.fixture(autouse=True)
def restore_db_log_level():
    """Put the `openforge.db` logger back, because these tests move it.

    `PgDB(os.environ)` is what the handler does in production, and `db_url`
    sets the logger's level from `LOG_LEVEL` as a side effect of building the
    URL. `init_app()` calls `load_dotenv()`, so once any earlier test has
    built the app, a developer's `.env` has put `LOG_LEVEL=DEBUG` into the
    environment — and the first `PgDB` built after that pins this logger at
    DEBUG for the rest of the session.

    That broke `test_tags_sql.py`'s
    `test_a_query_is_not_rendered_when_nothing_is_listening` from two files
    away: it gates on the effective level, and `caplog.at_level(WARNING)`
    sets root, which cannot mask a level set on the logger itself.

    Invisible in CI, which has no `.env` — so the suite was green there and
    red locally, on state no assertion mentions (openforge_catalog-4ea).
    """
    logger = logging.getLogger("openforge.db")
    before = logger.level
    yield
    logger.setLevel(before)


def _column_exists(db, table, column):
    with db.connection() as conn:
        with conn.cursor() as curs:
            curs.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = %s AND column_name = %s",
                (table, column),
            )
            return curs.fetchone() is not None


def _recorded(db):
    with db.connection() as conn:
        with conn.cursor() as curs:
            curs.execute("SELECT version FROM schema_versions")
            return {row[0] for row in curs.fetchall()}


def _roll_back_head(db):
    """Undo the newest migration through its own `down_impl`.

    Hand-rolled `ALTER TABLE` would pin this file to whatever the head
    version happens to be, so every future schema PR would have to edit it —
    and it would skip the `down_impl` it is standing in for, which nothing
    else in the suite asserts on.
    """
    head = get_schema_versions()[-1]
    with db.connection() as conn:
        head(conn).down(0)
        conn.commit()
    return head.version


def test_reports_the_head_and_applies_nothing_when_current(test_db):
    """The ordinary deploy: the schema is already where the image needs it.

    `applied` has to be empty here, which is what distinguishes this from a
    handler that reports success unconditionally.
    """
    head = max(_recorded(test_db))

    result = migrate.lambda_handler({}, None)

    assert result["ok"] is True
    assert result["schema_version_before"] == head
    assert result["schema_version_after"] == head
    assert result["applied"] == []


def test_applies_a_missing_version_and_names_it(test_db):
    """The head rolled back, then re-applied by the handler.

    Both halves are sampled *inside* the try, before any repair runs. An
    earlier version of this test asserted on the column after the `finally`
    had already put it back, so an `_apply` that only inserted
    `schema_versions` rows and executed no DDL passed it.
    """
    head = _roll_back_head(test_db)
    assert head not in _recorded(test_db)
    assert not _column_exists(test_db, "guides", "hero_image")

    try:
        result = migrate.lambda_handler({}, None)
        column_after = _column_exists(test_db, "guides", "hero_image")
        recorded_after = _recorded(test_db)
    finally:
        # Never leave the session database behind head: every later test in
        # this run would fail on something unrelated to what it asserts.
        if head not in _recorded(test_db):
            migrate._apply(test_db)

    assert result["ok"] is True
    assert result["schema_version_before"] == head - 1
    assert result["schema_version_after"] == head
    assert result["applied"] == [head]
    assert column_after, "the migration recorded its version but ran no DDL"
    assert head in recorded_after


def test_a_database_with_no_schema_versions_table_reads_as_empty(test_db):
    """A virgin database is a state, not a fault.

    No monkeypatch: the table is really renamed away, so this exercises the
    production path and keeps passing if the guard is narrowed to the one
    exception it means. The previous version patched
    `get_current_schema_version` to raise a bare `Exception`, which pinned
    `except Exception` rather than the behaviour — narrowing the guard made
    it fail.
    """
    with test_db.connection() as conn:
        with conn.cursor() as curs:
            curs.execute(sql.SQL("ALTER TABLE schema_versions RENAME TO sv_hidden"))
        conn.commit()

    try:
        assert migrate._recorded_versions(test_db, allow_missing=True) == set()
    finally:
        with test_db.connection() as conn:
            with conn.cursor() as curs:
                curs.execute(sql.SQL("ALTER TABLE sv_hidden RENAME TO schema_versions"))
            conn.commit()


def test_reading_the_versions_is_strict_by_default(test_db):
    """`allow_missing` has to be asked for, so the post-apply read is strict.

    Scope, honestly: this pins the *default*, not the call site. Passing
    `allow_missing=True` on the second read in `lambda_handler` is a mutant
    this does not kill — and it turns out not to need killing, because a
    swallowed read there returns an empty set and the head assertion then
    raises regardless. The assertion is what makes the strictness
    belt-and-braces rather than load-bearing.
    """
    with test_db.connection() as conn:
        with conn.cursor() as curs:
            curs.execute(sql.SQL("ALTER TABLE schema_versions RENAME TO sv_hidden"))
        conn.commit()

    try:
        with pytest.raises(Exception, match="schema_versions"):
            migrate._recorded_versions(test_db)
    finally:
        with test_db.connection() as conn:
            with conn.cursor() as curs:
                curs.execute(sql.SQL("ALTER TABLE sv_hidden RENAME TO schema_versions"))
            conn.commit()


def test_not_reaching_head_is_a_failure_not_a_quiet_no_op(test_db, monkeypatch):
    """The assertion that closes the silent-failure hole.

    A migration that does nothing, an `os.listdir` that finds no version
    modules, a read that fails — each leaves a payload shaped exactly like a
    healthy no-op, and the deploy gate cannot tell them apart. So the handler
    checks the end state instead of reporting it.
    """
    head = _roll_back_head(test_db)

    monkeypatch.setattr(migrate, "_apply", lambda db: None)

    try:
        with pytest.raises(RuntimeError, match=f"did not reach head {head}"):
            migrate.lambda_handler({}, None)
    finally:
        monkeypatch.undo()
        if head not in _recorded(test_db):
            migrate._apply(test_db)


def test_a_failing_migration_is_not_swallowed(test_db, monkeypatch):
    """The handler deliberately does not catch.

    A tidy {"ok": false} would leave the Lambda error metric silent and the
    log group without a stack trace, so the deploy would look healthy while
    the schema stayed behind. If someone wraps `_apply` in a try/except, this
    fails.
    """

    def boom(db):
        raise RuntimeError("migration 20 exploded")

    monkeypatch.setattr(migrate, "_apply", boom)

    with pytest.raises(RuntimeError, match="migration 20 exploded"):
        migrate.lambda_handler({}, None)
