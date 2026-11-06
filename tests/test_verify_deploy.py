"""The deploy verification script's verdicts.

The script exists to fail a deploy, so a false pass is the expensive
bug: it restores the green-over-500 state the script was written to
remove. Most cases inject a fake fetch; the ones covering `_fetch`
itself run against a real server on the loopback, because a stub cannot
show whether a 302 is followed or a 401 raises.
"""

import importlib.util
import json
import pathlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

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


def _fetch_from(answers):
    def fetch(method, url, headers=None, body=None):
        status, response_headers, text = answers[(method, url)]
        return status, response_headers, text.encode()

    return fetch


def _verdicts(answers):
    results = verify.run_checks(_fetch_from(answers), BASE)
    return {name: (ok, detail) for name, ok, detail in results}


def _run(answers, monkeypatch, argv=("--host", "alb.example")):
    """`main`, with the network replaced."""

    def fake(method, url, timeout, headers=None, body=None):
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


def test_guides_served_empty_is_a_failure():
    """A 200 with nothing in it means the fixtures did not land."""
    answers = _answers(
        {("GET", f"{BASE}/api/guides"): (200, {}, json.dumps({"guides": []}))}
    )

    verdicts = _verdicts(answers)

    assert verdicts["the API answers"][0] is False
    assert "no guides" in verdicts["the API answers"][1]


@pytest.mark.parametrize(
    "body",
    ["<html>a gateway error page</html>", "[]", '{"guides": "floor"}'],
    ids=["not-json", "json-but-a-list", "guides-not-a-list"],
)
def test_a_body_that_is_not_what_it_should_be_fails_cleanly(body):
    """Cleanly means naming the check rather than raising: a traceback
    says a deploy broke without saying where."""
    answers = _answers({("GET", f"{BASE}/api/guides"): (200, {}, body)})

    verdicts = _verdicts(answers)

    assert verdicts["the API answers"][0] is False


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


def test_the_id_comes_from_a_part_not_from_anything_with_an_id():
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


def test_a_missing_cloudflare_endpoint_fails_rather_than_passing():
    """The download route answers 404 rather than erroring when the
    endpoint is absent, so only a redirect is a pass."""
    answers = _answers({("GET", f"{BASE}/api/blueprints/bp-1/download"): (404, {}, "")})

    verdicts = _verdicts(answers)

    assert verdicts["a file is signed"] == (False, "HTTP 404, expected 302")


def test_a_200_on_the_download_is_not_a_pass():
    answers = _answers({("GET", f"{BASE}/api/blueprints/bp-1/download"): (200, {}, "")})

    verdicts = _verdicts(answers)

    assert verdicts["a file is signed"][0] is False


@pytest.mark.parametrize(
    "location",
    [
        "",
        "/relative/path?sig=abc",
        "//acct.r2.cloudflarestorage.com/f?X-Amz-Signature=abc",
        "http://acct.r2.cloudflarestorage.com/f?X-Amz-Signature=abc",
        "https://notr2.cloudflare.example/f?X-Amz-Signature=abc",
        "https://acct.r2.cloudflarestorage.com.evil.example/f?sig=abc",
    ],
    ids=["empty", "relative", "scheme-relative", "http", "wrong-host", "suffix-trick"],
)
def test_only_an_absolute_https_r2_url_is_accepted(location):
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
    assert "X-Amz-Signature" not in detail
    assert "sig=abc" not in detail


def test_credentials_r2_refuses_are_caught_despite_a_good_redirect():
    """The check that earns its place: bad Cloudflare values still
    produce a 302, and only R2's answer tells them apart."""
    answers = _answers({("GET", SIGNED): (403, {}, "")})

    verdicts = _verdicts(answers)

    assert verdicts["a file is signed"][0] is True
    assert verdicts["the signature is good"] == (
        False,
        "R2 answered 403 for the signed URL",
    )


@pytest.mark.parametrize("status", [301, 302, 404, 500])
def test_only_a_served_byte_counts_as_a_good_signature(status):
    answers = _answers({("GET", SIGNED): (status, {}, "")})

    verdicts = _verdicts(answers)

    assert verdicts["the signature is good"][0] is False


def test_an_unauthenticated_write_being_accepted_is_a_failure():
    answers = _answers({("POST", f"{BASE}/api/blueprints"): (201, {}, "")})

    verdicts = _verdicts(answers)

    assert verdicts["anonymous writes are refused"] == (
        False,
        "HTTP 201, expected 401",
    )


def test_a_500_on_the_write_route_is_also_a_failure():
    """An absent signing key is a 500 there, not a 401."""
    answers = _answers({("POST", f"{BASE}/api/blueprints"): (500, {}, "")})

    verdicts = _verdicts(answers)

    assert verdicts["anonymous writes are refused"][0] is False


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
    """Answers the three shapes `_fetch` has to get right."""

    def do_GET(self):
        if self.path == "/redirect":
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
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


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
