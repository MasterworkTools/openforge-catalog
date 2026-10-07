"""The invoke-and-verify script both deploys and the manual re-run share.

The load is invoked asynchronously and reports through an SQS queue, so the
script's job is to drain whatever was there before, invoke, wait, and read the
one record that belongs to *its* invoke. Each of those has a way of passing a
failure off as a success, which is what these tests hold.

`aws` is stubbed by a script that records every call and answers from a spec
file. The stub models the two SQS behaviours that matter: a short poll may
answer empty although the queue is not, and a record is identified by the
nonce the invoke carried.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / ".github/scripts/load-fixtures.sh"

STUB = """#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
spec = json.load(open(os.environ["STUB_SPEC"]))
with open("calls.jsonl", "a") as fh:
    fh.write(json.dumps(args) + "\\n")


def arg(name, default=None):
    return args[args.index(name) + 1] if name in args else default


def save():
    with open(os.environ["STUB_SPEC"], "w") as fh:
        json.dump(spec, fh)


if args[:2] == ["sqs", "get-queue-url"]:
    # The queue the script asks for is part of the contract, so it is checked
    # rather than ignored.
    if arg("--queue-name") != spec["queue_name"]:
        sys.exit(f"no such queue: {arg('--queue-name')}")
    print("https://sqs.example/q")

elif args[:2] == ["sqs", "receive-message"]:
    # A drain reads a batch; the wait reads one. Discriminated on that rather
    # than on the wait, so that adding a wait to the drain does not change
    # which branch a call takes.
    draining = arg("--max-number-of-messages") == "10"
    if draining and spec.get("short_poll_misses"):
        # What a short poll does: answer empty although a record is there.
        spec["short_poll_misses"] -= 1
        save()
        print("")
        sys.exit(0)
    pending = spec["queue"]
    if pending:
        body = pending.pop(0)
        # The sentinel stands for "this invoke's nonce", which only the stub
        # knows, because the script generates it.
        if (body.get("requestPayload") or {}).get("nonce") == "MATCH":
            body["requestPayload"]["nonce"] = spec.get("nonce")
        save()
        print(json.dumps({"Messages": [
            {"ReceiptHandle": "rh", "Body": json.dumps(body)}
        ]}))
    else:
        print("")

elif args[:2] == ["sqs", "delete-message"]:
    pass

elif args[:2] == ["lambda", "invoke"]:
    # The result only exists once the load has been asked for, which is what
    # lets one queue model both a leftover record and this load's.
    spec["queue"] = spec["queue"] + spec.pop("on_invoke", [])
    # Everything the real CLI needs, so dropping any of it is a failing test
    # rather than a broken deploy.
    assert arg("--function-name") == spec["function"], "wrong function"
    assert arg("--invocation-type") == "Event", "not an async invoke"
    assert arg("--cli-binary-format") == "raw-in-base64-out", "payload would be decoded"
    assert args[-1] == "/dev/null", "invoke needs an output path"
    sent = json.loads(arg("--payload"))
    spec["nonce"] = sent.get("nonce")
    save()
    print(json.dumps(spec.get("ack", {"StatusCode": 202})))

else:
    sys.exit(f"unexpected aws call: {args}")
"""


def _record(payload, condition="Success", function_error=None, nonce="MATCH"):
    """A Lambda async destination record, in a shape Lambda can deliver.

    A function error is never delivered with `condition: Success` — the
    on-success destination fires only on success — so asking for one moves the
    condition too.
    """
    response_context = {"statusCode": 200, "executedVersion": "$LATEST"}
    if function_error:
        response_context["functionError"] = function_error
        if condition == "Success":
            condition = "RetriesExhausted"
    return {
        "version": "1.0",
        "requestContext": {
            "requestId": "req-1",
            "condition": condition,
            "approximateInvokeCount": 1,
        },
        # "MATCH" is replaced with the nonce the script actually sent.
        "requestPayload": {"nonce": nonce},
        "responseContext": response_context,
        "responsePayload": payload,
    }


OK_NO_CHANGE = {"ok": True, "files": 45, "blueprints_changed": False, "applied": []}


@pytest.fixture
def run_with(tmp_path):
    """Run the script against a canned queue and invoke result."""

    def run(
        result=None,
        stale=None,
        ack=None,
        fixture=None,
        deadline="2",
        short_poll_misses=0,
        function="openforge-catalog-fixtures",
    ):
        spec = {
            "queue": stale or [],
            "on_invoke": [result] if result else [],
            "queue_name": f"{function}-result",
            "function": function,
            "short_poll_misses": short_poll_misses,
        }
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
        proc.nonce = json.loads(spec_path.read_text()).get("nonce")
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
    args = _invoke(proc)
    assert args[args.index("--invocation-type") + 1] == "Event"
    # And the record is deleted once read, or it reappears when its
    # visibility timeout lapses and the next run has to skip it.
    assert [c[1] for c in proc.calls].count("delete-message") == 1


def test_a_raise_is_read_off_the_record(run_with):
    """The handler's failures arrive as a record, not as a call that errored.

    This is the answerable-path failure, which is the one worth gating on, at
    the shape Lambda really delivers it: a non-Success condition carrying the
    error payload.
    """
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

    Lambda expires the event and delivers `EventAgeExceeded`, which is what
    `maximum_event_age_in_seconds` exists to produce. The payload here is a
    healthy one on purpose: the condition is what decides, and a record whose
    payload reads fine must still be refused when Lambda says it did not
    succeed.
    """
    proc = run_with(result=_record(OK_NO_CHANGE, condition="EventAgeExceeded"))

    assert proc.returncode != 0
    assert "EventAgeExceeded" in proc.stdout + proc.stderr


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
    # It did not go on to wait: the invoke is the last thing it did.
    assert [c[:2] for c in proc.calls][-1] == ["lambda", "invoke"]


def test_no_result_before_the_deadline_fails_and_warns_about_re_running(run_with):
    """The load may still hold the one concurrency slot there is."""
    proc = run_with(result=None, deadline="1")

    assert proc.returncode != 0
    assert "no result after" in proc.stdout + proc.stderr
    assert "still be running" in proc.stdout + proc.stderr


def test_a_stale_record_is_discarded_before_the_invoke(run_with):
    """Otherwise a previous load's record costs this one a full wait."""
    proc = run_with(result=_record(OK_NO_CHANGE), stale=[_record(OK_NO_CHANGE)])

    assert proc.returncode == 0, proc.stderr
    assert "discarding a stale result record" in proc.stdout
    kinds = [c[1] for c in proc.calls]
    assert kinds.index("delete-message") < kinds.index("invoke")


def test_the_drain_survives_a_short_polls_false_empty_answer(run_with):
    """A short poll samples a subset of servers and can answer empty.

    So the drain long-polls. With a short poll the stale record here outlives
    the drain, and the wait then reads a record from a load it never
    invoked — which is why the nonce check exists as well.
    """
    proc = run_with(
        result=_record(OK_NO_CHANGE),
        stale=[_record(OK_NO_CHANGE)],
        short_poll_misses=1,
    )

    assert proc.returncode == 0, proc.stderr
    drains = [c for c in proc.calls if c[1] == "receive-message" and "10" in c]
    assert drains, proc.calls
    assert all("--wait-time-seconds" in c for c in drains)


def test_another_runs_record_is_left_alone_rather_than_consumed(run_with):
    """The nonce is the only way to tell two loads' records apart.

    An Event invoke returns a status and no request id, so without this a
    collision's expiry record fails the healthy run. Not deleted either: its
    visibility timeout has to return it to whoever is waiting for it.
    """
    proc = run_with(result=_record(OK_NO_CHANGE, nonce="someone-else"), deadline="1")

    assert proc.returncode != 0
    assert "another run" in proc.stdout
    assert "no result after" in proc.stdout + proc.stderr
    assert "delete-message" not in [c[1] for c in proc.calls]


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
    sent = json.loads(_payload_of(proc))
    assert sent["fixture"] == 'odd"name.json'
    assert sent["nonce"] == proc.nonce


def test_an_empty_fixture_means_everything(run_with):
    """Which is what a deploy passes."""
    proc = run_with(result=_record(OK_NO_CHANGE), fixture="")

    assert proc.returncode == 0, proc.stderr
    assert "loading every fixture" in proc.stdout
    # The nonce travels even here; the handler ignores the key.
    assert json.loads(_payload_of(proc)) == {"nonce": proc.nonce}


def test_the_queue_and_the_deadline_match_the_infrastructure():
    """Two couplings the script cannot see, and nothing else holds.

    The script composes the queue name from the function name; terraform
    composes it from the deployment name. They agree only by spelling. And
    the script's default wait has to exceed the function's own ceiling plus
    the event's maximum age, or a load that times out reports nothing.
    """
    script = SCRIPT.read_text()
    tf = (REPO / "terraform/environments/production/main.tf").read_text()

    function = script.split('FUNCTION="${FUNCTION:-', 1)[1].split("}", 1)[0]
    assert 'name = "${local.name}-fixtures-result"' in tf
    assert function == "openforge-catalog-fixtures"
    assert 'name  = "openforge-catalog"' in tf

    deadline = int(script.split("DEADLINE_SECONDS:-", 1)[1].split("}", 1)[0])
    timeout = int(tf.split("timeout     = ", 1)[1].split("\n", 1)[0])
    age = int(tf.split("maximum_event_age_in_seconds = ", 1)[1].split("\n", 1)[0])
    assert deadline > timeout + age, (deadline, timeout, age)
