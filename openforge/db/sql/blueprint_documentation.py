import uuid

from psycopg import sql
from werkzeug.exceptions import NotFound

# Default recursion depth for changelog history queries
DEFAULT_CHANGELOG_RECURSION_DEPTH = 10


def get_blueprint_documentation(curs, blueprint_id: uuid.UUID, is_live: bool = None):
    """Get all documentation for a blueprint.

    Args:
        curs: Database cursor
        blueprint_id: UUID of the blueprint
        is_live: If True, only return live documentation.
            If False, only return non-live. If None, return all.
    """
    conditions = [sql.SQL("blueprint_id = {}").format(sql.Literal(blueprint_id))]

    if is_live is not None:
        conditions.append(sql.SQL("is_live = {}").format(sql.Literal(is_live)))

    query = sql.SQL(
        """
SELECT id, blueprint_id, document, document_type, is_live, created_at, updated_at
  FROM blueprint_documentation
  WHERE {}
  ORDER BY created_at DESC
"""
    ).format(sql.SQL(" AND ").join(conditions))
    curs.execute(query)
    return [dict(row) for row in curs.fetchall()]


def get_blueprint_documentation_by_id(curs, doc_id: uuid.UUID):
    """Get specific documentation entry by ID."""
    query = sql.SQL(
        """
SELECT id, blueprint_id, document, document_type, is_live, created_at, updated_at
  FROM blueprint_documentation
  WHERE id = {doc_id}
"""
    ).format(doc_id=sql.Literal(doc_id))
    curs.execute(query)
    result = curs.fetchone()
    if not result:
        raise NotFound("Blueprint documentation not found")
    return dict(result)


def create_blueprint_documentation(
    curs,
    blueprint_id: uuid.UUID,
    document: str,
    document_type: str = "changelog",
    is_live: bool = True,
):
    """Create new documentation for a blueprint."""
    # If making this document live, first mark existing live documents
    # of the same type as non-live. This prevents unique constraint violations
    if is_live:
        mark_other_documents_non_live(curs, blueprint_id, document_type, None)

    query = sql.SQL(
        """
INSERT INTO blueprint_documentation (blueprint_id, document, document_type, is_live)
  VALUES ({blueprint_id}, {document}, {document_type}, {is_live})
  RETURNING id, blueprint_id, document, document_type, is_live, created_at, updated_at
"""
    ).format(
        blueprint_id=sql.Literal(blueprint_id),
        document=sql.Literal(document),
        document_type=sql.Literal(document_type),
        is_live=sql.Literal(is_live),
    )
    curs.execute(query)
    return dict(curs.fetchone())


def update_blueprint_documentation(
    curs,
    doc_id: uuid.UUID,
    document: str,
    document_type: str = None,
    is_live: bool = None,
):
    """Update specific documentation entry."""
    # First get the current document to determine the final document_type
    # and blueprint_id
    current_doc = get_blueprint_documentation_by_id(curs, doc_id)
    final_document_type = document_type or current_doc["document_type"]
    blueprint_id = current_doc["blueprint_id"]

    # If making this document live, first mark existing live documents
    # of the same type as non-live. This prevents unique constraint violations
    if is_live:
        mark_other_documents_non_live(curs, blueprint_id, final_document_type, doc_id)

    update_parts = [sql.SQL("document = {}").format(sql.Literal(document))]

    if document_type is not None:
        update_parts.append(
            sql.SQL("document_type = {}").format(sql.Literal(document_type))
        )

    if is_live is not None:
        update_parts.append(sql.SQL("is_live = {}").format(sql.Literal(is_live)))

    query = sql.SQL(
        """
UPDATE blueprint_documentation
  SET {}, updated_at = CURRENT_TIMESTAMP
  WHERE id = {}
  RETURNING id, blueprint_id, document, document_type, is_live, created_at, updated_at
"""
    ).format(sql.SQL(", ").join(update_parts), sql.Literal(doc_id))
    curs.execute(query)

    result = curs.fetchone()
    if not result:
        raise NotFound("Blueprint documentation not found")
    return dict(result)


def delete_blueprint_documentation(curs, doc_id: uuid.UUID):
    """Delete specific documentation entry."""
    query = sql.SQL(
        """
DELETE FROM blueprint_documentation
  WHERE id = {doc_id}
  RETURNING id
"""
    ).format(doc_id=sql.Literal(doc_id))
    curs.execute(query)
    result = curs.fetchone()
    if not result:
        raise NotFound("Blueprint documentation not found")
    return dict(result)


def get_blueprint_changelog_history(
    curs, blueprint_id: uuid.UUID, limit: int = 10, offset: int = 0
):
    """Get changelog history for blueprint using the SQL function.

    Uses a CTE to call the expensive recursive function only once, then extracts
    both the paginated results and total count from the same result set.
    """
    query = sql.SQL(
        """
WITH history_cte AS (
    SELECT blueprint_id, blueprint_name, changelog, created_at, depth,
           successor_id, deprecated
    FROM get_blueprint_changelog_history({blueprint_id}, {recursion_depth})
)
SELECT
    (SELECT COUNT(*) FROM history_cte) AS total_count,
    (SELECT json_agg(t) FROM (
        SELECT * FROM history_cte
        ORDER BY depth ASC, created_at DESC NULLS LAST
        LIMIT {limit} OFFSET {offset}
    ) t) AS changelogs
"""
    ).format(
        blueprint_id=sql.Literal(blueprint_id),
        recursion_depth=sql.Literal(DEFAULT_CHANGELOG_RECURSION_DEPTH),
        limit=sql.Literal(limit),
        offset=sql.Literal(offset),
    )
    curs.execute(query)
    result = curs.fetchone()

    total_count = result["total_count"]
    changelogs = result["changelogs"] or []  # Handle case where no results

    return {
        "changelogs": changelogs,
        "has_more": (offset + limit) < total_count,
        "total_count": total_count,
    }


def mark_other_documents_non_live(
    curs, blueprint_id: uuid.UUID, document_type: str, exclude_doc_id: uuid.UUID = None
):
    """Mark other documents of the same type as non-live.

    This function is used when making a document live to ensure only one live document
    of each type exists per blueprint.

    Args:
        curs: Database cursor
        blueprint_id: UUID of the blueprint
        document_type: Type of document (e.g., 'instructions')
        exclude_doc_id: ID of the document to exclude from being marked non-live
            (None for new documents)
    """
    if exclude_doc_id is None:
        # For new documents, mark all existing live documents as non-live
        query = sql.SQL(
            """
UPDATE blueprint_documentation
SET is_live = false, updated_at = CURRENT_TIMESTAMP
WHERE blueprint_id = {}
AND document_type = {}
AND is_live = true
"""
        ).format(sql.Literal(blueprint_id), sql.Literal(document_type))
    else:
        # For existing documents, exclude the current document
        query = sql.SQL(
            """
UPDATE blueprint_documentation
SET is_live = false, updated_at = CURRENT_TIMESTAMP
WHERE blueprint_id = {}
AND document_type = {}
AND is_live = true
AND id != {}
"""
        ).format(
            sql.Literal(blueprint_id),
            sql.Literal(document_type),
            sql.Literal(exclude_doc_id),
        )
    curs.execute(query)


def set_changelogs_non_live(curs, blueprint_id: uuid.UUID):
    """Set all changelog documentation for a blueprint to non-live.

    This is used when disconnecting a successor relationship to mark any
    changelog entries on the successor as non-live.

    Args:
        curs: Database cursor
        blueprint_id: UUID of the blueprint whose changelogs should be marked non-live

    Returns:
        int: Number of changelog entries updated
    """
    query = sql.SQL(
        """
UPDATE blueprint_documentation
SET is_live = false, updated_at = CURRENT_TIMESTAMP
WHERE blueprint_id = {} AND document_type = 'changelog'
"""
    ).format(sql.Literal(blueprint_id))
    curs.execute(query)
    return curs.rowcount
