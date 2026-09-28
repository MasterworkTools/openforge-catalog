"""The migration Lambda's handler.

The `test_db` fixture has already migrated to head, so "it applies
pending migrations" cannot be observed by simply calling the handler —
there is nothing pending. The middle test makes version 19 genuinely
missing first, which is the only arrangement that can tell an apply from
a no-op.
"""

import logging

import pytest
from psycopg import sql

from openforge.app import migrate


@pytest.fixture(autouse=True)
def restore_db_log_level():
    """Put the `openforge.db` logger back, because these tests move it.

    `PgDB(os.environ)` is what the handler does in production, and
    `db_url` sets the logger's level from `LOG_LEVEL` as a side effect of
    building the URL. `openforge/app/__init__.py` calls `load_dotenv()`,
    so on a developer's machine `.env` puts `LOG_LEVEL=DEBUG` into the
    environment and the first `PgDB` built after that pins this logger at
    DEBUG for the rest of the session.

    That broke `test_tags_sql.py`'s
    `test_a_query_is_not_rendered_when_nothing_is_listening` from two
    files away: it gates on the effective level, and
    `caplog.at_level(WARNING)` sets root, which cannot mask a level set on
    the logger itself.

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


def _recorded_versions(db):
    with db.connection() as conn:
        with conn.cursor() as curs:
            curs.execute("SELECT version FROM schema_versions ORDER BY version")
            return [row[0] for row in curs.fetchall()]


def test_reports_the_version_and_applies_nothing_when_current(test_db):
    """The ordinary deploy: the schema is already where the image needs it.

    `applied` has to be False here, which is what distinguishes this from a
    handler that reports success unconditionally.
    """
    head = max(_recorded_versions(test_db))

    result = migrate.lambda_handler({}, None)

    assert result["ok"] is True
    assert result["schema_version_before"] == head
    assert result["schema_version_after"] == head
    assert result["applied"] is False


def test_applies_a_missing_version_and_says_so(test_db):
    """Version 19 removed, then put back by the handler rather than by hand.

    Both halves matter: the column has to come back (the migration really
    ran) *and* `applied` has to flip to True with the versions either side
    of it, which a handler that only ever reports the current version
    cannot do.
    """
    head = max(_recorded_versions(test_db))
    assert head == 19, f"this test pins version 19; head is {head}"
    assert _column_exists(test_db, "guides", "hero_image")

    with test_db.connection() as conn:
        with conn.cursor() as curs:
            curs.execute(sql.SQL("ALTER TABLE guides DROP COLUMN hero_image"))
            curs.execute(sql.SQL("DELETE FROM schema_versions WHERE version = 19"))
        conn.commit()

    try:
        result = migrate.lambda_handler({}, None)
    finally:
        # Never leave the session database short a column: every later test
        # in this run would fail on something unrelated to what it asserts.
        if not _column_exists(test_db, "guides", "hero_image"):
            with test_db.connection() as conn:
                with conn.cursor() as curs:
                    curs.execute(
                        sql.SQL("ALTER TABLE guides ADD COLUMN hero_image TEXT")
                    )
                    curs.execute(
                        sql.SQL(
                            "INSERT INTO schema_versions (version, created_at) "
                            "VALUES (19, NOW()) ON CONFLICT DO NOTHING"
                        )
                    )
                conn.commit()

    assert result["ok"] is True
    assert result["schema_version_before"] == 18
    assert result["schema_version_after"] == 19
    assert result["applied"] is True
    assert _column_exists(test_db, "guides", "hero_image")
    assert 19 in _recorded_versions(test_db)


def test_no_schema_versions_table_reads_as_no_version(test_db, monkeypatch):
    """A virgin database is a state, not a fault.

    The query fails outright when the table is absent, so the guard has to
    turn that into None — otherwise the first deploy into an empty database
    dies before it can create anything.
    """

    def raise_undefined_table(curs):
        raise Exception('relation "schema_versions" does not exist')

    monkeypatch.setattr(migrate, "get_current_schema_version", raise_undefined_table)

    assert migrate._current_version(test_db) is None


def test_a_failing_migration_is_not_swallowed(test_db, monkeypatch):
    """The handler deliberately does not catch.

    A tidy {"ok": false} would leave the Lambda error metric silent and the
    log group without a stack trace, so the deploy would look healthy while
    the schema stayed behind. If someone wraps `_apply` in a try/except,
    this fails.
    """

    def boom(db):
        raise RuntimeError("migration 20 exploded")

    monkeypatch.setattr(migrate, "_apply", boom)

    with pytest.raises(RuntimeError, match="migration 20 exploded"):
        migrate.lambda_handler({}, None)
