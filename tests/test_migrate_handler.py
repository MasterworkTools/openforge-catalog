"""The migration Lambda's handler.

The `test_db` fixture has already migrated to head, so "it applies pending
migrations" cannot be observed by simply calling the handler — there is
nothing pending. The tests that need something pending roll a version back
through the migration system itself, so they stay version-agnostic and
exercise the `down_impl` they stand in for.
"""

import logging

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

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


def _schema_shape(db):
    """Every column, index and constraint in the schema.

    Named nothing in particular on purpose. Asserting on `guides.hero_image`
    would pin this file to whichever version happens to be head, so the next
    schema PR would have to edit it — and comparing shapes additionally kills a
    `down_impl` that records its version without undoing anything, which
    checking one known column cannot.

    Columns alone are not enough, and this is not hypothetical: `version_13` is
    already a migration that adds only an extension, and a head that adds only an
    index or a constraint would leave the column set identical. That would both
    accuse its `down_impl` of doing nothing and make `_restore` return early,
    skipping the repair rather than short-circuiting it — the one way the repair
    can be silently missed.

    Covered: columns, indexes (by definition, so a same-named index that changes
    shape counts), constraints, and extensions — which is every migration in the
    tree today, `version_13` included. **Not** covered, so a head consisting only
    of one of these still needs a thought: triggers, sequences, views' contents, a
    column type or default change, and a generated-column expression. Widen this
    rather than assume it if the next migration is one of those.
    """
    with db.connection() as conn:
        with conn.cursor() as curs:
            curs.execute(
                """
                SELECT 'column', table_name, column_name
                  FROM information_schema.columns
                 WHERE table_schema = current_schema()
                UNION ALL
                SELECT 'index', tablename, indexdef
                  FROM pg_indexes
                 WHERE schemaname = current_schema()
                UNION ALL
                SELECT 'constraint', conrelid::regclass::text, conname
                  FROM pg_constraint
                 WHERE connamespace = current_schema()::regnamespace
                UNION ALL
                SELECT 'extension', extname, extversion
                  FROM pg_extension
                """
            )
            return set(curs.fetchall())


def _recorded(db):
    with db.connection() as conn:
        with conn.cursor() as curs:
            curs.execute("SELECT version FROM schema_versions")
            return {row[0] for row in curs.fetchall()}


def _restore(db, wanted_shape):
    """Put the schema back, and do not trust the bookkeeping to decide whether to.

    Triggered on the *shape*, because the failures these tests exist to catch are
    the ones that leave `schema_versions` claiming a version landed when its DDL
    did not — so a repair guarded by the version row short-circuits precisely
    when it is needed, `guides` stays dropped, and `conftest`'s autouse
    `clean_tables` then errors every remaining test in the session on a missing
    table. One real failure became a hundred that way.

    An unconditional `_apply` does not help either: `up()` skips a version
    `version_exists()` believes is applied. Dropping the schema takes
    `schema_versions` with it, which is what leaves nothing to skip. The session
    fixture's own teardown does the same thing, and `version_13` recreates the
    `pg_trgm` extension the drop removes.
    """
    if _schema_shape(db) == wanted_shape:
        return
    with db.connection() as conn:
        with conn.cursor() as curs:
            curs.execute(sql.SQL("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
        conn.commit()
    for schema in get_schema_versions():
        with db.connection() as conn:
            schema(conn).up()
            conn.commit()


def _roll_back_head(db):
    """Undo the newest migration through its own `down_impl`.

    Hand-rolled `ALTER TABLE` would pin this file to whatever the head
    version happens to be, and would skip the `down_impl` it is standing in
    for, which nothing else in the suite asserts on.
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
    full_shape = _schema_shape(test_db)
    prior = get_schema_versions()[-2].version

    head = _roll_back_head(test_db)
    try:
        # Inside the try, not before it: these run against a rolled-back schema,
        # so an assertion failing here must still reach the repair below or every
        # later test in the session fails on a missing table instead of its own
        # subject.
        assert head not in _recorded(test_db)
        rolled_back_shape = _schema_shape(test_db)
        assert rolled_back_shape != full_shape, "down_impl recorded but undid nothing"

        result = migrate.lambda_handler({}, None)
        shape_after = _schema_shape(test_db)
        recorded_after = _recorded(test_db)
    finally:
        # Never leave the session database short of the shape every later test
        # assumes: one real failure here would otherwise error the rest of the
        # session on a missing table, and those errors are what you read first.
        _restore(test_db, full_shape)

    assert result["ok"] is True
    assert result["schema_version_before"] == prior
    assert result["schema_version_after"] == head
    assert result["applied"] == [head]
    assert (
        shape_after == full_shape
    ), "the migration recorded its version but did not restore the schema"
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

    Two cases reach it: a migration that does nothing, and a version read that
    fails. Each leaves a payload shaped exactly like a healthy no-op and the
    deploy gate cannot tell them apart, so the handler checks the end state
    instead of reporting it.

    A third case does *not* reach it, and this docstring used to claim it did:
    an `os.listdir` finding no version modules never gets here, because `max()`
    raises first. That one belongs to
    `test_an_image_without_the_schema_modules_says_so`.
    """
    full_shape = _schema_shape(test_db)
    head = _roll_back_head(test_db)

    monkeypatch.setattr(migrate, "_apply", lambda db, versions: None)

    try:
        with pytest.raises(RuntimeError, match=f"did not reach head {head}"):
            migrate.lambda_handler({}, None)
    finally:
        monkeypatch.undo()
        _restore(test_db, full_shape)


def test_a_failing_migration_is_not_swallowed(test_db, monkeypatch):
    """The handler deliberately does not catch.

    A tidy {"ok": false} would leave the Lambda error metric silent and the
    log group without a stack trace, so the deploy would look healthy while
    the schema stayed behind. If someone wraps `_apply` in a try/except, this
    fails.
    """

    def boom(db, versions):
        raise RuntimeError("migration 20 exploded")

    monkeypatch.setattr(migrate, "_apply", boom)

    with pytest.raises(RuntimeError, match="migration 20 exploded"):
        migrate.lambda_handler({}, None)


def test_a_failure_part_way_keeps_the_versions_that_landed(test_db, monkeypatch):
    """The per-version commit, which nothing else pins.

    `_apply` opens a connection per version so a failure rolls back only the
    one in flight. Collapsing that to a single connection and a single commit
    survived every other test in this file, because they only ever make one
    version pending — with two, the earlier one has to still be recorded
    after the later one raises.
    """
    versions = get_schema_versions()
    head, prior = versions[-1], versions[-2]
    full_shape = _schema_shape(test_db)

    with test_db.connection() as conn:
        head(conn).down(0)
        prior(conn).down(0)
        conn.commit()

    def explode(self, curs):
        raise RuntimeError("version exploded half way")

    monkeypatch.setattr(head, "up_impl", explode)

    try:
        # Inside the try: this rollback dropped a table, so a failure here that
        # skipped the repair would take the rest of the session with it.
        assert prior.version not in _recorded(test_db)

        with pytest.raises(RuntimeError, match="version exploded half way"):
            migrate.lambda_handler({}, None)
        recorded = _recorded(test_db)
    finally:
        monkeypatch.undo()
        _restore(test_db, full_shape)

    assert prior.version in recorded, (
        "the version before the failure was rolled back too — "
        "one connection for the whole loop, not one per version"
    )
    assert head.version not in recorded


def test_the_guard_catches_only_a_missing_table(test_db):
    """The narrowing itself, which nothing else pinned.

    Reverting `except psycopg.errors.UndefinedTable` to `except Exception`
    left the whole file green, so the original P1 could be reintroduced in
    silence. A present table with the wrong shape is the cheapest way to
    reach the guard with something it must *not* swallow.
    """
    with test_db.connection() as conn:
        with conn.cursor() as curs:
            curs.execute(sql.SQL("ALTER TABLE schema_versions RENAME version TO v"))
        conn.commit()

    try:
        with pytest.raises(psycopg.errors.UndefinedColumn):
            migrate._recorded_versions(test_db, allow_missing=True)
    finally:
        with test_db.connection() as conn:
            with conn.cursor() as curs:
                curs.execute(sql.SQL("ALTER TABLE schema_versions RENAME v TO version"))
            conn.commit()


def test_a_version_reporting_failure_by_return_value_raises(test_db):
    """`break` there would have committed the half-finished version.

    Unreachable today — no `up()` in the tree returns falsy — but reverting the
    raise to `break` also left the file green, so the reason the branch exists
    was unpinned.
    """

    class Pretends:
        version = 999

        def __init__(self, conn):
            pass

        def up(self):
            return False

    with pytest.raises(RuntimeError, match="migration 999 reported failure"):
        migrate._apply(test_db, [Pretends])


def test_an_image_without_the_schema_modules_says_so(test_db, monkeypatch):
    """A packaging fault should not arrive looking like a database fault.

    `get_schema_versions()` imports every `.py` under that package and collects
    whatever registered through the decorator, so a build that ships the package
    but prunes the version modules registers none
    (openforge_catalog-li2). Before the explicit check, `max()` got there first
    and the log group — the only forensics this function has — read
    `max() iterable argument is empty`.

    The package being absent entirely is a different failure and cannot reach
    the handler: `migrate` imports from it, so that is an import error at cold
    start.
    """
    monkeypatch.setattr(migrate, "get_schema_versions", lambda: [])

    with pytest.raises(RuntimeError, match="no schema versions registered"):
        migrate.lambda_handler({}, None)


def test_a_virgin_database_reports_no_prior_version(test_db, monkeypatch):
    """The first-ever deploy, on a real empty database rather than a mock.

    A scratch database costs a CREATE, a PGDATABASE override and a DROP, and
    never touches the session database — I previously declined this test on the
    grounds that it would have to tear down `test_db`, which was wrong. Three
    mutants survive without it, all on the `if before` branches: `applied`
    forced empty, `allow_missing` never passed, and `schema_version_before`
    reported as 0 rather than None. That last one is what the deploy gate
    prints.
    """
    import os

    import psycopg

    from openforge.db import db_url

    # Per-process name. This is the only test in the suite that creates a
    # *server-level* object, and several agents share one Postgres here — under a
    # constant name, two concurrent runs lose two ways: a CREATE DATABASE race, and
    # one run's `finally` dropping the database the other is migrating, which
    # surfaces as a missing table and reads as a schema bug.
    scratch = f"{os.environ['PGDATABASE']}_virgin_{os.getpid()}"
    admin_dsn = db_url(os.environ)

    def _admin(statement):
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(statement)

    # No leading DROP: the name is unique to this run, and a DROP is the one
    # statement here that can fail with ObjectInUse against a concurrent holder.
    _admin(f"CREATE DATABASE {scratch}")
    try:
        monkeypatch.setitem(os.environ, "PGDATABASE", scratch)
        result = migrate.lambda_handler({}, None)
    finally:
        monkeypatch.undo()
        _admin(f"DROP DATABASE IF EXISTS {scratch}")

    every_version = sorted(schema.version for schema in get_schema_versions())
    assert result["ok"] is True
    assert result["schema_version_before"] is None
    assert result["schema_version_after"] == max(every_version)
    assert result["applied"] == every_version


def test_version_20_keeps_the_newest_row_at_each_path(test_db):
    """The repair has to tombstone the predecessors, not the current file.

    Rolling the head down removes only the index, so the duplicates seeded
    below can exist at all. `up` then has to pick the newest row per path,
    link the rest to it, and leave rows with no path alone.
    """
    full_shape = _schema_shape(test_db)
    head_version = _roll_back_head(test_db)
    head = get_schema_versions()[-1]

    path = "tiles/repair/dupe.stl"
    try:
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                for md5, day in (
                    ("md5-older", "2025-01-01"),
                    ("md5-newer", "2025-09-09"),
                ):
                    curs.execute(
                        "INSERT INTO blueprints (blueprint_name, blueprint_type,"
                        " full_name, file_md5, file_name, config, created_at)"
                        " VALUES ('dupe.stl','model',%s,%s,'dupe.stl','{}',%s)",
                        (path, md5, day),
                    )
                # A config row: no path, so the index must not consider it and
                # the repair must not touch it.
                curs.execute(
                    "INSERT INTO blueprints (blueprint_name, blueprint_type,"
                    " file_md5, config) VALUES ('cfg','blueprint','md5-cfg','{}')"
                )
            conn.commit()

        with test_db.connection() as conn:
            head(conn).up()
            conn.commit()

        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute(
                    "SELECT id, file_md5, deprecated, successor_id FROM blueprints"
                    " WHERE full_name = %s ORDER BY created_at",
                    (path,),
                )
                rows = curs.fetchall()
                curs.execute(
                    "SELECT deprecated FROM blueprints WHERE full_name IS NULL"
                )
                config_rows = curs.fetchall()

        older, newer = rows
        assert older["file_md5"] == "md5-older"
        assert older["deprecated"] is True
        assert older["successor_id"] == newer["id"]
        # The current file stays live and unlinked.
        assert newer["file_md5"] == "md5-newer"
        assert newer["deprecated"] is False
        assert newer["successor_id"] is None
        # A row with no path is none of the repair's business.
        assert [r["deprecated"] for r in config_rows] == [False]
        assert head_version == 20
    finally:
        _restore(test_db, full_shape)
