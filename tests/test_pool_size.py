"""The pool is sized for one request per Lambda container."""

import os

import pytest
from psycopg import connect
from psycopg_pool import PoolTimeout

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


def test_the_pool_will_not_grow_past_two(test_db):
    """The cap is what bounds Aurora sessions per container.

    Holding both slots must leave a third caller waiting rather than
    opening another backend, so the assertion is on the timeout and on
    the backend count together: `wait()` above only proves min_size.
    """
    env = _db_env()
    dbname = env["PGDATABASE"]
    with connect(db_url(env), autocommit=True) as control:
        before = _pids(control, dbname)
        db = PgDB(env)
        try:
            with db.pool.connection(), db.pool.connection():
                with pytest.raises(PoolTimeout):
                    db.pool.getconn(timeout=0.5)
                assert len(_pids(control, dbname) - before) == 2
        finally:
            db.close()

        assert _pids(control, dbname) & before == before
