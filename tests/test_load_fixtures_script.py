"""The invoke-and-verify script both deploys and the manual re-run share.

`aws lambda invoke` exits 0 for a function that raised, so the metadata has to
be read or a failed load passes as a success. That check is the only thing
standing between a broken load and a green release, and it used to be inlined
in three workflows — three chances to get it right in only two.

The tests stub `aws` with a script that writes canned files, which is the
whole of what the real one contributes here.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/load-fixtures.sh"


@pytest.fixture
def run_with(tmp_path):
    """Run the script against a canned invoke result."""

    def run(metadata, payload, fixture=None):
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        (fake_bin / "aws").write_text(
            "#!/usr/bin/env bash\n"
            # Recorded, because the payload the script builds is the half of
            # the contract a stub that ignores "$@" cannot check.
            'printf "%s\\n" "$@" > args.txt\n'
            f"cat > response.json <<'EOF'\n{json.dumps(payload)}\nEOF\n"
            f"cat <<'EOF'\n{json.dumps(metadata)}\nEOF\n"
        )
        (fake_bin / "aws").chmod(0o755)

        env = dict(os.environ, PATH=f"{fake_bin}:{os.environ['PATH']}")
        if fixture is not None:
            env["FIXTURE"] = fixture
        else:
            env.pop("FIXTURE", None)

        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
        )
        args_file = tmp_path / "args.txt"
        result.aws_args = (
            args_file.read_text().split("\n") if args_file.exists() else []
        )
        return result

    return run


def _payload_of(result):
    """The argument the script handed to `--payload`."""
    args = result.aws_args
    return args[args.index("--payload") + 1]


OK_NO_CHANGE = {"ok": True, "files": 45, "blueprints_changed": False, "applied": []}


def test_a_healthy_no_op_passes(run_with):
    """The common case: a release that carried no data change."""
    result = run_with({"StatusCode": 200}, OK_NO_CHANGE)

    assert result.returncode == 0, result.stderr
    assert "no blueprint changes" in result.stdout
    # Without this the CLI imposes a 60 s read timeout on a load measured in
    # minutes, and the deploy fails a load that actually completed.
    assert "--cli-read-timeout" in result.aws_args
    assert result.aws_args[result.aws_args.index("--cli-read-timeout") + 1] == "0"


def test_a_raise_fails_even_though_the_cli_exits_zero(run_with):
    """The reason this check exists at all."""
    result = run_with(
        {"StatusCode": 200, "FunctionError": "Unhandled"},
        {"errorMessage": "3 fixture paths are neither a live row nor listed by one"},
    )

    assert result.returncode != 0
    assert "fixture load failed" in result.stdout + result.stderr


def test_a_payload_that_does_not_report_ok_fails(run_with):
    """Belt to the FunctionError brace: a tidy failure is still a failure."""
    result = run_with({"StatusCode": 200}, {"ok": False})

    assert result.returncode != 0
    assert "did not report ok" in result.stdout + result.stderr


def test_changes_are_named_rather_than_counted(run_with):
    """An operator reading the log should see which fixtures moved."""
    result = run_with(
        {"StatusCode": 200},
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
        },
    )

    assert result.returncode == 0, result.stderr
    assert "bases.json" in result.stdout


def test_a_named_fixture_is_passed_through_as_json(run_with):
    """The manual re-run's single-file mode, and the quoting it needs.

    Asserted on what reached `aws`, not on the script's own echo: a quote in
    the name has to survive into the payload, which is what `json.dumps`
    is there for.
    """
    result = run_with({"StatusCode": 200}, OK_NO_CHANGE, fixture='odd"name.json')

    assert result.returncode == 0, result.stderr
    assert 'loading one fixture: odd"name.json' in result.stdout
    assert json.loads(_payload_of(result)) == {"fixture": 'odd"name.json'}
    assert "openforge-catalog-fixtures" in result.aws_args


def test_an_empty_fixture_means_everything(run_with):
    """Which is what a deploy passes."""
    result = run_with({"StatusCode": 200}, OK_NO_CHANGE, fixture="")

    assert result.returncode == 0, result.stderr
    assert "loading every fixture" in result.stdout
    assert json.loads(_payload_of(result)) == {}
