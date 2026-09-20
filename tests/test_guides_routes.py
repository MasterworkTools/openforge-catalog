import pytest
from psycopg.rows import dict_row

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


def test_listing_no_guides_is_a_404(client):
    response = client.get("/api/guides")

    assert response.status_code == 404
    assert response.json["guides"] == []


def test_fetching_a_guide_returns_its_document(client, wall_guide):
    response = client.get("/api/guides/wall")

    assert response.status_code == 200
    assert response.json["document"]["steps"][0]["key"] == "method"


def test_fetching_an_unknown_guide_is_a_404(client):
    assert client.get("/api/guides/nonesuch").status_code == 404


def test_resolving_recommends_a_part_per_role(client, wall_guide, catalog):
    response = client.get("/api/guides/wall/resolve?method=separate-wall")

    assert response.status_code == 200
    parts = {part["role"]: part for part in response.json["parts"]}
    assert parts["wall"]["blueprint"]["id"] == str(catalog["openforge"]["id"])
    assert parts["floor"]["blueprint"]["id"] == str(catalog["floor"]["id"])


def test_resolving_with_no_selections_offers_the_first_step(
    client, wall_guide, catalog
):
    response = client.get("/api/guides/wall/resolve")

    assert response.status_code == 200
    assert response.json["parts"] == []
    assert [step["key"] for step in response.json["steps"]] == ["method"]


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

    `_attach_images` has to skip the empty one. Every other test in
    this file either resolves everything or nothing, so the guard that
    does the skipping is never reached — and without it this is a 500.
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
    assert "answered more than once: method" in response.json["error"]


def test_resolving_an_unknown_guide_is_a_404(client):
    response = client.get("/api/guides/nonesuch/resolve")

    assert response.status_code == 404


def test_a_guide_with_no_steps_answered_still_lists_its_first_question(
    client, wall_guide, catalog
):
    """The page has to render before anyone has chosen anything."""
    response = client.get("/api/guides/wall/resolve")

    assert [step["key"] for step in response.json["steps"]] == ["method"]
    assert response.json["refinements"][0]["key"] == "texture"


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


def test_a_refinement_value_outside_its_namespace_is_a_bad_request(
    client, wall_guide, catalog
):
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

    from openforge.app.index import _decode_alb_query

    event = {
        "httpMethod": "GET",
        "path": "/api/guides/wall/resolve",
        "queryStringParameters": {
            "texture": "texture%7Ccave",
            "method": "build%7Cseparate+wall",
            "plus": "a%2Bb",
        },
        "headers": {"host": "example.com"},
        "body": None,
        "isBase64Encoded": False,
    }

    _decode_alb_query(event)
    environ = aws_lambda_wsgi.environ(event, None)

    from urllib.parse import parse_qs

    seen = {k: v[0] for k, v in parse_qs(environ["QUERY_STRING"]).items()}
    assert seen == {
        "texture": "texture|cave",
        "method": "build|separate wall",
        "plus": "a+b",
    }


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


def test_decoding_survives_a_request_with_no_query_string():
    from openforge.app.index import _decode_alb_query

    for params in ({}, None):
        event = {"queryStringParameters": params}
        _decode_alb_query(event)
        assert event["queryStringParameters"] == params


def test_an_unknown_guide_answers_json(client, wall_guide):
    """Every other error here is JSON; a client should not parse two shapes."""
    for url in ("/api/guides/nonesuch", "/api/guides/nonesuch/resolve"):
        response = client.get(url)

        assert response.status_code == 404, url
        assert response.is_json, url
        assert "nonesuch" in response.json["error"], url
