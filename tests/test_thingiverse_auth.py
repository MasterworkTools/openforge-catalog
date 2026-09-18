"""Tests for openforge.thingiverse.auth (TokenManager and JWT helpers)."""

import base64
import json
import stat
import time
from pathlib import Path

import pytest
import requests

from openforge.thingiverse.auth import (
    API_BASE,
    NotLoggedIn,
    ThingiverseAuthError,
    TokenManager,
    TwoFactorRequired,
    _jwt_exp,
    _token_expired,
)


def make_jwt(exp=None, payload_extra=None):
    """Build a structurally-valid, unsigned JWT for testing."""

    def seg(obj):
        raw = base64.urlsafe_b64encode(json.dumps(obj).encode()).decode()
        return raw.rstrip("=")

    payload = dict(payload_extra or {})
    if exp is not None:
        payload["exp"] = exp
    return f"{seg({'alg': 'none'})}.{seg(payload)}.fakesig"


class FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {}

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    """Duck-typed requests.Session capturing calls, returning queued responses."""

    def __init__(self):
        self.responses = []
        self.calls = []
        self.headers = {}
        self.closed = False

    def close(self):
        self.closed = True

    def queue(self, response):
        self.responses.append(response)
        return self

    def post(self, url, json=None, timeout=None, headers=None):
        self.calls.append(("POST", url, json))
        return self.responses.pop(0)

    def get(self, url, timeout=None, headers=None):
        self.calls.append(("GET", url, headers))
        return self.responses.pop(0)


@pytest.fixture
def token_file(tmp_path):
    return tmp_path / "config" / "thingiverse_tokens.json"


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def manager(token_file, session):
    return TokenManager(token_file=token_file, session=session)


def login_body(access, refresh, token="session-token-value"):
    jwt = {"access": access, "refresh": refresh}
    return {"message": "ok", "token": token, "jwt": jwt}


class TestJwtHelpers:
    def test_jwt_exp_extracts_claim(self):
        assert _jwt_exp(make_jwt(exp=1234567890)) == 1234567890

    def test_jwt_exp_no_claim_returns_none(self):
        assert _jwt_exp(make_jwt()) is None

    def test_jwt_exp_garbage_returns_none(self):
        assert _jwt_exp("not-a-jwt") is None
        assert _jwt_exp("") is None
        assert _jwt_exp("a.!!!notbase64!!!.c") is None

    def test_token_expired_future_exp(self):
        assert not _token_expired(make_jwt(exp=int(time.time()) + 3600))

    def test_token_expired_past_exp(self):
        assert _token_expired(make_jwt(exp=int(time.time()) - 10))

    def test_token_expired_within_leeway(self):
        # expires in 30s, leeway is 60s -> treat as expired
        assert _token_expired(make_jwt(exp=int(time.time()) + 30))

    def test_token_expired_undecodable_treated_expired(self):
        assert _token_expired("garbage")


class TestLogin:
    def test_login_success_stores_tokens(self, manager, session, token_file):
        access = make_jwt(exp=int(time.time()) + 3600)
        session.queue(FakeResponse(200, login_body(access, "refresh-jwt")))

        stored = manager.login("devon", "hunter2")

        assert stored["access"] == access
        assert stored["refresh"] == "refresh-jwt"
        assert stored["session_token"] == "session-token-value"
        on_disk = json.loads(token_file.read_text())
        assert on_disk["access"] == access
        method, url, body = session.calls[0]
        assert (method, url) == ("POST", f"{API_BASE}/v2/auth/login")
        assert body == {"usernameOrEmail": "devon", "password": "hunter2"}

    def test_login_token_file_is_owner_only(self, manager, session, token_file):
        session.queue(FakeResponse(200, login_body(make_jwt(exp=1), "r")))
        manager.login("devon", "pw")
        mode = stat.S_IMODE(token_file.stat().st_mode)
        assert mode == 0o600

    def test_login_202_raises_two_factor(self, manager, session):
        session.queue(FakeResponse(202, {"message": "2fa", "username": "devon"}))
        with pytest.raises(TwoFactorRequired):
            manager.login("devon", "pw")

    def test_login_401_raises_with_error_detail(self, manager, session):
        session.queue(FakeResponse(401, {"error": "Unauthorized access."}))
        with pytest.raises(ThingiverseAuthError, match="HTTP 401"):
            manager.login("devon", "wrong")

    def test_login_error_message_never_contains_password(self, manager, session):
        session.queue(FakeResponse(401, {"error": "Unauthorized access."}))
        with pytest.raises(ThingiverseAuthError) as excinfo:
            manager.login("devon", "s3cretpw")
        assert "s3cretpw" not in str(excinfo.value)

    def test_login_missing_tokens_in_body_raises(self, manager, session):
        session.queue(FakeResponse(200, {"message": "ok", "jwt": {}}))
        with pytest.raises(ThingiverseAuthError, match="no tokens"):
            manager.login("devon", "pw")

    def test_login_2fa_posts_code_and_stores(self, manager, session, token_file):
        access = make_jwt(exp=int(time.time()) + 3600)
        session.queue(FakeResponse(200, login_body(access, "refresh-jwt")))

        stored = manager.login_2fa("123456")

        assert stored["access"] == access
        method, url, body = session.calls[0]
        assert (method, url) == ("POST", f"{API_BASE}/v2/auth/2fa/login")
        assert body == {"code": "123456"}
        assert token_file.exists()


class TestAccessToken:
    def test_valid_stored_token_returned_without_refresh(
        self, manager, session, token_file
    ):
        access = make_jwt(exp=int(time.time()) + 3600)
        session.queue(FakeResponse(200, login_body(access, "refresh-jwt")))
        manager.login("devon", "pw")
        session.calls.clear()

        assert manager.access_token() == access
        assert session.calls == []  # no refresh round-trip

    def test_expired_token_triggers_refresh(self, manager, session):
        expired = make_jwt(exp=int(time.time()) - 100)
        fresh = make_jwt(exp=int(time.time()) + 3600)
        session.queue(FakeResponse(200, login_body(expired, "refresh-1")))
        manager.login("devon", "pw")
        # refresh endpoint returns JwtTokenResponse directly (no jwt wrapper)
        session.queue(FakeResponse(200, {"access": fresh, "refresh": "refresh-2"}))

        assert manager.access_token() == fresh
        method, url, body = session.calls[-1]
        assert (method, url) == ("POST", f"{API_BASE}/v2/auth/refresh")
        assert body == {"refresh_token": "refresh-1"}

    def test_refresh_rotates_stored_refresh_token(self, manager, session, token_file):
        expired = make_jwt(exp=int(time.time()) - 100)
        fresh = make_jwt(exp=int(time.time()) + 3600)
        session.queue(FakeResponse(200, login_body(expired, "refresh-1")))
        manager.login("devon", "pw")
        session.queue(FakeResponse(200, {"access": fresh, "refresh": "refresh-2"}))
        manager.access_token()

        assert json.loads(token_file.read_text())["refresh"] == "refresh-2"

    def test_no_token_file_raises_not_logged_in(self, manager):
        with pytest.raises(NotLoggedIn):
            manager.access_token()

    def test_write_token_stored_at_login(self, manager, session):
        access = make_jwt(exp=int(time.time()) + 3600)
        session.queue(FakeResponse(200, login_body(access, "r", token="wtok")))
        manager.login("devon", "pw")
        assert manager.write_token() == "wtok"

    def test_write_token_survives_refresh(self, manager, session, token_file):
        # login captures the write token; a later JWT refresh (whose
        # response has no `token`) must NOT drop it
        expired = make_jwt(exp=int(time.time()) - 100)
        fresh = make_jwt(exp=int(time.time()) + 3600)
        session.queue(FakeResponse(200, login_body(expired, "r1", token="wtok")))
        manager.login("devon", "pw")
        session.queue(FakeResponse(200, {"access": fresh, "refresh": "r2"}))
        manager.access_token()  # triggers refresh

        assert manager.write_token() == "wtok"
        assert json.loads(token_file.read_text())["session_token"] == "wtok"

    def test_write_token_missing_raises_not_logged_in(self, manager, session):
        # a login response without a `token` field -> no write token stored
        access = make_jwt(exp=int(time.time()) + 3600)
        body = {"message": "ok", "jwt": {"access": access, "refresh": "r"}}
        session.queue(FakeResponse(200, body))
        manager.login("devon", "pw")
        with pytest.raises(NotLoggedIn, match="no write token"):
            manager.write_token()

    def test_write_token_no_login_raises(self, manager):
        with pytest.raises(NotLoggedIn):
            manager.write_token()

    def test_corrupt_token_file_raises_not_logged_in(self, manager, token_file):
        token_file.parent.mkdir(parents=True)
        token_file.write_text("{not json")
        with pytest.raises(NotLoggedIn, match="corrupt"):
            manager.access_token()

    def test_rejected_refresh_raises_not_logged_in(self, manager, session):
        expired = make_jwt(exp=int(time.time()) - 100)
        session.queue(FakeResponse(200, login_body(expired, "refresh-1")))
        manager.login("devon", "pw")
        session.queue(FakeResponse(401, {"error": "invalid"}))

        with pytest.raises(NotLoggedIn, match="log in again"):
            manager.access_token()

    def test_auth_header_shape(self, manager, session):
        access = make_jwt(exp=int(time.time()) + 3600)
        session.queue(FakeResponse(200, login_body(access, "r")))
        manager.login("devon", "pw")

        assert manager.auth_header() == {"Authorization": f"Bearer {access}"}


class TestWhoamiAndLogout:
    def test_whoami_returns_user(self, manager, session):
        access = make_jwt(exp=int(time.time()) + 3600)
        session.queue(FakeResponse(200, login_body(access, "r")))
        manager.login("devon", "pw")
        session.queue(FakeResponse(200, {"id": 42, "name": "devonjones"}))

        user = manager.whoami()

        assert user == {"id": 42, "name": "devonjones"}
        method, url, headers = session.calls[-1]
        assert (method, url) == ("GET", f"{API_BASE}/v2/users/me")
        assert headers == {"Authorization": f"Bearer {access}"}

    def test_whoami_non_200_raises(self, manager, session):
        access = make_jwt(exp=int(time.time()) + 3600)
        session.queue(FakeResponse(200, login_body(access, "r")))
        manager.login("devon", "pw")
        session.queue(FakeResponse(500, {}))

        with pytest.raises(ThingiverseAuthError, match="HTTP 500"):
            manager.whoami()

    def test_logout_revokes_server_side_and_removes_file(
        self, manager, session, token_file
    ):
        access = make_jwt(exp=int(time.time()) + 3600)
        session.queue(FakeResponse(200, login_body(access, "r")))
        manager.login("devon", "pw")
        assert manager.is_logged_in()
        session.queue(FakeResponse(302))

        manager.logout()

        assert not token_file.exists()
        assert not manager.is_logged_in()
        method, url, headers = session.calls[-1]
        assert (method, url) == ("GET", f"{API_BASE}/v2/auth/logout")
        assert headers == {"Authorization": f"Bearer {access}"}

    def test_logout_removes_file_when_revocation_fails(
        self, manager, session, token_file
    ):
        class ExplodingSession(FakeSession):
            def get(self, url, timeout=None, headers=None):
                raise requests.ConnectionError("api unreachable")

        exploding = ExplodingSession()
        valid = make_jwt(exp=int(time.time()) + 3600)
        exploding.queue(FakeResponse(200, login_body(valid, "r")))
        manager = TokenManager(token_file=token_file, session=exploding)
        manager.login("devon", "pw")

        manager.logout()  # must not raise

        assert not token_file.exists()

    def test_logout_without_file_is_noop(self, manager, session):
        manager.logout()  # must not raise; no revoke call without tokens
        assert session.calls == []

    def test_logout_removes_file_when_tokens_unusable(
        self, manager, session, token_file
    ):
        # expired access + no refresh key: auth_header raises NotLoggedIn
        # (a ThingiverseAuthError) before any network call; logout must
        # still remove the file
        token_file.parent.mkdir(parents=True)
        expired = make_jwt(exp=int(time.time()) - 100)
        token_file.write_text(json.dumps({"access": expired}))

        manager.logout()  # must not raise

        assert not token_file.exists()
        assert session.calls == []


class TestConstruction:
    def test_token_file_from_env_var(self, monkeypatch, tmp_path):
        env_path = tmp_path / "from-env.json"
        monkeypatch.setenv("THINGIVERSE_TOKEN_FILE", str(env_path))
        manager = TokenManager(session=FakeSession())
        assert manager.token_file == env_path

    def test_token_file_default_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("THINGIVERSE_TOKEN_FILE", raising=False)
        manager = TokenManager(session=FakeSession())
        expected = Path("~/.config/openforge/thingiverse_tokens.json").expanduser()
        assert manager.token_file == expected

    def test_default_session_is_requests_session_with_user_agent(self, token_file):
        manager = TokenManager(token_file=token_file)
        assert isinstance(manager.session, requests.Session)
        assert manager.session.headers["User-Agent"] == "openforge-catalog-tools"
        manager.close()

    def test_context_manager_closes_session(self, token_file, session):
        with TokenManager(token_file=token_file, session=session) as manager:
            assert manager.session is session
        assert session.closed


class TestErrorBranches:
    def test_refresh_with_no_refresh_key_raises_not_logged_in(
        self, manager, token_file
    ):
        token_file.parent.mkdir(parents=True)
        token_file.write_text(json.dumps({"access": "only-access"}))
        with pytest.raises(NotLoggedIn, match="no refresh token stored"):
            manager.refresh()

    def test_non_json_error_body_still_raises_with_status(self, manager, session):
        # error-detail extraction failing must not mask the HTTP failure
        session.queue(FakeResponse(500, ValueError("not json")))
        with pytest.raises(ThingiverseAuthError, match="HTTP 500"):
            manager.login("devon", "pw")

    def test_null_jwt_in_login_body_raises(self, manager, session):
        session.queue(FakeResponse(200, {"message": "ok", "jwt": None}))
        with pytest.raises(ThingiverseAuthError, match="no tokens"):
            manager.login("devon", "pw")

    def test_non_dict_jwt_in_login_body_raises(self, manager, session):
        session.queue(FakeResponse(200, {"message": "ok", "jwt": "not-a-dict"}))
        with pytest.raises(ThingiverseAuthError, match="no tokens"):
            manager.login("devon", "pw")

    def test_failed_store_cleans_up_tmp_and_reraises(
        self, manager, session, token_file, monkeypatch
    ):
        session.queue(FakeResponse(200, login_body(make_jwt(exp=1), "r")))

        def explode(src, dst):
            raise OSError("disk full")

        monkeypatch.setattr("openforge.thingiverse.auth.os.replace", explode)
        with pytest.raises(OSError, match="disk full"):
            manager.login("devon", "pw")
        assert list(token_file.parent.glob("*.tmp")) == []
        assert not token_file.exists()

    def test_non_dict_jwt_payload_treated_as_expired(self):
        # a JWT whose payload decodes to a list must not crash exp parsing
        seg = base64.urlsafe_b64encode(json.dumps([1, 2]).encode()).decode()
        weird = f"x.{seg.rstrip('=')}.y"
        assert _jwt_exp(weird) is None
        assert _token_expired(weird)

    def test_store_leaves_no_tmp_file(self, manager, session, token_file):
        session.queue(FakeResponse(200, login_body(make_jwt(exp=1), "r")))
        manager.login("devon", "pw")
        leftovers = list(token_file.parent.glob("*.tmp"))
        assert leftovers == []
