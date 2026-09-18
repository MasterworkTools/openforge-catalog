from flask import current_app, jsonify, request
from jsonschema.exceptions import ValidationError
from psycopg.rows import dict_row

import openforge.db.sql.tag_descriptions as tag_description_sql
from openforge.db.sql.tag_utils import tag_to_array
from openforge.openapi import validate_schema


def get_tag_descriptions():
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            data = tag_description_sql.get_all_tag_descriptions(cursor)
            return jsonify(
                {tag_desc["tag"]: tag_desc["description"] for tag_desc in data}
            )


def create_tag_description():
    try:
        validate_schema("tag_description.yaml", request.json)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            tag = tag_to_array(request.json["tag"])
            data = tag_description_sql.insert_tag_description(
                cursor, tag, request.json.get("description")
            )
            return jsonify(data), 201


def get_tag_description_by_id(tag_description_id):
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            data = tag_description_sql.get_tag_description_by_id(
                cursor, tag_description_id
            )
            return jsonify(data)


def update_tag_description(tag_description_id):
    try:
        validate_schema("tag_description.yaml", request.json, required=False)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            data = tag_description_sql.update_tag_description(
                cursor, tag_description_id, request.json.get("description")
            )
            return jsonify(data)


def delete_tag_description(tag_description_id):
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            tag_description_sql.delete_tag_description(cursor, tag_description_id)
            return "", 204


def get_tag_description_by_tag(tag):
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            data = tag_description_sql.get_tag_description_by_tag(cursor, tag)
            return jsonify(data)


def update_tag_description_by_tag(tag):
    try:
        validate_schema("tag_description.yaml", request.json, required=False)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            data = tag_description_sql.update_tag_description_by_tag(
                cursor, tag, request.json.get("description")
            )
            return jsonify(data)


def delete_tag_description_by_tag(tag):
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            tag_description_sql.delete_tag_description_by_tag(cursor, tag)
            return "", 204
