import uuid

from flask import abort, current_app, jsonify, make_response, request
from jsonschema.exceptions import ValidationError
from psycopg.rows import dict_row

import openforge.db.sql.tags as tag_sql
from openforge.db.sql.tag_utils import array_to_tag
from openforge.openapi import validate_schema


def get_blueprint_tags(blueprint_id: uuid.UUID):
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            data = tag_sql.get_tags(cursor, blueprint_id)
            return jsonify(data)


def create_blueprint_tags(blueprint_id: uuid.UUID, tags: list[str]):
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            data = []
            for tag in tags:
                data.append(tag_sql.insert_tag(cursor, blueprint_id, tag))
            return jsonify(data)


def replace_blueprint_tags(blueprint_id: uuid.UUID, tags: list[str]):
    try:
        validate_schema("tags.yaml", tags)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            tag_sql.delete_all_blueprint_tags(cursor, blueprint_id)
            data = []
            for tag in tags:
                data.append(tag_sql.insert_tag(cursor, blueprint_id, tag))
            return jsonify(data)


def delete_blueprint_tag(blueprint_id: uuid.UUID, tag: str):
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            rows = tag_sql.delete_tag(cursor, blueprint_id, tag)
            if rows != 0:
                return make_response("", 204)
            else:
                abort(404)


def delete_blueprint_tags(blueprint_id: uuid.UUID):
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            tag_sql.delete_all_blueprint_tags(cursor, blueprint_id)
            return make_response("", 204)


def get_blueprint_ids_by_tag(tag: str):
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            data = tag_sql.get_blueprint_ids_by_tag(cursor, tag)
            return jsonify(data)


def query_tags():
    try:
        if len(request.data) > 0:
            validate_schema("tag_query.yaml", request.json)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            accept = []
            require = []
            deny = []
            if len(request.data) > 0:
                accept = request.json.get("accept", [])
                require = request.json.get("require", [])
                deny = request.json.get("deny", [])
            next = request.args.get("next")
            previous = request.args.get("previous")
            limit = request.args.get("limit", 20)
            models = request.args.get("models", "true").lower() == "true"
            blueprints = request.args.get("blueprints", "false").lower() == "true"
            search = request.args.get("search")
            if search == "":
                search = None
            bp_data = tag_sql.tag_search_blueprints(
                cursor,
                accept,
                require,
                deny,
                next,
                previous,
                limit,
                models=models,
                blueprints=blueprints,
                search=search,
            )
            tag_data = tag_sql.tag_search_tags(
                cursor,
                accept,
                require,
                deny,
                next,
                previous,
                limit,
                models=models,
                blueprints=blueprints,
                search=search,
            )
            image_data = tag_sql.tag_search_blueprint_images(
                cursor,
                accept,
                require,
                deny,
                next,
                previous,
                limit,
                models=models,
                blueprints=blueprints,
                search=search,
            )
            count = tag_sql.tag_search_blueprint_count(
                cursor,
                accept,
                require,
                deny,
                models=models,
                blueprints=blueprints,
                search=search,
            )
            start_count = 0
            if len(bp_data) > 0:
                start_count = tag_sql.tag_search_blueprint_start_count(
                    cursor,
                    accept,
                    require,
                    deny,
                    bp_data[0]["id"],
                    models=models,
                    blueprints=blueprints,
                    search=search,
                )
            tag_count = tag_sql.tag_search_tag_count(
                cursor,
                accept,
                require,
                deny,
                models=models,
                blueprints=blueprints,
                search=search,
            )
            tag_count = {
                array_to_tag(tag["tag"]): tag["tag_count"] for tag in tag_count
            }
            bps = _merge_blueprint_tag_data(bp_data, tag_data)
            bps = _merge_blueprint_image_data(bps, image_data)
            paging = _munge_paging(bps, count, start_count)

            return jsonify(
                {
                    "paging": paging,
                    "blueprints": bps,
                    "tag_counts": tag_count,
                }
            )


def _munge_paging(bps: list[dict], total_count: int, start_count: int) -> dict:
    previous_token = bps[0]["id"] if len(bps) > 0 else None
    next_token = bps[-1]["id"] if len(bps) > 0 else None
    paging = {
        "previous_token": previous_token,
        "next_token": next_token,
        "total_count": total_count,
        "start_count": start_count,
    }
    return paging


def _merge_blueprint_tag_data(bp_data: list[dict], tag_data: list[dict]) -> list[dict]:
    for bp in bp_data:
        bp["tags"] = [
            array_to_tag(tag["tag"])
            for tag in tag_data
            if tag["blueprint_id"] == bp["id"]
        ]
    return bp_data


def _merge_blueprint_image_data(
    bp_data: list[dict], image_data: list[dict]
) -> list[dict]:
    for bp in bp_data:
        bp["images"] = [
            _munge_image(image)
            for image in image_data
            if image["blueprint_id"] == bp["id"]
        ]
    return bp_data


def _munge_image(image: dict) -> dict:
    return {
        "id": image["id"],
        "image_name": image["image_name"],
        "image_url": image["image_url"],
        "created_at": image["created_at"],
        "updated_at": image["updated_at"],
    }
