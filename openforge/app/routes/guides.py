"""Guide endpoints: list, fetch, resolve.

`resolve` is the one that matters. It takes the selections a person has
made and returns the parts they should print, so the payload stays the
size of a parts list rather than the size of the catalog — see
docs/design/guided-builds.md and `openforge_catalog-i7c`.

It is a GET, where the design document proposed a POST. Resolving is a
pure function of the guide key and the selections, the selections are
already a query string (that is what the shareable URL is), and
nothing is written, so a POST would protect nothing.

What the GET buys today is the *option*, not the saving: the app sets
no cache headers anywhere, so a repeat of an already-resolved state
still costs an invocation. Production does sit behind CloudFront — the
distribution lives in openforge-infra-frontend rather than this repo's
terraform, which is why it is easy to miss — but `/api/*` there runs
the managed `CachingDisabled` policy, which pins every TTL to zero and
ignores the origin's `Cache-Control` outright. So a header alone buys
browser caching, which is most of this endpoint's traffic shape, and
edge caching additionally needs a cache-policy change in that repo.
The header to reach for is a short `Cache-Control: public,
max-age=...`, not an `ETag`: a conditional request still runs this
function to compute the validator, so it would save egress, which R2
already gives away, rather than invocations, which are the cost here.

A selection this API does not recognise is a 400, which makes the
shareable URL a narrower thing than a browser URL: the guide page must
build the query from the keys the guide document defines rather than
forwarding `window.location.search`, or a link that has been through
Facebook or a campaign tracker arrives carrying `fbclid` and answers
400. Ignoring unknown keys instead would make a typo'd selection
resolve silently against the wrong state, which is the failure this
module refuses everywhere else. `openforge_catalog-0bz` carries the
constraint.
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

    Every error these endpoints *raise deliberately* is a JSON body,
    and a client that parses one has to special-case the other. An
    unhandled exception is still werkzeug's HTML 500; no app-wide JSON
    error handler exists, and adding one is a change to every route
    rather than to these three.
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
            try:
                resolved = resolve(
                    guide["document"],
                    _selections_from_request(),
                    _candidate_finder(curs),
                    facets=_facet_finder(curs),
                    combinations=_combination_finder(curs),
                )
            except GuideSelectionError as e:
                # Both the query-string read and the engine raise this,
                # and the 400 is right for both because the invariant
                # is that GuideSelectionError means the *selections*
                # are wrong — never that the stored document is. A
                # guide that no longer validates must keep reaching the
                # 500 it deserves, so nothing inside this block should
                # start raising it for a document fault.
                #
                # Narrower than it looks today: GuideSelectionError is
                # a ValueError, and nothing reachable here raises a
                # bare one, so `except ValueError` would behave
                # identically and no test could tell. It stops being
                # identical the moment anything in this block
                # validates the document — which is the edit this
                # comment exists to warn off.
                return jsonify({"error": str(e)}), 400
            _attach_images(curs, resolved["parts"])
            return jsonify(resolved)


def guide_availability(guide_key: str):
    """Which offered answers would empty a part, and which answer did it.

    Its own endpoint because it costs several times what the parts
    cost — a predicate per role per offered answer — and the parts are
    what the person is waiting to see. The page renders on `resolve`
    and drops the dead answers when this lands.

    Same selections, same errors, same 404: it is the same question
    asked about the answers rather than about the pieces.
    """
    with current_app.db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide = _guide_or_404(curs, guide_key)
            try:
                resolved = resolve(
                    guide["document"],
                    _selections_from_request(),
                    _candidate_finder(curs),
                    exists=_existence_finder(curs),
                    facets=_facet_finder(curs),
                    combinations=_combination_finder(curs),
                )
            except GuideSelectionError as e:
                return jsonify({"error": str(e)}), 400
            questions = resolved["steps"] + resolved["refinements"]
            return jsonify(
                {
                    "unavailable": {
                        question["key"]: question["unavailable"]
                        for question in questions
                        if question["unavailable"]
                    },
                    # Which earlier answer is responsible for each, so
                    # the page can say why an answer is not there
                    # rather than simply not have it.
                    "because": {
                        question["key"]: question["because"]
                        for question in questions
                        if question.get("because")
                    },
                }
            )


def _selections_from_request() -> dict:
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
    silently.

    Making it hold everywhere needs `multi_value_headers` on the
    target group *and* an adapter that reads
    `multiValueQueryStringParameters`, which this one does not —
    tracked as `openforge_catalog-bji` rather than bodged. Do not do
    half of it: the target-group setting *replaces*
    `queryStringParameters` rather than adding a sibling, and
    `aws_lambda_wsgi` subscripts that key unconditionally, so flipping
    the checkbox alone raises `KeyError` out of `lambda_handler` for
    every request to the API — a 502 with no body, on every route,
    not just these.

    Raises `GuideSelectionError` rather than returning an error to be
    checked, because a question answered twice *is* a selection the
    guide cannot act on, and `resolve_guide` already answers 400 to
    that. A second error channel doing the same job is the kind of
    thing the next endpoint copies.
    """
    repeated = sorted(key for key in request.args if len(request.args.getlist(key)) > 1)
    if repeated:
        raise GuideSelectionError(f"answered more than once: {', '.join(repeated)}")
    return request.args.to_dict()


def _candidate_finder(curs):
    """Adapt the tag search to what the resolution engine expects.

    The engine speaks in plain tag strings; `tag_search_blueprints`
    wants the `tag_query` shape, and does the ordering and the
    deprecated / models filtering the guide wants anyway.
    """

    def find_candidates(predicate: dict) -> list[dict]:
        # to_tag_query is the one place a guide predicate becomes the
        # shape the search takes. Passing the bare strings straight
        # through would be ignored silently rather than rejected.
        #
        # One row, because the engine narrows and asks again rather
        # than paging: a limit that varies would be flexibility with
        # no second value.
        found = tag_sql.tag_search_blueprints(curs, **to_tag_query(predicate), limit=1)
        _attach_tags(curs, found)
        return found

    return find_candidates


def _facet_finder(curs):
    """What answers a namespace question actually has, here and now.

    Given the predicate that narrows a part, the tags it carries under
    a namespace — so a guide offers the connectors that exist for
    *these* bases rather than a list somebody wrote down once.
    """

    def facets(predicate: dict, namespace: str) -> list[dict]:
        return tag_sql.tag_search_namespace_facets(
            curs, **to_tag_query(predicate), namespace=namespace
        )

    return facets


def _combination_finder(curs):
    """The distinct sets of tags a namespace's pieces actually carry."""

    def combinations(predicate: dict, namespace: str, exclude: list) -> list[dict]:
        return tag_sql.tag_search_namespace_combinations(
            curs, **to_tag_query(predicate), namespace=namespace, exclude=exclude
        )

    return combinations


def _existence_finder(curs):
    """The same search without the tags, for the availability pass.

    That pass asks "is there anything at all" around thirty times a
    request and never looks at what it found, so fetching each
    candidate's tags is a second round trip per question for something
    nobody reads.
    """

    def exists(predicate: dict) -> bool:
        return tag_sql.tag_search_blueprint_exists(curs, **to_tag_query(predicate))

    return exists


def _attach_tags(curs, blueprints: list[dict]) -> None:
    """Put each blueprint's tags on it, as plain strings.

    Two callers need these and neither can get them from the search.
    A role with `match` has to read the size of the part it sits under,
    which is not known until that part is chosen; and the page shows
    the tags beside each piece, because the fastest way to see that a
    guide is recommending the wrong thing is to read what it actually
    asked for.

    One query per successful search rather than one batch at the end:
    the engine needs them mid-resolution, and a search that found
    nothing does not ask.
    """
    if not blueprints:
        return
    by_blueprint = {}
    for tag in tag_sql.get_tags_for_blueprints(
        curs, [blueprint["id"] for blueprint in blueprints]
    ):
        by_blueprint.setdefault(tag["blueprint_id"], []).append(tag["tag"])
    for blueprint in blueprints:
        blueprint["tags"] = by_blueprint.get(blueprint["id"], [])


def _attach_images(curs, parts: list[dict]) -> None:
    """Give each recommended part its images, in one query."""
    blueprint_ids = [part["blueprint"]["id"] for part in parts if part["blueprint"]]
    images = image_sql.get_images_for_blueprints(curs, blueprint_ids)
    for part in parts:
        if not part["blueprint"]:
            continue
        part["blueprint"]["images"] = [
            image
            for image in images
            if image["blueprint_id"] == part["blueprint"]["id"]
        ]
