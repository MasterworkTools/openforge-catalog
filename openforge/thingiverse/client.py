"""Thingiverse write-API client.

Wraps the v1 write endpoints (create/update/delete thing, upload +
finalize files, publish, read a thing's files) against
`https://api.thingiverse.com` directly, authorized with the opaque write
token from `TokenManager.write_token()`.

The full contract this implements — endpoints, payloads, the
upload→finalize flow, and the hash-encoding quirk — is documented in
docs/thingiverse-api-v2-private.md and was confirmed live against
devonjones's account.

Notes:
- Auth is the opaque `token` from login, NOT the access JWT.
- Target `api.thingiverse.com` directly; the `www.thingiverse.com/api`
  origin is Cloudflare-challenged for non-browser clients.
- File `hash` comes back as hex MD5 on older uploads and base64 MD5 on
  newer ones; `normalize_hash()` converts both to lowercase hex to match
  the catalog's `file_md5`.
"""

import base64
import binascii
import logging
from pathlib import Path
from typing import Dict, List, Optional

import requests

from openforge.thingiverse.auth import TokenManager

logger = logging.getLogger(__name__)

API_BASE = "https://api.thingiverse.com"
REQUEST_TIMEOUT = 120  # STL uploads are large
USER_AGENT = "openforge-catalog-tools"


class ThingiverseAPIError(Exception):
    """A Thingiverse API call returned a non-2xx response.

    Attributes:
        status: HTTP status code
        detail: The API's error message, if any
    """

    def __init__(self, status: int, detail: str, method: str, path: str):
        self.status = status
        self.detail = detail
        msg = f"{method} {path} -> HTTP {status}"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


def normalize_hash(h: Optional[str]) -> Optional[str]:
    """Normalize a Thingiverse file hash to lowercase hex MD5.

    Recent uploads return base64-encoded MD5 (24 chars ending in `=`);
    older ones return 32-char hex. Both decode to the same MD5 the catalog
    stores as `file_md5`. Returns None for a falsy input.
    """
    if not h:
        return None
    if len(h) == 24 and h.endswith("="):
        try:
            return binascii.hexlify(base64.b64decode(h, validate=True)).decode()
        except (binascii.Error, ValueError):
            # A hash we can't decode would silently fail (or coincidentally
            # collide) in the sync diff — surface it instead of hiding it.
            logger.warning("unrecognized file hash %r; using as-is", h)
            return h.lower()
    return h.lower()


class ThingiverseClient:
    """Client for the Thingiverse write API.

    Args:
        token_manager: Provides the write token (and is re-consulted per
            request so a re-login mid-run is picked up).
        session: HTTP session (injectable for tests).
    """

    def __init__(
        self,
        token_manager: TokenManager,
        session: Optional[requests.Session] = None,
    ):
        self.tokens = token_manager
        if session is None:
            session = requests.Session()
            session.headers["User-Agent"] = USER_AGENT
        self.session = session

    # -- things ---------------------------------------------------------

    def create_thing(
        self,
        name: str,
        license: str,
        category: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        """Create a draft thing. Returns the created thing (incl. `id`).

        `license` is a slug (e.g. "cc"); `category` is a display name
        (e.g. "Toy & Game Accessories"). name/license/category are required
        by the API.
        """
        payload = {"name": name, "license": license, "category": category}
        if description is not None:
            payload["description"] = description
        if tags is not None:
            payload["tags"] = tags
        return self._request("POST", "/things/", json=payload)

    def get_thing(self, thing_id: int) -> Dict:
        """Fetch a thing by id."""
        return self._request("GET", f"/things/{thing_id}")

    def update_thing(self, thing_id: int, **fields) -> Dict:
        """Patch fields on an existing thing."""
        return self._request("PATCH", f"/things/{thing_id}", json=fields)

    def delete_thing(self, thing_id: int) -> Dict:
        """Delete a thing. Returns `{"ok": "ok"}`."""
        return self._request("DELETE", f"/things/{thing_id}")

    def publish_thing(self, thing_id: int) -> Dict:
        """Publish a draft thing."""
        return self._request("POST", f"/things/{thing_id}/publish")

    # -- files ----------------------------------------------------------

    def get_thing_files(self, thing_id: int) -> List[Dict]:
        """List a thing's files, each with a normalized-hex `md5` added.

        The raw `hash` field is preserved; `md5` is `normalize_hash(hash)`
        so callers can compare directly to the catalog's `file_md5`.
        """
        data = self._request("GET", f"/things/{thing_id}/files")
        files = data if isinstance(data, list) else data.get("files", [])
        for f in files:
            f["md5"] = normalize_hash(f.get("hash"))
        return files

    def upload_file(self, thing_id: int, path: Path) -> Dict:
        """Upload a file to a thing as a pending upload. Returns `{id}`.

        The upload is PENDING until finalize_files() commits it — an
        un-finalized file does not appear in get_thing_files().
        """
        path = Path(path)
        with open(path, "rb") as fh:
            files = {"file": (path.name, fh)}
            return self._request("POST", f"/files/{thing_id}/uploadFile", files=files)

    def delete_file(self, thing_id: int, file_id: int) -> Dict:
        """Delete a single file from a thing.

        This is the file-granular removal the sync engine uses to drop a
        file that's no longer in the manifest (vs. delete_thing()).
        """
        return self._request("DELETE", f"/things/{thing_id}/files/{file_id}")

    def finalize_files(self, thing_id: int, file_ids: List[int]) -> Dict:
        """Commit pending uploads, associating them with the thing.

        Ranks are assigned by list order (10, 20, …). Rank numbering is
        CALL-SCOPED — a later finalize restarts at 10 rather than
        continuing — so callers adding files incrementally should pass the
        full intended set in one call. The sync engine finalizes a thing's
        uploads together, so this holds.
        """
        pending = [{"id": fid, "rank": (i + 1) * 10} for i, fid in enumerate(file_ids)]
        payload = {
            "pending_uploads": pending,
            "target_id": thing_id,
            "target_type": "thing",
        }
        return self._request("POST", f"/files/{thing_id}/FinalizeFiles", json=payload)

    # -- internals ------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> Dict:
        """Issue an authenticated request; raise on non-2xx, return JSON."""
        headers = {"Authorization": f"Bearer {self.tokens.write_token()}"}
        resp = self.session.request(
            method,
            f"{API_BASE}{path}",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            **kwargs,
        )
        # Log method/path/status only — never the headers or the token.
        logger.debug("%s %s -> %s", method, path, resp.status_code)
        if not 200 <= resp.status_code < 300:
            detail = ""
            try:
                # Error bodies are {"error": "..."}; a non-JSON body (e.g. a
                # Cloudflare 429 HTML page) yields no detail, not a crash.
                detail = resp.json().get("error", "")
            except (ValueError, AttributeError):
                pass
            raise ThingiverseAPIError(resp.status_code, detail, method, path)
        try:
            return resp.json()
        except ValueError:
            # Some write endpoints legitimately return an empty body. Log it
            # so a truncated/corrupt 2xx body (which would otherwise read as
            # "zero files" downstream and trigger spurious re-uploads) is
            # visible rather than silently masked.
            logger.warning("2xx body from %s %s did not parse as JSON", method, path)
            return {}

    def close(self):
        """Release the HTTP session."""
        self.session.close()

    def __enter__(self) -> "ThingiverseClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
