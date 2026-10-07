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

from yaml import safe_load

from openforge.db import PgDB
from openforge.db.fixtures import (
    _get_fixture_type,
    check_guide_fixture,
    find_fixtures,
    is_blueprint_fixture,
    is_tag_description_fixture,
    is_tag_documentation_fixture,
    load_fixtures,
)
from openforge.db.fixtures.utils import write_output


def _fixture_files(fixture):
    """The files to load — all of them, or the one an operator named.

    A named fixture that matches nothing raises rather than loading everything
    or loading nothing, because both of those look like success to the caller.
    """
    # Sorted, because `find_fixtures` walks `iterdir()`. Unsorted, a load that
    # fails part way leaves a different set committed on each image, and the
    # retry starts from a state nobody can predict.
    files = sorted(find_fixtures(""), key=lambda f: (f.parent.name, f.name))
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
    """Validate every fixture, and return the paths that must stay answerable.

    Two jobs in one pass, deliberately. This is what makes a bad fixture crash
    before the first write rather than after some files have committed, so it
    has to cover every fixture — a fault in a file that sorts late would
    otherwise be found only once everything ahead of it had landed. Re-reading
    them separately would double the cost of the one expensive part.

    It checks what the loader checks, not merely that the file parses. A guide
    that is valid YAML and invalid against its schema is the likelier fault
    than a syntax error, and a syntax-only gate lets it through.

    The paths come from the blueprint fixtures only, since they are the ones
    that own rows. An entry a fixture marks deprecated is excluded: asking for
    no live row is what that flag means.

    Only the path strings are kept. The fixtures are tens of megabytes and
    this runs beside a load with its own appetite, so each file is parsed and
    dropped rather than held.
    """
    paths = set()
    for f in files:
        # Named before it is parsed, for the same reason the loader names its
        # files: this is the first code to touch a fixture, and nothing it
        # raises carries the filename. `json.load` reports a line and column
        # of a stream it will not name, and a structurally wrong file raises
        # from inside the loop below.
        write_output(f"{f.name}: checking\n")
        with open(f) as fh:
            loaded = json.load(fh) if f.suffix == ".json" else safe_load(fh)

        # The loader decides a fixture's type by its directory and reads both
        # formats, so testing the extension would leave a YAML blueprint
        # fixture ungated. None carries paths today; the rule should not
        # depend on that.
        #
        # Every type `_get_fixture_type` returns is validated here, so none is
        # gated by where its directory happens to sort. The tag descriptions
        # are the last file of a load, and their schema demands a string value
        # for every key — which is where YAML's bare `yes` lands.
        fixture_type = _get_fixture_type(f)
        if fixture_type == "blueprint":
            is_blueprint_fixture(loaded)
        elif fixture_type == "guide":
            check_guide_fixture(loaded, f.name)
        elif fixture_type == "tag_description":
            is_tag_description_fixture(loaded)
        elif fixture_type == "tag_documentation":
            is_tag_documentation_fixture(loaded)

        if fixture_type != "blueprint":
            continue
        for item in loaded:
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


def _moved_blueprints(results):
    """The blueprint fixtures that actually changed something.

    Only the blueprint figures can say whether a load moved anything. A guide
    reports the key it upserted and a tag fixture the number of entries it
    wrote, both unconditionally, so a `changed` derived from those would be
    true on every deploy — the same always-true report that
    `openforge_catalog-9fm` removed from the summary.

    The `type` test comes first because the other results carry no blueprint
    keys at all, and every deploy loads some.
    """
    return [
        r
        for r in results
        if r["type"] == "blueprint"
        and (r["added"] or r["modified"] or r["deprecated"] or r["consolidated"])
    ]


def lambda_handler(event, context):
    fixture = (event or {}).get("fixture")
    db = PgDB(os.environ, use_pool=False)
    files = _fixture_files(fixture)

    # Parsed before anything is written. This reads only the fixture files, so
    # the answer is the same either side of the load — but after it, a
    # malformed fixture has already committed every file ahead of it, and the
    # retry re-reads the same bad file and fails again. It is the one failure
    # in this design that does not converge, and the fix is to crash first.
    expected = _expected_paths(files)

    with db.connection() as conn:
        results = load_fixtures(conn, "", files)

    # The end state, asserted rather than reported — the same reason the
    # migration asserts it reached head. A load that quietly dropped paths
    # produces a payload indistinguishable from a healthy no-op, and that is
    # the failure this gate exists to stop: the catalog has no way to answer
    # for a file the fixtures still list.
    missing = expected - _answerable(db)
    if missing:
        raise RuntimeError(
            f"{len(missing)} fixture paths are neither a live row nor listed "
            f"by one after the load, e.g. {sorted(missing)[:3]}"
        )

    moved = _moved_blueprints(results)
    return {
        "ok": True,
        "fixture": fixture,
        "files": len(results),
        "blueprints_changed": bool(moved),
        "applied": moved,
    }
