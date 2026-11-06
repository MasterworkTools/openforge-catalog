"""The deploy verification script's verdicts.

The script exists to fail a deploy, so what matters is that each broken
API it is meant to catch produces a failure, and that a working one
produces none. The HTTP calls go through one injected function, so
every case here is a dictionary of canned answers.
"""

import importlib.util
import json
import pathlib

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
RESOLVE = {"parts": [{"id": "bp-1", "full_name": "tiles/floor.stl"}]}


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
            {"Location": SIGNED},
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


def test_guides_served_empty_is_a_failure():
    """A 200 with nothing in it means the fixtures did not land, which
    the answerable-path gate would not catch either."""
    answers = _answers(
        {("GET", f"{BASE}/api/guides"): (200, {}, json.dumps({"guides": []}))}
    )

    verdicts = _verdicts(answers)

    assert verdicts["the API answers"][0] is False
    assert "no guides" in verdicts["the API answers"][1]


def test_a_missing_cloudflare_endpoint_fails_rather_than_passing():
    """The download route answers 404 rather than erroring when the
    endpoint is absent, so only a redirect is a pass."""
    answers = _answers({("GET", f"{BASE}/api/blueprints/bp-1/download"): (404, {}, "")})

    verdicts = _verdicts(answers)

    assert verdicts["a file is signed"] == (False, "HTTP 404, expected 302")


def test_a_redirect_somewhere_other_than_r2_is_a_failure():
    answers = _answers(
        {
            ("GET", f"{BASE}/api/blueprints/bp-1/download"): (
                302,
                {"Location": "https://example.invalid/f.stl?sig=abc"},
                "",
            )
        }
    )

    verdicts = _verdicts(answers)

    ok, detail = verdicts["a file is signed"]
    assert ok is False
    assert "not R2" in detail


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


def test_no_signed_url_is_ever_logged(capsys):
    """The signature and access key ride in the query string."""
    verify.main(["--host", "alb.example", "--attempts", "1"])
    printed = capsys.readouterr().out

    assert "X-Amz-Signature" not in printed


@pytest.fixture(autouse=True)
def _no_real_requests(monkeypatch):
    """`main` must not reach the network from the test suite."""
    answers = _answers()

    def fake(method, url, timeout, headers=None, body=None):
        status, response_headers, text = answers[(method, url)]
        return status, response_headers, text.encode()

    monkeypatch.setattr(verify, "_fetch", fake)


def test_a_cold_start_is_retried_rather_than_failed():
    """The first answer after a deploy can be a cold start."""
    attempts = []

    def fetch(method, url, headers=None, body=None):
        attempts.append(url)
        if len(attempts) < 3:
            return 500, {}, b""
        return 200, {}, json.dumps(GUIDES).encode()

    assert verify._wait_for_the_api(
        fetch, BASE, attempts=4, delay=0, sleep=lambda _: None
    )
    assert len(attempts) == 3


def test_an_api_that_never_answers_runs_out_of_attempts():
    def fetch(method, url, headers=None, body=None):
        return 500, {}, b""

    assert not verify._wait_for_the_api(
        fetch, BASE, attempts=3, delay=0, sleep=lambda _: None
    )


def test_main_exits_non_zero_when_a_check_fails(monkeypatch):
    answers = _answers({("GET", SIGNED): (403, {}, "")})

    def fake(method, url, timeout, headers=None, body=None):
        status, response_headers, text = answers[(method, url)]
        return status, response_headers, text.encode()

    monkeypatch.setattr(verify, "_fetch", fake)

    assert verify.main(["--host", "alb.example", "--attempts", "1"]) == 1


def test_main_exits_zero_on_a_healthy_deploy():
    assert verify.main(["--host", "alb.example", "--attempts", "1"]) == 0
