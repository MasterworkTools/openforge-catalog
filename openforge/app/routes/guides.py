"""Guide endpoints: list, fetch, resolve.

`resolve` is the one that matters. It takes the selections a person has
made and returns the parts they should print, so the payload stays the
size of a parts list rather than the size of the catalog — see
docs/design/guided-builds.md and `openforge_catalog-i7c`.

It is a GET, where the design document proposed a POST. Resolving is a
pure function of the guide key and the selections, the selections are
already a query string (that is what the shareable URL is), and
nothing is written, so a POST would protect nothing.

What the GET buys today is the *option*, not the saving. `/api` is an
ALB target with no CloudFront in front of it and the app sets no cache
headers anywhere, so a repeat of an already-resolved state still costs
an invocation. The point is that collecting that saving later is a
response header rather than an API change — and the header to reach
for is a short `Cache-Control: public, max-age=...`, not an `ETag`: a
conditional request still runs this function to compute the validator,
so it would save egress, which R2 already gives away, rather than
invocations, which are the cost here.
"""

from flask import abort, current_app, jsonify, make_response, request
from psycopg.rows import dict_row
from werkzeug.exceptions import NotFound

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
            return jsonify(_guide_or_404(curs, guide_key))


def _guide_or_404(curs, guide_key: str) -> dict:
    """Fetch a guide, or abort with JSON rather than werkzeug's HTML.

    Every other error these endpoints answer with is a JSON body, and
    a client that parses one has to special-case the other.
    """
    try:
        return guide_sql.get_guide_by_key(curs, guide_key)
    except NotFound:
        abort(make_response(jsonify({"error": f"No guide {guide_key!r}"}), 404))


def resolve_guide(guide_key: str):
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            # The guide is looked up before the query string is read:
            # telling someone their selections are wrong about a guide
            # that does not exist sends them looking in the wrong
            # place.
            guide = _guide_or_404(curs, guide_key)
            selections, error = _selections_from_request()
            if error:
                return error
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

    Behind the ALB this check cannot fire, because an ALB collapses a
    repeated key to its last value before Lambda sees the request and
    the adapter reads `queryStringParameters` as a plain map. So the
    guarantee holds for the development server and for anything else
    that speaks WSGI directly, and in production the last value wins
    silently. Making it hold everywhere needs
    `multi_value_headers` on the target group *and* an adapter that
    reads `multiValueQueryStringParameters`, which this one does not —
    tracked rather than bodged.
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
