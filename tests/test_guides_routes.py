import copy
import logging

import pytest
from psycopg.rows import dict_row

import openforge.app.routes.guides as guides
import openforge.db.sql.blueprints as blueprint_sql
import openforge.db.sql.guides as guide_sql
import openforge.db.sql.tags as tag_sql
from openforge.app.index import app as flask_app
from tests.test_helpers import create_test_blueprint

WALL_GUIDE = {
    "key": "wall",
    "title": "How do I make a wall?",
    "summary": "Three ways.",
    "steps": [
        {
            "key": "method",
            "prompt": "How do you want to build it?",
            "options": [
                {
                    "key": "separate-wall",
                    "title": "Separate wall",
                    "roles": {"floor": None, "wall": None},
                    "tags": {"require": ["build|separate wall"]},
                }
            ],
        }
    ],
    "roles": {
        "wall": {
            "title": "Wall",
            "query": {"require": ["shape|wall"]},
            "prefer": ["connection|openforge"],
        },
        "floor": {"title": "Floor", "query": {"require": ["shape|floor"]}},
    },
    "refinements": [
        {
            "key": "texture",
            "role": "*",
            "prompt": "Texture",
            "from_namespace": "texture",
        }
    ],
}


@pytest.fixture
def client(test_db):
    flask_app.config["TESTING"] = True
    flask_app.db = test_db
    with flask_app.test_client() as client:
        yield client


@pytest.fixture
def wall_guide(test_db):
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            return guide_sql.upsert_guide(curs, WALL_GUIDE)


def make_blueprint(test_db, name, tags):
    """A searchable model: the guide only ever recommends models."""
    data = create_test_blueprint(blueprint_name=name, blueprint_type="model")
    del data["tags"]
    del data["images"]
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            blueprint = blueprint_sql.insert_blueprint(curs, data, words=[])
            for tag in tags:
                tag_sql.insert_tag(curs, blueprint["id"], tag)
            return blueprint


@pytest.fixture
def catalog(test_db):
    """Enough variety that a query can pick wrongly.

    Two textures rather than one, so a refinement can empty some roles
    and not others — the mixed parts list the engine is built to
    produce and the route has to survive. And one wall that is not a
    separate wall, so the method option's predicate excludes something
    rather than being satisfied by everything present.
    """
    return {
        # Not asserted on directly, and not dead: it is what `prefer`
        # has to beat. Delete it and the role's `prefer:
        # connection|openforge` still picks the openforge wall, so
        # three tests go on passing with the preference gone.
        "plain": make_blueprint(
            test_db,
            "a plain wall",
            ["build|separate wall", "shape|wall", "texture|cave"],
        ),
        "openforge": make_blueprint(
            test_db,
            "b openforge wall",
            [
                "build|separate wall",
                "shape|wall",
                "connection|openforge",
                "texture|cave",
            ],
        ),
        "floor": make_blueprint(
            test_db,
            "c floor",
            ["build|separate wall", "shape|floor", "texture|cave"],
        ),
        # A towne wall: the only piece of its texture, so asking for
        # towne leaves the wall role recommended and the floor role
        # empty.
        "towne": make_blueprint(
            test_db,
            "d towne wall",
            [
                "build|separate wall",
                "shape|wall",
                "connection|openforge",
                "texture|towne",
            ],
        ),
        # An s2w wall, which the method option must exclude. Without
        # it every blueprint present satisfies the option's predicate
        # and the predicate could be dropped unnoticed.
        #
        # The leading "a" is load-bearing: candidates come back in
        # blueprint_name order, so this sorts ahead of "b openforge
        # wall" and wins the moment the predicate stops excluding it.
        # Rename it to anything after "b" and dropping the predicate
        # goes unnoticed again.
        "s2w": make_blueprint(
            test_db,
            "a s2w wall",
            ["build|s2w", "shape|wall", "connection|openforge", "texture|cave"],
        ),
    }


def test_listing_guides_carries_titles(client, wall_guide):
    response = client.get("/api/guides")

    assert response.status_code == 200
    assert response.json["guides"][0]["guide_key"] == "wall"
    assert response.json["guides"][0]["title"] == "How do I make a wall?"
    assert response.json["guides"][0]["summary"] == "Three ways."
    # And not the document: the list is a menu, and a guide's steps are
    # the bulk of it.
    assert "document" not in response.json["guides"][0]


def test_listing_no_guides_is_a_404(client):
    response = client.get("/api/guides")

    assert response.status_code == 404
    assert response.json["guides"] == []


def test_fetching_a_guide_returns_its_document(client, wall_guide):
    response = client.get("/api/guides/wall")

    assert response.status_code == 200
    assert response.json["document"]["steps"][0]["key"] == "method"


def test_resolving_recommends_a_part_per_role(client, wall_guide, catalog):
    response = client.get("/api/guides/wall/resolve?method=separate-wall")

    assert response.status_code == 200
    parts = {part["role"]: part for part in response.json["parts"]}
    assert parts["wall"]["blueprint"]["id"] == str(catalog["openforge"]["id"])
    assert parts["floor"]["blueprint"]["id"] == str(catalog["floor"]["id"])


def test_resolving_with_no_selections_offers_the_first_step(
    client, wall_guide, catalog
):
    """The page has to render before anyone has chosen anything."""
    response = client.get("/api/guides/wall/resolve")

    assert response.status_code == 200
    assert response.json["parts"] == []
    assert [step["key"] for step in response.json["steps"]] == ["method"]
    # And offers nothing to refine, because there is nothing yet to
    # refine: a texture question with no part to apply to takes an
    # answer that changes nothing.
    assert response.json["refinements"] == []


def test_a_refinement_appears_once_it_has_a_part_to_apply_to(
    client, wall_guide, catalog
):
    """The other side of the rule above."""
    response = client.get("/api/guides/wall/resolve?method=separate-wall")

    assert response.status_code == 200
    assert [r["key"] for r in response.json["refinements"]] == ["texture"]


def test_a_refinement_that_reaches_no_part_is_not_offered(client, test_db, catalog):
    """A question about parts this build does not have.

    This one applies to the wall alone, and this method builds only a
    floor — so asking it would take an answer that fits every way and
    changes nothing, which is worse than silence. It is why "how do
    the bases clip together?" disappears from the wall guide when both
    pieces print with their bases built in.
    """
    document = copy.deepcopy(WALL_GUIDE)
    document["steps"][0]["options"][0]["roles"] = {"floor": None}
    document["refinements"] = document["refinements"] + [
        {
            "key": "side-locks",
            "role": "wall",
            "prompt": "Locks on the wall ends?",
            "on_tags": {"require": ["connection|side|openlock"]},
            "off_tags": {"deny": ["connection|side|openlock"]},
        }
    ]
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, document)

    response = client.get("/api/guides/wall/resolve?method=separate-wall")

    assert [p["role"] for p in response.json["parts"]] == ["floor"]
    assert [r["key"] for r in response.json["refinements"]] == ["texture"]


def test_a_refinement_narrows_the_recommendation(client, wall_guide, catalog):
    """Narrows, rather than empties — and not every role by the same amount.

    Asking for towne moves the wall off the openforge cave wall that
    `prefer` would otherwise pick, and leaves the floor with nothing,
    because the only floor in the catalog is cave. That mixed parts
    list is what `resolve.py`'s third rule produces and what the route
    has to render.
    """
    response = client.get(
        "/api/guides/wall/resolve?method=separate-wall&texture=texture%7Ctowne"
    )

    assert response.status_code == 200
    parts = {p["role"]: p for p in response.json["parts"]}
    assert parts["wall"]["blueprint"]["blueprint_name"] == "d towne wall"
    assert parts["floor"]["blueprint"] is None


def test_a_part_that_resolved_to_nothing_does_not_break_the_pictures(
    client, wall_guide, catalog, test_db
):
    """One role recommended, one empty, in the same response.

    `_attach_images` has to skip the empty one, and this is the only
    test that puts a real image on the recommended part while another
    part is empty — so it pins the attaching, not just the skipping.
    (The skipping is pinned more widely than this docstring once
    claimed: `test_a_refinement_narrows_the_recommendation` resolves
    to the same mixed list and fails without the guard too.)
    """
    import openforge.db.sql.images as image_sql

    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            image_sql.insert_image_for_blueprint(
                curs,
                catalog["towne"]["id"],
                {
                    "image_name": "towne wall",
                    "image_url": "https://objects.openforge.tools/t.png",
                },
            )

    response = client.get(
        "/api/guides/wall/resolve?method=separate-wall&texture=texture%7Ctowne"
    )

    assert response.status_code == 200
    parts = {p["role"]: p for p in response.json["parts"]}
    assert [i["image_url"] for i in parts["wall"]["blueprint"]["images"]] == [
        "https://objects.openforge.tools/t.png"
    ]
    assert parts["floor"]["blueprint"] is None


def test_a_selection_the_guide_does_not_offer_is_a_400(client, wall_guide):
    response = client.get("/api/guides/wall/resolve?method=wall-on-tile")

    assert response.status_code == 400
    assert "wall-on-tile" in response.json["error"]


def test_a_question_answered_twice_is_a_bad_request(client, wall_guide):
    """`?method=a&method=b` describes no state the guide can be in.

    Flask hands a repeated parameter over as a list, and picking one of
    the values would return a parts list for a question the person did
    not answer that way.
    """
    response = client.get("/api/guides/wall/resolve?method=separate-wall&method=s2w")

    assert response.status_code == 400
    # `repr`-quoted, like every other key this endpoint echoes: a
    # repeated key is attacker-supplied too, and it was the one message
    # in the function that did not escape its input.
    assert "answered more than once: 'method'" in response.json["error"]

    # And the plural path: every offender named, in a fixed order
    # rather than in whatever order the client built the URL.
    response = client.get(
        "/api/guides/wall/resolve?texture=a&texture=b&method=x&method=y"
    )

    assert response.status_code == 400
    assert "answered more than once: 'method', 'texture'" in response.json["error"]


# Determinism is not asserted here. Two GETs of one URL against an
# untouched database are equal by construction — same pure function,
# same rows, no cache — so asserting it proves nothing, and a link is
# not immune to the catalog changing either: a new row sharing a name
# with a lower id legitimately wins. What holds the property up is the
# total ordering in tag_search_blueprints, which is pinned where it
# lives, in tests/test_tags_sql.py.
def test_the_recommendation_carries_what_a_parts_list_needs(
    client, wall_guide, catalog
):
    """Name and a download id, or the page cannot render a part."""
    response = client.get("/api/guides/wall/resolve?method=separate-wall")

    wall = next(p for p in response.json["parts"] if p["role"] == "wall")
    assert wall["blueprint"]["blueprint_name"] == "b openforge wall"
    assert wall["blueprint"]["id"] == str(catalog["openforge"]["id"])
    assert wall["title"] == "Wall"


def test_a_recommended_part_carries_its_tags(client, wall_guide, catalog):
    """The search does not return tags; something has to fetch them.

    Two callers need them and both fail quietly without: a role with
    `match` reads the size of the part above it from here, and the
    page shows them beside each piece because while the guides are
    being written the tags are how you see that a recommendation is
    wrong. Plain strings, not arrays — the page prints them and the
    namespace match splits them on `|`.
    """
    response = client.get("/api/guides/wall/resolve?method=separate-wall")

    wall = next(p for p in response.json["parts"] if p["role"] == "wall")
    tags = wall["blueprint"]["tags"]
    assert all(isinstance(tag, str) for tag in tags)
    assert sorted(tags) == [
        "build|separate wall",
        "connection|openforge",
        "shape|wall",
        "texture|cave",
    ]


def test_the_predicate_reaches_the_search_in_the_shape_it_takes(
    client, wall_guide, catalog
):
    """The conversion is the thing that silently fails if skipped.

    tag_search_blueprints ignores a bare tag string, so a dropped
    require matches everything and a dropped deny matches nothing.
    Asking for a texture no candidate has must therefore come back
    empty rather than come back with whatever sorted first.
    """
    response = client.get(
        "/api/guides/wall/resolve?method=separate-wall&texture=texture%7Cnonesuch"
    )

    parts = {p["role"]: p for p in response.json["parts"]}
    assert parts["wall"]["blueprint"] is None
    assert parts["floor"]["blueprint"] is None


def test_a_recommended_part_carries_its_picture(client, wall_guide, catalog, test_db):
    """A parts list without thumbnails is a list of filenames."""
    import openforge.db.sql.images as image_sql

    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            image_sql.insert_image_for_blueprint(
                curs,
                catalog["openforge"]["id"],
                {
                    "image_name": "openforge wall",
                    "image_url": "https://objects.openforge.tools/x.png",
                },
            )

    response = client.get("/api/guides/wall/resolve?method=separate-wall")

    wall = next(p for p in response.json["parts"] if p["role"] == "wall")
    assert [i["image_url"] for i in wall["blueprint"]["images"]] == [
        "https://objects.openforge.tools/x.png"
    ]
    # The role that found no picture still resolves, with an empty list
    # rather than a missing key.
    floor = next(p for p in response.json["parts"] if p["role"] == "floor")
    assert floor["blueprint"]["images"] == []


def test_an_unknown_guide_is_a_404_even_with_a_bad_query(client, wall_guide):
    """Which check wins when both would fire.

    A 400 for the query string would tell someone their selections are
    wrong about a guide that does not exist, which sends them looking
    in the wrong place.
    """
    response = client.get(
        "/api/guides/nonesuch/resolve?method=separate-wall&method=s2w"
    )

    assert response.status_code == 404


def test_a_refinement_value_outside_its_namespace_is_a_bad_request(client, wall_guide):
    """The other road to a 400: the refinement, not the step.

    Both existing 400 tests go through the step path, so the
    refinement validator was unreached from HTTP.
    """
    response = client.get(
        "/api/guides/wall/resolve?method=separate-wall&texture=shape%7Cwall"
    )

    assert response.status_code == 400
    assert "texture" in response.json["error"]


# The Flask test client hands values to Flask already decoded, so every
# test above passes whether or not the ALB path works. These go at the
# boundary the client cannot reach: an ALB delivers query values still
# percent-encoded, and aws_lambda_wsgi re-encodes whatever it is given.
def test_alb_query_values_survive_the_lambda_adapter():
    """A guide's selections are tags, and tags carry pipes.

    Without the decode, `texture%7Ccave` is double-encoded, reaches
    Flask as the literal `texture%7Ccave`, fails the refinement's
    namespace check and answers 400 — in production only, for every
    refinement, invisibly to this suite.
    """
    import aws_lambda_wsgi

    from openforge.app.index import _decode_alb_event

    event = {
        "httpMethod": "GET",
        "path": "/api/tag-documentation/component%7Cmagnetic+led",
        "queryStringParameters": {
            "texture": "texture%7Ccave",
            "method": "build%7Cseparate+wall",
            "plus": "a%2Bb",
        },
        "headers": {"host": "example.com"},
        "body": None,
        "isBase64Encoded": False,
    }

    _decode_alb_event(event)
    environ = aws_lambda_wsgi.environ(event, None)

    from urllib.parse import parse_qs

    seen = {k: v[0] for k, v in parse_qs(environ["QUERY_STRING"]).items()}
    assert seen == {
        "texture": "texture|cave",
        "method": "build|separate wall",
        "plus": "a+b",
    }
    # The path is encoded by the ALB too, and a pipe-delimited tag in
    # a path segment is how /api/tag-documentation/<tag> is addressed
    # — that route returns nothing in production for the encoded form.
    # The `+` stays a plus. A query string spells a space that way;
    # a path segment does not, so the path never goes through
    # `unquote_plus`, and this is the character that tells them apart.
    assert environ["PATH_INFO"] == "/api/tag-documentation/component|magnetic+led"


def test_a_refinement_survives_the_whole_lambda_path(client, wall_guide, catalog):
    """Through lambda_handler, not the test client.

    This is the only test in the suite that exercises the entry point
    production actually calls. Without the decode inside it, the
    refinement value arrives doubly encoded and the response is a 400.
    """
    import json as _json

    from openforge.app.index import lambda_handler

    response = lambda_handler(
        {
            "httpMethod": "GET",
            "path": "/api/guides/wall/resolve",
            "queryStringParameters": {
                "method": "separate-wall",
                "texture": "texture%7Ctowne",
            },
            "headers": {
                "host": "example.com",
                # What an ALB actually sends, and what the adapter
                # needs to build a WSGI environ.
                "x-forwarded-proto": "https",
                "x-forwarded-port": "443",
                "x-forwarded-for": "203.0.113.1",
            },
            "body": None,
            "isBase64Encoded": False,
        },
        None,
    )

    assert response["statusCode"] == 200, response["body"]
    parts = {p["role"]: p for p in _json.loads(response["body"])["parts"]}
    assert parts["wall"]["blueprint"]["blueprint_name"] == "d towne wall"


def test_a_non_latin_1_path_does_not_crash_the_invocation():
    """PATH_INFO is a latin-1 slot, so the path decodes to latin-1.

    `aws_lambda_wsgi` assigns `event["path"]` to PATH_INFO verbatim
    and werkzeug does `.encode("latin1")` on it to recover the bytes.
    Decode `%E2%82%AC` as UTF-8 and the slot holds a real `\u20ac`,
    which cannot be encoded back: `UnicodeEncodeError` escapes
    `lambda_handler` itself, so there is no response at all — the ALB
    serves its own 502 and the Lambda error metric ticks.

    Decoding to latin-1 puts the raw bytes there instead, which is
    what a real WSGI server does, and werkzeug decodes them as UTF-8
    on the way in. The route then sees the character the client sent
    rather than a replacement character.
    """
    import json as _json

    from openforge.app.index import lambda_handler

    def get(path):
        return lambda_handler(
            {
                "httpMethod": "GET",
                "path": path,
                "queryStringParameters": {},
                "headers": {
                    "host": "example.com",
                    "x-forwarded-proto": "https",
                    "x-forwarded-port": "443",
                    "x-forwarded-for": "203.0.113.1",
                },
                "body": None,
                "isBase64Encoded": False,
            },
            None,
        )

    # Raises rather than answering, before this fix.
    euro = get("/api/guides/%E2%82%AC")
    assert euro["statusCode"] == 404

    # And unencoded, which is what curl sends and the ALB passes
    # through. `unquote` left a non-escape character alone, which is
    # why fixing the escaped form left this one still crashing and
    # why the decode goes via `unquote_to_bytes` instead.
    raw_euro = get("/api/guides/\u20ac")
    assert raw_euro["statusCode"] == 404

    # And the quieter half: a character that does fit in latin-1 is
    # not a crash, it is a silent corruption.
    cafe = get("/api/guides/caf%C3%A9")
    assert cafe["statusCode"] == 404
    assert "café" in _json.loads(cafe["body"])["error"]


def test_an_encoded_slash_stays_encoded():
    """Decoding `%2F` would invent a separator the ALB never saw.

    The edge routes on the encoded path. If Flask dispatched on a
    decoded one, `/api/blueprints/1%2Fdownload` would reach the
    download route while the path rule at the edge matched against
    something else.

    There is already one: `terraform/environments/production/main.tf`
    puts an ALB listener rule on `/api/*`. That one is broad enough
    that a decoded slash cannot escape it — every path this could
    affect is still under `/api/`. The rule that would break is a
    narrower one, `/api/admin/*` or a WAF pattern or a CloudFront
    behaviour, and this wants pinning before someone adds it rather
    than after.
    """
    from openforge.app.index import _decode_alb_event

    event = {"path": "/api/blueprints/1%2Fdownload%7Cx", "httpMethod": "GET"}
    _decode_alb_event(event)

    # The pipe decodes; the slash does not.
    assert event["path"] == "/api/blueprints/1%2Fdownload|x"

    # Lower case too — a client picks the case, not us, and without
    # the IGNORECASE flag `%2f` decodes and dispatches to the download
    # route. It comes back upper case because the rejoin writes the
    # separator, which is the same encoding spelled once.
    event = {"path": "/api/blueprints/1%2fdownload", "httpMethod": "GET"}
    _decode_alb_event(event)

    assert event["path"] == "/api/blueprints/1%2Fdownload"


def test_a_query_key_is_left_encoded_so_two_spellings_cannot_collide(
    client, wall_guide
):
    """Decoding keys looks symmetric and silently answers a question twice.

    `%74exture` is `texture`. Decode the keys and the two collapse into
    one dict entry, the loser disappearing with no error, so the same
    pair of selections resolves to a different parts list depending on
    which one the client wrote last. That is exactly what
    `_selections_from_request` refuses — and it cannot see it, because
    only one key ever reaches Flask.

    Left encoded, `%74exture` is simply an unknown key and the guide
    says so. No key this app reads needs decoding: they are plain
    words, which `quote_plus` returns unchanged.
    """
    import json as _json

    from openforge.app.index import _decode_alb_event, lambda_handler

    event = {"queryStringParameters": {"texture": "a", "%74exture": "b"}}
    _decode_alb_event(event)

    assert event["queryStringParameters"] == {"texture": "a", "%74exture": "b"}

    response = lambda_handler(
        {
            "httpMethod": "GET",
            "path": "/api/guides/wall/resolve",
            "queryStringParameters": {
                "method": "separate-wall",
                "%74exture": "texture%7Ctowne",
            },
            "headers": {
                "host": "example.com",
                "x-forwarded-proto": "https",
                "x-forwarded-port": "443",
                "x-forwarded-for": "203.0.113.1",
            },
            "body": None,
            "isBase64Encoded": False,
        },
        None,
    )

    assert response["statusCode"] == 400
    assert "%74exture" in _json.loads(response["body"])["error"]


def test_decoding_survives_a_request_with_no_query_string():
    from openforge.app.index import _decode_alb_event

    for params in ({}, None):
        event = {"queryStringParameters": params}
        _decode_alb_event(event)
        assert event["queryStringParameters"] == params


def test_an_unknown_guide_answers_json(client, wall_guide):
    """Every other error here is JSON; a client should not parse two shapes."""
    for url in ("/api/guides/nonesuch", "/api/guides/nonesuch/resolve"):
        response = client.get(url)

        assert response.status_code == 404, url
        assert response.is_json, url
        assert "nonesuch" in response.json["error"], url


def test_a_stored_guide_that_no_longer_validates_is_a_500_not_a_400(client, test_db):
    """The `except` around `resolve` must stay narrow.

    `GuideSelectionError` means the selections are wrong. A stored
    document that no longer validates is *our* fault, and fail-fast
    (openforge/CLAUDE.md) says it should surface as a 500 with a
    traceback rather than be reported to the person as a bad request
    they cannot fix by choosing differently.

    Nothing enforced that: `upsert_guide` writes whatever it is given,
    so a document can reach the route malformed, and widening the
    `except` to `Exception` passed the whole suite. This is the test
    that makes the invariant in that comment a rule.
    """
    # An option naming a role the document does not define. This is
    # one of the things validation.py refuses, so it can only be here
    # if the document was written before a rule existed, or around the
    # validator — and `_parts` reads `document["roles"][name]`.
    broken = {
        "key": "broken",
        "title": "A guide that lost a role",
        "steps": [
            {
                "key": "method",
                "prompt": "How?",
                "options": [
                    {
                        "key": "separate-wall",
                        "title": "Separate wall",
                        "roles": {"wall": None},
                    }
                ],
            }
        ],
        # Non-empty, and without "wall". An empty `roles` is refused
        # by a schema rule that fires first, so this is what makes the
        # comment above true of the document beneath it: the check
        # that would catch this one is the unknown-role
        # cross-reference in validation.py.
        "roles": {"floor": {"title": "Floor", "query": {"require": ["shape|floor"]}}},
    }
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, broken)

    with pytest.raises(KeyError):
        client.get("/api/guides/broken/resolve?method=separate-wall")


@pytest.fixture
def choosy_guide(test_db):
    """The wall guide with a closed texture list, which can be greyed.

    An open namespace cannot: its answers are every tag in the
    namespace, so there is no list to walk.
    """
    document = copy.deepcopy(WALL_GUIDE)
    document["refinements"][0]["choices"] = [
        {"tag": "texture|cave"},
        {"tag": "texture|towne"},
    ]
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            return guide_sql.upsert_guide(curs, document)


def test_availability_names_the_answers_that_would_empty_a_part(
    client, choosy_guide, catalog
):
    """The greying-out, and why it is a second request.

    Working this out means re-composing every role for every answer on
    offer, which costs several times what the parts cost — so the page
    draws on /resolve and greys the buttons when this lands. It has to
    answer the same question about the same selections.
    """
    response = client.get("/api/guides/wall/availability?method=separate-wall")

    assert response.status_code == 200
    # One towne wall exists and no towne floor does, so choosing towne
    # leaves the floor with nothing; cave has both.
    assert response.json["unavailable"]["texture"] == ["texture|towne"]


def test_availability_says_which_part_a_missing_answer_would_empty(
    client, choosy_guide, catalog
):
    """`because` is the other half of the answer, and it was untested.

    Dropping an answer with no explanation reads as a bug in the page.
    The part it would leave empty is always knowable, so it is always
    said.
    """
    response = client.get("/api/guides/wall/availability?method=separate-wall")

    assert response.status_code == 200
    reason = response.json["because"]["texture"]["texture|towne"]
    assert reason["part"] == "Floor"


def test_availability_blames_an_answer_only_when_one_is_responsible(
    client, choosy_guide, catalog
):
    """Attribution is a claim, and a wrong one is worse than none.

    `_blame` works by removing one earlier answer at a time and seeing
    whether the option comes back. A removal that changes which parts
    are in play proves nothing — unbuilding the floor makes every
    predicate about the floor hold trivially — so the guard exists to
    refuse that evidence, and without it the first question is blamed
    for everything.
    """
    response = client.get("/api/guides/wall/availability?method=separate-wall")

    reason = response.json["because"]["texture"]["texture|towne"]
    # `method` is the only other answer, and removing it unbuilds the
    # very part being reported — so there is no honest blame to make
    # and the reason says only what is empty.
    assert "question" not in reason
    assert "prompt" not in reason


def test_availability_names_the_answer_responsible_when_one_is(
    client, test_db, choosy_guide, catalog
):
    """The positive half of blame, which no test reached.

    The existing test pins the *guard* — that blame is withheld when
    removing the only other answer unbuilds the part. It passes with
    `_blame` stubbed to `return None`, so the branch that actually
    names a question had never run, while the page renders the phrase
    it produces.

    Here the size question is the culprit and the method is not:
    dropping the size brings the cave wall back without changing which
    parts are in play, so there is an honest answer to point at.
    """
    # A texture with a complete set of parts, so nothing but the size
    # can empty it — towne cannot serve here, because it has no floor
    # at any size and so is dead for a reason blame must refuse to
    # pin on the size question.
    make_blueprint(
        test_db,
        "e cave wall wide",
        ["build|separate wall", "shape|wall", "texture|cave", "size|width|4"],
    )
    make_blueprint(
        test_db,
        "f cave floor wide",
        ["build|separate wall", "shape|floor", "texture|cave", "size|width|4"],
    )
    make_blueprint(
        test_db,
        "g rough wall",
        ["build|separate wall", "shape|wall", "texture|rough_stone"],
    )
    make_blueprint(
        test_db,
        "h rough floor",
        ["build|separate wall", "shape|floor", "texture|rough_stone"],
    )
    document = copy.deepcopy(WALL_GUIDE)
    document["refinements"][0]["choices"] = [
        {"tag": "texture|cave"},
        # Complete at no size, missing at 4 inch — so the size is the
        # single answer responsible, and there is something to name.
        {"tag": "texture|rough_stone"},
    ]
    document["steps"].append(
        {
            "key": "size",
            "prompt": "How wide?",
            "options": [
                {
                    "key": "four",
                    "title": "4 inch",
                    "tags": {"require": ["size|width|4"]},
                }
            ],
        }
    )
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, document)

    response = client.get(
        "/api/guides/wall/availability?method=separate-wall&size=four"
    )

    assert response.status_code == 200
    reason = response.json["because"]["texture"]["texture|rough_stone"]
    assert reason["part"] in ("Wall", "Floor")
    assert reason["question"] == "size"
    assert reason["prompt"] == "How wide?"


def test_availability_counts_the_pieces_behind_each_part(client, wall_guide, catalog):
    """The "N options" bar reads this.

    One means the guide decided; more than one means there is a choice
    worth opening the catalog for. A part that resolved to nothing has
    no count rather than a count of zero, because the page has nothing
    to offer for it.
    """
    response = client.get("/api/guides/wall/availability?method=separate-wall")

    assert response.status_code == 200
    options = response.json["options"]
    assert options["wall"] >= 1
    parts = {
        p["role"]: p
        for p in client.get("/api/guides/wall/resolve?method=separate-wall").json[
            "parts"
        ]
    }
    for role, part in parts.items():
        assert (role in options) == (part["blueprint"] is not None)


def test_the_option_count_is_the_number_this_part_could_have_been(
    client, choosy_guide, catalog
):
    """The number, not merely a number.

    `count(part["query"])` replaced with `count({})` — every part
    reporting the whole catalog — left every route test green, because
    the only assertion was `>= 1`. The count drives a bar that says "6
    options", so being wrong by the size of the catalog matters.
    """
    response = client.get(
        "/api/guides/wall/availability?method=separate-wall&texture=texture%7Ccave"
    )

    assert response.status_code == 200
    options = response.json["options"]
    # Exactly the cave walls this branch can use — two of them — not
    # every model in the catalog, which is larger. Asserted against a
    # search for the part's own predicate rather than a literal, so
    # the number stays honest if the fixture grows.
    resolved = client.get(
        "/api/guides/wall/resolve?method=separate-wall&texture=texture%7Ccave"
    ).json
    wall = next(p for p in resolved["parts"] if p["role"] == "wall")
    assert wall["blueprint"] is not None
    assert options["wall"] == 2
    # And fewer than the catalog holds, which is what `count({})`
    # would have reported — the fixture builds five pieces and no one
    # role can use them all.
    assert options["wall"] < len(catalog)


def test_a_part_that_resolved_to_nothing_has_no_count(client, choosy_guide, catalog):
    """No count rather than a count of zero.

    The page has nothing to offer for a part it could not fill, so the
    bar must not appear at all. The previous test could not tell:
    every part resolved, so `(role in options) == (blueprint is not
    None)` only ever compared True with True.
    """
    response = client.get(
        "/api/guides/wall/availability?method=separate-wall&texture=texture%7Ctowne"
    )
    resolved = client.get(
        "/api/guides/wall/resolve?method=separate-wall&texture=texture%7Ctowne"
    ).json

    empty = [p["role"] for p in resolved["parts"] if p["blueprint"] is None]
    assert empty, "the fixture no longer produces an empty part here"
    for role in empty:
        assert role not in response.json["options"]


def test_a_pinned_part_is_not_counted_as_a_choice(client, test_db, wall_guide, catalog):
    """A pinned part is not a question, so it gets no "N options" bar.

    Its count would be how many pieces the *guide* would have
    considered, which is not what the person chose to look at.
    """
    odd = make_blueprint(
        test_db, "an odd wall", ["shape|wall", "build|separate wall", "texture|cave"]
    )

    response = client.get(
        f"/api/guides/wall/availability?method=separate-wall&part.wall={odd['file_md5']}"
    )

    assert response.status_code == 200
    assert "wall" not in response.json["options"]
    # The roles nobody pinned still carry theirs.
    assert "floor" in response.json["options"]


def test_availability_has_nothing_to_say_about_an_open_namespace(
    client, wall_guide, catalog
):
    """Its answers are every tag in the namespace, so there is no list.

    Worth pinning rather than leaving implicit: it is the reason a
    refinement gets `choices` at all, and someone reading only the
    greying would otherwise call this a bug.
    """
    response = client.get("/api/guides/wall/availability?method=separate-wall")

    assert response.status_code == 200
    assert "texture" not in response.json["unavailable"]


def test_availability_is_silent_when_every_answer_works(client, wall_guide, catalog):
    """An empty map rather than a list of empty lists."""
    response = client.get("/api/guides/wall/availability")

    assert response.status_code == 200
    assert response.json["unavailable"] == {}


def test_resolving_does_not_pay_for_availability(client, wall_guide, catalog):
    """The hot path must not do the expensive pass.

    Guarded by the count of searches rather than by a clock: the engine
    asks the catalog once per role per offered answer when it is
    working out availability, and once per role when it is not.
    """
    response = client.get("/api/guides/wall/resolve?method=separate-wall")

    assert response.status_code == 200
    for question in response.json["steps"] + response.json["refinements"]:
        assert question["unavailable"] == []


def test_availability_refuses_the_same_bad_selections_resolve_does(client, wall_guide):
    response = client.get("/api/guides/wall/availability?method=nonesuch")

    assert response.status_code == 400
    assert "nonesuch" in response.json["error"]


def test_availability_for_an_unknown_guide_is_a_404(client, wall_guide):
    response = client.get("/api/guides/nonesuch/availability")

    assert response.status_code == 404


def test_a_namespace_refinement_offers_what_the_parts_carry(client, test_db, catalog):
    """Derived answers, not a list somebody typed into the guide.

    A guide that names its own answers goes stale the moment the
    catalog gains a connector. This one says only which namespace to
    ask about, and the answers come from the parts it applies to.
    """
    document = copy.deepcopy(WALL_GUIDE)
    document["refinements"] = [
        {
            "key": "connectors",
            "role": "wall",
            "prompt": "Connectors?",
            "from_namespace": "connection",
        }
    ]
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, document)

    response = client.get("/api/guides/wall/resolve?method=separate-wall")

    offered = response.json["refinements"][0]["choices"]
    # Two of the three separate walls carry it and nothing carries
    # anything else, so that is the whole of the answer — with the
    # count behind it, because an answer with 240 pieces and one with
    # 4 are worth telling apart.
    assert [c["tag"] for c in offered] == ["connection|openforge"]
    assert offered[0]["count"] == 2


def test_derived_answers_are_immediate_children_of_the_namespace(
    client, test_db, catalog
):
    """`connection|side` and `connection|side|openlock` sit on the same
    pieces, so offering both offers one answer twice. A variant belongs
    to the question about its parent, not the question about the
    family."""
    document = copy.deepcopy(WALL_GUIDE)
    document["refinements"] = [
        {
            "key": "connectors",
            "role": "wall",
            "prompt": "Connectors?",
            "from_namespace": "connection",
        }
    ]
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, document)
            blueprint = make_blueprint(
                test_db,
                "e side wall",
                [
                    "build|separate wall",
                    "shape|wall",
                    "connection|openforge",
                    "connection|side",
                    "connection|side|openlock",
                    "texture|cave",
                ],
            )
    assert blueprint is not None

    response = client.get("/api/guides/wall/resolve?method=separate-wall")

    assert [c["tag"] for c in response.json["refinements"][0]["choices"]] == [
        "connection|openforge",
        "connection|side",
    ]


def test_a_curated_choice_list_is_left_alone(client, test_db, catalog):
    """`choices` is an override, and has to beat derivation.

    The texture question needs it: `substitute` means the roles are
    asked for *different* tags, so what they carry cannot be
    intersected into one list.
    """
    document = copy.deepcopy(WALL_GUIDE)
    document["refinements"][0]["choices"] = [
        {"tag": "texture|cave"},
        {"tag": "texture|nonesuch"},
    ]
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, document)

    response = client.get("/api/guides/wall/resolve?method=separate-wall")

    assert [c["tag"] for c in response.json["refinements"][0]["choices"]] == [
        "texture|cave",
        "texture|nonesuch",
    ]


def test_a_later_question_must_not_grey_out_the_first_screen(client, test_db, catalog):
    """A role has to be answerable before the question that narrows it.

    The trap, hit three times on this guide: move a required tag off a
    role and onto a later step, and the role matches *nothing* until
    that step is answered — because a sweep with nothing exempt takes
    everything. The availability pass then correctly reports that
    every first answer empties a part, and greys out the whole opening
    screen. The page is not broken-looking; it is unusable, and the
    cause is three questions away.

    `allow` is the fix each time: permit what the later question will
    choose between, so the role resolves now and narrows later.
    """
    document = copy.deepcopy(WALL_GUIDE)
    # A sweep over the namespace that makes a wall a wall...
    document["roles"]["wall"]["query"] = {
        "require": ["build|separate wall"],
        "deny_children": ["shape"],
        "allow": ["shape|wall"],
    }
    # ...and a later question that decides which one.
    document["steps"].append(
        {
            "key": "height",
            "prompt": "How tall?",
            "options": [
                {
                    "key": "normal",
                    "title": "Normal",
                    "roles": {"wall": {"require": ["shape|wall"]}},
                }
            ],
        }
    )
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, document)

    response = client.get("/api/guides/wall/availability")

    assert response.status_code == 200
    assert response.json["unavailable"] == {}


def test_without_the_allow_the_first_screen_does_grey_out(client, test_db, catalog):
    """The other half, so the guard above cannot pass vacuously."""
    document = copy.deepcopy(WALL_GUIDE)
    document["roles"]["wall"]["query"] = {
        "require": ["build|separate wall"],
        "deny_children": ["shape"],
    }
    document["steps"].append(
        {
            "key": "height",
            "prompt": "How tall?",
            "options": [
                {
                    "key": "normal",
                    "title": "Normal",
                    "roles": {"wall": {"require": ["shape|wall"]}},
                }
            ],
        }
    )
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, document)

    response = client.get("/api/guides/wall/availability")

    assert response.json["unavailable"]["method"] == ["separate-wall"]


@pytest.fixture
def clip_catalog(test_db):
    """Bases whose connection tags are not independent of each other.

    Modelled on the real ones: a base is OpenLOCK or DragonLock, with
    magnets or without, and the OpenLOCK one may be topless — but
    nothing is both topless and unsupported, which is the pairing three
    separate yes/no questions would happily offer.
    """
    # Named so that the *plain* OpenLOCK base sorts last. All three
    # openlock bases match a bare `require: connection|openlock`, and
    # candidates come back in name order — so if the plain one sorted
    # first, a predicate that failed to exclude the others would still
    # return it and the test would pass on an accident.
    combos = {
        "z plain openlock": ["connection|openlock"],
        "a openlock with magnets": [
            "connection|openlock",
            "connection|magnetic",
            "connection|magnetic|flex",
        ],
        "b openlock topless": [
            "connection|openlock",
            "connection|openlock|topless",
        ],
        "c dragonlock": ["connection|dragonlock"],
    }
    for name, tags in combos.items():
        # `build|separate wall` because the method option asks every
        # role it names for it.
        make_blueprint(test_db, name, ["shape|base", "build|separate wall", *tags])
    return combos


def test_a_combination_refinement_offers_the_sets_that_exist(
    client, test_db, catalog, clip_catalog
):
    """Whole combinations, not one tag at a time.

    Four bases, four answers — and no answer pairing tags that no base
    carries together, which is the thing separate questions cannot
    promise.
    """
    document = copy.deepcopy(WALL_GUIDE)
    document["roles"]["base"] = {"title": "Base", "query": {"require": ["shape|base"]}}
    document["steps"][0]["options"][0]["roles"]["base"] = None
    document["refinements"] = [
        {
            "key": "clips",
            "role": "base",
            "prompt": "Clips?",
            "from_combination": "connection",
            "exclude": ["connection|magnetic|flex"],
        }
    ]
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, document)

    response = client.get("/api/guides/wall/resolve?method=separate-wall")

    offered = response.json["refinements"][0]["choices"]
    assert [c["title"] for c in offered] == [
        "Dragonlock",
        "Magnetic + openlock",
        "Openlock",
        "Openlock topless",
    ]
    # The excluded tag is hidden from the label, not refused: the
    # magnetic base is still one of the four.
    assert all("flex" not in c["title"] for c in offered)


def test_exclude_takes_the_whole_subtree(client, test_db, catalog, clip_catalog):
    """`exclude` names a parent and means everything under it.

    A question about how a piece clips *down* has no use for the side
    clips the connectors question already asked about, and the piece
    carries both. Naming `connection|side` has to keep a side system
    nobody has designed yet out of the list too — listing the ones
    that exist today is the thing that goes stale.
    """
    make_blueprint(
        test_db,
        "d openlock with side clips",
        [
            "shape|base",
            "build|separate wall",
            "connection|openlock",
            "connection|side",
            "connection|side|openlock",
        ],
    )
    document = copy.deepcopy(WALL_GUIDE)
    document["roles"]["base"] = {"title": "Base", "query": {"require": ["shape|base"]}}
    document["steps"][0]["options"][0]["roles"]["base"] = None
    document["refinements"] = [
        {
            "key": "clips",
            "role": "base",
            "prompt": "Clips?",
            "from_combination": "connection",
            "exclude": ["connection|side"],
        }
    ]
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, document)

    response = client.get("/api/guides/wall/resolve?method=separate-wall")

    offered = [c["tag"] for c in response.json["refinements"][0]["choices"]]
    assert not any("side" in tag for tag in offered)
    # And the side-clipped base is not a fifth answer of its own: with
    # its side tags hidden it is plain OpenLOCK, like the others.
    assert "connection|openlock" in offered


def test_exclude_takes_that_subtree_and_not_a_namesake_under_another(
    client, test_db, catalog, clip_catalog
):
    """`exclude` is anchored at the front, not "contains these words".

    `@>` on its own is positionless containment, so
    `exclude: ['connection|side']` also hid `connection|openlock|side`,
    which lives under `connection|openlock` and has nothing to do with
    the side-clip question. The piece carrying it was then merged into
    the plain OpenLOCK answer and counted towards its label.
    """
    make_blueprint(
        test_db,
        "d openlock side-mount",
        [
            "shape|base",
            "build|separate wall",
            "connection|openlock",
            # Under `connection|openlock`, sharing only a word with the
            # `connection|side` subtree being hidden.
            "connection|openlock|side",
        ],
    )
    document = copy.deepcopy(WALL_GUIDE)
    document["roles"]["base"] = {"title": "Base", "query": {"require": ["shape|base"]}}
    document["steps"][0]["options"][0]["roles"]["base"] = None
    document["refinements"] = [
        {
            "key": "clips",
            "role": "base",
            "prompt": "Clips?",
            "from_combination": "connection",
            "exclude": ["connection|side"],
        }
    ]
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, document)

    response = client.get("/api/guides/wall/resolve?method=separate-wall")

    offered = [c["tag"] for c in response.json["refinements"][0]["choices"]]
    # It is its own answer, distinguishable from plain OpenLOCK.
    assert "connection|openlock,connection|openlock|side" in offered
    assert "connection|openlock" in offered


def test_choosing_a_combination_excludes_the_others(
    client, test_db, catalog, clip_catalog
):
    """Exact, or it is not a combination.

    Asking for plain OpenLOCK has to exclude the magnetic one and the
    topless one, which a bare `require` would not — all three carry
    `connection|openlock`.
    """
    document = copy.deepcopy(WALL_GUIDE)
    document["roles"]["base"] = {"title": "Base", "query": {"require": ["shape|base"]}}
    document["steps"][0]["options"][0]["roles"]["base"] = None
    document["refinements"] = [
        {
            "key": "clips",
            "role": "base",
            "prompt": "Clips?",
            "from_combination": "connection",
            "exclude": ["connection|magnetic|flex"],
        }
    ]
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, document)

    response = client.get(
        "/api/guides/wall/resolve?method=separate-wall&clips=connection%7Copenlock"
    )

    base = next(p for p in response.json["parts"] if p["role"] == "base")
    assert base["blueprint"]["blueprint_name"] == "z plain openlock"


def test_the_options_narrow_with_the_size_the_base_inherits(client, test_db):
    """Base size changes the answers, and by data rather than a rule.

    A base copies its width from the piece standing on it, so the clip
    combinations on offer have to be the ones *that* size has. In the
    real catalog a 1-inch dungeon stone wall base has four and a 2-inch
    one has seven; here, one and two.

    Without the inherited size in the derivation, both sizes offer
    everything and the narrow base's question lists answers it cannot
    honour.
    """
    document = copy.deepcopy(WALL_GUIDE)
    document["roles"] = {
        "wall": {"title": "Wall", "query": {"require": ["shape|wall"]}},
        "base": {
            "title": "Base",
            "query": {"require": ["shape|base"]},
            "under": "wall",
            "match": ["size|width"],
        },
    }
    document["steps"] = [
        {
            "key": "size",
            "prompt": "How wide?",
            "options": [
                {
                    "key": "one",
                    "title": "1",
                    "roles": {"wall": {"require": ["size|width|1"]}, "base": None},
                },
                {
                    "key": "two",
                    "title": "2",
                    "roles": {"wall": {"require": ["size|width|2"]}, "base": None},
                },
            ],
        }
    ]
    document["refinements"] = [
        {
            "key": "clips",
            "role": "base",
            "prompt": "Clips?",
            "from_combination": "connection",
        }
    ]
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, document)
    make_blueprint(test_db, "wall 1", ["shape|wall", "size|width|1"])
    make_blueprint(test_db, "wall 2", ["shape|wall", "size|width|2"])
    # The narrow base comes in one flavour; the wide one in two.
    make_blueprint(
        test_db, "base 1", ["shape|base", "size|width|1", "connection|openlock"]
    )
    make_blueprint(
        test_db, "base 2a", ["shape|base", "size|width|2", "connection|openlock"]
    )
    make_blueprint(
        test_db, "base 2b", ["shape|base", "size|width|2", "connection|dragonlock"]
    )

    narrow = client.get("/api/guides/wall/resolve?size=one")
    wide = client.get("/api/guides/wall/resolve?size=two")

    assert [c["title"] for c in narrow.json["refinements"][0]["choices"]] == [
        "Openlock"
    ]
    assert [c["title"] for c in wide.json["refinements"][0]["choices"]] == [
        "Dragonlock",
        "Openlock",
    ]


def test_a_pinned_part_beats_the_search(client, test_db, wall_guide, catalog):
    """Someone who picked a part was looking at it when they picked it.

    No predicate this guide composes is a better answer than the one
    they gave, so the pin wins outright — and the page can say whose
    choice it was, which is the only way it can explain why changing
    a texture leaves that one piece alone.
    """
    odd = make_blueprint(
        test_db, "an odd wall", ["shape|wall", "build|separate wall", "texture|cave"]
    )

    response = client.get(
        "/api/guides/wall/resolve?method=separate-wall"
        f"&texture=texture%7Cdungeon_stone&part.wall={odd['file_md5']}"
    )

    wall = next(p for p in response.json["parts"] if p["role"] == "wall")
    assert wall["blueprint"]["blueprint_name"] == "an odd wall"
    assert wall["pinned"] is True
    # The other roles are untouched: pinning one part is not opting
    # out of the guide.
    assert all(p["pinned"] is False for p in response.json["parts"] if p != wall)


def test_a_pin_nobody_can_find_falls_back_to_the_recommendation(
    client, wall_guide, catalog
):
    """A guide URL outlives the catalog it was made from.

    A pinned file that has been deleted or replaced should leave a
    page of parts, not a 404 — the guide still knows what it would
    have recommended.
    """
    response = client.get(
        "/api/guides/wall/resolve?method=separate-wall&part.wall=nosuchmd5"
    )

    assert response.status_code == 200
    wall = next(p for p in response.json["parts"] if p["role"] == "wall")
    assert wall["blueprint"] is not None
    assert wall["pinned"] is False


def test_a_pin_names_a_role_this_guide_has(client, wall_guide, catalog):
    """Still strict. `part.` is a key space, not an escape hatch."""
    response = client.get(
        "/api/guides/wall/resolve?method=separate-wall&part.nosuchrole=abc"
    )

    assert response.status_code == 400
    assert "part.nosuchrole" in response.json["error"]


def test_a_pin_that_matches_nothing_is_logged_where_it_can_be_seen(
    client, wall_guide, catalog, caplog
):
    """The one case the fallback's docstring says it wants to see.

    At WARNING, not INFO: nothing sets `LOG_LEVEL` in the production
    Lambda, so `app.logger` is NOTSET under a root logger the runtime
    leaves at WARNING, and an INFO line was evaluated and discarded in
    the one place it was written for.
    """
    import logging

    with caplog.at_level(logging.WARNING):
        response = client.get(
            "/api/guides/wall/resolve?method=separate-wall&part.wall=nosuchmd5"
        )

    assert response.status_code == 200
    assert "nosuchmd5" in caplog.text
    assert any(r.levelno >= logging.WARNING for r in caplog.records)


def test_a_pin_cannot_forge_a_log_line(client, wall_guide, catalog, caplog):
    """The md5 is a query parameter, so it is attacker-shaped.

    A raw `%s` of `?part.wall=%0A...` splits the record in a Text-format
    CloudWatch log, and whitespace-only input logged as nothing at all.
    `%r` and a length cap answer both.
    """
    import logging

    forged = "a\nWARNING forged entry"
    with caplog.at_level(logging.WARNING):
        client.get(
            "/api/guides/wall/resolve",
            query_string={"method": "separate-wall", "part.wall": forged},
        )

    # The newline is escaped rather than ending the line, and nothing
    # unbounded reaches the log.
    assert "\\n" in caplog.text
    assert "\nWARNING forged entry" not in caplog.text


def test_a_nul_byte_in_a_selection_is_a_bad_request(client, wall_guide, catalog):
    """A NUL never reaches the server, so the route has to answer first.

    `sql.Literal` raises `DataError` while building the statement, which
    escapes as an HTML 500 with no JSON body — for a request whose
    honest answer is 400, arriving from a hand-editable URL.
    """
    for query in (
        "part.wall=%00",
        "texture=texture%7Ca%00b",
        "%00=x",
    ):
        got = client.get(f"/api/guides/wall/resolve?{query}")
        assert got.status_code == 400, query
        assert "NUL" in got.get_json()["error"], query


def test_a_nul_byte_in_the_guide_key_is_a_404(client, wall_guide, catalog):
    """A key carrying a NUL names no stored guide, and says so as one."""
    got = client.get("/api/guides/wa%00ll/resolve")
    assert got.status_code == 404
    assert "No guide" in got.get_json()["error"]


def test_an_enormous_selection_is_refused_rather_than_queried(
    client, wall_guide, catalog
):
    """Without a cap the whole value went to Postgres, and got a 200."""
    got = client.get(f"/api/guides/wall/resolve?part.wall={'a' * 200_000}")
    assert got.status_code == 400
    error = got.get_json()["error"]
    assert "longer than" in error
    # The *answer* is the offender, not the key. Saying `'part.wall' is
    # longer than 256 characters` about a nine-character key is a false
    # statement, and asserting only "longer than" could not see it.
    assert "the answer to 'part.wall'" in error
    # And the echo is capped, or refusing a 200KB value answers with a
    # 200KB body.
    assert len(error) < 2 * guides.SELECTION_CHARS


def test_the_selection_cap_is_the_cap_it_says(client, wall_guide, catalog):
    """Pinned at the boundary, in both directions.

    A test that sends 200,000 characters passes whatever the cap is —
    it stays green if the cap is raised a hundredfold, and green if the
    length is only checked on values. One character either side of
    `SELECTION_CHARS` is what actually holds the number.
    """
    at_limit = "a" * guides.SELECTION_CHARS
    assert client.get(f"/api/guides/wall/resolve?part.wall={at_limit}").status_code == (
        200
    )
    over = "a" * (guides.SELECTION_CHARS + 1)
    assert client.get(f"/api/guides/wall/resolve?part.wall={over}").status_code == 400
    # And the key is measured too, not only the value.
    assert client.get(f"/api/guides/wall/resolve?{over}=x").status_code == 400


def test_a_refused_selection_cannot_forge_a_line_in_the_body(
    client, wall_guide, catalog
):
    """The body escapes what it echoes, like the log line does.

    The key is attacker-supplied and comes straight back; `repr` is
    what stops a newline in it from looking like a second message.
    """
    got = client.get("/api/guides/wall/resolve?a%0Ab=" + "x" * 300)
    assert got.status_code == 400
    error = got.get_json()["error"]
    assert "\\n" in error
    assert "\n" not in error


def test_the_pin_log_is_truncated_not_merely_escaped(
    client, wall_guide, catalog, caplog
):
    """The cap is asserted, not just described.

    The forged-line test uses a short payload, so `MD5_CHARS` could be
    raised or deleted with it still green.
    """
    long_pin = "b" * (guides.MD5_CHARS * 4)
    with caplog.at_level(logging.WARNING):
        # The method has to be answered for the wall role to be reached
        # at all, which is where the pin is looked up.
        client.get(
            f"/api/guides/wall/resolve?method=separate-wall&part.wall={long_pin}"
        )
    lines = [r.getMessage() for r in caplog.records if "guide pin" in r.getMessage()]
    assert lines, "no pin-miss record"
    assert "b" * guides.MD5_CHARS in lines[0]
    assert "b" * (guides.MD5_CHARS + 1) not in lines[0]


def test_a_rotted_recommendation_is_the_guide_s_fault_not_the_visitor_s(
    client, test_db, catalog
):
    """A document fault must not come back as a bad request.

    `_with_defaults` merges the guide's own recommendations into the
    answers before they are validated, and the validator could not tell
    the two apart — so a guide whose `default` named an option it no
    longer has answered 400 on an *empty* query string, telling someone
    their selections were wrong when they had not made any. Nothing
    alarms on a 400 and CloudWatch is the only forensics here, so it
    would have read as people typing bad URLs for as long as it lasted.
    """
    document = copy.deepcopy(WALL_GUIDE)
    document["steps"][0]["default"] = "no-such-option"
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            # Straight past the fixture loader, which is what would have
            # caught this: the drift being modelled is a stored document
            # that stopped matching its own options.
            guide_sql.upsert_guide(curs, document)

    with pytest.raises(ValueError, match="guide is invalid"):
        client.get("/api/guides/wall/resolve")


def test_a_bad_answer_is_still_the_visitor_s_fault(client, wall_guide, catalog):
    """The other side of it: what they actually sent still 400s."""
    response = client.get("/api/guides/wall/resolve?method=no-such-option")

    assert response.status_code == 400
    assert "has no option" in response.json["error"]


def test_blame_names_an_earlier_answer_when_that_is_the_one_responsible(
    client, test_db, catalog
):
    """The mirror of the test below, and the case the first guard broke.

    Deleting a key outright unanswers every step after it, so the
    guard that noticed the truncation withheld blame for every step
    except the last one — five of the six in the shipped wall guide.
    Clearing a question on screen re-applies the recommendation below
    it instead, which is what the counterfactual now does, so an
    earlier step is blameable again when it really is at fault.
    """
    for name, tags in (
        ("e cave wall", ["texture|cave", "size|width|4", "finish|rough"]),
        ("f cave floor", ["texture|cave", "size|width|4", "finish|rough"]),
        # Present at the recommended size, absent at the chosen one —
        # so the size is the culprit and the finish is harmless.
        ("g rough wall", ["texture|rough_stone", "size|width|1", "finish|rough"]),
        ("h rough floor", ["texture|rough_stone", "size|width|1", "finish|rough"]),
    ):
        shape = "shape|wall" if "wall" in name else "shape|floor"
        make_blueprint(test_db, name, ["build|separate wall", shape, *tags])

    document = copy.deepcopy(WALL_GUIDE)
    document["refinements"][0]["choices"] = [
        {"tag": "texture|cave"},
        {"tag": "texture|rough_stone"},
    ]
    # The culprit comes first and carries a recommendation, so clearing
    # it leaves the finish below it answered.
    document["steps"].append(
        {
            "key": "size",
            "prompt": "How wide?",
            "default": "one",
            "options": [
                {
                    "key": "four",
                    "title": "4 inch",
                    "tags": {"require": ["size|width|4"]},
                },
                {
                    "key": "one",
                    "title": "1 inch",
                    "tags": {"require": ["size|width|1"]},
                },
            ],
        }
    )
    document["steps"].append(
        {
            "key": "finish",
            "prompt": "What finish?",
            "options": [
                {
                    "key": "rough",
                    "title": "Rough",
                    "tags": {"require": ["finish|rough"]},
                }
            ],
        }
    )
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, document)

    response = client.get(
        "/api/guides/wall/availability?method=separate-wall&size=four&finish=rough"
    )

    assert response.status_code == 200
    reason = response.json["because"]["texture"]["texture|rough_stone"]
    assert reason["question"] == "size", (
        f"blamed {reason.get('question')!r}; an earlier step with a "
        "recommendation is blameable, because clearing it re-answers it "
        "rather than truncating the steps below"
    )
    assert reason["prompt"] == "How wide?"


def test_blame_names_a_later_answer_rather_than_the_one_that_truncates_it(
    client, test_db, catalog
):
    """Removing an earlier answer removes every answer after it.

    The wizard rule is that a step is reachable only once every step
    before it is answered, so `_blame`'s hypothetical — the selections
    with one key deleted — silently drops every *later* step answer
    too. That state is one the page can never be in, and the earliest
    removable question therefore "revives" the part and takes the
    blame for a question after it.

    Here the finish is the culprit and the size is harmless. Dropping
    the size also drops the finish, which is why it used to look like
    the answer.
    """
    for name, tags in (
        ("e cave wall", ["texture|cave", "size|width|4", "finish|rough"]),
        ("f cave floor", ["texture|cave", "size|width|4", "finish|rough"]),
        # Complete at the chosen size, absent at the chosen finish — so
        # the finish is the single answer responsible.
        ("g rough wall", ["texture|rough_stone", "size|width|4", "finish|smooth"]),
        ("h rough floor", ["texture|rough_stone", "size|width|4", "finish|smooth"]),
    ):
        shape = "shape|wall" if "wall" in name else "shape|floor"
        make_blueprint(test_db, name, ["build|separate wall", shape, *tags])

    document = copy.deepcopy(WALL_GUIDE)
    document["refinements"][0]["choices"] = [
        {"tag": "texture|cave"},
        {"tag": "texture|rough_stone"},
    ]
    # Order matters and is the whole point: the harmless question comes
    # first, so removing it truncates the culprit.
    document["steps"].append(
        {
            "key": "size",
            "prompt": "How wide?",
            "options": [
                {
                    "key": "four",
                    "title": "4 inch",
                    "tags": {"require": ["size|width|4"]},
                }
            ],
        }
    )
    document["steps"].append(
        {
            "key": "finish",
            "prompt": "What finish?",
            "options": [
                {
                    "key": "rough",
                    "title": "Rough",
                    "tags": {"require": ["finish|rough"]},
                }
            ],
        }
    )
    with test_db.connection() as conn:
        with conn.cursor(row_factory=dict_row) as curs:
            guide_sql.upsert_guide(curs, document)

    response = client.get(
        "/api/guides/wall/availability?method=separate-wall&size=four&finish=rough"
    )

    assert response.status_code == 200
    reason = response.json["because"]["texture"]["texture|rough_stone"]
    assert reason["question"] == "finish", (
        f"blamed {reason['question']!r}; removing it must not take another "
        "answer with it"
    )
    assert reason["prompt"] == "What finish?"
