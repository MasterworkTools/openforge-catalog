import json
import os

from dotenv import load_dotenv
from flask import Flask

from openforge.app.services.session_service import SessionService
from openforge.db import PgDB

#: What the Lambda cannot start without once it reads from a secret.
#: The CLOUDFLARE values are here because their absence is invisible
#: until someone asks for a file, and then it is a 500 rather than a
#: configuration error anyone can see.
FROM_SECRET = (
    "API_TOKEN",
    "SECRET_KEY",
    "CLOUDFLARE_ENDPOINT",
    "CLOUDFLARE_ACCESS_KEY_ID",
    "CLOUDFLARE_SECRET_ACCESS_KEY",
)


def _app_secret() -> dict:
    """The app secret's values, or nothing when none is configured.

    The Lambda is given `APP_SECRET_ARN` rather than the values, so that
    nothing terraform reads at plan time can carry them into state or
    into the function's environment. Fetched once per process, so a
    rotated secret reaches new containers without a redeploy.
    """
    arn = os.environ.get("APP_SECRET_ARN")
    if not arn:
        return {}
    import boto3  # only Lambda sets the ARN; keep the import off the CLI path
    from botocore.config import Config

    # Fail fast for the same reason the database secret does: botocore's
    # default 60 s connect timeout outlasts the function, so a VPC with no
    # route to Secrets Manager would time out as something else.
    fast_fail = Config(connect_timeout=3, retries={"max_attempts": 2})
    client = boto3.client("secretsmanager", config=fast_fail)
    return json.loads(client.get_secret_value(SecretId=arn)["SecretString"])


def _setting(name: str, secret: dict, default=None):
    """A setting from the environment, the app secret, or neither.

    The environment wins, so local development and the tests set the
    plain variables and never reach AWS.
    """
    return os.environ.get(name) or secret.get(name) or default


def init_app(app: Flask):
    load_dotenv()

    # Before the pool, so a failed fetch does not build one per retry:
    # `_initialized` is only set once this returns, so every request
    # would come back here and make another.
    secret = _app_secret()

    def setting(name, default=None):
        return _setting(name, secret, default)

    # A secret in use has to carry everything. Terraform used to fail
    # its plan on a missing key; nothing would now, and API_TOKEN has a
    # development default that would otherwise be served to the
    # internet.
    if os.environ.get("APP_SECRET_ARN"):
        missing = [name for name in FROM_SECRET if not setting(name)]
        if missing:
            raise ValueError(f"app secret is missing: {', '.join(missing)}")

    # Use pool-less mode for testing to avoid logging errors during cleanup
    use_pool = not app.config.get("TESTING", False)
    db = PgDB(os.environ, app.logger, use_pool=use_pool)
    app.config["API_TOKEN"] = setting("API_TOKEN", "1234567890")
    app.config["SECRET_KEY"] = setting("SECRET_KEY")
    if not app.config["SECRET_KEY"]:
        raise ValueError("SECRET_KEY not configured.")
    app.config["CLOUDFLARE_ENDPOINT"] = setting("CLOUDFLARE_ENDPOINT")
    app.config["CLOUDFLARE_ACCESS_KEY_ID"] = setting("CLOUDFLARE_ACCESS_KEY_ID")
    app.config["CLOUDFLARE_SECRET_ACCESS_KEY"] = setting("CLOUDFLARE_SECRET_ACCESS_KEY")
    app.config["S3_BUCKET_NAME"] = os.environ.get("S3_BUCKET_NAME", "openforge-models")
    app.config["FILE_DOMAIN"] = os.environ.get(
        "FILE_DOMAIN", "https://objects.openforge.tools"
    )
    app.db = db
    app.session_service = SessionService(
        db, app.config["API_TOKEN"], app.config["SECRET_KEY"]
    )
    if "LOG_LEVEL" in os.environ:
        app.logger.setLevel(os.environ["LOG_LEVEL"])
