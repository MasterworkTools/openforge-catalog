"""Tests for openforge.thingiverse.cli (tv_auth command surface)."""

import logging

import pytest
from click.testing import CliRunner

import openforge.thingiverse.cli as cli_mod
from openforge.thingiverse.auth import (
    NotLoggedIn,
    ThingiverseAuthError,
    TwoFactorRequired,
)
from openforge.thingiverse.cli import _configure_logging, cli


class FakeManager:
    """Scriptable TokenManager stand-in recording CLI-driven calls."""

    def __init__(
        self,
        login_effect=None,
        whoami_result=None,
        whoami_effect=None,
        logged_in=True,
    ):
        self.login_effect = login_effect
        self.whoami_result = whoami_result or {"id": 42, "name": "devonjones"}
        self.whoami_effect = whoami_effect
        self.logged_in = logged_in
        self.calls = []
        self.token_file = "/fake/tokens.json"

    def login(self, username, password):
        self.calls.append(("login", username, password))
        if self.login_effect:
            raise self.login_effect

    def login_2fa(self, code):
        self.calls.append(("login_2fa", code))

    def whoami(self):
        self.calls.append(("whoami",))
        if self.whoami_effect:
            raise self.whoami_effect
        return self.whoami_result

    def is_logged_in(self):
        return self.logged_in

    def logout(self):
        self.calls.append(("logout",))


@pytest.fixture
def runner():
    return CliRunner()


def install(monkeypatch, manager):
    """Patch the CLI's TokenManager at point of use."""
    monkeypatch.setattr(cli_mod, "TokenManager", lambda: manager)
    return manager


class TestConfigureLogging:
    @pytest.mark.parametrize(
        "verbose,quiet,expected",
        [
            (0, False, logging.WARNING),
            (1, False, logging.INFO),
            (2, False, logging.DEBUG),
            (5, False, logging.DEBUG),  # clamps, never below DEBUG
            (0, True, logging.ERROR),
            (3, True, logging.ERROR),  # quiet wins over -v
        ],
    )
    def test_level_ladder(self, monkeypatch, verbose, quiet, expected):
        captured = {}
        monkeypatch.setattr(
            cli_mod.logging,
            "basicConfig",
            lambda **kwargs: captured.update(kwargs),
        )
        _configure_logging(verbose, quiet)
        assert captured["level"] == expected


class TestLogin:
    def test_login_success(self, runner, monkeypatch):
        manager = install(monkeypatch, FakeManager())

        result = runner.invoke(cli, ["login"], input="devon@example.com\nhunter2\n")

        assert result.exit_code == 0
        assert "Logged in as devonjones (id 42)" in result.output
        assert ("login", "devon@example.com", "hunter2") in manager.calls

    def test_login_2fa_flow_prompts_for_code(self, runner, monkeypatch):
        manager = install(
            monkeypatch, FakeManager(login_effect=TwoFactorRequired("2FA"))
        )

        result = runner.invoke(cli, ["login"], input="devon\nhunter2\n123456\n")

        assert result.exit_code == 0
        assert ("login_2fa", "123456") in manager.calls
        assert "Logged in as devonjones" in result.output

    def test_login_bad_credentials_fails_cleanly(self, runner, monkeypatch):
        install(
            monkeypatch,
            FakeManager(login_effect=ThingiverseAuthError("login failed: HTTP 401")),
        )

        result = runner.invoke(cli, ["login"], input="devon\nwrong\n")

        assert result.exit_code != 0
        assert "login failed: HTTP 401" in result.output

    def test_login_password_not_echoed(self, runner, monkeypatch):
        install(monkeypatch, FakeManager())

        result = runner.invoke(cli, ["login"], input="devon\nhunter2\n")

        assert "hunter2" not in result.output


class TestStatus:
    def test_status_logged_in(self, runner, monkeypatch):
        install(monkeypatch, FakeManager())

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Logged in as devonjones (id 42)" in result.output

    def test_status_not_logged_in_exits_1(self, runner, monkeypatch):
        install(monkeypatch, FakeManager(logged_in=False))

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 1
        assert "Not logged in." in result.output

    def test_status_unusable_tokens_exits_1(self, runner, monkeypatch):
        install(
            monkeypatch,
            FakeManager(whoami_effect=NotLoggedIn("refresh token rejected")),
        )

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 1
        assert "Tokens stored but unusable" in result.output

    def test_status_api_error_fails(self, runner, monkeypatch):
        install(
            monkeypatch,
            FakeManager(whoami_effect=ThingiverseAuthError("HTTP 500")),
        )

        result = runner.invoke(cli, ["status"])

        assert result.exit_code != 0
        assert "HTTP 500" in result.output


class TestLogout:
    def test_logout(self, runner, monkeypatch):
        manager = install(monkeypatch, FakeManager())

        result = runner.invoke(cli, ["logout"])

        assert result.exit_code == 0
        assert "Logged out" in result.output
        assert ("logout",) in manager.calls
