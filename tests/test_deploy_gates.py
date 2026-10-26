"""The job graph both deploy workflows rely on, asserted rather than stated.

Nothing promotes the API image or the frontend unless the migration and the
fixture load both succeeded. That invariant is what makes a schema change
expand/contract rather than a coin flip, and it lives in the `needs` and `if`
of two YAML files where a one-word edit retargets it silently.
"""

from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github/workflows"

# Each step gated on the one before it, in the order a release runs.
CHAIN = [
    "docker-build",
    "tofu-apply-migrate",
    "migrate",
    "load-fixtures",
    "tofu-apply",
    "frontend-deploy",
]


@pytest.fixture(params=["staging", "production"])
def env(request):
    """An environment's name and its deploy workflow's jobs."""
    with open(WORKFLOWS / f"{request.param}.yaml") as f:
        return request.param, yaml.safe_load(f)["jobs"]


def test_every_step_is_gated_on_the_one_before_it(env):
    _, jobs = env
    for earlier, later in zip(CHAIN, CHAIN[1:]):
        job = jobs[later]
        needs = job["needs"]
        assert needs == earlier or earlier in needs, f"{later} does not need {earlier}"
        # `needs` alone still runs the job when its dependency was skipped.
        assert f"needs.{earlier}.result == 'success'" in job["if"]


def test_the_first_apply_creates_everything_the_load_needs(env):
    """`-target` walks dependencies, not dependents.

    The second apply is gated on the load succeeding, so anything the load
    step touches that the first apply does not create cannot be created at
    all: the load fails, the apply is skipped, and re-running the failed jobs
    re-fails because the apply that would fix it is behind the gate.
    """
    name, jobs = env
    step = next(
        s
        for s in jobs["tofu-apply-migrate"]["steps"]
        if "-target=" in str(s.get("run", ""))
    )
    targeted = {
        line.split("-target=", 1)[1].strip().rstrip("\\").strip()
        for line in step["run"].splitlines()
        if "-target=" in line
    }

    # Everything the load's own invoke depends on existing.
    assert "aws_lambda_function.fixtures" in targeted
    assert "aws_lambda_function_event_invoke_config.fixtures" in targeted
    # The queue and the send grant are dependencies of that config, so
    # -target pulls them in; this fails if that stops being true.
    root = Path(__file__).resolve().parents[1] / "terraform/environments"
    tf = (root / name / "main.tf").read_text()
    marker = 'resource "aws_lambda_function_event_invoke_config" "fixtures"'
    # Stop at the block's own closing brace. Stopping at the next `resource`
    # runs on into the policy document beside it, which names the queue too,
    # so the queue assertion would pass with the destination removed.
    config = tf.split(marker, 1)[1].split("\n}\n", 1)[0]
    assert "aws_sqs_queue.fixtures_result" in config
    assert "aws_iam_role_policy.fixtures_result" in config


def test_the_job_cap_is_above_the_wait_it_backs(env):
    """The cap is a backstop, so it has to be above what it backs.

    The script gives up first and says the load may still be running. Below
    its deadline the job is killed mid-wait instead, with nothing said about
    why — and the release strands on a load that may have succeeded.
    """
    _, jobs = env
    script = (
        Path(__file__).resolve().parents[1] / ".github/scripts/load-fixtures.sh"
    ).read_text()
    deadline = int(script.split("DEADLINE_SECONDS:-", 1)[1].split("}", 1)[0])

    cap = jobs["load-fixtures"]["timeout-minutes"] * 60
    assert cap > deadline, (cap, deadline)


def test_the_manual_workflow_caps_itself_the_same_way():
    """It runs the same script, so it needs the same headroom."""
    with open(WORKFLOWS / "load-fixtures.yaml") as f:
        jobs = yaml.safe_load(f)["jobs"]
    script = (
        Path(__file__).resolve().parents[1] / ".github/scripts/load-fixtures.sh"
    ).read_text()
    deadline = int(script.split("DEADLINE_SECONDS:-", 1)[1].split("}", 1)[0])

    assert jobs, "no jobs in the manual workflow"
    for name, job in jobs.items():
        assert job["timeout-minutes"] * 60 > deadline, (name, job["timeout-minutes"])


def test_the_two_environments_run_the_same_chain():
    graphs = []
    for env in ("staging", "production"):
        with open(WORKFLOWS / f"{env}.yaml") as f:
            jobs = yaml.safe_load(f)["jobs"]
        graphs.append({k: (v.get("needs"), v.get("if")) for k, v in jobs.items()})

    assert graphs[0] == graphs[1]
