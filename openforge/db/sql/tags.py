import json
import logging
import uuid

from psycopg import cursor, sql

from openforge.db import get_logger

from .tag_utils import array_to_tag, convert_tag_dict, tag_to_array


def _log_query(query: sql.Composed) -> None:
    """Dump a composed query, but only when something is listening.

    `as_string()` renders the whole composition, which is not free,
    and the argument to `debug()` is evaluated whether or not DEBUG is
    on. The guide's availability pass builds thirty-odd of these per
    request, so the level check comes first rather than inside the
    logger.
    """
    logger = get_logger()
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(query.join("\n").as_string())


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
    _log_query(query)
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
    _log_query(query)
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
    _log_query(query)
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
    _log_query(query)
    curs.execute(query)
    return curs.rowcount


def delete_all_blueprint_tags(curs: cursor, blueprint_id: uuid.UUID) -> dict:
    query = sql.SQL(
        """
DELETE FROM tags
  WHERE blueprint_id = {blueprint_id}
"""
    ).format(blueprint_id=sql.Literal(blueprint_id))
    _log_query(query)
    curs.execute(query)
    return curs.rowcount


def delete_all_tags(curs: cursor) -> dict:
    query = sql.SQL("DELETE FROM tags")
    _log_query(query)
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
    _log_query(query)
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
    _log_query(query)
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
    deny_children: list[dict] | None = None,
    allow: list[dict] | None = None,
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
            deny_children=deny_children,
            allow=allow,
        ),
        sql.SQL("  )"),
        sql.SQL("  ORDER BY blueprints.blueprint_name, blueprints.id"),
    ]
    query = sql.Composed(parts)
    _log_query(query)
    curs.execute(query)
    return [_convert_config(row) for row in curs.fetchall()]


def tag_search_blueprint_exists(
    curs: cursor,
    accept: list[str],
    require: list[str],
    deny: list[str],
    models: bool = True,
    blueprints: bool = False,
    search: str | None = None,
    deny_children: list[dict] | None = None,
    allow: list[dict] | None = None,
) -> bool:
    """Is there a single blueprint matching this predicate?

    The guide's availability pass asks this about thirty times per
    request, to drop the answers that would empty a part. It never
    looks at what it found, so it wants neither the row nor the order
    — and the order is the expensive half, since it sorts every match
    before LIMIT 1 discards the rest.
    """
    parts = [
        sql.SQL("SELECT EXISTS ("),
        sql.SQL("  SELECT 1"),
        sql.SQL("  FROM blueprints"),
        sql.SQL("  WHERE blueprints.id IN ("),
        _query_tags_basics(
            accept,
            require,
            deny,
            None,
            None,
            1,
            models=models,
            blueprints=blueprints,
            search=search,
            deny_children=deny_children,
            allow=allow,
            do_order=False,
        ),
        sql.SQL("  )"),
        sql.SQL(") AS found"),
    ]
    query = sql.Composed(parts)
    _log_query(query)
    curs.execute(query)
    return bool(curs.fetchone()["found"])


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
    deny_children: list[dict] | None = None,
    allow: list[dict] | None = None,
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
            deny_children=deny_children,
            allow=allow,
        ),
        sql.SQL("  )"),
        sql.SQL("  ORDER BY bptags.blueprint_id"),
    ]
    query = sql.Composed(parts)
    _log_query(query)
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
    deny_children: list[dict] | None = None,
    allow: list[dict] | None = None,
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
            deny_children=deny_children,
            allow=allow,
        ),
        sql.SQL("  )"),
        sql.SQL("  ORDER BY bpi.blueprint_id"),
    ]
    query = sql.Composed(parts)
    _log_query(query)
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
    deny_children: list[dict] | None = None,
    allow: list[dict] | None = None,
) -> int:
    """How many blueprints match this predicate?

    The guide asks this once per part, to say whether there is more
    than one piece behind a recommendation — "dungeon stone" leaves
    exactly one wall at this size and "towne" leaves six, and only the
    second is worth opening a dialog over.

    Unordered, like the existence query above and for the same reason:
    sorting every match in order to count them is the expensive half
    of a question that never looks at what it found.
    """
    parts = [
        sql.SQL("SELECT COUNT(*)"),
        sql.SQL("  FROM blueprints"),
        sql.SQL("  WHERE blueprints.id IN ("),
        _query_tags_basics(
            accept,
            require,
            deny,
            do_limit=False,
            do_order=False,
            models=models,
            blueprints=blueprints,
            search=search,
            deny_children=deny_children,
            allow=allow,
        ),
        sql.SQL("  )"),
    ]
    query = sql.Composed(parts)
    _log_query(query)
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
    deny_children: list[dict] | None = None,
    allow: list[dict] | None = None,
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
            deny_children=deny_children,
            allow=allow,
        ),
        sql.SQL("  )"),
        sql.SQL(
            "    AND blueprints.blueprint_name < "
            "(SELECT blueprint_name FROM blueprints WHERE id = {first})"
        ).format(first=sql.Literal(first)),
    ]
    query = sql.Composed(parts)
    _log_query(query)
    curs.execute(query)
    return curs.fetchone()["count"]


def tag_search_namespace_facets(
    curs: cursor,
    accept: list[str],
    require: list[str],
    deny: list[str],
    namespace: str,
    models: bool = True,
    blueprints: bool = False,
    search: str | None = None,
    deny_children: list[dict] | None = None,
    allow: list[dict] | None = None,
) -> list[dict]:
    """Tags under `namespace` carried by what this predicate matches.

    What a guide offers as answers, rather than a list somebody typed
    into a fixture. Two things follow from deriving it: an option the
    catalog does not have is never offered, and one it gains later
    appears without anyone editing a guide.

    Counted, because a question with 240 answers behind one of them
    and 4 behind another is worth showing that way, and ordered by the
    tag so the list does not reshuffle as counts drift.
    """
    parts = [
        # The description comes along for the ride. A derived answer
        # has no hand-written blurb by definition, and the catalog
        # already explains its own tags — so a connector added next
        # year arrives with its explanation rather than as a bare word.
        sql.SQL("SELECT COUNT(*) AS tag_count, t.tag,"),
        sql.SQL("       MIN(d.description) AS description"),
        sql.SQL("  FROM tags AS t"),
        sql.SQL("  LEFT JOIN tag_descriptions AS d ON d.tag = t.tag"),
        sql.SQL("  WHERE t.blueprint_id IN ("),
        _query_tags_basics(
            accept,
            require,
            deny,
            do_limit=False,
            do_order=False,
            models=models,
            blueprints=blueprints,
            search=search,
            deny_children=deny_children,
            allow=allow,
        ),
        sql.SQL("  )"),
        # The namespace itself is not an answer — `connection` is the
        # question. Everything strictly beneath it is.
        sql.SQL("    AND t.tag @> {ns} AND t.tag[1] = {first}").format(
            ns=sql.Literal(namespace.split("|")),
            first=sql.Literal(namespace.split("|")[0]),
        ),
        sql.SQL("    AND t.tag[1:{depth}] = {ns}").format(
            depth=sql.Literal(len(namespace.split("|"))),
            ns=sql.Literal(namespace.split("|")),
        ),
        # Immediate children only. `connection|magnetic` and
        # `connection|magnetic|flex` sit on the same 125 bases, so
        # offering both is offering the same answer twice — and a
        # variant belongs to the question about its parent, not to the
        # question about the family.
        sql.SQL("    AND array_length(t.tag, 1) = {depth}").format(
            depth=sql.Literal(len(namespace.split("|")) + 1)
        ),
        sql.SQL("  GROUP BY t.tag"),
        sql.SQL("  ORDER BY t.tag"),
    ]
    query = sql.Composed(parts)
    _log_query(query)
    curs.execute(query)
    return [
        {
            "tag": array_to_tag(row["tag"]),
            "count": row["tag_count"],
            "blurb": row["description"],
        }
        for row in curs.fetchall()
    ]


def tag_search_namespace_combinations(
    curs: cursor,
    accept: list[str],
    require: list[str],
    deny: list[str],
    namespace: str,
    exclude: list[str] | None = None,
    models: bool = True,
    blueprints: bool = False,
    search: str | None = None,
    deny_children: list[dict] | None = None,
    allow: list[dict] | None = None,
) -> list[dict]:
    """The distinct *sets* of tags under `namespace` that pieces carry.

    Not each tag on its own, which is what
    `tag_search_namespace_facets` gives: the whole combination a piece
    actually has, so "OpenLOCK with magnets" and "OpenLOCK topless
    without" are two answers rather than three overlapping questions.

    Some pairings do not exist — nothing is both topless and
    unsupported — and asking about each tag separately cannot say so.
    Asking which combination you want cannot express it in the first
    place.

    `exclude` drops tags that only add noise: every magnetic base in
    the catalog is also `magnetic|flex`, so listing both doubles the
    label and distinguishes nothing. It drops the whole subtree, not
    the one tag — a question about how a wall clips *down* has no use
    for `connection|side` and none for a side system nobody has
    invented yet, and a hand-written list of the ones that exist today
    is the thing that goes stale.
    """
    excluded = exclude or []
    depth = len(namespace.split("|"))
    parts = [
        sql.SQL("SELECT combo, COUNT(*) AS piece_count FROM ("),
        sql.SQL("  SELECT t.blueprint_id,"),
        sql.SQL(
            "         array_agg(array_to_string(t.tag, '|') ORDER BY t.tag) AS combo"
        ),
        sql.SQL("    FROM tags AS t"),
        sql.SQL("    WHERE t.blueprint_id IN ("),
        _query_tags_basics(
            accept,
            require,
            deny,
            do_limit=False,
            do_order=False,
            models=models,
            blueprints=blueprints,
            search=search,
            deny_children=deny_children,
            allow=allow,
        ),
        sql.SQL("    )"),
        sql.SQL("      AND t.tag @> {ns}").format(ns=sql.Literal(namespace.split("|"))),
        sql.SQL("      AND t.tag[1:{depth}] = {ns}").format(
            depth=sql.Literal(depth), ns=sql.Literal(namespace.split("|"))
        ),
        sql.SQL("      AND array_length(t.tag, 1) > {depth}").format(
            depth=sql.Literal(depth)
        ),
    ]
    for tag in excluded:
        parts.append(
            sql.SQL("      AND NOT (t.tag @> {tag})").format(
                tag=sql.Literal(tag.split("|"))
            )
        )
    parts += [
        sql.SQL("    GROUP BY t.blueprint_id"),
        sql.SQL(" ) AS per_piece"),
        sql.SQL(" GROUP BY combo"),
        sql.SQL(" ORDER BY combo"),
    ]
    query = sql.Composed(parts)
    _log_query(query)
    curs.execute(query)
    return [
        {"tags": list(row["combo"]), "count": row["piece_count"]}
        for row in curs.fetchall()
    ]


def tag_search_tag_count(
    curs: cursor,
    accept: list[str],
    require: list[str],
    deny: list[str],
    models: bool = True,
    blueprints: bool = False,
    search: str | None = None,
    deny_children: list[dict] | None = None,
    allow: list[dict] | None = None,
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
            deny_children=deny_children,
            allow=allow,
        ),
        sql.SQL("  )"),
        sql.SQL("  GROUP BY t.tag"),
    ]
    query = sql.Composed(parts)
    _log_query(query)
    curs.execute(query)
    return curs.fetchall()


def _query_tags_exclusions(
    deny: list[str],
    require: list[str],
    deny_children: list[dict] | None,
    allow: list[dict] | None,
) -> list[sql.Composed | sql.SQL]:
    """The NOT terms: plain denies, and the child sweeps.

    A child sweep means "nothing else under this tag", and what counts
    as "else" is whatever `require` and `allow` did not already ask
    for — that is what `exempt` carries. Order does not matter: every
    term is an AND in the same WHERE clause, so moving them changes
    the SQL and no rows.
    """
    parts: list[sql.Composed | sql.SQL] = []
    for d in deny:
        parts.append(sql.SQL("    AND bp2.id NOT IN ("))
        parts.append(_query_tags_deny([d]))
        parts.append(sql.SQL("    )"))

    exempt = [t["tag"] for t in (require or []) if "tag" in t]
    exempt += [t["tag"] for t in (allow or []) if "tag" in t]
    for parent in deny_children or []:
        if "tag" not in parent:
            continue
        parts.append(sql.SQL("    AND NOT EXISTS ("))
        parts.append(_query_tags_deny_children(parent["tag"], exempt))
        parts.append(sql.SQL("    )"))
    return parts


def _query_tags_types(models: bool, blueprints: bool) -> list[sql.SQL]:
    """Which blueprint types the search is over. Both means either."""
    if models and blueprints:
        return [
            sql.SQL(
                "    AND (bp2.blueprint_type = 'model' "
                "OR bp2.blueprint_type = 'blueprint')"
            )
        ]
    if models:
        return [sql.SQL("    AND bp2.blueprint_type = 'model'")]
    if blueprints:
        return [sql.SQL("    AND bp2.blueprint_type = 'blueprint'")]
    return []


def _query_tags_basics(
    accept: list[str],
    require: list[str],
    deny: list[str],
    next: uuid.UUID | None = None,
    previous: uuid.UUID | None = None,
    limit: int = 20,
    do_limit: bool = True,
    do_order: bool = True,
    models: bool = True,
    blueprints: bool = False,
    search: str | None = None,
    deny_children: list[dict] | None = None,
    allow: list[dict] | None = None,
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

    deny_parts = _query_tags_exclusions(deny, require, deny_children, allow)

    query_parts += _query_tags_types(models, blueprints)
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
    # blueprint_name is not unique — 159 names are shared by two or
    # more records, mostly bases — so ordering by it alone is not a
    # total order and LIMIT picks arbitrarily among the ties. Guides
    # resolve a role with LIMIT 1, so without the id the same
    # selections can recommend a different part after any unrelated
    # write, and a shared guide URL stops meaning one thing.
    # An existence check wants no order at all: the sort runs over
    # every matching row before LIMIT 1 takes one, and "is there
    # anything" does not care which.
    end_parts = []
    if do_order:
        end_parts.append(
            sql.SQL(
                "      ORDER BY bp2.blueprint_name %s, bp2.id %s"
                % ("DESC" if previous else "ASC", "DESC" if previous else "ASC")
            )
        )
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


def _query_tags_deny_children(parent: str, exempt: list[str]) -> sql.Composed:
    """Blueprints carrying any tag *strictly under* `parent`.

    Subtracted from a result set, this is "has nothing below this tag".
    `component|wall` survives it; `component|wall|curved` does not —
    which is how a guide asks for a plain wall rather than listing
    every variant it does not want.

    `exempt` is the tags that survive anyway, and it is why this cannot
    simply be a `deny`: the caller has already said which children it
    wants (`shape|floor|wall`), and those have to survive the sweep.

    Not by ordering. Every term here is an AND in one WHERE clause, so
    moving this block above the `deny` loop or above the includes
    changes the generated SQL and not one row. What does the work is
    `exempt` itself: the sweep is not run *after* the includes, it is
    *told about* them.
    """
    depth = len(parent.split("|"))
    tags_name = f"tags_child_{depth}_neg"
    parts = [
        # Correlated, not a set to subtract. This used to build
        # `DISTINCT bp_neg.id` over every blueprint carrying any tag
        # below the parent and hand it to `NOT IN` — which means
        # materialising most of the catalog for a sweep over a broad
        # parent like `shape` (21,033 tag rows). As `NOT EXISTS` it
        # asks one indexed question per candidate row instead, and the
        # join to blueprints goes with it: a tag only exists if its
        # blueprint does.
        sql.SQL("      SELECT 1"),
        sql.SQL("  FROM tags AS {table}").format(table=sql.Identifier(tags_name)),
        sql.SQL("  WHERE {table}.blueprint_id = bp2.id").format(
            table=sql.Identifier(tags_name)
        ),
        # Redundant with the slice below, and there to be indexable.
        # `tag[1:n] = ...` cannot use the GIN index, so the sweep was
        # a sequential scan of all 81,931 tag rows; `@>` is a
        # containment test the index answers, and ANDing it in front
        # turns the scan into a bitmap index scan — 26.3ms to 3.3ms
        # for `deny_children: [component|wall]`, same 954 rows.
        # Containment is positionless, so it is a superset of the
        # slice and narrows nothing on its own.
        sql.SQL("    AND {table}.tag @> {parent}").format(
            table=sql.Identifier(tags_name),
            parent=sql.Literal(parent.split("|")),
        ),
        sql.SQL("    AND {table}.tag[1:{depth}] = {parent}").format(
            table=sql.Identifier(tags_name),
            depth=sql.Literal(depth),
            parent=sql.Literal(parent.split("|")),
        ),
        sql.SQL("    AND array_length({table}.tag, 1) > {depth}").format(
            table=sql.Identifier(tags_name),
            depth=sql.Literal(depth),
        ),
    ]
    for tag in exempt:
        parts.append(
            sql.SQL("    AND {table}.tag <> {tag}").format(
                table=sql.Identifier(tags_name),
                tag=sql.Literal(tag.split("|")),
            )
        )
    return sql.Composed(parts).join("\n      ")


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
