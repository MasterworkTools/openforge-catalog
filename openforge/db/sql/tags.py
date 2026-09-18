import json
import uuid

from psycopg import cursor, sql

from openforge.db import get_logger

from .tag_utils import array_to_tag, convert_tag_dict, tag_to_array


def _convert_tag(tag: dict) -> dict:
    return convert_tag_dict(tag)


def _convert_config(data: dict) -> dict:
    if "config" in data:
        if isinstance(data["config"], str):
            data["blueprint_config"] = json.loads(data["config"])
        else:
            data["blueprint_config"] = data["config"]
        del data["config"]
    return data


def get_tags(curs: cursor, blueprint_id: uuid.UUID) -> list[dict]:
    query = sql.SQL(
        """
SELECT id, blueprint_id, tag, created_at, updated_at
  FROM tags
  WHERE blueprint_id = {blueprint_id}
"""
    ).format(blueprint_id=sql.Literal(blueprint_id))
    get_logger().debug(query.join("\n").as_string())
    curs.execute(query)
    return [_convert_tag(row) for row in curs.fetchall()]


def get_tag_by_id(curs: cursor, tag_id: uuid.UUID) -> dict:
    query = sql.SQL(
        """
SELECT id, blueprint_id, tag, created_at, updated_at
  FROM tags
  WHERE id = {tag_id}
"""
    ).format(tag_id=sql.Literal(tag_id))
    get_logger().debug(query.join("\n").as_string())
    curs.execute(query)
    return _convert_tag(curs.fetchone())


def insert_tag(curs: cursor, blueprint_id: uuid.UUID, tag: str) -> dict:
    tag_arr = tag_to_array(tag)
    query = sql.SQL(
        """
WITH new_tags AS (
  INSERT INTO tags (
    blueprint_id, tag
  ) VALUES (
    {blueprint_id}, {tag}
  ) ON CONFLICT DO NOTHING
  RETURNING id
)
SELECT COALESCE(
  (SELECT id FROM new_tags),
  (SELECT id FROM tags WHERE blueprint_id = {blueprint_id} AND tag = {tag})
) AS id
"""
    ).format(blueprint_id=sql.Literal(blueprint_id), tag=sql.Literal(tag_arr))
    get_logger().debug(query.join("\n").as_string())
    curs.execute(query)
    return get_tag_by_id(curs, curs.fetchone()["id"])


def delete_tag(curs: cursor, blueprint_id: uuid.UUID, tag: str) -> dict:
    tag_arr = tag_to_array(tag)
    query = sql.SQL(
        """
DELETE FROM tags
  WHERE blueprint_id = {blueprint_id}
    AND tag = {tag}
"""
    ).format(blueprint_id=sql.Literal(blueprint_id), tag=sql.Literal(tag_arr))
    get_logger().debug(query.join("\n").as_string())
    curs.execute(query)
    return curs.rowcount


def delete_all_blueprint_tags(curs: cursor, blueprint_id: uuid.UUID) -> dict:
    query = sql.SQL(
        """
DELETE FROM tags
  WHERE blueprint_id = {blueprint_id}
"""
    ).format(blueprint_id=sql.Literal(blueprint_id))
    get_logger().debug(query.join("\n").as_string())
    curs.execute(query)
    return curs.rowcount


def delete_all_tags(curs: cursor) -> dict:
    query = sql.SQL("DELETE FROM tags")
    get_logger().debug(query.join("\n").as_string())
    curs.execute(query)
    return curs.rowcount


def get_tags_for_blueprints(curs: cursor, blueprint_ids: list[uuid.UUID]) -> list[dict]:
    """Get all tags for multiple blueprints in a single query.

    Args:
        curs: Database cursor
        blueprint_ids: List of blueprint IDs to get tags for

    Returns:
        List of tag dictionaries with blueprint_id included
    """
    if not blueprint_ids:
        return []

    query = sql.SQL(
        """
SELECT id, blueprint_id, tag, created_at, updated_at
  FROM tags
  WHERE blueprint_id IN ({blueprint_ids})
  ORDER BY blueprint_id, tag
"""
    ).format(
        blueprint_ids=sql.SQL(",").join(sql.Literal(bp_id) for bp_id in blueprint_ids)
    )
    get_logger().debug(query.join("\n").as_string())
    curs.execute(query)
    return [_convert_tag(row) for row in curs.fetchall()]


def get_blueprint_ids_by_tag(curs: cursor, tag: str) -> list[uuid.UUID]:
    tags = tag_to_array(tag)
    query_list = [
        sql.SQL(
            """
SELECT DISTINCT blueprint_id
  FROM tags
  WHERE tag[1] = {tag}
"""
        ).format(tag=sql.Literal(tags.pop(0)))
    ]
    counter = 1
    for t in tags:
        counter += 1
        query_list.append(
            sql.SQL(
                """
    AND tag[{counter}] = {tag}
"""
            ).format(tag=sql.Literal(t), counter=sql.Literal(counter))
        )
    query = sql.Composed(query_list)
    get_logger().debug(query.join("\n").as_string())
    curs.execute(query.join("\n"))
    return [row["blueprint_id"] for row in curs.fetchall()]


def tag_search_blueprints(
    curs: cursor,
    accept: list[str],
    require: list[str],
    deny: list[str],
    next: uuid.UUID | None = None,
    previous: uuid.UUID | None = None,
    limit: int = 20,
    models: bool = True,
    blueprints: bool = False,
    search: str | None = None,
) -> list[uuid.UUID]:
    parts = [
        sql.SQL("SELECT *"),
        sql.SQL("  FROM blueprints"),
        sql.SQL("  WHERE blueprints.id IN ("),
        _query_tags_basics(
            accept,
            require,
            deny,
            next,
            previous,
            limit,
            models=models,
            blueprints=blueprints,
            search=search,
        ),
        sql.SQL("  )"),
        sql.SQL("  ORDER BY blueprints.blueprint_name"),
    ]
    query = sql.Composed(parts)
    get_logger().debug(query.join("\n").as_string())
    curs.execute(query)
    return [_convert_config(row) for row in curs.fetchall()]


def tag_search_tags(
    curs: cursor,
    accept: list[str],
    require: list[str],
    deny: list[str],
    next: uuid.UUID | None = None,
    previous: uuid.UUID | None = None,
    limit: int = 20,
    models: bool = True,
    blueprints: bool = False,
    search: str | None = None,
) -> list[uuid.UUID]:
    parts = [
        sql.SQL("SELECT *"),
        sql.SQL("  FROM tags AS bptags"),
        sql.SQL("  WHERE bptags.blueprint_id IN ("),
        _query_tags_basics(
            accept,
            require,
            deny,
            next,
            previous,
            limit,
            models=models,
            blueprints=blueprints,
            search=search,
        ),
        sql.SQL("  )"),
        sql.SQL("  ORDER BY bptags.blueprint_id"),
    ]
    query = sql.Composed(parts)
    get_logger().debug(query.join("\n").as_string())
    curs.execute(query)
    return curs.fetchall()


def tag_search_blueprint_images(
    curs: cursor,
    accept: list[str],
    require: list[str],
    deny: list[str],
    next: uuid.UUID | None = None,
    previous: uuid.UUID | None = None,
    limit: int = 20,
    models: bool = True,
    blueprints: bool = False,
    search: str | None = None,
) -> list[dict]:
    parts = [
        sql.SQL(
            "SELECT bpi.blueprint_id,images.id, images.image_name, "
            "images.image_url, images.created_at, images.updated_at"
        ),
        sql.SQL("  FROM images"),
        sql.SQL("    JOIN blueprint_images AS bpi ON images.id = bpi.image_id"),
        sql.SQL("  WHERE bpi.blueprint_id IN ("),
        _query_tags_basics(
            accept,
            require,
            deny,
            next,
            previous,
            limit,
            models=models,
            blueprints=blueprints,
            search=search,
        ),
        sql.SQL("  )"),
        sql.SQL("  ORDER BY bpi.blueprint_id"),
    ]
    query = sql.Composed(parts)
    get_logger().debug(query.join("\n").as_string())
    curs.execute(query)
    return curs.fetchall()


def tag_search_blueprint_count(
    curs: cursor,
    accept: list[str],
    require: list[str],
    deny: list[str],
    models: bool = True,
    blueprints: bool = False,
    search: str | None = None,
) -> int:
    parts = [
        sql.SQL("SELECT COUNT(*)"),
        sql.SQL("  FROM blueprints"),
        sql.SQL("  WHERE blueprints.id IN ("),
        _query_tags_basics(
            accept,
            require,
            deny,
            do_limit=False,
            models=models,
            blueprints=blueprints,
            search=search,
        ),
        sql.SQL("  )"),
    ]
    query = sql.Composed(parts)
    get_logger().debug(query.join("\n").as_string())
    curs.execute(query)
    return curs.fetchone()["count"]


def tag_search_blueprint_start_count(
    curs: cursor,
    accept: list[str],
    require: list[str],
    deny: list[str],
    first: uuid.UUID,
    models: bool = True,
    blueprints: bool = False,
    search: str | None = None,
) -> int:
    parts = [
        sql.SQL("SELECT COUNT(*)"),
        sql.SQL("  FROM blueprints"),
        sql.SQL("  WHERE blueprints.id IN ("),
        _query_tags_basics(
            accept,
            require,
            deny,
            do_limit=False,
            models=models,
            blueprints=blueprints,
            search=search,
        ),
        sql.SQL("  )"),
        sql.SQL(
            "    AND blueprints.blueprint_name < "
            "(SELECT blueprint_name FROM blueprints WHERE id = {first})"
        ).format(first=sql.Literal(first)),
    ]
    query = sql.Composed(parts)
    get_logger().debug(query.join("\n").as_string())
    curs.execute(query)
    return curs.fetchone()["count"]


def tag_search_tag_count(
    curs: cursor,
    accept: list[str],
    require: list[str],
    deny: list[str],
    models: bool = True,
    blueprints: bool = False,
    search: str | None = None,
) -> list[dict]:
    parts = [
        sql.SQL("SELECT COUNT(*) AS tag_count, t.tag"),
        sql.SQL("  FROM tags AS t"),
        sql.SQL("  WHERE t.blueprint_id IN ("),
        _query_tags_basics(
            accept,
            require,
            deny,
            do_limit=False,
            models=models,
            blueprints=blueprints,
            search=search,
        ),
        sql.SQL("  )"),
        sql.SQL("  GROUP BY t.tag"),
    ]
    query = sql.Composed(parts)
    get_logger().debug(query.join("\n").as_string())
    curs.execute(query)
    return curs.fetchall()


def _query_tags_basics(
    accept: list[str],
    require: list[str],
    deny: list[str],
    next: uuid.UUID | None = None,
    previous: uuid.UUID | None = None,
    limit: int = 20,
    do_limit: bool = True,
    models: bool = True,
    blueprints: bool = False,
    search: str | None = None,
) -> sql.Composed:
    query_parts = [
        sql.SQL(
            """
SELECT DISTINCT bp.id
  FROM blueprints AS bp, (
    SELECT bp2.id, bp2.blueprint_name
      FROM blueprints bp2"""
        )
    ]
    query_parts.append(_query_tags_include(accept, require))
    if query_parts[-1] == sql.Composed([]):
        query_parts = query_parts[:-1]

    # Always exclude deprecated blueprints first
    query_parts.append(sql.SQL("    WHERE bp2.deprecated = false"))

    deny_parts = []
    if len(deny) > 0:
        for d in deny:
            deny_parts.append(sql.SQL("    AND bp2.id NOT IN ("))
            deny_parts.append(_query_tags_deny([d]))
            deny_parts.append(sql.SQL("    )"))

    # Handle blueprint type filtering
    if models and blueprints:
        # When both are requested, use OR logic
        query_parts.append(
            sql.SQL(
                "    AND (bp2.blueprint_type = 'model' "
                "OR bp2.blueprint_type = 'blueprint')"
            )
        )
    elif models:
        query_parts.append(sql.SQL("    AND bp2.blueprint_type = 'model'"))
    elif blueprints:
        query_parts.append(sql.SQL("    AND bp2.blueprint_type = 'blueprint'"))
    if search:
        query_parts.append(
            sql.SQL(
                "    AND to_tsvector('english', bp2.search_text) @@ "
                "websearch_to_tsquery('english', {search})"
            ).format(search=sql.Literal(search))
        )
    if next:
        query_parts.append(
            sql.SQL(
                "        AND bp2.blueprint_name > "
                "(SELECT blueprint_name FROM blueprints WHERE id = {next})"
            ).format(next=sql.Literal(next))
        )
    elif previous:
        query_parts.append(
            sql.SQL(
                "        AND bp2.blueprint_name < "
                "(SELECT blueprint_name FROM blueprints WHERE id = {previous})"
            ).format(previous=sql.Literal(previous))
        )
    end_parts = [
        sql.SQL(
            "      ORDER BY bp2.blueprint_name %s" % ("DESC" if previous else "ASC")
        )
    ]
    if do_limit:
        end_parts.append(
            sql.SQL("      LIMIT {limit}").format(limit=sql.Literal(limit))
        )
    end_parts.append(
        sql.SQL(
            """    ) as bp_name
    WHERE bp_name.id = bp.id
"""
        )
    )
    query = sql.Composed(query_parts + deny_parts + end_parts)
    return query.join("\n")


def _query_tags_include(accept: list[str], require: list[str]) -> sql.Composed:
    joins = []
    wheres = []
    counter = 0

    def _query_tag_require(counter: int, require_tag: str) -> int:
        tags_name = "tags_%s" % counter
        joins.append(
            sql.SQL("    JOIN tags AS {table} ON bp2.id = {table}.blueprint_id").format(
                table=sql.Identifier(tags_name)
            )
        )
        tags = require_tag.split("|")
        wheres.append(
            sql.SQL("  AND {table}.tag = {tags}").format(
                table=sql.Identifier(tags_name),
                tags=sql.Literal(tags),
            )
        )
        return counter + 1

    def _query_tag_accept(counter: int, accept_tag: str) -> int:
        tags_name = "tags_%s" % counter
        joins.append(
            sql.SQL("    JOIN tags AS {table} ON bp2.id = {table}.blueprint_id").format(
                table=sql.Identifier(tags_name)
            )
        )
        tags = accept_tag.split("|")
        wheres.append(sql.SQL("  AND ("))
        t = 1
        sql_and = ""
        for tag in tags:
            wheres.append(
                sql.SQL("     %s {table}.tag[%s] = {tag}" % (sql_and, t)).format(
                    table=sql.Identifier(tags_name),
                    tag=sql.Literal(tag),
                )
            )
            sql_and = "   AND"
            t += 1
        wheres.append(sql.SQL("    )"))
        return counter + 1

    for req in require:
        if "tag" in req:
            counter = _query_tag_require(counter, req["tag"])
    for acc in accept:
        if "tag" in acc:
            counter = _query_tag_accept(counter, acc["tag"])
    return sql.Composed(joins + wheres).join("\n")


def get_all_unique_tags(
    curs: cursor, search: str = None, limit: int = 100, offset: int = 0
) -> dict:
    """Get all unique tags in the system with optional search filtering.

    Args:
        curs: Database cursor
        search: Optional search string to filter tags
        limit: Maximum number of results to return
        offset: Number of results to skip

    Returns:
        Dictionary with tags array and pagination info
    """
    # Build WHERE clause for search
    where_clause = sql.SQL("")
    if search:
        # Search anywhere in the tag hierarchy
        where_clause = sql.SQL("WHERE array_to_string(tag, '|') ILIKE {search}").format(
            search=sql.Literal(f"%{search}%")
        )

    # Get total count
    count_query = sql.SQL(
        """
SELECT COUNT(DISTINCT tag) as total
FROM tags
{where_clause}
"""
    ).format(where_clause=where_clause)

    curs.execute(count_query)
    total_count = curs.fetchone()["total"]

    # Get paginated results
    query = sql.SQL(
        """
SELECT DISTINCT tag, COUNT(*) as blueprint_count
FROM tags
{where_clause}
GROUP BY tag
ORDER BY tag
LIMIT {limit} OFFSET {offset}
"""
    ).format(
        where_clause=where_clause, limit=sql.Literal(limit), offset=sql.Literal(offset)
    )

    curs.execute(query)
    tags = [
        {"tag": array_to_tag(row["tag"]), "blueprint_count": row["blueprint_count"]}
        for row in curs.fetchall()
    ]

    return {
        "tags": tags,
        "total_count": total_count,
        "has_more": (offset + len(tags)) < total_count,
    }


def _query_tags_deny(deny: list[str]) -> sql.Composed:
    deny_parts = []
    if len(deny) > 0:
        deny_parts.extend(
            [
                sql.SQL("      SELECT DISTINCT bp_neg.id"),
                sql.SQL("  FROM blueprints AS bp_neg"),
            ]
        )

        neg_joins = []
        neg_wheres = []
        neg_counter = 0

        # Always exclude deprecated blueprints first
        neg_wheres.append(sql.SQL("  WHERE bp_neg.deprecated = false"))

        for d in deny:
            if "tag" in d:
                neg_tags_name = f"tags_{neg_counter}_neg"
                neg_tags = d["tag"].split("|")
                neg_joins.append(
                    sql.SQL(
                        "    JOIN tags AS {table} ON bp_neg.id = {table}.blueprint_id"
                    ).format(table=sql.Identifier(neg_tags_name))
                )
                neg_wheres.append(
                    sql.SQL("    AND {table}.tag = {tags}").format(
                        table=sql.Identifier(neg_tags_name),
                        tags=sql.Literal(neg_tags),
                    )
                )
                neg_counter += 1

    return sql.Composed(deny_parts + neg_joins + neg_wheres).join("\n      ")
