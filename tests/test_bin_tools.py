"""The two `bin/` database tools set the `openforge.db` log level.

They are extensionless click scripts, so they are loaded by path rather than
imported.
"""

import importlib.machinery
import importlib.util
import logging
import os
from pathlib import Path

from click.testing import CliRunner

BIN = Path(__file__).resolve().parent.parent / "bin"


def _load(name):
    loader = importlib.machinery.SourceFileLoader(f"bin_{name}", str(BIN / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_db_update_sets_the_db_log_level(test_db, monkeypatch):
    monkeypatch.setitem(os.environ, "LOG_LEVEL", "WARNING")
    logging.getLogger("openforge.db").setLevel(logging.NOTSET)

    result = CliRunner().invoke(_load("db_update").cli, ["version"], obj={})

    assert result.exit_code == 0, result.output
    assert logging.getLogger("openforge.db").level == logging.WARNING


def test_fixtures_sets_the_db_log_level(test_db, monkeypatch):
    """Invoked with a fixture that does not exist, so it loads nothing."""
    monkeypatch.setitem(os.environ, "LOG_LEVEL", "WARNING")
    logging.getLogger("openforge.db").setLevel(logging.NOTSET)

    result = CliRunner().invoke(
        _load("fixtures").main, ["--fixture", "no-such-fixture.json"]
    )

    assert isinstance(result.exception, SystemExit)
    assert result.exit_code == 1
    assert "not found in fixtures directory" in result.output
    assert logging.getLogger("openforge.db").level == logging.WARNING
