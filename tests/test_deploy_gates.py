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
def jobs(request):
    with open(WORKFLOWS / f"{request.param}.yaml") as f:
        return yaml.safe_load(f)["jobs"]


def test_every_step_is_gated_on_the_one_before_it(jobs):
    for earlier, later in zip(CHAIN, CHAIN[1:]):
        job = jobs[later]
        needs = job["needs"]
        assert needs == earlier or earlier in needs, f"{later} does not need {earlier}"
        # `needs` alone still runs the job when its dependency was skipped.
        assert f"needs.{earlier}.result == 'success'" in job["if"]


def test_the_first_apply_creates_everything_the_load_needs(jobs):
    """`-target` walks dependencies, not dependents.

    The second apply is gated on the load succeeding, so anything the load
    step touches that the first apply does not create cannot be created at
    all: the load fails, the apply is skipped, and re-running the failed jobs
    re-fails because the apply that would fix it is behind the gate.
    """
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
    tf = (
        Path(__file__).resolve().parents[1] / "terraform/environments/staging/main.tf"
    ).read_text()
    marker = 'resource "aws_lambda_function_event_invoke_config" "fixtures"'
    config = tf.split(marker, 1)[1].split("\nresource ", 1)[0]
    assert "aws_sqs_queue.fixtures_result" in config
    assert "aws_iam_role_policy.fixtures_result" in config


def test_the_two_environments_run_the_same_chain():
    graphs = []
    for env in ("staging", "production"):
        with open(WORKFLOWS / f"{env}.yaml") as f:
            jobs = yaml.safe_load(f)["jobs"]
        graphs.append({k: (v.get("needs"), v.get("if")) for k, v in jobs.items()})

    assert graphs[0] == graphs[1]
