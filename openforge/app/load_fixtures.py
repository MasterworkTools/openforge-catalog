"""`bin/fixtures`, reachable from a GitHub Actions runner.

A third function from the same image as the API and the migration, for the
reason `openforge/app/migrate.py` sets out: Aurora admits the application and
bastion security groups only, so nothing in CI can reach it, and a function
inside the VPC already reads the password from `DB_SECRET_ARN`.

There is no upload step at any point. `Dockerfile.api.deploy` copies the whole
`openforge` package, fixtures included, so this reads them off its own
filesystem. That is why the API's limits on fixture uploads
(`openforge_catalog-ot6`) do not apply here — they are properties of shipping
fixtures over HTTP, and this path never does.

It loads every fixture, never a named subset, unless an operator asks for one
by hand. A release whose data spans files is the normal case and the
dependency is invisible: `nova_trail.json` left production briefly broken
because the nova_trail wall bases live in `bases.json`, and nothing said so
(`openforge_catalog-25m`). Loading everything costs little, because an
incremental load of unchanged data is a no-op.

The deploy invokes this after the migration and before the apply that promotes
the API image, so data arrives behind the schema it needs and ahead of the
code that reads it.

Errors are deliberately **not** caught, as in the migration: a raise gives the
invoke a `FunctionError`, a stack trace in the log group and a tick on the
error metric, where a tidy `{"ok": false}` would give the alarms nothing.
"""

import json
import os

from openforge.db import PgDB
from openforge.db.fixtures import find_fixtures, load_fixtures


def _fixture_files(fixture):
    """The files to load — all of them, or the one an operator named.

    A named fixture that matches nothing raises rather than loading everything
    or loading nothing, because both of those look like success to the caller.
    """
    files = list(find_fixtures(""))
    if not files:
        raise RuntimeError(
            "no fixtures found in the openforge package, so there is nothing "
            "to load; this is a packaging fault rather than a database one"
        )
    if not fixture:
        return files

    chosen = [f for f in files if f.name == fixture]
    if not chosen:
        raise RuntimeError(
            f"no fixture named {fixture!r}; available: "
            f"{', '.join(sorted(f.name for f in files))}"
        )
    return chosen


def _expected_paths(files):
    """The paths the blueprint fixtures say should be answerable.

    An entry the fixture marks deprecated is excluded: asking for no live row
    is what that flag means, and exactly one path in the catalog is in that
    position.

    Only the path strings are kept. The fixtures are tens of megabytes and
    this runs beside a load that has its own appetite, so each file is parsed
    and dropped rather than held.
    """
    paths = set()
    for f in files:
        if f.suffix != ".json" or f.parent.name != "blueprints":
            continue
        with open(f) as fh:
            for item in json.load(fh):
                if item.get("deprecated"):
                    continue
                metadata = item.get("file_metadata") or {}
                if metadata.get("full_name"):
                    paths.add(metadata["full_name"])
    return paths


def _answerable(db):
    """Every path a live row either owns or speaks for as a duplicate."""
    with db.connection() as conn:
        with conn.cursor() as curs:
            curs.execute(
                "SELECT full_name, consolidated_paths FROM blueprints"
                " WHERE NOT deprecated AND full_name IS NOT NULL"
            )
            answerable = set()
            for full_name, listed in curs.fetchall():
                answerable.add(full_name)
                answerable.update(listed or [])
            return answerable


def lambda_handler(event, context):
    fixture = (event or {}).get("fixture")
    db = PgDB(os.environ, use_pool=False)
    files = _fixture_files(fixture)

    with db.connection() as conn:
        results = load_fixtures(conn, "", files)

    # The end state, asserted rather than reported — the same reason the
    # migration asserts it reached head. A load that quietly dropped paths
    # produces a payload indistinguishable from a healthy no-op, and that is
    # the failure this gate exists to stop: the catalog has no way to answer
    # for a file the fixtures still list.
    missing = _expected_paths(files) - _answerable(db)
    if missing:
        raise RuntimeError(
            f"{len(missing)} fixture paths are neither a live row nor listed "
            f"by one after the load, e.g. {sorted(missing)[:3]}"
        )

    # Only the blueprint figures can say whether anything changed. A guide
    # reports the key it upserted and a tag fixture the number of entries it
    # wrote, both unconditionally, so a `changed` derived from those would be
    # true on every deploy — the same shape of always-true report that
    # `openforge_catalog-9fm` removed from the summary.
    moved = [
        r
        for r in results
        if r["type"] == "blueprint"
        and (r["added"] or r["modified"] or r["deprecated"] or r["consolidated"])
    ]
    return {
        "ok": True,
        "fixture": fixture,
        "files": len(results),
        "blueprints_changed": bool(moved),
        "applied": moved,
    }
