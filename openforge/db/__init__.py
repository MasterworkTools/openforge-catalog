import json
import logging
from urllib.parse import quote

import psycopg
from flask import current_app
from psycopg_pool import ConnectionPool

LOGGER = logging.getLogger(__name__)


class PgDB:
    def __init__(self, vars, ext_logger=None, use_pool=True):
        self.database_url = db_url(vars, ext_logger)
        self.use_pool = use_pool
        if use_pool:
            self.pool = ConnectionPool(self.database_url, open=True)
        else:
            self.pool = None

    def connection(self):
        """Get a database connection, either from pool or direct."""
        if self.use_pool and self.pool:
            return self.pool.connection()
        else:
            return psycopg.connect(self.database_url)

    def __enter__(self):
        return self

    def close(self):
        """Gracefully close the database connection/pool."""
        if self.pool:
            try:
                self.pool.close()
            except Exception:
                # Ignore errors during shutdown
                pass
            self.pool = None

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        # Only try to close if we have a pool and it's not already closed
        if hasattr(self, "pool") and self.pool is not None:
            try:
                self.pool.close()
            except Exception:
                # Ignore errors during garbage collection
                pass


def db_url(vars, ext_logger=None):
    args = {
        "user": "openforge",
        "database": "openforge",
        "password": "openforge",
        "host": "localhost",
        "port": 5432,
    }
    LOGGER = ext_logger if ext_logger else logging.getLogger(__name__)
    if "PGUSER" in vars:
        args["user"] = vars["PGUSER"]
    if "PGPASSWORD" in vars:
        args["password"] = vars["PGPASSWORD"]
    elif "DB_SECRET_ARN" in vars:
        args["password"] = _password_from_secret(vars["DB_SECRET_ARN"])
    if "PGHOST" in vars:
        args["host"] = vars["PGHOST"]
    if "PGPORT" in vars:
        args["port"] = vars["PGPORT"]
    if "PGDATABASE" in vars:
        args["database"] = vars["PGDATABASE"]
    if "LOG_LEVEL" in vars:
        LOGGER.setLevel(vars["LOG_LEVEL"])

    # libpq percent-decodes the URI, so a password containing '%' must be encoded.
    password = quote(args["password"], safe="")
    return f"postgresql://{args['user']}:{password}@{args['host']}:{args['port']}/{args['database']}"


def _password_from_secret(arn):
    """Read the password from an RDS-managed Secrets Manager secret.

    Fetched once per process (the pool is built at init), so a rotated
    password reaches new Lambda containers without a redeploy.
    ponytail: warm containers keep the old password until they recycle;
    pass a reconnect hook to ConnectionPool if rotation is ever enabled.
    """
    import boto3  # only Lambda sets DB_SECRET_ARN; keep the import off the CLI path
    from botocore.config import Config

    # Fail fast if the VPC has no path to Secrets Manager: botocore's default
    # 60 s connect timeout would outlast the function timeout and hide the cause.
    fast_fail = Config(connect_timeout=3, retries={"max_attempts": 2})
    client = boto3.client("secretsmanager", config=fast_fail)
    secret = client.get_secret_value(SecretId=arn)
    return json.loads(secret["SecretString"])["password"]


def get_logger():
    if current_app:
        return current_app.logger
    return LOGGER
