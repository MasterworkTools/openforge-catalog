"""Tests for openforge.thingiverse.client (ThingiverseClient)."""

import base64
import binascii

import pytest

from openforge.thingiverse.auth import NotLoggedIn
from openforge.thingiverse.client import (
    API_BASE,
    ThingiverseAPIError,
    ThingiverseClient,
    normalize_hash,
)

MD5_HEX = "2d56b05653ee9ad44205c53a09657285"
MD5_B64 = base64.b64encode(binascii.unhexlify(MD5_HEX)).decode()  # ends with '='


class FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {}

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    def __init__(self):
        self.responses = []
        self.calls = []
        self.headers = {}
        self.closed = False

    def queue(self, resp):
        self.responses.append(resp)
        return self

    def request(self, method, url, headers=None, timeout=None, **kwargs):
        self.calls.append({"method": method, "url": url, "headers": headers, **kwargs})
        return self.responses.pop(0)

    def close(self):
        self.closed = True


class FakeTokenManager:
    def __init__(self, token="write-tok"):
        self._token = token
        self.calls = 0

    def write_token(self):
        self.calls += 1
        if self._token is None:
            raise NotLoggedIn("no write token")
        return self._token


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def client(session):
    return ThingiverseClient(FakeTokenManager(), session=session)


class TestNormalizeHash:
    def test_base64_md5_to_hex(self):
        assert normalize_hash(MD5_B64) == MD5_HEX

    def test_hex_passthrough_lowercased(self):
        assert normalize_hash(MD5_HEX.upper()) == MD5_HEX

    def test_none_and_empty(self):
        assert normalize_hash(None) is None
        assert normalize_hash("") is None

    def test_invalid_base64_falls_back_to_lower_and_warns(self, caplog):
        import logging

        junk = "!!!!!!!!!!!!!!!!!!!!!!=="  # 24 chars, ends '=', not base64
        with caplog.at_level(logging.WARNING):
            assert normalize_hash(junk) == junk.lower()
        assert "unrecognized file hash" in caplog.text


class TestThings:
    def test_create_thing_payload(self, client, session):
        session.queue(FakeResponse(200, {"id": 999, "name": "X"}))
        thing = client.create_thing(
            "My Thing", license="cc", category="Toy & Game Accessories"
        )
        assert thing["id"] == 999
        call = session.calls[0]
        assert call["method"] == "POST"
        assert call["url"] == f"{API_BASE}/things/"
        assert call["headers"]["Authorization"] == "Bearer write-tok"
        assert call["json"] == {
            "name": "My Thing",
            "license": "cc",
            "category": "Toy & Game Accessories",
        }

    def test_create_thing_optional_fields(self, client, session):
        session.queue(FakeResponse(200, {"id": 1}))
        client.create_thing("N", "cc", "Cat", description="hi", tags=["a", "b"])
        assert session.calls[0]["json"]["description"] == "hi"
        assert session.calls[0]["json"]["tags"] == ["a", "b"]

    def test_get_thing(self, client, session):
        session.queue(FakeResponse(200, {"id": 5, "name": "T"}))
        assert client.get_thing(5)["name"] == "T"
        assert session.calls[0]["url"] == f"{API_BASE}/things/5"

    def test_update_thing_patches_fields(self, client, session):
        session.queue(FakeResponse(200, {"id": 5}))
        client.update_thing(5, description="new", name="renamed")
        call = session.calls[0]
        assert call["method"] == "PATCH"
        assert call["json"] == {"description": "new", "name": "renamed"}

    def test_delete_thing(self, client, session):
        session.queue(FakeResponse(200, {"ok": "ok"}))
        assert client.delete_thing(7)["ok"] == "ok"
        assert session.calls[0]["method"] == "DELETE"
        assert session.calls[0]["url"] == f"{API_BASE}/things/7"

    def test_publish_thing(self, client, session):
        session.queue(FakeResponse(200, {"ok": "ok"}))
        client.publish_thing(7)
        assert session.calls[0]["url"] == f"{API_BASE}/things/7/publish"


class TestFileDelete:
    def test_delete_file(self, client, session):
        session.queue(FakeResponse(200, {"ok": "ok"}))
        client.delete_file(7, 555)
        call = session.calls[0]
        assert call["method"] == "DELETE"
        assert call["url"] == f"{API_BASE}/things/7/files/555"


class TestFiles:
    def test_get_thing_files_adds_normalized_md5(self, client, session):
        session.queue(
            FakeResponse(
                200,
                [
                    {"id": 1, "name": "a.stl", "hash": MD5_B64},
                    {"id": 2, "name": "b.stl", "hash": MD5_HEX},
                ],
            )
        )
        files = client.get_thing_files(9)
        assert files[0]["md5"] == MD5_HEX  # base64 decoded
        assert files[1]["md5"] == MD5_HEX  # hex preserved
        # raw hash preserved too
        assert files[0]["hash"] == MD5_B64

    def test_get_thing_files_handles_wrapped_list(self, client, session):
        session.queue(FakeResponse(200, {"files": [{"id": 1, "hash": MD5_HEX}]}))
        files = client.get_thing_files(9)
        assert files[0]["md5"] == MD5_HEX

    def test_upload_file_multipart(self, client, session, tmp_path):
        stl = tmp_path / "model.stl"
        stl.write_bytes(b"solid x\nendsolid x\n")
        session.queue(FakeResponse(200, {"id": 44950762}))

        result = client.upload_file(9, stl)

        assert result["id"] == 44950762
        call = session.calls[0]
        assert call["method"] == "POST"
        assert call["url"] == f"{API_BASE}/files/9/uploadFile"
        assert "files" in call  # multipart, not json
        assert call["files"]["file"][0] == "model.stl"

    def test_finalize_files_payload_and_ranks(self, client, session):
        session.queue(FakeResponse(200, {"ok": "ok"}))
        client.finalize_files(9, [111, 222, 333])
        call = session.calls[0]
        assert call["url"] == f"{API_BASE}/files/9/FinalizeFiles"
        assert call["json"] == {
            "pending_uploads": [
                {"id": 111, "rank": 10},
                {"id": 222, "rank": 20},
                {"id": 333, "rank": 30},
            ],
            "target_id": 9,
            "target_type": "thing",
        }


class TestErrorsAndAuth:
    def test_non_2xx_raises_with_detail(self, client, session):
        session.queue(FakeResponse(400, {"error": "license is required"}))
        with pytest.raises(ThingiverseAPIError) as exc:
            client.create_thing("N", "", "Cat")
        assert exc.value.status == 400
        assert "license is required" in str(exc.value)

    def test_non_2xx_non_json_body(self, client, session):
        session.queue(FakeResponse(429, ValueError("cloudflare html")))
        with pytest.raises(ThingiverseAPIError) as exc:
            client.get_thing(1)
        assert exc.value.status == 429

    def test_empty_body_returns_empty_dict_and_warns(self, client, session, caplog):
        import logging

        session.queue(FakeResponse(200, ValueError("no body")))
        with caplog.at_level(logging.WARNING):
            assert client.get_thing(1) == {}
        assert "did not parse as JSON" in caplog.text

    def test_write_token_consulted_per_request(self, session):
        tm = FakeTokenManager()
        client = ThingiverseClient(tm, session=session)
        session.queue(FakeResponse(200, {"id": 1}))
        session.queue(FakeResponse(200, {"id": 1}))
        client.get_thing(1)
        client.get_thing(1)
        assert tm.calls == 2  # re-consulted each request (picks up re-login)

    def test_not_logged_in_propagates(self, session):
        client = ThingiverseClient(FakeTokenManager(token=None), session=session)
        with pytest.raises(NotLoggedIn):
            client.get_thing(1)

    def test_context_manager_closes(self, session):
        with ThingiverseClient(FakeTokenManager(), session=session) as c:
            assert c.session is session
        assert session.closed

    def test_default_session_is_requests_session(self):
        import requests

        client = ThingiverseClient(FakeTokenManager())
        assert isinstance(client.session, requests.Session)
        assert client.session.headers["User-Agent"] == "openforge-catalog-tools"
        client.close()
