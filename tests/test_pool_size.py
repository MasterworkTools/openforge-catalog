"""The pool is sized for one request per Lambda container.

psycopg_pool fills to min_size when open=True, so the library default
holds idle sessions against Aurora's connection cap.
"""

import os

from psycopg import connect

from openforge.db import PgDB, db_url


def _db_env():
    """The environment without LOG_LEVEL.

    `db_url` sets the `openforge.db` logger level from it, and app init
    has `load_dotenv`'d it in by now, so passing it would leave that
    logger reconfigured for every test that runs after this one.
    """
    return {k: v for k, v in os.environ.items() if k != "LOG_LEVEL"}


def _pids(control, dbname):
    with control.cursor() as curs:
        curs.execute("SELECT pid FROM pg_stat_activity WHERE datname = %s", (dbname,))
        return {row[0] for row in curs.fetchall()}


def test_the_pool_holds_one_connection(test_db):
    """A full pool is one backend, and closing it releases that backend.

    Counts new backend pids rather than a total, so an unrelated session
    on the same database does not change the result. The control
    connection is autocommit because `pg_stat_activity` is snapshotted
    for the transaction.
    """
    env = _db_env()
    dbname = env["PGDATABASE"]
    with connect(db_url(env), autocommit=True) as control:
        before = _pids(control, dbname)
        db = PgDB(env)
        try:
            db.pool.wait(timeout=10)
            opened = _pids(control, dbname) - before
        finally:
            db.close()

        assert len(opened) == 1
        assert _pids(control, dbname) & opened == set()
