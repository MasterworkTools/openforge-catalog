"""The app's runtime secret fetch.

The Lambda is given an ARN rather than the values, so these cover the
three states that matter: no ARN at all, which is local development and
the tests; the secret supplying a value; and an explicit variable
winning over the secret.
"""

import json
from unittest.mock import MagicMock, patch

from openforge.app import _app_secret, _setting


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
