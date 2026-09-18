import json
import re
import uuid

from psycopg import cursor, sql
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb
from werkzeug.exceptions import NotFound


def _blueprint_defaults(data: dict) -> dict:
    defaults = {
        "config": {},
        "file_md5": sql.NULL,
        "file_size": sql.NULL,
        "file_name": sql.NULL,
        "full_name": sql.NULL,
        "file_modified_at": sql.NULL,
        "storage_address": sql.NULL,
        # Phase 1 fields
        "consolidated_paths": sql.NULL,
        "deprecated": False,
        "successor_id": sql.NULL,
    }
    defaults.update(data)
    defaults = _convert_blueprint_config(defaults)
    defaults["config"] = Jsonb(defaults["config"])
    return defaults


def _convert_blueprint_config(data: dict) -> dict:
    if "blueprint_config" in data:
        data["config"] = json.dumps(data["blueprint_config"])
        del data["blueprint_config"]
    return data


def _convert_config(data: dict) -> dict:
    if "config" in data:
        if isinstance(data["config"], str):
            data["blueprint_config"] = json.loads(data["config"])
        else:
            data["blueprint_config"] = data["config"]
        del data["config"]
    return data


def get_all_blueprints(curs: cursor) -> list[dict]:
    query = sql.SQL(
        """
SELECT id, blueprint_name, blueprint_type, config, file_md5, file_size,
       file_name, full_name, file_modified_at, storage_address,
       consolidated_paths, deprecated, successor_id,
       created_at, updated_at
  FROM blueprints
"""
    )
    curs.execute(query)
    return [_convert_config(dict(row)) for row in curs.fetchall()]


def get_deprecated_blueprints(curs: cursor) -> list[dict]:
    """Get all deprecated blueprints with successor information."""
    query = sql.SQL(
        """
SELECT b.id, b.blueprint_name, b.blueprint_type, b.config, b.file_md5, b.file_size,
       b.file_name, b.full_name, b.file_modified_at, b.storage_address,
       b.consolidated_paths, b.deprecated, b.successor_id,
       b.created_at, b.updated_at,
       s.blueprint_name as successor_name,
       s.full_name as successor_full_name,
       cl.document as changelog
  FROM blueprints b
  LEFT JOIN blueprints s ON b.successor_id = s.id
  LEFT JOIN blueprint_documentation cl ON s.id = cl.blueprint_id
    AND cl.document_type = 'changelog'
    AND cl.is_live = true
  WHERE b.deprecated = true
  ORDER BY b.created_at DESC
"""
    )
    curs.execute(query)
    results = []
    for row in curs.fetchall():
        blueprint = _convert_config(dict(row))
        # Add successor info if available
        if row.get("successor_name"):
            blueprint["successor_info"] = {
                "name": row["successor_name"],
                "full_name": row["successor_full_name"],
                "changelog": row.get("changelog"),
            }
        results.append(blueprint)
    return results


def blueprint_search_text(data: dict, words: list[str]) -> str:
    retwords = set()
    retwords.update(words)
    retwords.update(re.split(r"[^a-zA-Z0-9]", data["blueprint_name"]))
    return " ".join(retwords)


def insert_blueprint(
    curs: cursor, data: dict, rescue_md5_conflict: bool = False, words: list[str] = []
) -> dict:
    data["search_text"] = blueprint_search_text(data, words)
    query_list = [
        sql.SQL(
            """
INSERT INTO blueprints (
  blueprint_name, blueprint_type, config, file_md5, file_size, file_name,
  full_name, file_modified_at, storage_address, search_text,
  consolidated_paths, deprecated, successor_id
) VALUES (
  {blueprint_name}, {blueprint_type}, {config}, {file_md5}, {file_size}, {file_name},
  {full_name}, {file_modified_at}, {storage_address}, {search_text},
  {consolidated_paths}, {deprecated}, {successor_id}
)
"""
        ).format(**_blueprint_defaults(data))
    ]
    if rescue_md5_conflict:
        query_list.append(
            sql.SQL("ON CONFLICT ON CONSTRAINT blueprints_file_md5_key DO NOTHING")
        )
    query_list.append(sql.SQL("RETURNING id"))
    query = sql.Composed(query_list)
    curs.execute(query.join("\n"))
    row = curs.fetchone()
    if row:
        return get_blueprint_by_id(curs, row["id"])
    elif rescue_md5_conflict and data.get("file_md5") is not sql.NULL:
        return get_blueprint_by_md5(curs, data["file_md5"])
    else:
        raise UniqueViolation("MD5 not unique")


def get_blueprint_by_id(curs: cursor, blueprint_id: uuid.UUID) -> dict:
    query = sql.SQL(
        """
SELECT id, blueprint_name, blueprint_type, config, file_md5, file_size,
       file_name, full_name, file_modified_at, storage_address,
       consolidated_paths, deprecated, successor_id,
       created_at, updated_at
  FROM blueprints
  WHERE id = {blueprint_id}
"""
    ).format(blueprint_id=sql.Literal(blueprint_id))
    curs.execute(query)
    if curs.rowcount > 0:
        return _convert_config(dict(curs.fetchone()))
    else:
        raise NotFound("Blueprint not found")


def get_blueprint_by_md5(curs: cursor, md5: str) -> dict:
    query = sql.SQL(
        """
SELECT id, blueprint_name, blueprint_type, config, file_md5, file_size,
       file_name, full_name, file_modified_at, storage_address,
       consolidated_paths, deprecated, successor_id,
       created_at, updated_at
  FROM blueprints
  WHERE file_md5 = {md5}
"""
    ).format(md5=sql.Literal(md5))
    curs.execute(query)
    if curs.rowcount > 0:
        return _convert_config(dict(curs.fetchone()))
    else:
        raise NotFound("Blueprint not found")


def update_blueprint(curs: cursor, blueprint_id: uuid.UUID, data: dict) -> dict:
    newdata = {}
    newdata.update(data)
    data = _convert_blueprint_config(newdata)
    query_list = [
        sql.SQL("UPDATE blueprints"),
        sql.SQL("  SET"),
    ]

    fields = [
        "blueprint_name",
        "blueprint_type",
        "config",
        "file_md5",
        "file_size",
        "file_name",
        "full_name",
        "file_modified_at",
        "storage_address",
        "search_text",
        # Phase 1 fields
        "consolidated_paths",
        "deprecated",
        "successor_id",
    ]

    comma = ""
    for field in fields:
        if field in data:
            query_list.append(
                sql.SQL(f"{comma}{field} = " + "{value}").format(value=data[field])
            )
            comma = ", "
    query_list.append(sql.SQL(f"{comma}updated_at = NOW()"))

    query_list.append(
        sql.SQL("  WHERE id = {blueprint_id}").format(
            blueprint_id=sql.Literal(blueprint_id)
        )
    )
    query = sql.Composed(query_list)
    curs.execute(query.join("\n"))
    if curs.rowcount > 0:
        return get_blueprint_by_id(curs, blueprint_id)
    else:
        raise NotFound("Blueprint not found")


def delete_blueprint(curs: cursor, blueprint_id: uuid.UUID) -> dict:
    query = sql.SQL("DELETE FROM blueprints WHERE id = {blueprint_id}").format(
        blueprint_id=sql.Literal(blueprint_id)
    )
    curs.execute(query)
    return curs.rowcount


def delete_all_blueprints(curs: cursor) -> bool:
    query = sql.SQL("TRUNCATE blueprints CASCADE")
    curs.execute(query)
    return True


def get_blueprints_by_full_name(curs: cursor, full_name: str) -> list[dict]:
    """Get all blueprints with the given full_name (for path consolidation)."""
    query = sql.SQL(
        """
SELECT id, blueprint_name, blueprint_type, config, file_md5, file_size,
       file_name, full_name, file_modified_at, storage_address,
       consolidated_paths, deprecated, successor_id,
       created_at, updated_at
  FROM blueprints
  WHERE full_name = {full_name} AND deprecated = false
  ORDER BY created_at DESC
"""
    ).format(full_name=sql.Literal(full_name))
    curs.execute(query)
    return [_convert_config(dict(row)) for row in curs.fetchall()]


def get_blueprints_by_md5(curs: cursor, md5: str) -> list[dict]:
    """Get all blueprints with the given MD5 (for versioning)."""
    query = sql.SQL(
        """
SELECT id, blueprint_name, blueprint_type, config, file_md5, file_size,
       file_name, full_name, file_modified_at, storage_address,
       consolidated_paths, deprecated, successor_id,
       created_at, updated_at
  FROM blueprints
  WHERE file_md5 = {md5}
  ORDER BY created_at DESC
"""
    ).format(md5=sql.Literal(md5))
    curs.execute(query)
    return [_convert_config(dict(row)) for row in curs.fetchall()]


def get_blueprints_by_md5_including_deprecated(curs: cursor, md5: str) -> list[dict]:
    """Get all blueprints with the given MD5 including deprecated ones.

    Used for versioning.
    """
    query = sql.SQL(
        """
SELECT id, blueprint_name, blueprint_type, config, file_md5, file_size,
       file_name, full_name, file_modified_at, storage_address,
       consolidated_paths, deprecated, successor_id,
       created_at, updated_at
  FROM blueprints
  WHERE file_md5 = {md5}
  ORDER BY created_at DESC
"""
    ).format(md5=sql.Literal(md5))
    curs.execute(query)
    return [_convert_config(dict(row)) for row in curs.fetchall()]


def get_non_deprecated_blueprints(curs: cursor) -> list[dict]:
    """Get all non-deprecated blueprints for comparison."""
    query = sql.SQL(
        """
SELECT id, blueprint_name, blueprint_type, config, file_md5, file_size,
       file_name, full_name, file_modified_at, storage_address,
       consolidated_paths, deprecated, successor_id,
       created_at, updated_at
  FROM blueprints
  WHERE deprecated = false
  ORDER BY full_name, created_at DESC
"""
    )
    curs.execute(query)
    return [_convert_config(dict(row)) for row in curs.fetchall()]


def mark_blueprint_deprecated(
    curs: cursor, blueprint_id: uuid.UUID, successor_id: uuid.UUID = None
) -> dict:
    """Mark a blueprint as deprecated with optional successor."""
    data = {"deprecated": True}
    if successor_id:
        data["successor_id"] = successor_id

    return update_blueprint(curs, blueprint_id, data)


def get_current_version_by_md5(curs: cursor, md5: str) -> dict:
    """Get the current version of a blueprint by MD5, following the successor chain."""
    query = sql.SQL(
        """
SELECT find_current_version_by_md5({md5}) as id
"""
    ).format(md5=sql.Literal(md5))
    curs.execute(query)

    result = curs.fetchone()
    if result and result["id"]:
        return get_blueprint_by_id(curs, result["id"])
    else:
        raise NotFound("Blueprint not found")
