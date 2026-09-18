"""db_url builds the connection string from the environment.

The password may come from PGPASSWORD or, on Lambda, from the RDS-managed
secret named by DB_SECRET_ARN.
"""

import json

from openforge.db import db_url


class FakeSecretsManager:
    def __init__(self, password):
        self.password = password
        self.requested = []

    def get_secret_value(self, SecretId):
        self.requested.append(SecretId)
        body = {"username": "openforge", "password": self.password}
        return {"SecretString": json.dumps(body)}


def _fake_boto3(monkeypatch, client):
    import boto3

    monkeypatch.setattr(boto3, "client", lambda service, **kwargs: client)


def test_db_secret_arn_supplies_the_password(monkeypatch):
    client = FakeSecretsManager("from-secret")
    _fake_boto3(monkeypatch, client)

    arn = "arn:aws:secretsmanager:us-east-1:1:secret:x"
    url = db_url({"DB_SECRET_ARN": arn, "PGHOST": "db"})

    assert url == "postgresql://openforge:from-secret@db:5432/openforge"
    assert client.requested == [arn]


def test_pgpassword_wins_over_db_secret_arn(monkeypatch):
    client = FakeSecretsManager("from-secret")
    _fake_boto3(monkeypatch, client)

    url = db_url({"PGPASSWORD": "from-env", "DB_SECRET_ARN": "arn:whatever"})

    assert "from-env@" in url
    assert client.requested == []


def test_without_either_the_default_password_is_used():
    assert db_url({}) == "postgresql://openforge:openforge@localhost:5432/openforge"


def test_password_is_percent_encoded_for_libpq():
    url = db_url({"PGPASSWORD": "a%41b@c/d"})

    assert url == "postgresql://openforge:a%2541b%40c%2Fd@localhost:5432/openforge"
