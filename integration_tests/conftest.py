"""
Pytest configuration and fixtures for Documentation System integration tests.
"""

import os
from typing import Dict, Optional

import pytest
import requests
from psycopg.rows import dict_row

from openforge.db import PgDB

from .test_constants import TEST_DATA_PREFIX


@pytest.fixture(scope="session")
def base_url():
    """Base URL for the API server."""
    return os.environ.get("TEST_BASE_URL", "http://localhost:5328")


@pytest.fixture(scope="session")
def api_key():
    """API key for authentication."""
    return os.environ.get("API_TOKEN", "1234567890")


@pytest.fixture(scope="session")
def db():
    """Database connection fixture."""
    try:
        db_conn = PgDB(os.environ, use_pool=False)
        yield db_conn
    except Exception as e:
        pytest.skip(f"Database connection failed: {e}")


@pytest.fixture(scope="session")
def test_blueprint_id(base_url):
    """Get a test blueprint ID from the API."""
    try:
        response = requests.get(f"{base_url}/api/blueprints", timeout=10)
        response.raise_for_status()
        blueprints = response.json()

        if not blueprints:
            pytest.skip("No blueprints available for testing")

        return blueprints[0]["id"]
    except Exception as e:
        pytest.skip(f"Failed to get test blueprint: {e}")


@pytest.fixture(scope="function")
def db_transaction(db):
    """Provide database transaction isolation for tests."""
    with db.connection() as conn:
        # Start a transaction
        conn.autocommit = False
        yield conn
        # Rollback the transaction to undo all changes
        conn.rollback()


@pytest.fixture(scope="function")
def cleanup_test_data(db):
    """Clean up test data before and after each test."""
    # Track created test data IDs
    created_tag_doc_ids = []
    created_blueprint_doc_ids = []

    # Check if we should keep test data
    keep_test_data = os.environ.get("KEEP_TEST_DATA") == "true"

    # Clean up before test (only if we're not keeping test data)
    if not keep_test_data:
        with db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                # Clean up any existing test data from previous runs
                # using unique test prefix
                curs.execute(
                    """
                    DELETE FROM tag_documentation
                    WHERE document LIKE %s
                """,
                    (f"{TEST_DATA_PREFIX}%",),
                )

                curs.execute(
                    """
                    DELETE FROM blueprint_documentation
                    WHERE document LIKE %s
                """,
                    (f"{TEST_DATA_PREFIX}%",),
                )
                conn.commit()

    yield {
        "tag_doc_ids": created_tag_doc_ids,
        "blueprint_doc_ids": created_blueprint_doc_ids,
    }

    # Clean up after test by ID (only if KEEP_TEST_DATA is not set)
    if not keep_test_data:
        with db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                if created_tag_doc_ids:
                    placeholders = ",".join(["%s"] * len(created_tag_doc_ids))
                    curs.execute(
                        f"""
                        DELETE FROM tag_documentation
                        WHERE id IN ({placeholders})
                    """,
                        created_tag_doc_ids,
                    )

                if created_blueprint_doc_ids:
                    placeholders = ",".join(["%s"] * len(created_blueprint_doc_ids))
                    curs.execute(
                        f"""
                        DELETE FROM blueprint_documentation
                        WHERE id IN ({placeholders})
                    """,
                        created_blueprint_doc_ids,
                    )

                conn.commit()


@pytest.fixture(scope="function")
def test_blueprint_documentation(db, cleanup_test_data):
    """Create test blueprint documentation and track IDs for cleanup."""

    def create_test_doc(blueprint_id, document, document_type="changelog"):
        """Helper to create test documentation and track ID."""
        with db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                curs.execute(
                    """
                    INSERT INTO blueprint_documentation
                    (blueprint_id, document, document_type)
                    VALUES (%s, %s, %s)
                    RETURNING id, blueprint_id, document, document_type,
                              created_at, updated_at
                """,
                    (blueprint_id, document, document_type),
                )
                result = curs.fetchone()
                conn.commit()

                if result:
                    # Track the ID for cleanup
                    cleanup_test_data["blueprint_doc_ids"].append(result["id"])
                    return result
                return None

    return create_test_doc


@pytest.fixture(scope="session")
def test_tag_documentation(db):
    """Create test tag documentation for the test session."""
    test_tags = [
        {
            "tag_array": ["texture", "dungeon_stone"],
            "document": (
                "Dungeon stone texture provides a dark, weathered appearance "
                "suitable for underground environments."
            ),
            "document_type": "instructions",
        },
        {
            "tag_array": ["connection", "openforge"],
            "document": (
                "OpenForge connection system allows for modular tile assembly "
                "with magnetic connections."
            ),
            "document_type": "instructions",
        },
        {
            "tag_array": ["build", "topless"],
            "document": (
                "Topless build style creates open-top structures for easy "
                "access and visibility."
            ),
            "document_type": "instructions",
        },
    ]

    created_docs = []
    created_ids = []

    with db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            for tag_data in test_tags:
                try:
                    query = """
                    INSERT INTO tag_documentation (tag, document, document_type)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id, tag, document, document_type, created_at, updated_at
                    """
                    curs.execute(
                        query,
                        (
                            tag_data["tag_array"],
                            tag_data["document"],
                            tag_data["document_type"],
                        ),
                    )
                    result = curs.fetchone()

                    if result:
                        created_docs.append(
                            {
                                "id": result["id"],
                                "tag": result["tag"],
                                "document": result["document"],
                                "document_type": result["document_type"],
                            }
                        )
                        created_ids.append(result["id"])

                except Exception as e:
                    tag_path = "/".join(tag_data["tag_array"])
                    print(
                        f"Warning: Failed to create test tag documentation "
                        f"for {tag_path}: {e}"
                    )

            conn.commit()

    yield created_docs

    # Clean up test tag documentation by ID
    if created_ids:
        with db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                placeholders = ",".join(["%s"] * len(created_ids))
                curs.execute(
                    f"""
                    DELETE FROM tag_documentation
                    WHERE id IN ({placeholders})
                """,
                    created_ids,
                )
                conn.commit()


class APIClient:
    """Simple API client for making requests."""

    def __init__(self, base_url: str, api_key: Optional[str]):
        self.base_url = base_url
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        files: Optional[Dict] = None,
        **kwargs,
    ) -> requests.Response:
        """Make an API request."""
        url = f"{self.base_url}{endpoint}"

        # Add authentication if not provided
        if headers is None:
            headers = {}
        if "Authorization" not in headers and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Handle multipart requests (files present)
        if files is not None:
            # For multipart requests, we need to let requests set the
            # Content-Type automatically
            # Remove any Content-Type headers to prevent conflicts
            headers.pop("Content-Type", None)

            # Create a new session for this request without the default
            # Content-Type header
            temp_session = requests.Session()
            if self.api_key:
                temp_session.headers.update({"Authorization": f"Bearer {self.api_key}"})

            request_kwargs = kwargs.copy()
            request_kwargs.update({"data": data, "files": files, "headers": headers})
            return temp_session.request(method, url, **request_kwargs)

        # Handle regular JSON requests
        request_kwargs = kwargs.copy()
        if data is not None and "json" not in request_kwargs:
            request_kwargs["json"] = data

        # Make the request with headers
        return self.session.request(method, url, headers=headers, **request_kwargs)

    def get(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("GET", endpoint, **kwargs)

    def post(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        **kwargs,
    ) -> requests.Response:
        return self.request("POST", endpoint, data=data, files=files, **kwargs)

    def put(
        self, endpoint: str, data: Optional[Dict] = None, **kwargs
    ) -> requests.Response:
        return self.request("PUT", endpoint, data=data, **kwargs)

    def patch(
        self, endpoint: str, data: Optional[Dict] = None, **kwargs
    ) -> requests.Response:
        return self.request("PATCH", endpoint, data=data, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("DELETE", endpoint, **kwargs)


@pytest.fixture
def api_client(base_url, api_key):
    """API client fixture."""
    return APIClient(base_url, api_key)


@pytest.fixture
def api_client_no_auth(base_url):
    """API client fixture without authentication."""
    return APIClient(base_url, None)
