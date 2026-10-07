"""The invoke-and-verify script both deploys and the manual re-run share.

The load is invoked asynchronously and reports through an SQS queue, so the
script's job is to drain whatever was there before, invoke, wait, and read the
one record Lambda delivers. Each of those has a way of passing a failure off
as a success, which is what these tests hold.

`aws` is stubbed by a script that records every call and answers from a spec
file, which is the whole of what the real one contributes here.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/load-fixtures.sh"

STUB = """#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
spec = json.load(open(os.environ["STUB_SPEC"]))
with open("calls.jsonl", "a") as fh:
    fh.write(json.dumps(args) + "\\n")


def arg(name, default=None):
    return args[args.index(name) + 1] if name in args else default


if args[:2] == ["sqs", "get-queue-url"]:
    print("https://sqs.example/q")
elif args[:2] == ["sqs", "receive-message"]:
    # A drain reads a batch without waiting; the poll waits. Telling them
    # apart is what lets a spec seed stale records without also answering
    # the poll.
    draining = arg("--wait-time-seconds") is None
    key = "stale" if draining else "result"
    pending = spec.get(key) or []
    if pending:
        body = pending.pop(0)
        spec[key] = pending
        with open(os.environ["STUB_SPEC"], "w") as fh:
            json.dump(spec, fh)
        print(json.dumps({"Messages": [
            {"ReceiptHandle": f"rh-{key}", "Body": json.dumps(body)}
        ]}))
    else:
        print("")
elif args[:2] == ["sqs", "delete-message"]:
    pass
elif args[:2] == ["lambda", "invoke"]:
    print(json.dumps(spec.get("ack", {"StatusCode": 202})))
else:
    sys.exit(f"unexpected aws call: {args}")
"""


def _record(payload, condition="Success", function_error=None):
    """A Lambda async destination record, in the shape Lambda delivers."""
    response_context = {"statusCode": 200, "executedVersion": "$LATEST"}
    if function_error:
        response_context["functionError"] = function_error
    return {
        "version": "1.0",
        "requestContext": {
            "requestId": "req-1",
            "condition": condition,
            "approximateInvokeCount": 1,
        },
        "requestPayload": {},
        "responseContext": response_context,
        "responsePayload": payload,
    }


OK_NO_CHANGE = {"ok": True, "files": 45, "blueprints_changed": False, "applied": []}


@pytest.fixture
def run_with(tmp_path):
    """Run the script against a canned queue and invoke result."""

    def run(result=None, stale=None, ack=None, fixture=None, deadline="2"):
        spec = {"result": [result] if result else [], "stale": stale or []}
        if ack is not None:
            spec["ack"] = ack
        spec_path = tmp_path / "spec.json"
        spec_path.write_text(json.dumps(spec))

        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        (fake_bin / "aws").write_text(STUB)
        (fake_bin / "aws").chmod(0o755)

        env = dict(
            os.environ,
            PATH=f"{fake_bin}:{os.environ['PATH']}",
            STUB_SPEC=str(spec_path),
            DEADLINE_SECONDS=deadline,
        )
        if fixture is not None:
            env["FIXTURE"] = fixture
        else:
            env.pop("FIXTURE", None)

        proc = subprocess.run(
            # Run the file, as all four call sites do, so the executable bit
            # and the shebang are part of what these tests hold.
            [str(SCRIPT)],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
        )
        calls_file = tmp_path / "calls.jsonl"
        proc.calls = (
            [json.loads(line) for line in calls_file.read_text().splitlines()]
            if calls_file.exists()
            else []
        )
        return proc

    return run


def _invoke(proc):
    """The arguments of the one `lambda invoke` call."""
    invokes = [c for c in proc.calls if c[:2] == ["lambda", "invoke"]]
    assert len(invokes) == 1, invokes
    return invokes[0]


def _payload_of(proc):
    args = _invoke(proc)
    return args[args.index("--payload") + 1]


def test_a_healthy_no_op_passes(run_with):
    """The common case: a release that carried no data change."""
    proc = run_with(result=_record(OK_NO_CHANGE))

    assert proc.returncode == 0, proc.stderr
    assert "no blueprint changes" in proc.stdout
    # Asynchronous, which is the reason this script does not simply read the
    # invoke's response: a load outlives the socket a synchronous call needs.
    assert "--invocation-type" in _invoke(proc)
    assert _invoke(proc)[_invoke(proc).index("--invocation-type") + 1] == "Event"


def test_a_raise_is_read_off_the_record(run_with):
    """The handler's failures arrive as a record, not as a call that errored."""
    proc = run_with(
        result=_record(
            {"errorMessage": "3 fixture paths are neither a live row nor listed"},
            function_error="Unhandled",
        )
    )

    assert proc.returncode != 0
    assert "fixture load failed" in proc.stdout + proc.stderr


def test_an_expired_event_fails_rather_than_looking_absent(run_with):
    """A load that never ran because it collided with another one.

    Lambda expires the event and delivers a record saying so. The payload here
    is a healthy one on purpose: the condition is what decides, and a record
    whose payload reads fine must still be refused when Lambda says it did not
    succeed.
    """
    proc = run_with(result=_record(OK_NO_CHANGE, condition="RetriesExhausted"))

    assert proc.returncode != 0
    assert "RetriesExhausted" in proc.stdout + proc.stderr


def test_a_payload_that_does_not_report_ok_fails(run_with):
    """Belt to the condition's brace: a tidy failure is still a failure."""
    proc = run_with(result=_record({"ok": False}))

    assert proc.returncode != 0
    assert "did not report ok" in proc.stdout + proc.stderr


def test_an_invoke_that_was_not_accepted_fails_immediately(run_with):
    """No record will ever arrive, so waiting for one would waste the job."""
    proc = run_with(result=_record(OK_NO_CHANGE), ack={"StatusCode": 500})

    assert proc.returncode != 0
    assert "not accepted" in proc.stdout + proc.stderr
    # It did not go on to wait out the deadline.
    assert not [c for c in proc.calls if "--wait-time-seconds" in c]


def test_no_result_before_the_deadline_fails_and_warns_about_re_running(run_with):
    """The load may still hold the one concurrency slot there is."""
    proc = run_with(result=None, deadline="1")

    assert proc.returncode != 0
    assert "no result after" in proc.stdout + proc.stderr
    assert "still be running" in proc.stdout + proc.stderr


def test_a_stale_record_is_discarded_before_the_invoke(run_with):
    """Otherwise a previous load's record passes as this one's.

    The stale record here would pass every later check, so a script that read
    it would report success for a load it never waited for.
    """
    proc = run_with(result=_record(OK_NO_CHANGE), stale=[_record(OK_NO_CHANGE)])

    assert proc.returncode == 0, proc.stderr
    assert "discarding a stale result record" in proc.stdout
    # Drained before invoking, not after.
    kinds = [c[1] for c in proc.calls]
    assert kinds.index("delete-message") < kinds.index("invoke")


def test_changes_are_named_rather_than_counted(run_with):
    """An operator reading the log should see which fixtures moved."""
    proc = run_with(
        result=_record(
            {
                "ok": True,
                "files": 45,
                "blueprints_changed": True,
                "applied": [
                    {
                        "file": "bases.json",
                        "type": "blueprint",
                        "added": 7,
                        "modified": 0,
                        "deprecated": 0,
                        "consolidated": 2,
                    }
                ],
            }
        )
    )

    assert proc.returncode == 0, proc.stderr
    assert "bases.json" in proc.stdout


def test_a_named_fixture_is_passed_through_as_json(run_with):
    """The manual re-run's single-file mode, and the quoting it needs."""
    proc = run_with(result=_record(OK_NO_CHANGE), fixture='odd"name.json')

    assert proc.returncode == 0, proc.stderr
    assert 'loading one fixture: odd"name.json' in proc.stdout
    assert json.loads(_payload_of(proc)) == {"fixture": 'odd"name.json'}
    assert "openforge-catalog-fixtures" in _invoke(proc)


def test_an_empty_fixture_means_everything(run_with):
    """Which is what a deploy passes."""
    proc = run_with(result=_record(OK_NO_CHANGE), fixture="")

    assert proc.returncode == 0, proc.stderr
    assert "loading every fixture" in proc.stdout
    assert json.loads(_payload_of(proc)) == {}
