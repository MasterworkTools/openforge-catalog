"""Thingiverse v2 authentication and token management.

Handles the password login flow (including 2FA), persists the long-lived
refresh token to a local dotfile, and transparently refreshes the
short-lived access JWT for API calls.

Token lifecycle (see docs/thingiverse-api-v2.md):
- POST /v2/auth/login {usernameOrEmail, password} -> 200 AuthTokensResponse
  or 202 (2FA required, complete via POST /v2/auth/2fa/login {code})
- POST /v2/auth/refresh {refresh_token} -> JwtTokenResponse {access, refresh}

Passwords are never stored; only the tokens Thingiverse returns are
persisted, to a 0600 file outside the repo tree.
"""

import base64
import binascii
import contextlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://api.thingiverse.com"
REQUEST_TIMEOUT = 30
USER_AGENT = "openforge-catalog-tools"

# Refresh the access token this many seconds before its exp claim.
EXPIRY_LEEWAY = 60

DEFAULT_TOKEN_FILE = "~/.config/openforge/thingiverse_tokens.json"
TOKEN_FILE_ENV_VAR = "THINGIVERSE_TOKEN_FILE"


class ThingiverseAuthError(Exception):
    """Base class for Thingiverse authentication failures."""


class TwoFactorRequired(ThingiverseAuthError):
    """Login accepted but a 2FA code is needed to finish (HTTP 202)."""


class NotLoggedIn(ThingiverseAuthError):
    """No usable tokens are stored; an interactive login is required."""


def _jwt_exp(token: str) -> Optional[int]:
    """Extract the exp claim from a JWT without verifying the signature.

    Args:
        token: Encoded JWT string

    Returns:
        Unix timestamp from the exp claim, or None if the token can't be
        decoded or has no exp claim
    """
    try:
        payload_b64 = token.split(".")[1]
        # JWT segments are base64url without padding
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        if not isinstance(payload, dict):
            return None
        exp = payload.get("exp")
        return int(exp) if exp is not None else None
    except (IndexError, ValueError, binascii.Error, json.JSONDecodeError):
        return None


def _token_expired(token: str) -> bool:
    """Report whether a JWT is expired (or close enough to need a refresh).

    Tokens whose exp claim can't be read are treated as expired so the
    caller falls through to a refresh rather than sending a dud token.
    """
    exp = _jwt_exp(token)
    if exp is None:
        return True
    return time.time() >= exp - EXPIRY_LEEWAY


class TokenManager:
    """Manages Thingiverse v2 tokens: login, persistence, and refresh.

    Args:
        token_file: Where tokens are persisted. Defaults to
            $THINGIVERSE_TOKEN_FILE, falling back to
            ~/.config/openforge/thingiverse_tokens.json
        session: HTTP session to use (injectable for tests). Cookies must
            persist across calls within the session because the 2FA
            completion request is tied to the login attempt's cookies.
    """

    def __init__(
        self,
        token_file: Optional[Path] = None,
        session: Optional[requests.Session] = None,
    ):
        if token_file is None:
            token_file = Path(
                os.environ.get(TOKEN_FILE_ENV_VAR) or DEFAULT_TOKEN_FILE
            ).expanduser()
        self.token_file = Path(token_file)
        if session is None:
            session = requests.Session()
            session.headers["User-Agent"] = USER_AGENT
        self.session = session

    # -- login flows ----------------------------------------------------

    def login(self, username_or_email: str, password: str) -> Dict:
        """Log in with username/email and password; persist the tokens.

        Args:
            username_or_email: Thingiverse account identifier
            password: Account password (used for this call only, not stored)

        Returns:
            Stored token metadata (never the password)

        Raises:
            TwoFactorRequired: If the account has 2FA enabled; complete
                the login with login_2fa() on this same TokenManager
            ThingiverseAuthError: On bad credentials or unexpected response
        """
        resp = self.session.post(
            f"{API_BASE}/v2/auth/login",
            json={"usernameOrEmail": username_or_email, "password": password},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 202:
            logger.info("login accepted, 2FA required")
            raise TwoFactorRequired(
                "2FA code required to complete login (check your authenticator app)"
            )
        return self._handle_token_response(resp, "login")

    def login_2fa(self, code: str) -> Dict:
        """Complete a 2FA login with the authenticator code.

        Must be called on the same TokenManager that raised
        TwoFactorRequired — the 2FA exchange is tied to the login
        attempt's session cookies.
        """
        resp = self.session.post(
            f"{API_BASE}/v2/auth/2fa/login",
            json={"code": code},
            timeout=REQUEST_TIMEOUT,
        )
        return self._handle_token_response(resp, "2FA login")

    # -- token access ---------------------------------------------------

    def access_token(self) -> str:
        """Return a valid access JWT, refreshing it if needed.

        Raises:
            NotLoggedIn: If no tokens are stored or the refresh token is
                rejected — an interactive login is required
        """
        tokens = self._load_tokens()
        access = tokens.get("access")
        if access and not _token_expired(access):
            return access
        return self.refresh()

    def auth_header(self) -> Dict[str, str]:
        """Return the Authorization header for API calls."""
        return {"Authorization": f"Bearer {self.access_token()}"}

    def refresh(self) -> str:
        """Exchange the stored refresh token for a new access JWT.

        Returns:
            The new access token (the rotated refresh token is persisted)

        Raises:
            NotLoggedIn: If no refresh token is stored or it's rejected
        """
        tokens = self._load_tokens()
        refresh_token = tokens.get("refresh")
        if not refresh_token:
            raise NotLoggedIn("no refresh token stored; log in first")
        resp = self.session.post(
            f"{API_BASE}/v2/auth/refresh",
            json={"refresh_token": refresh_token},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 401:
            raise NotLoggedIn(
                "refresh token rejected (expired or revoked); log in again"
            )
        stored = self._handle_token_response(resp, "token refresh")
        return stored["access"]

    def whoami(self) -> Dict:
        """Fetch the authenticated user via GET /v2/users/me.

        Useful to verify the stored tokens belong to the expected account.
        """
        resp = self.session.get(
            f"{API_BASE}/v2/users/me",
            headers=self.auth_header(),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            raise ThingiverseAuthError(
                f"GET /v2/users/me returned HTTP {resp.status_code}"
            )
        return resp.json()

    def logout(self):
        """Revoke the session server-side (best effort) and delete tokens.

        Server-side revocation via GET /v2/auth/logout is best-effort: an
        unreachable API or already-dead tokens must not block removing the
        local token file.
        """
        if self.is_logged_in():
            try:
                self.session.get(
                    f"{API_BASE}/v2/auth/logout",
                    headers=self.auth_header(),
                    timeout=REQUEST_TIMEOUT,
                )
            except (ThingiverseAuthError, requests.RequestException) as e:
                logger.warning("server-side logout failed: %s", e)
        try:
            self.token_file.unlink()
            logger.info("removed token file")
        except FileNotFoundError:
            pass

    def is_logged_in(self) -> bool:
        """Report whether tokens are stored (not whether they're valid)."""
        return self.token_file.exists()

    def write_token(self) -> str:
        """Return the opaque token used to authorize v1 write-API calls.

        This is the `token` field from login (see
        docs/thingiverse-api-v2-private.md), distinct from the access JWT.

        Raises:
            NotLoggedIn: If no write token is stored — it is captured only
                at login (not refresh), so a re-login is required
        """
        token = self._load_tokens().get("session_token")
        if not token:
            raise NotLoggedIn(
                "no write token stored; log in again (captured only at login)"
            )
        return token

    def close(self):
        """Release the HTTP session's connection pool.

        One-shot CLI invocations can skip this; long-running callers
        (the sync engine) should use the context-manager form or call
        close() when done. Reuse one TokenManager per process — don't
        construct one per item in a loop.
        """
        self.session.close()

    def __enter__(self) -> "TokenManager":
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    # -- internals ------------------------------------------------------

    def _handle_token_response(self, resp: requests.Response, action: str) -> Dict:
        """Validate a token-bearing response and persist its tokens."""
        if resp.status_code != 200:
            # Response bodies for auth errors are {"error": "..."} per the
            # API doc; include the message but never echo tokens.
            detail = ""
            try:
                detail = resp.json().get("error", "")
            except (ValueError, AttributeError):
                pass
            raise ThingiverseAuthError(
                f"{action} failed: HTTP {resp.status_code}"
                + (f" ({detail})" if detail else "")
            )
        body = resp.json()
        # Login endpoints return AuthTokensResponse {token, jwt: {access,
        # refresh}}; the refresh endpoint returns JwtTokenResponse
        # {access, refresh} directly. `or body` also covers "jwt": null.
        jwt = body.get("jwt") or body
        if not isinstance(jwt, dict):
            raise ThingiverseAuthError(f"{action} succeeded but response had no tokens")
        access = jwt.get("access")
        refresh = jwt.get("refresh")
        if not access or not refresh:
            raise ThingiverseAuthError(f"{action} succeeded but response had no tokens")
        stored = {
            "access": access,
            "refresh": refresh,
            "stored_at": int(time.time()),
        }
        # The `token` field is the opaque write token used against the v1
        # write API (docs/thingiverse-api-v2-private.md). It's only present
        # on login responses, NOT on refresh — carry the existing one
        # forward on refresh so a JWT refresh doesn't drop the write token.
        if body.get("token"):
            stored["session_token"] = body["token"]
        else:
            existing = self._peek_tokens()
            if existing.get("session_token"):
                stored["session_token"] = existing["session_token"]
        self._store_tokens(stored)
        logger.info("%s succeeded, tokens stored", action)
        return stored

    def _store_tokens(self, tokens: Dict):
        """Write tokens atomically with owner-only permissions.

        Written to a temp file in the same directory and swapped in with
        os.replace so a crash mid-write can't corrupt the stored tokens.
        """
        parent = self.token_file.parent
        parent.mkdir(parents=True, exist_ok=True)
        os.chmod(parent, 0o700)
        tmp_path = self.token_file.with_name(self.token_file.name + ".tmp")
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(tokens, f, indent=2)
            os.replace(tmp_path, self.token_file)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp_path)
            raise

    def _peek_tokens(self) -> Dict:
        """Read stored tokens, returning {} if absent or unreadable.

        Used only to carry an existing session_token forward on refresh; a
        missing-or-corrupt file just means "no prior token to carry" (the
        caller is about to write a fresh, valid token file regardless).
        """
        try:
            return self._load_tokens()
        except NotLoggedIn:
            return {}

    def _load_tokens(self) -> Dict:
        """Read stored tokens.

        Raises:
            NotLoggedIn: If the token file doesn't exist or is unreadable
        """
        try:
            with open(self.token_file) as f:
                return json.load(f)
        except FileNotFoundError:
            raise NotLoggedIn(f"no tokens at {self.token_file}; log in first") from None
        except json.JSONDecodeError as e:
            raise NotLoggedIn(
                f"token file {self.token_file} is corrupt; log in again"
            ) from e
