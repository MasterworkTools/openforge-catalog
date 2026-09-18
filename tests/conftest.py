import logging
import os

import pytest
from psycopg import sql

from openforge.db import PgDB

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set environment variables for testing (must be done before app import)
os.environ["API_TOKEN"] = "test_token"
os.environ["SECRET_KEY"] = "test_secret_key_for_csrf_tokens"

# Set PostgreSQL environment variables for testing
os.environ["PGDATABASE"] = "openforge_test"
os.environ["PGUSER"] = "openforge"
os.environ["PGPASSWORD"] = "openforge"
os.environ["PGHOST"] = "localhost"
os.environ["PGPORT"] = "5432"


@pytest.fixture(scope="session")
def test_db():
    """Create a test database connection and run migrations in the public schema"""
    with PgDB(os.environ, use_pool=False) as db:
        with db.connection() as conn:
            with conn.cursor() as curs:
                # Run migrations in the public schema
                from openforge.db.schema import get_schema_versions

                versions = get_schema_versions()
                for schema in versions:
                    logger.info(f"Applying migration: {schema.__name__}")
                    schema(conn).up()
                    conn.commit()
                # Log current schema and tables
                curs.execute("SELECT current_schema()")
                current_schema = curs.fetchone()[0]
                logger.info(f"Current schema after migrations: {current_schema}")
                curs.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = current_schema()"
                )
                tables = [row[0] for row in curs.fetchall()]
                logger.info(f"Tables in schema after migrations: {tables}")
        yield db
        # Teardown: run migrations down in reverse order,
        # then drop and recreate public schema
        with db.connection() as conn:
            with conn.cursor() as curs:
                from openforge.db.schema import get_schema_versions

                versions = get_schema_versions()
                for schema in reversed(versions):
                    schema(conn).down(0)
                    conn.commit()
                curs.execute(
                    sql.SQL("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
                )
                conn.commit()


@pytest.fixture(autouse=True)
def clean_tables(test_db):
    """Clean all tables before each test"""
    with test_db.connection() as conn:
        with conn.cursor() as curs:
            curs.execute(
                sql.SQL(
                    "TRUNCATE blueprints, tags, images, blueprint_images, "
                    "blueprint_documentation, tag_descriptions, openscad_source, "
                    "tag_documentation, sessions, thingiverse_things, "
                    "thingiverse_files CASCADE"
                )
            )
            conn.commit()
    yield


@pytest.fixture
def auth_client(client):
    """Provide an authenticated client with the correct Authorization header."""
    client.environ_base = {"HTTP_AUTHORIZATION": os.environ["API_TOKEN"]}
    return client
