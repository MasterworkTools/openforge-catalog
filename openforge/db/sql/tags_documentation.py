import uuid

from psycopg import sql
from werkzeug.exceptions import NotFound

from .tag_utils import convert_tag_dict, tag_to_array


def get_tag_documentation(curs, tag_array: list[str], is_live: bool = None):
    """Get documentation for a specific tag.

    Args:
        curs: Database cursor
        tag_array: Tag array to get documentation for
        is_live: If True, only return live documentation.
            If False, only return non-live. If None, return all.
    """
    conditions = [sql.SQL("tag = {}").format(sql.Literal(tag_array))]

    if is_live is not None:
        conditions.append(sql.SQL("is_live = {}").format(sql.Literal(is_live)))

    query = sql.SQL(
        """
SELECT id, tag, document, document_type, is_live, created_at, updated_at
  FROM tag_documentation
  WHERE {}
  ORDER BY created_at DESC
"""
    ).format(sql.SQL(" AND ").join(conditions))
    curs.execute(query)
    return [convert_tag_dict(dict(row)) for row in curs.fetchall()]


def get_tag_documentation_by_id(curs, doc_id: uuid.UUID):
    """Get specific tag documentation entry by ID."""
    query = sql.SQL(
        """
SELECT id, tag, document, document_type, is_live, created_at, updated_at
  FROM tag_documentation
  WHERE id = {doc_id}
"""
    ).format(doc_id=sql.Literal(doc_id))
    curs.execute(query)
    result = curs.fetchone()
    if not result:
        raise NotFound("Tag documentation not found")
    return convert_tag_dict(dict(result))


def create_tag_documentation(
    curs,
    tag_array: list[str],
    document: str,
    document_type: str = "instructions",
    is_live: bool = True,
):
    """Create new documentation for a tag."""
    # If making this document live, first mark existing live documents
    # of the same type as non-live. This prevents unique constraint violations
    if is_live:
        mark_other_documents_non_live(curs, tag_array, document_type, None)

    query = sql.SQL(
        """
INSERT INTO tag_documentation (tag, document, document_type, is_live)
  VALUES ({tag_array}, {document}, {document_type}, {is_live})
  RETURNING id, tag, document, document_type, is_live, created_at, updated_at
"""
    ).format(
        tag_array=sql.Literal(tag_array),
        document=sql.Literal(document),
        document_type=sql.Literal(document_type),
        is_live=sql.Literal(is_live),
    )
    curs.execute(query)
    return convert_tag_dict(dict(curs.fetchone()))


def update_tag_documentation(
    curs,
    doc_id: uuid.UUID,
    document: str,
    document_type: str = None,
    is_live: bool = None,
):
    """Update specific tag documentation entry."""
    # First get the current document to determine the final document_type
    # and tag_array
    current_doc = get_tag_documentation_by_id(curs, doc_id)
    final_document_type = document_type or current_doc["document_type"]
    # Convert tag back to array if it's a string
    # (convert_tag_dict converts to pipe-delimited)
    tag_array = (
        tag_to_array(current_doc["tag"])
        if isinstance(current_doc["tag"], str)
        else current_doc["tag"]
    )

    # If making this document live, first mark existing live documents
    # of the same type as non-live. This prevents unique constraint violations
    if is_live:
        mark_other_documents_non_live(curs, tag_array, final_document_type, doc_id)

    update_parts = [sql.SQL("document = {}").format(sql.Literal(document))]

    if document_type is not None:
        update_parts.append(
            sql.SQL("document_type = {}").format(sql.Literal(document_type))
        )

    if is_live is not None:
        update_parts.append(sql.SQL("is_live = {}").format(sql.Literal(is_live)))

    query = sql.SQL(
        """
UPDATE tag_documentation
  SET {}, updated_at = CURRENT_TIMESTAMP
  WHERE id = {}
  RETURNING id, tag, document, document_type, is_live, created_at, updated_at
"""
    ).format(sql.SQL(", ").join(update_parts), sql.Literal(doc_id))
    curs.execute(query)

    result = curs.fetchone()
    if not result:
        raise NotFound("Tag documentation not found")
    return convert_tag_dict(dict(result))


def delete_tag_documentation(curs, doc_id: uuid.UUID):
    """Delete specific tag documentation entry."""
    query = sql.SQL(
        """
DELETE FROM tag_documentation
  WHERE id = {doc_id}
  RETURNING id
"""
    ).format(doc_id=sql.Literal(doc_id))
    curs.execute(query)
    result = curs.fetchone()
    if not result:
        raise NotFound("Tag documentation not found")
    return dict(result)


def get_all_tag_documentation(curs):
    """Get all tag documentation."""
    query = sql.SQL(
        """
SELECT id, tag, document, document_type, created_at, updated_at
  FROM tag_documentation
  ORDER BY tag, created_at DESC
"""
    )
    curs.execute(query)
    return [convert_tag_dict(dict(row)) for row in curs.fetchall()]


def get_tag_documentation_by_tag_prefix(curs, tag):
    """Get tag documentation by tag, including child tags (prefix match)."""
    tag_arr = tag_to_array(tag)
    n = len(tag_arr)
    query = sql.SQL(
        """
SELECT id, tag, document, document_type, created_at, updated_at
  FROM tag_documentation
  WHERE tag[1:{n}] = {prefix}
  ORDER BY array_length(tag, 1), tag, created_at DESC
"""
    ).format(n=sql.Literal(n), prefix=sql.Literal(tag_arr))
    curs.execute(query)
    return [convert_tag_dict(dict(row)) for row in curs.fetchall()]


def get_tag_documentation_for_blueprint(
    curs, blueprint_id: uuid.UUID, is_live: bool = None
):
    """Get documentation for all tags associated with a blueprint.

    Args:
        curs: Database cursor
        blueprint_id: UUID of the blueprint to get tag documentation for
        is_live: If True, only return live documentation.
            If False, only return non-live. If None, return all.

    Returns:
        dict: Mapping of tag string (pipe-delimited) to list of documentation
    """
    conditions = [sql.SQL("t.blueprint_id = {}").format(sql.Literal(blueprint_id))]

    if is_live is not None:
        conditions.append(sql.SQL("td.is_live = {}").format(sql.Literal(is_live)))

    query = sql.SQL(
        """
SELECT td.id, td.tag, td.document, td.document_type, td.is_live,
       td.created_at, td.updated_at
  FROM tag_documentation td
  INNER JOIN tags t ON td.tag = t.tag
  WHERE {}
  ORDER BY td.tag, td.created_at DESC
"""
    ).format(sql.SQL(" AND ").join(conditions))

    curs.execute(query)
    results = [convert_tag_dict(dict(row)) for row in curs.fetchall()]

    # Group results by tag
    tag_documentation = {}
    for result in results:
        tag_string = result["tag"]  # This is already converted to pipe-delimited string
        if tag_string not in tag_documentation:
            tag_documentation[tag_string] = []
        tag_documentation[tag_string].append(result)

    return tag_documentation


def mark_other_documents_non_live(
    curs, tag_array: list[str], document_type: str, exclude_doc_id: uuid.UUID = None
):
    """Mark other documents of the same type as non-live.

    This function is used when making a document live to ensure only one live document
    of each type exists per tag.

    Args:
        curs: Database cursor
        tag_array: Tag array
        document_type: Type of document (e.g., 'instructions')
        exclude_doc_id: ID of the document to exclude from being marked non-live
            (None for new documents)
    """
    if exclude_doc_id is None:
        # For new documents, mark all existing live documents as non-live
        query = sql.SQL(
            """
UPDATE tag_documentation
SET is_live = false, updated_at = CURRENT_TIMESTAMP
WHERE tag = {}
AND document_type = {}
AND is_live = true
"""
        ).format(sql.Literal(tag_array), sql.Literal(document_type))
    else:
        # For existing documents, exclude the current document
        query = sql.SQL(
            """
UPDATE tag_documentation
SET is_live = false, updated_at = CURRENT_TIMESTAMP
WHERE tag = {}
AND document_type = {}
AND is_live = true
AND id != {}
"""
        ).format(
            sql.Literal(tag_array),
            sql.Literal(document_type),
            sql.Literal(exclude_doc_id),
        )
    curs.execute(query)
