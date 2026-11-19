"""The pool is sized for one request per Lambda container."""

import os
from time import monotonic, sleep

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


def _still_live(control, dbname, pids, timeout=5.0):
    """Which of `pids` are still backends, polled until none are.

    `pool.close()` returns before the server has reaped the backends, so
    a single read right after it fails intermittently.
    """
    deadline = monotonic() + timeout
    while True:
        live = _pids(control, dbname) & pids
        if not live or monotonic() > deadline:
            return live
        sleep(0.05)


def test_the_pool_holds_one_connection(test_db):
    """A full pool is one backend, and closing it releases that backend.

    Counts new backend pids rather than a total, so an unrelated session
    on the same database does not change the result. The control
    connection is autocommit because `pg_stat_activity` is snapshotted
    for the transaction. The pool is held in a local because `close()`
    drops the attribute: the finalizer then takes the backend away
    whether or not `close()` ran, without setting `closed`, so that flag
    is the only thing that distinguishes them.
    """
    env = _db_env()
    dbname = env["PGDATABASE"]
    with connect(db_url(env), autocommit=True) as control:
        before = _pids(control, dbname)
        db = PgDB(env)
        pool = db.pool
        try:
            pool.wait(timeout=10)
            opened = _pids(control, dbname) - before
        finally:
            db.close()

        assert len(opened) == 1
        assert pool.closed
        assert _still_live(control, dbname, opened) == set()


def test_the_pool_will_not_grow_past_two(test_db):
    env = _db_env()
    dbname = env["PGDATABASE"]
    with connect(db_url(env), autocommit=True) as control:
        before = _pids(control, dbname)
        db = PgDB(env)
        pool = db.pool
        opened = set()
        try:
            with pool.connection(), pool.connection():
                # The cap is what this pins; the count below only adds
                # that both slots are real backends.
                with pytest.raises(PoolTimeout):
                    pool.getconn(timeout=0.5)
                opened = _pids(control, dbname) - before
                assert len(opened) == 2
        finally:
            db.close()

        assert _still_live(control, dbname, opened) == set()
