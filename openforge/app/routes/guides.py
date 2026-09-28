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

None of that is shipped. This paragraph is the reasoning for a change
nobody has made, kept because the reasoning is the expensive part and
the trap it names (`CachingDisabled` silently discarding the header)
is the kind of thing that gets rediscovered the hard way. The work
itself is `openforge_catalog-lrk`, alongside the rest of what these
endpoints cost.

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

import openforge.db.sql.blueprints as blueprint_sql
import openforge.db.sql.guides as guide_sql
import openforge.db.sql.images as image_sql
import openforge.db.sql.tags as tag_sql
from openforge.guides.resolve import (
    KEY_CHARS,
    GuideSelectionError,
    listed,
    quoted,
    resolve,
    to_tag_query,
)


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
    rather than to these four.
    """
    # A NUL never reaches the server: `sql.Literal` raises `DataError`
    # while building the statement, which is an unhandled 500 with an
    # HTML body for a key that self-evidently names no stored guide.
    # `%00` in a path is reachable from a hand-edited URL, so it is
    # answered the same way any other unknown key is.
    if "\x00" in guide_key:
        abort(make_response(jsonify({"error": f"No guide {guide_key!r}"}), 404))
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
                    find_pinned=_pinned_finder(curs),
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
                # `except ValueError` would NOT behave identically, and
                # a test says so now: `reject_bad_recommendations`
                # (`openforge/guides/validation.py`, called at the top
                # of `resolve`) raises a bare one for a rotted
                # `default`, and widening this catch would swallow it
                # back into a 400 and silently undo that fix. This is
                # the edit the comment exists to warn off, and it is
                # the only thing holding that rule — nothing deeper
                # enforces it.
                _log_bad_request(guide_key, e)
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
                # No `facets`/`combinations`: those only feed the
                # derived `choices` list, which this response does not
                # carry. Measured, the saving is two statements a
                # request, all of it `combinations` — `facets` never ran
                # on this endpoint at all — and the responses are
                # byte-identical either way. Small, but it is the
                # endpoint whose own docstring is an apology for what it
                # costs. `unavailable` and `because` come from `exists`
                # and are unaffected.
                #
                # No absolute counts here on purpose: they were quoted
                # three times and stale three times, because later
                # commits kept moving them. The delta and the reason
                # survive a rebase; `52 → 50` did not.
                resolved = resolve(
                    guide["document"],
                    _selections_from_request(),
                    _candidate_finder(curs),
                    exists=_existence_finder(curs),
                    find_pinned=_pinned_finder(curs),
                )
            except GuideSelectionError as e:
                _log_bad_request(guide_key, e)
                return jsonify({"error": str(e)}), 400
            questions = resolved["steps"] + resolved["refinements"]
            count = _counter(curs)
            return jsonify(
                {
                    # How many pieces each part could have been. One
                    # is a decision the guide made; more than one is a
                    # choice somebody might want to make themselves.
                    "options": {
                        part["role"]: count(part["query"])
                        for part in resolved["parts"]
                        if part["blueprint"] is not None and not part["pinned"]
                    },
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


def _log_bad_request(guide_key: str, error: Exception) -> None:
    """Record a refused request, because nothing else does.

    A 400 leaves no trace: no alarm, no metric, and CloudWatch is this
    Lambda's only forensics. Two bugs in this feature hid there for a
    round each — a rotted recommendation blamed on the visitor, and an
    over-long value reported under the wrong key — and both looked
    exactly like people typing bad URLs.

    WARNING for the same reason `_pinned_finder` uses it: nothing sets
    `LOG_LEVEL` in the production Lambda, so INFO would be evaluated
    and discarded.

    Bounded here rather than at each raise. Ten messages feed this, and
    the claim that all of them had been through `_shown` was true in
    effect and false in its reason — `_reject_unknown_selections` has
    its own quoting, and the refinement refusals rely on a cap applied
    several frames earlier in another module. A bound at the sink holds
    for the eleventh message too.
    """
    current_app.logger.warning(
        "guide %s refused a request: %s",
        quoted(guide_key, SELECTION_CHARS),
        quoted(str(error), MESSAGE_CHARS),
    )


#: Cap for a whole refusal message on its way to CloudWatch. Ample for
#: every message the module raises; it exists so that a future one
#: cannot quietly become unbounded.
MESSAGE_CHARS = 1000


#: Generous cap for one selection. The longest the guide itself ever
#: produces is a tag or an md5; this is well above both, so it bounds
#: what a hand-edited URL can send to Postgres without constraining
#: anything real.
SELECTION_CHARS = 256


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

    The NUL and length checks are here, at the one place every endpoint
    reads the query string, rather than at each thing a selection can
    become. A selection reaches the database as a `sql.Literal`, and
    that raises `DataError` on a NUL *while building the statement* —
    an unhandled 500 with an HTML body, for a request whose honest
    answer is 400. Length is the same argument in the other direction:
    without a cap a 200KB pin was sent to Postgres in full and answered
    200. Every real selection is a tag, an option key or an md5, so the
    cap is far above anything the guide itself produces.
    """
    repeated = sorted(key for key in request.args if len(request.args.getlist(key)) > 1)
    if repeated:
        raise GuideSelectionError(
            f"answered more than once: {listed(repeated, KEY_CHARS)}"
        )
    selections = request.args.to_dict()
    for key, value in selections.items():
        _reject_bad_selection(what="key", part=key)
        _reject_bad_selection(what=f"the answer to {_shown(key)}", part=value)
    return selections


def _shown(text: str) -> str:
    """`quoted` at the cap a whole selection is allowed."""
    return quoted(text, SELECTION_CHARS)


def _reject_bad_selection(*, what: str, part: str) -> None:
    """Refuse a selection the search cannot be asked about.

    `what` names which half is at fault. Reporting the key for both was
    a false statement in the body: an over-long *value* came back as
    "'part.wall' is longer than 256 characters" about a nine-character
    key.

    The rule comes before the offender. These used to be the only two
    of the ten refusal messages that put an unbounded value in the
    middle and the rule at the end, and the log sink cuts from the
    end — so a NUL and an over-long value were indistinguishable in
    CloudWatch, and the only length left in the line was the message's
    own rather than the value's.
    """
    if "\x00" in part:
        raise GuideSelectionError(f"{what} contains a NUL byte: {_shown(part)}")
    if len(part) > SELECTION_CHARS:
        raise GuideSelectionError(
            f"{what} is longer than {SELECTION_CHARS} characters: {_shown(part)}"
        )


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


def _counter(curs):
    """How many pieces are behind a part's recommendation.

    On the availability endpoint rather than on `resolve`, because it
    is a count per part and `resolve` is what the person is waiting
    for. One means the guide has decided; six means there is a choice
    worth opening.
    """

    def count(predicate: dict) -> int:
        return tag_sql.tag_search_blueprint_count(curs, **to_tag_query(predicate))

    return count


#: An md5 is 32 hex characters; anything longer is not one.
MD5_CHARS = 32


def _pinned_finder(curs):
    """The piece someone pinned to a role, by md5.

    A miss is not an error. A guide URL outlives the catalog it was
    made from, and a pin whose file has been deleted or replaced
    should fall back to what the guide would have recommended anyway
    — a page of parts is a better answer to a stale link than a 404.

    Logged all the same. The intended case — an old link to a file
    that has since been rescanned — and a caller bug that sends a
    uuid where an md5 belongs produce the identical silent `None`,
    and only one of those is fine.

    At WARNING, not INFO. A pin that no longer resolves is an anomaly
    rather than a milestone, and more practically: nothing sets
    `LOG_LEVEL` in the production Lambda, so `app.logger` is NOTSET
    under a root logger the runtime leaves at WARNING. An INFO line
    here was evaluated and discarded in the one place it was written
    for.

    `%r`, and the value truncated, because the md5 is a query
    parameter: a raw `%s` of `?part.wall=%0Aforged` splits the log
    line, and whitespace-only input logged as nothing at all.
    """

    def find_pinned(md5: str) -> dict | None:
        try:
            found = blueprint_sql.get_blueprint_by_md5(curs, md5)
        except NotFound:
            current_app.logger.warning(
                "guide pin %r matches no blueprint", md5[:MD5_CHARS]
            )
            return None
        _attach_tags(curs, [found])
        return found

    return find_pinned


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

    That pass asks "is there anything at all" about fifty times a
    request — 48 on the shipped wall guide — and never looks at what
    it found, so fetching each candidate's tags is a second round trip
    per question for something nobody reads.
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
