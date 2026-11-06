"""The deploy verification script's verdicts.

The script exists to fail a deploy, so a false pass is the expensive
bug: it restores the green-over-500 state the script was written to
remove. Most cases inject a fake fetch; the ones covering `_fetch`
itself run against a real server on the loopback, because a stub cannot
show whether a 302 is followed or a 401 raises.
"""

import email.message
import importlib.util
import json
import pathlib
import threading
import time
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "verify_deploy.py"


def _load():
    spec = importlib.util.spec_from_file_location("verify_deploy", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify = _load()

BASE = "http://alb.example"
SIGNED = "https://acct.r2.cloudflarestorage.com/f.stl?X-Amz-Signature=abc"

GUIDES = {"guides": [{"guide_key": "floor"}, {"guide_key": "door"}]}
RESOLVE = {
    "parts": [{"role": "floor", "blueprint": {"id": "bp-1", "full_name": "f.stl"}}]
}


def _answers(overrides=None):
    """A healthy API, with any single answer replaced."""
    answers = {
        ("GET", f"{BASE}/api/guides"): (200, {}, json.dumps(GUIDES)),
        ("GET", f"{BASE}/api/guides/floor/resolve"): (
            200,
            {},
            json.dumps(RESOLVE),
        ),
        ("GET", f"{BASE}/api/blueprints/bp-1/download"): (
            302,
            {"location": SIGNED},
            "",
        ),
        ("GET", SIGNED): (206, {}, "x"),
        ("POST", f"{BASE}/api/blueprints"): (401, {}, ""),
    }
    answers.update(overrides or {})
    return answers


def _fetch_from(answers, calls=None):
    def fetch(method, url, headers=None, body=None):
        if calls is not None:
            calls.append(
                {"method": method, "url": url, "headers": headers or {}, "body": body}
            )
        status, response_headers, text = answers[(method, url)]
        return status, response_headers, text.encode()

    return fetch


def _verdicts(answers):
    results = verify.run_checks(_fetch_from(answers), BASE)
    return {name: (ok, detail) for name, ok, detail in results}


def _run(answers, monkeypatch, argv=("--host", "alb.example"), calls=None):
    """`main`, with the network replaced."""

    def fake(method, url, timeout, headers=None, body=None):
        if calls is not None:
            calls.append(
                {
                    "method": method,
                    "url": url,
                    "timeout": timeout,
                    "headers": headers or {},
                    "body": body,
                }
            )
        status, response_headers, text = answers[(method, url)]
        return status, response_headers, text.encode()

    monkeypatch.setattr(verify, "_fetch", fake)
    return verify.main([*argv, "--attempts", "1", "--delay", "0"])


def test_a_working_api_passes_every_check():
    verdicts = _verdicts(_answers())

    assert len(verdicts) == 5
    assert all(ok for ok, _ in verdicts.values())


def test_an_api_that_cannot_start_fails_the_first_check():
    """A missing value in the app secret makes init raise, which is a
    500 on every route."""
    answers = _answers({("GET", f"{BASE}/api/guides"): (500, {}, "")})

    verdicts = _verdicts(answers)

    assert verdicts["the API answers"] == (False, "HTTP 500")
    # Nothing after it ran, because each check needs the one before.
    assert len(verdicts) == 1


def test_a_dead_api_makes_the_job_fail(monkeypatch):
    """The whole point. `main` has to exit non-zero, not merely report:
    a zero exit here is the green-over-500 deploy this replaces."""
    answers = _answers({("GET", f"{BASE}/api/guides"): (500, {}, "")})

    assert _run(answers, monkeypatch) == 1


@pytest.mark.parametrize(
    "body,says",
    [
        ("<html>a gateway error page</html>", "not JSON"),
        ("[]", "not an object"),
        ('{"guides": "floor"}', "no guides"),
        ('{"guides": []}', "no guides"),
    ],
    ids=["not-json", "json-but-a-list", "guides-not-a-list", "guides-empty"],
)
def test_a_body_that_is_not_what_it_should_be_fails_cleanly(body, says):
    """Cleanly means naming the check rather than raising: a traceback
    says a deploy broke without saying where."""
    answers = _answers({("GET", f"{BASE}/api/guides"): (200, {}, body)})

    verdicts = _verdicts(answers)

    ok, detail = verdicts["the API answers"]
    assert ok is False
    assert says in detail


def test_a_resolve_that_fails_is_reported_as_the_resolve():
    answers = _answers({("GET", f"{BASE}/api/guides/floor/resolve"): (500, {}, "")})

    verdicts = _verdicts(answers)

    assert verdicts["a guide resolves"] == (False, "resolve floor: HTTP 500")


def test_a_resolve_with_no_parts_is_a_failure():
    answers = _answers(
        {
            ("GET", f"{BASE}/api/guides/floor/resolve"): (
                200,
                {},
                json.dumps({"parts": []}),
            )
        }
    )

    verdicts = _verdicts(answers)

    assert verdicts["a guide resolves"][0] is False
    assert "no blueprint" in verdicts["a guide resolves"][1]


def test_an_id_elsewhere_in_the_response_is_not_mistaken_for_a_part():
    """A resolve response carries ids for steps, roles and refinements
    too. Picking one of those would make the download check fail and
    blame signing."""
    answers = _answers(
        {
            ("GET", f"{BASE}/api/guides/floor/resolve"): (
                200,
                {},
                json.dumps(
                    {
                        "steps": [{"id": "step-1", "name": "size"}],
                        "parts": [{"blueprint": {"id": "bp-1", "name": "f"}}],
                    }
                ),
            )
        }
    )

    verdicts = _verdicts(answers)

    assert verdicts["a file is signed"][0] is True


@pytest.mark.parametrize("status", [404, 200, 500])
def test_only_a_redirect_is_a_signed_download(status):
    """The route answers 404 rather than erroring when the Cloudflare
    endpoint is absent, so a redirect is the only pass."""
    answers = _answers(
        {("GET", f"{BASE}/api/blueprints/bp-1/download"): (status, {}, "")}
    )

    verdicts = _verdicts(answers)

    assert verdicts["a file is signed"] == (False, f"HTTP {status}, expected 302")


ABSOLUTE = "not an absolute https URL"
NOT_R2 = "not R2"


@pytest.mark.parametrize(
    "location,expected",
    [
        ("", ABSOLUTE),
        ("/relative/path?sig=abc", ABSOLUTE),
        ("//acct.r2.cloudflarestorage.com/f?X-Amz-Signature=abc", ABSOLUTE),
        ("http://acct.r2.cloudflarestorage.com/f?X-Amz-Sig=abc", ABSOLUTE),
        ("https://notr2.cloudflare.example/f?X-Amz-Signature=abc", NOT_R2),
        ("https://acct.r2.cloudflarestorage.com.evil.example/f?sig=abc", NOT_R2),
        ("https://evilr2.cloudflarestorage.com/f?sig=abc", NOT_R2),
    ],
    ids=[
        "empty",
        "relative",
        "scheme-relative",
        "http",
        "wrong-host",
        "suffix-trick",
        "no-leading-dot",
    ],
)
def test_only_an_absolute_https_r2_url_is_accepted(location, expected):
    """A scheme-relative or malformed target reaches urllib as a
    ValueError quoting the whole presigned URL, so it has to be refused
    here rather than fetched."""
    answers = _answers(
        {
            ("GET", f"{BASE}/api/blueprints/bp-1/download"): (
                302,
                {"location": location},
                "",
            )
        }
    )

    verdicts = _verdicts(answers)

    ok, detail = verdicts["a file is signed"]
    assert ok is False
    # Which check refused it, so a host test written without the
    # leading dot cannot pass by hitting the other branch.
    assert expected in detail
    assert "X-Amz-Signature" not in detail
    assert "sig=abc" not in detail


@pytest.mark.parametrize("status", [403, 301, 302, 404, 500])
def test_only_a_served_byte_counts_as_a_good_signature(status):
    """The check that earns its place: bad Cloudflare credentials still
    produce a 302, and only R2's answer tells them apart. So the
    redirect step has to pass while this one fails."""
    answers = _answers({("GET", SIGNED): (status, {}, "")})

    verdicts = _verdicts(answers)

    assert verdicts["a file is signed"][0] is True
    assert verdicts["the signature is good"] == (
        False,
        f"R2 answered {status} for the signed URL",
    )


@pytest.mark.parametrize("status", [201, 200, 403, 500])
def test_only_a_401_proves_the_write_route_is_guarded(status):
    """An absent signing key is a 500 there rather than a 401, and a 403
    is some other refusal, not this one."""
    answers = _answers({("POST", f"{BASE}/api/blueprints"): (status, {}, "")})

    verdicts = _verdicts(answers)

    assert verdicts["anonymous writes are refused"] == (
        False,
        f"HTTP {status}, expected 401",
    )


def test_no_signed_url_is_ever_logged(capsys, monkeypatch):
    """The signature and access key ride in the query string."""
    _run(_answers(), monkeypatch)
    printed = capsys.readouterr().out

    assert "X-Amz-Signature" not in printed
    assert "acct.r2.cloudflarestorage.com" in printed


def test_a_cold_start_is_retried_rather_than_failed():
    """The first answer after a deploy can be a cold start."""
    seen = []

    def fetch(method, url, headers=None, body=None):
        if not url.endswith("/api/guides"):
            return 200, {}, json.dumps(RESOLVE).encode()
        seen.append(url)
        if len(seen) < 3:
            raise verify.Failed("no answer: timed out")
        return 200, {}, json.dumps(GUIDES).encode()

    results = verify.run_checks(fetch, BASE, attempts=4, delay=0, sleep=lambda _: None)

    assert results[0][1] is True
    assert len(seen) == 3


def test_a_connection_that_never_succeeds_runs_out_of_attempts():
    """A refused connection has to be retried like a slow one, and then
    reported rather than raised."""

    def fetch(method, url, headers=None, body=None):
        raise verify.Failed("no answer: [Errno 111] Connection refused")

    results = verify.run_checks(fetch, BASE, attempts=3, delay=0, sleep=lambda _: None)

    assert results == [
        ("the API answers", False, "no answer: [Errno 111] Connection refused")
    ]


def test_an_empty_host_is_refused_rather_than_verified(capsys):
    """The workflow passes a job output. If that output is empty the job
    must fail saying so, not probe `http://`."""
    assert verify.main(["--host", "  "]) == 1
    assert "no API hostname" in capsys.readouterr().out


def test_main_exits_zero_on_a_healthy_deploy(monkeypatch):
    assert _run(_answers(), monkeypatch) == 0


class _Handler(BaseHTTPRequestHandler):
    """Answers the shapes `_fetch` has to get right, and echoes the
    request so the headers and body it sends are observable."""

    def _echo(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        length = int(self.headers.get("Content-Length") or 0)
        self.wfile.write(
            json.dumps(
                {
                    "method": self.command,
                    "agent": self.headers.get("User-Agent"),
                    "range": self.headers.get("Range"),
                    "body": self.rfile.read(length).decode(),
                }
            ).encode()
        )

    def do_POST(self):
        self._echo()

    def do_GET(self):
        if self.path == "/echo":
            self._echo()
        elif self.path == "/slow":
            time.sleep(1.5)
            self.send_response(200)
            self.end_headers()
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "https://elsewhere.example/x")
            self.end_headers()
        elif self.path == "/refused":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"no")
        else:
            self.send_response(200)
            self.send_header("X-Odd-Case", "yes")
            self.end_headers()
            self.wfile.write(b"hello")

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def server():
    # Threading, so `/slow` sleeping past its client's timeout does not
    # make the next test queue behind it.
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture(autouse=True)
def _no_proxy(monkeypatch):
    """urllib honours http_proxy, so a proxied runner would send the
    loopback tests to the proxy."""
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")


def test_a_redirect_is_returned_not_followed(server):
    """Following it would fetch the target and report its 200, so every
    deploy would pass whatever the API said."""
    status, headers, _ = verify._fetch("GET", server + "/redirect", 5)

    assert status == 302
    assert headers["location"] == "https://elsewhere.example/x"


def test_an_http_error_is_an_answer_rather_than_an_exception(server):
    """The 401 check depends on this: if a 4xx raised, the expected
    refusal would look like a broken deploy."""
    status, _, body = verify._fetch("GET", server + "/refused", 5)

    assert (status, body) == (401, b"no")


def test_a_header_sent_in_any_case_is_found(server):
    status, headers, body = verify._fetch("GET", server + "/plain", 5)

    assert (status, body) == (200, b"hello")
    # Sent as X-Odd-Case; a case-sensitive lookup of Location has
    # already produced a false "302 with no Location".
    assert headers["x-odd-case"] == "yes"


def test_a_closed_port_is_a_failure_not_a_traceback():
    """A connection error has to arrive as `Failed` so the retry loop
    sees it and the log names the check."""
    with pytest.raises(verify.Failed) as caught:
        verify._fetch("GET", "http://127.0.0.1:1/plain", 2)

    assert "no answer" in str(caught.value)
    # The socket's reason, not the exception class: "no answer:
    # URLError" would tell whoever reads the log nothing.
    assert "URLError" not in str(caught.value)


def test_a_malformed_url_never_reaches_the_log_with_its_query():
    """urllib raises a ValueError quoting the whole URL. If that message
    were used as the detail, a presigned URL would land in the log."""
    with pytest.raises(verify.Failed) as caught:
        verify._fetch("GET", "//host/path?X-Amz-Signature=abc", 2)

    assert "X-Amz-Signature" not in str(caught.value)


def test_a_stalled_error_body_is_still_reported_as_its_status(monkeypatch):
    """`answer.read()` runs inside the HTTPError handler, where a
    sibling except clause cannot reach it. A 5xx whose body stalls --
    a cold Lambda -- would otherwise skip the retry and crash."""

    class Stalled(urllib.error.HTTPError):
        def read(self, *args):
            raise TimeoutError("timed out")

    stalled = Stalled(
        url="http://alb.example/api/guides",
        code=503,
        msg="unavailable",
        hdrs=email.message.Message(),
        fp=None,
    )

    class Opener:
        def open(self, *args, **kwargs):
            raise stalled

    monkeypatch.setattr(verify.urllib.request, "build_opener", lambda *a: Opener())

    status, _, body = verify._fetch("GET", "http://alb.example/api/guides", 2)

    assert (status, body) == (503, b"")


def test_a_mistyped_attempt_count_does_not_crash():
    """`--attempts 0` would leave the retry returning None, and
    unpacking that is a traceback rather than a verdict."""
    answers = _answers({("GET", f"{BASE}/api/guides"): (500, {}, "")})

    results = verify.run_checks(
        _fetch_from(answers), BASE, attempts=0, delay=0, sleep=lambda _: None
    )

    assert results == [("the API answers", False, "HTTP 500")]


def test_guides_that_are_not_objects_fail_cleanly():
    """A list of strings is a broken API, so it has to name the check
    rather than raise from `.get`."""
    answers = _answers(
        {
            ("GET", f"{BASE}/api/guides"): (
                200,
                {},
                json.dumps({"guides": ["floor", "door"]}),
            )
        }
    )

    verdicts = _verdicts(answers)

    assert verdicts["the API answers"][0] is False


def test_a_part_that_is_not_an_object_is_skipped_not_fatal():
    answers = _answers(
        {
            ("GET", f"{BASE}/api/guides/floor/resolve"): (
                200,
                {},
                json.dumps({"parts": ["junk", {"blueprint": {"id": "bp-1"}}]}),
            )
        }
    )

    verdicts = _verdicts(answers)

    assert verdicts["a guide resolves"][0] is True


def test_a_host_that_never_answers_times_out_rather_than_hanging(server):
    """Without the timeout a blackholed ALB hangs the verify job to the
    job default instead of failing, holding the deploy's concurrency
    group with it."""
    with pytest.raises(verify.Failed) as caught:
        verify._fetch("GET", server + "/slow", 0.2)

    assert "no answer" in str(caught.value)


def test_the_request_carries_the_agent_the_range_and_the_body(server):
    """A CDN may refuse urllib's default agent, the signature check
    needs the Range to read one byte, and the write check has to be a
    POST with a body or the 401 proves nothing."""
    _, _, body = verify._fetch(
        "POST",
        server + "/echo",
        5,
        headers={"Range": "bytes=0-0"},
        body=b'{"x": 1}',
    )
    sent = json.loads(body)

    assert sent["method"] == "POST"
    assert sent["agent"] == verify.AGENT
    assert sent["range"] == "bytes=0-0"
    assert sent["body"] == '{"x": 1}'


def test_main_passes_the_retry_settings_and_the_scheme_through(monkeypatch):
    """`main` could stop forwarding these and every check would still
    pass: the default is one attempt, so cold starts would fail
    releases and nothing here would say so."""
    seen = {"urls": [], "sleeps": []}

    def fake(method, url, timeout, headers=None, body=None):
        seen["urls"].append(url)
        return 500, {}, b""

    monkeypatch.setattr(verify, "_fetch", fake)
    monkeypatch.setattr(verify.time, "sleep", seen["sleeps"].append)

    code = verify.main(
        [
            "--host",
            "alb.example",
            "--scheme",
            "https",
            "--attempts",
            "3",
            "--delay",
            "7",
        ]
    )

    assert code == 1
    assert seen["urls"] == ["https://alb.example/api/guides"] * 3
    assert seen["sleeps"] == [7.0, 7.0]


def test_a_failure_stops_the_checks_after_it():
    """Each check needs the one before, so running on would report
    failures caused by the first rather than found independently."""
    answers = _answers({("GET", f"{BASE}/api/blueprints/bp-1/download"): (404, {}, "")})

    results = verify.run_checks(_fetch_from(answers), BASE)

    assert [name for name, _, _ in results] == [
        "the API answers",
        "a guide resolves",
        "a file is signed",
    ]


@pytest.mark.parametrize(
    "document",
    ['{"parts": null}', '{"parts": [{"blueprint": null}]}', "{}"],
    ids=["parts-null", "blueprint-null", "no-parts-key"],
)
def test_a_resolve_missing_its_parts_fails_cleanly(document):
    answers = _answers(
        {("GET", f"{BASE}/api/guides/floor/resolve"): (200, {}, document)}
    )

    verdicts = _verdicts(answers)

    assert verdicts["a guide resolves"][0] is False
    assert "no blueprint" in verdicts["a guide resolves"][1]


@pytest.mark.parametrize(
    "broken",
    [
        {("GET", f"{BASE}/api/guides/floor/resolve"): (500, {}, "")},
        {("GET", f"{BASE}/api/blueprints/bp-1/download"): (404, {}, "")},
        {("GET", SIGNED): (403, {}, "")},
        {("POST", f"{BASE}/api/blueprints"): (201, {}, "")},
    ],
    ids=["resolve", "download", "signature", "write"],
)
def test_a_failure_at_any_step_makes_the_job_fail(broken, monkeypatch):
    """Not only the first one. `any` in place of `all` would print
    "every check passed" and exit 0 for every failure after step 1,
    which is the green-over-broken deploy this exists to stop."""
    assert _run(_answers(broken), monkeypatch) == 1


def test_each_check_sends_what_it_needs_to_mean_anything():
    """Without the Range the signature check downloads a whole STL, and
    without a POST body the 401 proves nothing about the write path."""
    calls = []

    verify.run_checks(_fetch_from(_answers(), calls), BASE)
    sent = {(call["method"], call["url"]): call for call in calls}

    assert sent[("GET", SIGNED)]["headers"]["Range"] == "bytes=0-0"
    write = sent[("POST", f"{BASE}/api/blueprints")]
    assert write["body"] == b"{}"
    assert write["headers"]["Content-Type"] == "application/json"


def test_main_hands_the_timeout_and_the_pieces_to_each_request(monkeypatch):
    """`main` wraps `_fetch` to bind the timeout. A wrapper that
    swapped the headers and body, or pinned its own timeout, would
    leave every check passing."""
    calls = []

    _run(
        _answers(),
        monkeypatch,
        argv=("--host", "alb.example", "--timeout", "7"),
        calls=calls,
    )

    assert {call["timeout"] for call in calls} == {7.0}
    write = next(call for call in calls if call["method"] == "POST")
    assert write["body"] == b"{}"
    assert write["headers"]["Content-Type"] == "application/json"


def test_the_default_timeout_is_short_enough_to_be_a_timeout(monkeypatch):
    """The Lambda's own limit is 30s, so a client default above that
    would never fire."""
    calls = []

    _run(_answers(), monkeypatch, calls=calls)

    assert {call["timeout"] for call in calls} == {20.0}
