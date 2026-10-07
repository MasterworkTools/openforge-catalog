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
    if spec.get("receive_failures"):
        # SQS answering 5xx. Not a failed load, and the script must say so.
        spec["receive_failures"] -= 1
        save()
        sys.exit("ServiceUnavailable")
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
        receive_failures=0,
        function="openforge-catalog-fixtures",
    ):
        spec = {
            "queue": stale or [],
            "on_invoke": [result] if result else [],
            "queue_name": f"{function}-result",
            "function": function,
            "receive_failures": receive_failures,
        }
        if ack is not None:
            spec["ack"] = ack
        spec_path = tmp_path / "spec.json"
        spec_path.write_text(json.dumps(spec))

        fake_bin = tmp_path / "bin"
        fake_bin.mkdir(exist_ok=True)
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


def test_a_leftover_record_is_skipped_and_this_loads_result_still_found(run_with):
    """What replaced draining the queue.

    An uncollected record from an earlier run is on the queue before this
    load starts. The wait draws it first, fails the nonce check, leaves it
    where it is, and goes on to find its own — so a leftover costs a poll
    rather than a wrong verdict. The stub does not redeliver the skipped
    record, which stands for its visibility timeout not having lapsed yet.
    """
    proc = run_with(
        result=_record(OK_NO_CHANGE),
        stale=[_record(OK_NO_CHANGE, nonce="an-earlier-run")],
    )

    assert proc.returncode == 0, proc.stderr
    assert "a record from another run" in proc.stdout
    assert "no blueprint changes" in proc.stdout
    # Only this load's record is consumed; the other is left for its owner.
    assert [c[1] for c in proc.calls].count("delete-message") == 1


def test_only_another_runs_record_fails_rather_than_being_consumed(run_with):
    """The nonce is the only way to tell two loads' records apart.

    An Event invoke returns a status and no request id, so without this a
    collision's expiry record would fail the healthy run. The record is not
    deleted either: its visibility timeout has to return it to whoever is
    waiting for it.
    """
    proc = run_with(result=_record(OK_NO_CHANGE, nonce="someone-else"), deadline="1")

    assert proc.returncode != 0
    assert "a record from another run" in proc.stdout
    assert "no result after" in proc.stdout + proc.stderr
    assert "delete-message" not in [c[1] for c in proc.calls]


def test_a_failed_receive_is_retried_rather_than_failing_the_load(run_with):
    """One SQS error is not a failed load.

    Aborting here would reintroduce the fragility this script exists to
    remove, and with one chance per poll rather than one for the whole load
    it would be worse than what it replaced.
    """
    proc = run_with(result=_record(OK_NO_CHANGE), receive_failures=1, deadline="60")

    assert proc.returncode == 0, proc.stderr
    assert "receive failed; retrying" in proc.stdout
    assert "no blueprint changes" in proc.stdout


def test_each_run_sends_a_different_nonce(run_with):
    """A run-scoped value is not enough, and is the plausible wrong edit.

    Anything derived from the commit — the sha, say — is identical for the
    staging and production deploys of one release, which is exactly the pair
    the correlation exists to separate.
    """
    first = run_with(result=_record(OK_NO_CHANGE))
    second = run_with(result=_record(OK_NO_CHANGE))

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first.nonce and second.nonce
    assert first.nonce != second.nonce


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


def _blocks(env):
    """The fixture-load blocks of one environment's terraform, by name."""
    tf = (REPO / f"terraform/environments/{env}/main.tf").read_text()
    out = {}
    for head in (
        'resource "aws_sqs_queue" "fixtures_result"',
        'resource "aws_lambda_function_event_invoke_config" "fixtures"',
        'resource "aws_lambda_function" "fixtures"',
        'resource "aws_iam_role_policy" "fixtures_result"',
    ):
        assert head in tf, (env, head)
        out[head] = tf.split(head, 1)[1].split("\n}\n", 1)[0]
    return out


def _number(block, key):
    """A terraform numeric attribute, whatever `fmt` did to the spacing."""
    line = next(line for line in block.splitlines() if line.strip().startswith(key))
    return int(line.split("=", 1)[1].strip())


def test_the_two_environments_configure_the_load_identically():
    """Otherwise a value held in one is unheld in the other.

    These four blocks are byte-identical today and there is no reason for
    them to diverge, so comparing them is what stops a production-only edit
    going unnoticed by every test that reads staging.
    """
    assert _blocks("staging") == _blocks("production")


def test_the_queue_and_the_deadline_match_the_infrastructure():
    """Couplings the script cannot see, and nothing else holds.

    The script composes the queue name from the function name; terraform
    composes it from the deployment name, so they agree only by spelling.
    The script's default wait has to exceed the function's own ceiling plus
    the event's maximum age, or a load that times out reports nothing. And a
    record left for another run has to become visible again well inside a
    load, or its owner never sees it.

    Every number is read out of the block it belongs to. Searching the file
    finds the migration function's ceiling first, which is the same value
    today and would pass for the wrong reason.
    """
    script = SCRIPT.read_text()
    blocks = _blocks("production")
    function_block = blocks['resource "aws_lambda_function" "fixtures"']
    config_block = blocks[
        'resource "aws_lambda_function_event_invoke_config" "fixtures"'
    ]
    queue_block = blocks['resource "aws_sqs_queue" "fixtures_result"']

    name = script.split('FUNCTION="${FUNCTION:-', 1)[1].split("}", 1)[0]
    assert name == "openforge-catalog-fixtures"
    assert 'name = "${local.name}-fixtures-result"' in queue_block
    assert (
        'name  = "openforge-catalog"'
        in (REPO / "terraform/environments/production/main.tf").read_text()
    )

    deadline = int(script.split("DEADLINE_SECONDS:-", 1)[1].split("}", 1)[0])
    timeout = _number(function_block, "timeout")
    age = _number(config_block, "maximum_event_age_in_seconds")
    retention = _number(queue_block, "message_retention_seconds")
    visibility = _number(queue_block, "visibility_timeout_seconds")

    assert deadline > timeout + age, (deadline, timeout, age)
    assert retention > timeout + age, (retention, timeout, age)
    assert visibility < timeout, (visibility, timeout)

    # Not bounds but outright requirements, and an identical edit to both
    # environments would slip past comparing them with each other.
    assert _number(config_block, "maximum_retry_attempts") == 0
    assert "function_name = aws_lambda_function.fixtures.function_name" in (
        config_block.replace("  ", " ")
    )
    assert 'function_name = "${local.name}-fixtures"' in (
        function_block.replace("  ", " ")
    )
