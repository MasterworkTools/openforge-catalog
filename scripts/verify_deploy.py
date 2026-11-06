#!/usr/bin/env python3
"""Ask a deployed API whether it actually works, and fail if it does not.

The deploy chain is green when every step succeeded, which is not the
same as the API serving. The lambda target group carries no health
check, so nothing else notices an API that starts by raising: the ALB
keeps routing to a function returning 500.

Stdlib only. The deploy jobs have no virtualenv and install nothing.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

# `/health` is not routed through the ALB: the listener rule forwards
# `/api/*` only, so probing it reports the listener's fixed 404 whatever
# the app is doing.
GUIDES = "/api/guides"

R2_SUFFIX = ".r2.cloudflarestorage.com"

# urllib's default announces itself as Python-urllib, which a CDN may
# refuse. A refusal here would fail every deploy.
AGENT = "openforge-catalog-deploy-verify"


class Failed(Exception):
    """A check that did not pass.

    The message is logged, so it must never carry a URL: the download
    redirect is presigned and its signature rides in the query string.
    """


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A 302 is the result here, not something to follow."""

    def redirect_request(self, *args):
        return None


def _lower(headers):
    """Header names folded, because a response may spell them either way."""
    return {name.lower(): value for name, value in headers.items()}


def _fetch(method, url, timeout, headers=None, body=None):
    """Status, headers and body. An HTTP error is an answer; nothing else.

    A transport failure raises `Failed` rather than propagating, both so
    a cold start can be retried and so no exception quoting the URL can
    reach a log. `URLError.reason` is the underlying socket error and
    never holds the URL; for anything else only the type is named.
    """
    try:
        # Inside the try: a malformed URL raises here, from a ValueError
        # that quotes the whole URL.
        request = urllib.request.Request(
            url,
            method=method,
            data=body,
            headers={"User-Agent": AGENT, **(headers or {})},
        )
        opener = urllib.request.build_opener(_NoRedirect)
        with opener.open(request, timeout=timeout) as response:
            return response.status, _lower(response.headers), response.read()
    except urllib.error.HTTPError as answer:
        return answer.code, _lower(answer.headers), answer.read()
    except urllib.error.URLError as broken:
        raise Failed(f"no answer: {broken.reason}") from None
    except Exception as broken:
        raise Failed(f"no answer: {type(broken).__name__}") from None


def _document(body):
    """A JSON object, or a failure saying what arrived instead."""
    try:
        document = json.loads(body)
    except ValueError:
        raise Failed("answered 200 with a body that is not JSON") from None
    if not isinstance(document, dict):
        raise Failed("answered 200 with JSON that is not an object") from None
    return document


def _host_of(url):
    """A URL reduced to what is safe to log."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _guides(fetch, base):
    status, _, body = fetch("GET", base + GUIDES)
    if status != 200:
        raise Failed(f"HTTP {status}")
    guides = _document(body).get("guides")
    if not isinstance(guides, list) or not guides:
        raise Failed("answered 200 with no guides")
    keys = sorted(str(guide.get("guide_key", "?")) for guide in guides)
    return guides[0], f"{len(guides)} guides: {', '.join(keys)}"


def _blueprint_id(fetch, base, guide):
    """A real blueprint id, from a bounded response.

    `/api/blueprints` returns every row and exceeds the ALB's response
    limit, so a guide's resolved parts are where an id comes from.
    """
    key = guide.get("guide_key")
    status, _, body = fetch("GET", f"{base}/api/guides/{key}/resolve")
    if status != 200:
        raise Failed(f"resolve {key}: HTTP {status}")
    for part in _document(body).get("parts") or []:
        found = (part.get("blueprint") or {}).get("id")
        if found:
            return found, f"resolved {key}"
    raise Failed(f"resolve {key}: no blueprint in the parts")


def _signed_url(fetch, base, blueprint_id):
    """The download redirect, which needs the Cloudflare values.

    Without them the route answers 404 rather than erroring, so a
    redirect is the positive result. The target has to be an absolute
    https URL: a malformed one reaches urllib as a `ValueError` quoting
    the whole presigned URL.
    """
    url = f"{base}/api/blueprints/{blueprint_id}/download"
    status, headers, _ = fetch("GET", url)
    if status != 302:
        raise Failed(f"HTTP {status}, expected 302")
    target = headers.get("location", "")
    parts = urlsplit(target)
    if parts.scheme != "https" or not parts.netloc:
        raise Failed("302 to something that is not an absolute https URL")
    if not parts.netloc.endswith(R2_SUFFIX):
        raise Failed(f"redirect to {_host_of(target)}, not R2")
    return target, f"redirect to {_host_of(target)}"


def _r2_accepts(fetch, target):
    """One byte through the signature.

    A redirect only proves something was signed. R2 refusing it is a
    403, and the redirect looks identical either way.
    """
    status, _, _ = fetch("GET", target, headers={"Range": "bytes=0-0"})
    if status not in (200, 206):
        raise Failed(f"R2 answered {status} for the signed URL")
    return None, f"R2 served the signed URL ({status})"


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
        raise Failed(f"HTTP {status}, expected 401")
    return None, "401 without credentials"


def _retrying(call, attempts, delay, sleep):
    """The first answer, retried: a cold start is not a broken deploy."""
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except Failed as failure:
            if attempt == attempts:
                raise
            print(f"  attempt {attempt}: {failure}", flush=True)
            sleep(delay)


def run_checks(fetch, base, attempts=1, delay=0.0, sleep=time.sleep):
    """Every check, in order, each needing what came before it.

    Returns a list of (name, ok, detail) and stops at the first failure,
    because a later check cannot run without an earlier one's result.
    """
    results = []

    def step(name, call, *args):
        try:
            value, detail = call(*args)
        except Failed as failure:
            results.append((name, False, str(failure)))
            print(f"  FAIL {name}: {failure}", flush=True)
            raise
        results.append((name, True, detail))
        print(f"  ok   {name}: {detail}", flush=True)
        return value

    def answer_or_retry():
        return _retrying(lambda: _guides(fetch, base), attempts, delay, sleep)

    try:
        guide = step("the API answers", answer_or_retry)
        found = step("a guide resolves", _blueprint_id, fetch, base, guide)
        target = step("a file is signed", _signed_url, fetch, base, found)
        step("the signature is good", _r2_accepts, fetch, target)
        step("anonymous writes are refused", _rejects_anonymous, fetch, base)
    except Failed:
        pass
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="the ALB hostname")
    parser.add_argument("--scheme", default="http")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--delay", type=float, default=10.0)
    args = parser.parse_args(argv)

    if not args.host.strip():
        print("::error::no API hostname was given")
        return 1

    base = f"{args.scheme}://{args.host}"

    def fetch(method, url, headers=None, body=None):
        return _fetch(method, url, args.timeout, headers, body)

    print(f"verifying {base}", flush=True)
    results = run_checks(fetch, base, args.attempts, args.delay, time.sleep)
    if not results or not all(ok for _, ok, _ in results):
        print("::error::the deployed API is not serving correctly")
        return 1
    print("every check passed", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
