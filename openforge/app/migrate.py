"""`bin/db_update up`, reachable from a GitHub Actions runner.

Migrations were manual because nothing in CI can reach Aurora
(openforge_catalog-jag). The cluster only accepts connections from inside
the VPC — its security group admits the application and bastion groups and
nothing else — and a GitHub runner is outside it. The API Lambda is inside,
and already reads the database password from `DB_SECRET_ARN`, so the
cheapest way in is a second function from the *same image* with a different
command: see `image_config` in `terraform/environments/staging/main.tf`. No
extra build, no second image to keep in step, and the code and psycopg are
in there already.

The deploy invokes this between the apply that creates it and the apply that
promotes the API image, so the schema is ahead of the code that needs it.

Errors are deliberately **not** caught. A raise gives the invoke a
`FunctionError`, a stack trace in the log group and a tick on the Lambda
error metric; a tidy `{"ok": false}` would give CI a string to inspect and
the alarms nothing. The workflow fails on any payload without `ok: true`,
which covers both.

What this reports is the set of versions that actually landed, not a
before/after high-water mark. A scalar maximum cannot describe a version
arriving *below* the head — the series already has a hole at 15 — so
filling one would execute DDL and report "nothing applied".
"""

import os

import psycopg

from openforge.db import PgDB
from openforge.db.schema import get_schema_versions


def _recorded_versions(db, allow_missing=False):
    """The versions `schema_versions` holds.

    `allow_missing` is true for exactly one caller: the read *before*
    anything is applied. A database nobody has migrated has no
    `schema_versions` table at all, which is a state rather than a fault —
    `version_01` creates it, with `IF NOT EXISTS`, and overrides `up` so it
    can bootstrap one.

    After `_apply` the table certainly exists, so that read is unguarded.
    A swallowed failure there would be worse than a crash: the handler
    would report a schema transition nobody had verified, and the deploy
    gate would pass it.

    Selecting the whole column rather than `MAX(version)` also sidesteps
    `get_current_schema_version`, whose `fetchone()[0]` raises `TypeError`
    rather than returning nothing when the table exists but is empty.
    """
    with db.connection() as conn:
        with conn.cursor() as curs:
            if allow_missing:
                try:
                    curs.execute("SELECT version FROM schema_versions")
                except psycopg.errors.UndefinedTable:
                    return set()
            else:
                curs.execute("SELECT version FROM schema_versions")
            return {row[0] for row in curs.fetchall()}


def _apply(db):
    """Run the pending migrations, committing each on its own.

    The same loop as `bin/db_update up`, and the per-version commit is the
    point of it: a failure half way leaves the versions that did land
    recorded and rolls back only the one in flight, so a re-run resumes
    rather than starting over.

    A falsy `up()` raises rather than breaking. No `up()` in the tree
    returns falsy today — failure arrives as an exception — but `break`
    would leave the `with` block *normally*, and psycopg commits on a clean
    exit, so the one thing a version could do to signal "I did not finish"
    would commit its half-finished work.
    """
    for schema in get_schema_versions():
        with db.connection() as conn:
            if not schema(conn).up():
                raise RuntimeError(
                    f"migration {schema.version} reported failure without raising"
                )
            conn.commit()


def lambda_handler(event, context):
    db = PgDB(os.environ, use_pool=False)

    before = _recorded_versions(db, allow_missing=True)
    _apply(db)
    after = _recorded_versions(db)

    # The end state, asserted rather than reported. Every other way this
    # can go wrong produces a payload that looks like a healthy no-op:
    # a migration that silently does nothing, an empty `get_schema_versions()`
    # (its `os.listdir` needs the modules unzipped on disk), a version read
    # that fails. All of them leave the head unrecorded, and the deploy must
    # not proceed on any of them.
    head = max(schema.version for schema in get_schema_versions())
    if head not in after:
        raise RuntimeError(
            f"migrations did not reach head {head}; recorded: {sorted(after)}"
        )

    return {
        "ok": True,
        "schema_version_before": max(before) if before else None,
        "schema_version_after": max(after),
        "applied": sorted(after - before),
    }
