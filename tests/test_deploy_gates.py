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


def test_the_two_environments_run_the_same_chain():
    graphs = []
    for env in ("staging", "production"):
        with open(WORKFLOWS / f"{env}.yaml") as f:
            jobs = yaml.safe_load(f)["jobs"]
        graphs.append({k: (v.get("needs"), v.get("if")) for k, v in jobs.items()})

    assert graphs[0] == graphs[1]
