#!/usr/bin/env python3
"""Ask a deployed API whether it actually works, and fail if it does not.

The deploy chain is green when every step succeeded, which is not the
same as the API serving. Nothing else notices an API that starts by
raising: the lambda target group carries no health check, and lambda
target groups have them off by default, so the ALB keeps routing to a
function returning 500.

Stdlib only. The deploy jobs have no virtualenv and install nothing.

Never prints a signed URL. The signature and access key live in the
query string, so every URL is reduced to its host before it is logged.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit

# `/health` is not routed through the ALB -- the listener rule forwards
# `/api/*` only -- so a probe of it reports the listener's fixed 404
# whatever the app is doing.
GUIDES = "/api/guides"

R2_SUFFIX = ".r2.cloudflarestorage.com"

# urllib's default announces itself as Python-urllib, which a CDN may
# refuse. A refusal here would fail every deploy.
AGENT = "openforge-catalog-deploy-verify"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A 302 is the result here, not something to follow."""

    def redirect_request(self, *args):
        return None


def _fetch(method, url, timeout, headers=None, body=None):
    """Status, headers and body, with an HTTP error being an answer."""
    request = urllib.request.Request(
        url,
        method=method,
        data=body,
        headers={"User-Agent": AGENT, **(headers or {})},
    )
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as caught:
        return caught.code, dict(caught.headers), caught.read()


def _host_of(url):
    """A URL reduced to what is safe to log."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _guides(fetch, base):
    status, _, body = fetch("GET", base + GUIDES)
    if status != 200:
        return False, f"HTTP {status}", None
    guides = json.loads(body).get("guides") or []
    if not guides:
        return False, "answered 200 with no guides", None
    keys = sorted(g.get("guide_key", "?") for g in guides)
    return True, f"{len(guides)} guides: {', '.join(keys)}", guides[0]


def _blueprint_id(fetch, base, guide):
    """A real blueprint id, from a bounded response.

    `/api/blueprints` returns every row and exceeds the ALB's response
    limit, so a guide's resolved parts are where an id comes from.
    """
    key = guide.get("guide_key")
    status, _, body = fetch("GET", f"{base}/api/guides/{key}/resolve")
    if status != 200:
        return False, f"resolve {key}: HTTP {status}", None
    found = _ids(json.loads(body), [])
    if not found:
        return False, f"resolve {key}: no blueprint in the parts", None
    return True, f"resolved {key}", found[0]


def _ids(node, out):
    if isinstance(node, dict):
        named = "full_name" in node or "name" in node
        if "id" in node and named:
            out.append(node["id"])
        for value in node.values():
            _ids(value, out)
    elif isinstance(node, list):
        for value in node:
            _ids(value, out)
    return out


def _signed_url(fetch, base, blueprint_id):
    """The download redirect, which needs the Cloudflare values.

    Without them the route answers 404 rather than erroring, so a
    redirect is the positive result.
    """
    url = f"{base}/api/blueprints/{blueprint_id}/download"
    status, headers, _ = fetch("GET", url)
    if status != 302:
        return False, f"HTTP {status}, expected 302", None
    target = headers.get("Location", "")
    if not target:
        return False, "302 with no Location", None
    host = _host_of(target)
    if not urlsplit(target).netloc.endswith(R2_SUFFIX):
        return False, f"redirect to {host}, not R2", None
    return True, f"redirect to {host}", target


def _r2_accepts(fetch, target):
    """One byte through the signature.

    A redirect only proves something was signed. R2 refusing it is a
    403, and the redirect looks identical either way.
    """
    status, _, _ = fetch("GET", target, headers={"Range": "bytes=0-0"})
    if status not in (200, 206):
        return False, f"R2 answered {status} for the signed URL", None
    return True, f"R2 served the signed URL ({status})", None


def _rejects_anonymous(fetch, base):
    """An authenticated route without credentials.

    401 means the session service was built from the token and the
    signing key. 500 means it was not.
    """
    status, _, _ = fetch(
        "POST",
        base + "/api/blueprints",
        headers={"Content-Type": "application/json"},
        body=b"{}",
    )
    if status != 401:
        return False, f"HTTP {status}, expected 401", None
    return True, "401 without credentials", None


def run_checks(fetch, base):
    """Every check, in order, each needing what came before it.

    Returns a list of (name, ok, detail). Stops at the first failure,
    because each later check needs the previous one's result.
    """
    results = []

    ok, detail, guide = _guides(fetch, base)
    results.append(("the API answers", ok, detail))
    if not ok:
        return results

    ok, detail, blueprint_id = _blueprint_id(fetch, base, guide)
    results.append(("a guide resolves", ok, detail))
    if not ok:
        return results

    ok, detail, target = _signed_url(fetch, base, blueprint_id)
    results.append(("a file is signed", ok, detail))
    if not ok:
        return results

    ok, detail, _ = _r2_accepts(fetch, target)
    results.append(("the signature is good", ok, detail))
    if not ok:
        return results

    ok, detail, _ = _rejects_anonymous(fetch, base)
    results.append(("anonymous writes are refused", ok, detail))
    return results


def _wait_for_the_api(fetch, base, attempts, delay, sleep):
    """The first answer, retried, because a cold start is not a failure."""
    for attempt in range(1, attempts + 1):
        ok, detail, _ = _guides(fetch, base)
        if ok:
            return True
        print(f"  attempt {attempt}: {detail}", flush=True)
        if attempt < attempts:
            sleep(delay)
    return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="the ALB hostname")
    parser.add_argument("--scheme", default="http")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--delay", type=float, default=10.0)
    args = parser.parse_args(argv)

    import time

    base = f"{args.scheme}://{args.host}"

    def fetch(method, url, headers=None, body=None):
        return _fetch(method, url, args.timeout, headers, body)

    print(f"verifying {base}", flush=True)
    if not _wait_for_the_api(fetch, base, args.attempts, args.delay, time.sleep):
        print("::error::the API never answered")
        return 1

    failed = False
    for name, ok, detail in run_checks(fetch, base):
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: {detail}", flush=True)
        failed = failed or not ok
    if failed:
        print("::error::the deployed API is not serving correctly")
        return 1
    print("every check passed", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
