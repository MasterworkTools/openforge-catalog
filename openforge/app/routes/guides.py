"""Guide endpoints: list, fetch, resolve.

`resolve` is the one that matters. It takes the selections a person has
made and returns the parts they should print, so the payload stays the
size of a parts list rather than the size of the catalog — see
docs/design/guided-builds.md and `openforge_catalog-i7c`.

It is a GET, where the design document proposed a POST. Resolving is a
pure function of the guide key and the selections, the selections are
already a query string (that is what the shareable URL is), and a body
version of the same state would only cost cacheability: every repeat of
a state someone has already resolved becomes another Lambda invocation
and another round of catalog queries. Nothing is written, so there is
nothing a POST would protect.
"""

from flask import current_app, jsonify, request
from psycopg.rows import dict_row

import openforge.db.sql.guides as guide_sql
import openforge.db.sql.images as image_sql
import openforge.db.sql.tags as tag_sql
from openforge.guides.resolve import GuideSelectionError, resolve, to_tag_query


def get_guides():
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guides = guide_sql.get_all_guides(curs)
            if not guides:
                return jsonify({"guides": []}), 404
            return jsonify({"guides": guides})


def get_guide(guide_key: str):
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            return jsonify(guide_sql.get_guide_by_key(curs, guide_key))


def resolve_guide(guide_key: str):
    selections, error = _selections_from_request()
    if error:
        return error
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide = guide_sql.get_guide_by_key(curs, guide_key)
            try:
                resolved = resolve(
                    guide["document"], selections, _candidate_finder(curs)
                )
            except GuideSelectionError as e:
                return jsonify({"error": str(e)}), 400
            _attach_images(curs, resolved["parts"])
            return jsonify(resolved)


def _selections_from_request():
    """Read the selections out of the query string.

    A repeated parameter is refused rather than resolved on one of its
    values: `?method=a&method=b` is a URL that does not describe a
    state this guide can be in, and silently picking one would hand
    back a parts list for a question the person did not answer that
    way.
    """
    repeated = sorted(key for key in request.args if len(request.args.getlist(key)) > 1)
    if repeated:
        return None, (
            jsonify({"error": f"answered more than once: {', '.join(repeated)}"}),
            400,
        )
    return request.args.to_dict(), None


def _candidate_finder(curs):
    """Adapt the tag search to what the resolution engine expects.

    The engine speaks in plain tag strings; `tag_search_blueprints`
    wants the `tag_query` shape, and does the ordering and the
    deprecated / models filtering the guide wants anyway.
    """

    def find_candidates(predicate: dict, limit: int) -> list[dict]:
        # to_tag_query is the one place a guide predicate becomes the
        # shape the search takes. Passing the bare strings straight
        # through would be ignored silently rather than rejected.
        return tag_sql.tag_search_blueprints(
            curs, **to_tag_query(predicate), limit=limit
        )

    return find_candidates


def _attach_images(curs, parts: list[dict]) -> None:
    """Give each recommended part its images, in one query."""
    blueprint_ids = [part["blueprint"]["id"] for part in parts if part["blueprint"]]
    if not blueprint_ids:
        return
    images = image_sql.get_images_for_blueprints(curs, blueprint_ids)
    for part in parts:
        if not part["blueprint"]:
            continue
        part["blueprint"]["images"] = [
            image
            for image in images
            if image["blueprint_id"] == part["blueprint"]["id"]
        ]
