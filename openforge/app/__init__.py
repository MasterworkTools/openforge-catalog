import os

from dotenv import load_dotenv
from flask import Flask

from openforge.app.services.session_service import SessionService
from openforge.db import PgDB


def init_app(app: Flask):
    load_dotenv()

    # Use pool-less mode for testing to avoid logging errors during cleanup
    use_pool = not app.config.get("TESTING", False)
    db = PgDB(os.environ, app.logger, use_pool=use_pool)
    app.config["API_TOKEN"] = os.environ.get("API_TOKEN", "1234567890")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
    if not app.config["SECRET_KEY"]:
        raise ValueError("SECRET_KEY not configured.")
    app.config["CLOUDFLARE_ENDPOINT"] = os.environ.get("CLOUDFLARE_ENDPOINT")
    app.config["CLOUDFLARE_ACCESS_KEY_ID"] = os.environ.get("CLOUDFLARE_ACCESS_KEY_ID")
    app.config["CLOUDFLARE_SECRET_ACCESS_KEY"] = os.environ.get(
        "CLOUDFLARE_SECRET_ACCESS_KEY"
    )
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
