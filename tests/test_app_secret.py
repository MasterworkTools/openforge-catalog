"""The app's runtime secret fetch.

The Lambda is given an ARN rather than the values, so these cover the
three states that matter: no ARN at all, which is local development and
the tests; the secret supplying a value; and an explicit variable
winning over the secret.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from openforge.app import FROM_SECRET, _app_secret, _setting, init_app


def test_no_arn_fetches_nothing(monkeypatch):
    """Local development and the test suite never reach AWS."""
    monkeypatch.delenv("APP_SECRET_ARN", raising=False)

    with patch("boto3.client") as client:
        assert _app_secret() == {}

    client.assert_not_called()


def test_an_arn_is_read_once_from_secrets_manager(monkeypatch):
    monkeypatch.setenv("APP_SECRET_ARN", "arn:aws:secretsmanager:::secret:app")
    payload = {"API_TOKEN": "from-secret", "SECRET_KEY": "k"}
    fake = MagicMock()
    fake.get_secret_value.return_value = {"SecretString": json.dumps(payload)}

    with patch("boto3.client", return_value=fake) as client:
        assert _app_secret() == payload

    client.assert_called_once()
    fake.get_secret_value.assert_called_once_with(
        SecretId="arn:aws:secretsmanager:::secret:app"
    )


def test_the_fetch_fails_fast_rather_than_outlasting_the_function(monkeypatch):
    """botocore's default connect timeout outlives the Lambda, so a VPC
    with no route to Secrets Manager would surface as something else."""
    monkeypatch.setenv("APP_SECRET_ARN", "arn:aws:secretsmanager:::secret:app")
    fake = MagicMock()
    fake.get_secret_value.return_value = {"SecretString": "{}"}

    with patch("boto3.client", return_value=fake) as client:
        _app_secret()

    config = client.call_args.kwargs["config"]
    assert config.connect_timeout == 3
    assert config.retries["max_attempts"] == 2


def test_the_environment_wins_over_the_secret(monkeypatch):
    """Local development sets the plain variable and must keep working
    unchanged once the Lambda is reading from a secret."""
    monkeypatch.setenv("API_TOKEN", "from-env")

    assert _setting("API_TOKEN", {"API_TOKEN": "from-secret"}) == "from-env"


def test_the_secret_supplies_what_the_environment_does_not(monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)

    assert _setting("API_TOKEN", {"API_TOKEN": "from-secret"}) == "from-secret"


def test_the_default_is_the_last_resort(monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)

    assert _setting("API_TOKEN", {}, "fallback") == "fallback"


def test_an_empty_value_in_the_secret_is_not_a_value(monkeypatch):
    """So the guard's truth test catches an empty value as well as an
    absent one, and the resolver still reaches the default."""
    monkeypatch.delenv("API_TOKEN", raising=False)

    assert _setting("API_TOKEN", {"API_TOKEN": ""}, "fallback") == "fallback"
    assert _setting("API_TOKEN", {"API_TOKEN": ""}) is None


def test_every_value_the_lambda_needs_is_required_from_the_secret():
    """The five the Lambda cannot start without. API_TOKEN carries a
    development default, so a secret missing it would otherwise serve
    `1234567890` to the internet rather than fail."""
    assert set(FROM_SECRET) == {
        "API_TOKEN",
        "SECRET_KEY",
        "CLOUDFLARE_ENDPOINT",
        "CLOUDFLARE_ACCESS_KEY_ID",
        "CLOUDFLARE_SECRET_ACCESS_KEY",
    }


def test_an_incomplete_secret_does_not_fall_back_to_the_default_token(monkeypatch):
    """The default is for a developer with no ARN, never for a Lambda
    whose secret came back short."""
    monkeypatch.setenv("APP_SECRET_ARN", "arn:aws:secretsmanager:::secret:app")
    for name in FROM_SECRET:
        monkeypatch.delenv(name, raising=False)

    assert _setting("API_TOKEN", {"SECRET_KEY": "k"}) is None
    assert _setting("API_TOKEN", {"SECRET_KEY": "k"}, "1234567890") == "1234567890"

    # So the guard, not the resolver, is what has to catch it.
    missing = [n for n in FROM_SECRET if not _setting(n, {"SECRET_KEY": "k"})]
    assert "API_TOKEN" in missing


def test_init_app_refuses_to_start_on_an_incomplete_secret(monkeypatch):
    """Through `init_app`, not through the pieces: the guard is what
    stands between a short secret and a Lambda serving the development
    token. It raises before the connection pool, so no database is
    needed here.
    """
    monkeypatch.setenv("APP_SECRET_ARN", "arn:aws:secretsmanager:::secret:app")
    for name in FROM_SECRET:
        monkeypatch.delenv(name, raising=False)

    # Absent and present-but-empty both have to count as missing.
    short = {"SECRET_KEY": "k", "CLOUDFLARE_ENDPOINT": ""}
    with (
        patch("openforge.app.load_dotenv"),
        patch("openforge.app._app_secret", return_value=short),
    ):
        with pytest.raises(ValueError) as caught:
            init_app(Flask(__name__))

    message = str(caught.value)
    assert "API_TOKEN" in message
    assert "CLOUDFLARE_ACCESS_KEY_ID" in message
    assert "CLOUDFLARE_ENDPOINT" in message
    # The one the short secret does carry must not be named.
    assert "SECRET_KEY" not in message


def test_init_app_is_happy_when_the_secret_is_complete(monkeypatch):
    """The guard must not fire on a good secret, or every cold start
    fails instead of the bad ones."""
    monkeypatch.setenv("APP_SECRET_ARN", "arn:aws:secretsmanager:::secret:app")
    for name in FROM_SECRET:
        monkeypatch.delenv(name, raising=False)

    whole = {name: f"value-for-{name}" for name in FROM_SECRET}
    app = Flask(__name__)
    app.config["TESTING"] = True
    with (
        patch("openforge.app.load_dotenv"),
        patch("openforge.app._app_secret", return_value=whole),
        patch("openforge.app.PgDB"),
    ):
        init_app(app)

    for name in FROM_SECRET:
        assert app.config[name] == f"value-for-{name}"


def test_a_developer_without_an_arn_is_not_held_to_the_secret(monkeypatch):
    """The guard is for a Lambda reading a secret. Applying it to a
    developer who has set only SECRET_KEY would make the app refuse to
    start locally, which is the thing this change promised not to do.
    """
    monkeypatch.delenv("APP_SECRET_ARN", raising=False)
    for name in FROM_SECRET:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SECRET_KEY", "local-only")

    app = Flask(__name__)
    app.config["TESTING"] = True
    with patch("openforge.app.load_dotenv"), patch("openforge.app.PgDB"):
        init_app(app)

    # No Cloudflare values anywhere, and it still starts.
    assert app.config["CLOUDFLARE_ENDPOINT"] is None
    assert app.config["API_TOKEN"] == "1234567890"
