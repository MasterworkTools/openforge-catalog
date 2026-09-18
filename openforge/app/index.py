import os

import aws_lambda_wsgi
from flask import Flask, request
from flask_cors import CORS

import openforge.app.routes.blueprint_documentation as blueprint_doc_routes
import openforge.app.routes.blueprint_successor as successor_routes
import openforge.app.routes.blueprints as blueprint_routes
import openforge.app.routes.fixtures as fixture_routes
import openforge.app.routes.images as image_routes
import openforge.app.routes.sessions as session_routes
import openforge.app.routes.tag_descriptions as tag_description_routes
import openforge.app.routes.tags as tag_routes
import openforge.app.routes.tags_documentation as tags_doc_routes
from openforge.app.middleware.csrf import csrf_protect
from openforge.app.routes import authenticate

app = Flask(__name__)

# Initialize CORS only in development/testing environments
if os.environ.get("FLASK_DEBUG") == "1":
    CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000"])

# Don't initialize the rest of the app at module level to avoid pool creation
# during testing - init_app will be called when the app is actually used


def ensure_app_initialized():
    """Ensure the app is initialized before handling requests."""
    if not hasattr(app, "_initialized"):
        from openforge.app import init_app

        init_app(app)
        app._initialized = True


@app.before_request
def before_request():
    ensure_app_initialized()


####################
### Health Check
####################


@app.route("/health", methods=["GET"])
def health_check():
    return {"status": "healthy"}, 200


####################
### Admin Fixture Loading routes
####################


@app.route("/api/admin/fixtures", methods=["POST"])
@authenticate(methods=["POST"], disable_sessions=["POST"], disable_csrf=["POST"])
def load_fixture():
    """Load fixture via API with auto-detection (admin only, API key auth)."""
    return fixture_routes.load_fixture()


@app.route("/api/admin/fixtures/blueprints", methods=["POST"])
@authenticate(methods=["POST"], disable_sessions=["POST"], disable_csrf=["POST"])
def load_blueprint_fixture():
    """Load a blueprint fixture file via API upload (admin only, API key auth)."""
    return fixture_routes.load_blueprint_fixture()


@app.route("/api/admin/fixtures/tag-descriptions", methods=["POST"])
@authenticate(methods=["POST"], disable_sessions=["POST"], disable_csrf=["POST"])
def load_tag_description_fixture():
    """Load a tag description fixture file via API upload (admin only, API key auth)."""
    return fixture_routes.load_tag_description_fixture()


@app.route("/api/admin/fixtures/tag-documentation", methods=["POST"])
@authenticate(methods=["POST"], disable_sessions=["POST"], disable_csrf=["POST"])
def load_tag_documentation_fixture():
    """Load tag documentation fixture via API (admin only, API key auth)."""
    return fixture_routes.load_tag_documentation_fixture()


####################
### Session Management routes
####################


@app.route("/api/admin/sessions", methods=["POST"])
def create_session():
    """Create a new admin session."""
    return session_routes.create_session()


@app.route("/api/admin/sessions/validate", methods=["GET"])
def validate_session():
    """Validate current session."""
    return session_routes.validate_session()


@app.route("/api/admin/sessions", methods=["DELETE"])
@authenticate(disable_api_keys=["DELETE"])
@csrf_protect
def delete_session():
    """Delete current session (logout)."""
    return session_routes.delete_session()


####################
### Blueprint Documentation routes
####################


@app.route("/api/blueprints/<blueprint_id>/documentation", methods=["GET", "POST"])
@authenticate(methods=["POST"])
@csrf_protect
def blueprint_documentation(blueprint_id):
    if request.method == "GET":
        return blueprint_doc_routes.get_blueprint_documentation(blueprint_id)
    elif request.method == "POST":
        return blueprint_doc_routes.create_blueprint_documentation(blueprint_id)


@app.route(
    "/api/blueprints/<blueprint_id>/documentation/<doc_id>",
    methods=["GET", "PATCH", "DELETE"],
)
@authenticate(methods=["PATCH", "DELETE"])
@csrf_protect
def blueprint_documentation_entry(blueprint_id, doc_id):
    if request.method == "GET":
        return blueprint_doc_routes.get_blueprint_documentation_entry(
            blueprint_id, doc_id
        )
    elif request.method == "PATCH":
        return blueprint_doc_routes.update_blueprint_documentation(blueprint_id, doc_id)
    elif request.method == "DELETE":
        return blueprint_doc_routes.delete_blueprint_documentation(blueprint_id, doc_id)


@app.route("/api/blueprints/<blueprint_id>/changelog-history", methods=["GET"])
def blueprint_changelog_history(blueprint_id):
    return blueprint_doc_routes.get_blueprint_changelog_history(blueprint_id)


@app.route("/api/blueprints/<blueprint_id>/all-documentation", methods=["GET"])
def blueprint_all_documentation(blueprint_id):
    return blueprint_doc_routes.get_blueprint_all_documentation(blueprint_id)


####################
### Blueprint routes
####################


@app.route("/api/blueprints", methods=["GET", "POST"])
@authenticate(methods=["POST"])
@csrf_protect
def blueprints():
    if request.method == "GET":
        return blueprint_routes.get_blueprints()
    elif request.method == "POST":
        return blueprint_routes.create_blueprint()


@app.route("/api/blueprints/deprecated", methods=["GET"])
def deprecated_blueprints():
    return blueprint_routes.get_deprecated_blueprints()


@app.route("/api/blueprints/tags", methods=["POST"])
def tags():
    return tag_routes.query_tags()


@app.route("/api/blueprints/tags/<tag>", methods=["GET"])
def blueprints_by_tag(tag):
    return tag_routes.get_blueprint_ids_by_tag(tag)


@app.route("/api/blueprints/md5/<md5>", methods=["GET"])
def blueprint_by_md5(md5):
    if request.method == "GET":
        return blueprint_routes.get_blueprint_by_md5(md5)


@app.route("/api/blueprints/<blueprint_id>", methods=["GET", "PATCH", "DELETE"])
@authenticate(methods=["PATCH", "DELETE"])
@csrf_protect
def blueprint(blueprint_id):
    if request.method == "GET":
        return blueprint_routes.get_blueprint_by_id(blueprint_id)
    elif request.method == "PATCH":
        return blueprint_routes.update_blueprint(blueprint_id)
    elif request.method == "DELETE":
        return blueprint_routes.delete_blueprint(blueprint_id)


@app.route("/api/blueprints/<blueprint_id>/download", methods=["GET"])
def download_blueprint(blueprint_id):
    return blueprint_routes.download_blueprint(blueprint_id)


@app.route("/api/blueprints/<blueprint_id>/thumbnail-variants", methods=["GET"])
def blueprint_thumbnail_variants(blueprint_id):
    return blueprint_routes.get_blueprint_thumbnail_variants(blueprint_id)


@app.route(
    "/api/blueprints/<blueprint_id>/thumbnail-variants/default-angle",
    methods=["PATCH"],
)
@authenticate(methods=["PATCH"])
@csrf_protect
def blueprint_default_angle(blueprint_id):
    return blueprint_routes.set_blueprint_default_angle(blueprint_id)


@app.route("/api/blueprints/<blueprint_id>/tags", methods=["GET", "POST", "DELETE"])
@authenticate(methods=["POST", "DELETE"])
@csrf_protect
def blueprint_tags(blueprint_id):
    if request.method == "GET":
        return tag_routes.get_blueprint_tags(blueprint_id)
    elif request.method == "POST":
        return tag_routes.replace_blueprint_tags(blueprint_id, request.json)
    elif request.method == "DELETE":
        return tag_routes.delete_blueprint_tags(blueprint_id)


@app.route("/api/blueprints/<blueprint_id>/tags/<tag>", methods=["POST", "DELETE"])
@authenticate(methods=["POST", "DELETE"])
@csrf_protect
def blueprint_tag(blueprint_id, tag):
    if request.method == "POST":
        return tag_routes.create_blueprint_tags(blueprint_id, [tag])
    elif request.method == "DELETE":
        return tag_routes.delete_blueprint_tag(blueprint_id, tag)


@app.route("/api/blueprints/<blueprint_id>/disconnect-successor", methods=["POST"])
@authenticate(methods=["POST"])
@csrf_protect
def disconnect_successor(blueprint_id):
    return successor_routes.disconnect_successor(blueprint_id)


####################
### Image routes
####################


@app.route("/api/images", methods=["GET", "POST"])
@authenticate(methods=["POST"])
@csrf_protect
def images():
    if request.method == "GET":
        return image_routes.get_images()
    elif request.method == "POST":
        return image_routes.create_image()


@app.route("/api/images/<image_id>", methods=["GET", "PATCH", "DELETE"])
@authenticate(methods=["PATCH", "DELETE"])
@csrf_protect
def image(image_id):
    if request.method == "GET":
        return image_routes.get_image_by_id(image_id)
    elif request.method == "PATCH":
        return image_routes.update_image(image_id)
    elif request.method == "DELETE":
        return image_routes.delete_image(image_id)


####################
### Tag Description routes
####################


@app.route("/api/tag-descriptions", methods=["GET", "POST"])
@authenticate(methods=["POST"])
@csrf_protect
def tag_descriptions():
    if request.method == "GET":
        return tag_description_routes.get_tag_descriptions()
    elif request.method == "POST":
        return tag_description_routes.create_tag_description()


@app.route(
    "/api/tag-descriptions/<tag_description_id>", methods=["GET", "PATCH", "DELETE"]
)
@authenticate(methods=["PATCH", "DELETE"])
@csrf_protect
def tag_description(tag_description_id):
    if request.method == "GET":
        return tag_description_routes.get_tag_description_by_id(tag_description_id)
    elif request.method == "PATCH":
        return tag_description_routes.update_tag_description(tag_description_id)
    elif request.method == "DELETE":
        return tag_description_routes.delete_tag_description(tag_description_id)


@app.route("/api/tag/<tag>/description", methods=["GET", "PATCH", "DELETE"])
@authenticate(methods=["PATCH", "DELETE"])
@csrf_protect
def tag_description_by_tag(tag):
    if request.method == "GET":
        return tag_description_routes.get_tag_description_by_tag(tag)
    elif request.method == "PATCH":
        return tag_description_routes.update_tag_description_by_tag(tag)
    elif request.method == "DELETE":
        return tag_description_routes.delete_tag_description_by_tag(tag)


####################
### Tag Documentation routes
####################


@app.route("/api/tags/<path:tag_path>/documentation", methods=["GET", "POST"])
@authenticate(methods=["POST"])
@csrf_protect
def tag_documentation(tag_path):
    # Convert path to tag array
    tag_array = tag_path.split("/")

    if request.method == "GET":
        return tags_doc_routes.get_tag_documentation(tag_array)
    elif request.method == "POST":
        return tags_doc_routes.create_tag_documentation(tag_array)


@app.route(
    "/api/tags/<path:tag_path>/documentation/<doc_id>",
    methods=["GET", "PATCH", "DELETE"],
)
@authenticate(methods=["PATCH", "DELETE"])
@csrf_protect
def tag_documentation_entry(tag_path, doc_id):
    # Convert path to tag array
    tag_array = tag_path.split("/")

    if request.method == "GET":
        return tags_doc_routes.get_tag_documentation_entry(tag_array, doc_id)
    elif request.method == "PATCH":
        return tags_doc_routes.update_tag_documentation(tag_array, doc_id)
    elif request.method == "DELETE":
        return tags_doc_routes.delete_tag_documentation(tag_array, doc_id)


@app.route("/api/tag-documentation", methods=["GET"])
def all_tag_documentation():
    return tags_doc_routes.get_all_tag_documentation()


@app.route("/api/tag-documentation/<tag>", methods=["GET"])
def tag_documentation_by_prefix(tag):
    return tags_doc_routes.get_tag_documentation_by_tag_prefix(tag)


def lambda_handler(event, context):
    return aws_lambda_wsgi.response(app.wsgi_app, event, context)
