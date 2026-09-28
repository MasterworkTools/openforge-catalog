"""`bin/db_update up`, reachable from a GitHub Actions runner.

Migrations were manual because nothing in CI can reach Aurora: the cluster
sits in private subnets and the runner has no route in, so automating this
looked like it needed a NAT or a tunnel (openforge_catalog-jag).

It does not. The API Lambda is already in those subnets and already reads
the database password from `DB_SECRET_ARN`, so the cheapest way in is a
second function from the *same image* with a different command — see
`image_config` in `terraform/environments/staging/main.tf`. No extra build,
no second image to keep in step, and the code and psycopg are in there
already.

The deploy invokes this between `tofu apply` and the frontend sync, so the
schema is ahead of the image that needs it and the site is never promoted
in front of a database that cannot serve it.

Errors are deliberately **not** caught. A raise gives the invoke a
`FunctionError`, a stack trace in the log group and a tick on the Lambda
error metric; a tidy `{"ok": false}` would give CI a string to inspect and
the alarms nothing. The workflow fails on any payload without `ok: true`,
which covers both.
"""

import os

from openforge.db import PgDB
from openforge.db.schema import get_current_schema_version, get_schema_versions


def _current_version(db):
    """The recorded schema version, or None before version 1 has ever run.

    A virgin database has no `schema_versions` table, so the query itself
    fails rather than returning nothing. That is a state, not a fault:
    `version_01` creates the table with IF NOT EXISTS and overrides `up`
    precisely so it can bootstrap one.
    """
    with db.connection() as conn:
        with conn.cursor() as curs:
            try:
                return get_current_schema_version(curs)
            except Exception:
                return None


def _apply(db):
    """Run the pending migrations, committing each on its own.

    The same loop as `bin/db_update up`, and the per-version commit is the
    point of it: a failure half way leaves the versions that did land
    recorded, so a re-run resumes rather than starting over.
    """
    for schema in get_schema_versions():
        with db.connection() as conn:
            if not schema(conn).up():
                break
            conn.commit()


def lambda_handler(event, context):
    db = PgDB(os.environ, use_pool=False)
    before = _current_version(db)
    _apply(db)
    after = _current_version(db)
    return {
        "ok": True,
        "schema_version_before": before,
        "schema_version_after": after,
        "applied": before != after,
    }
