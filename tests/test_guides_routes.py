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
    response = client.get(
        "/api/guides/wall/resolve?method=separate-wall&texture=texture%7Ctowne"
    )

    assert response.status_code == 200
    parts = {part["role"]: part for part in response.json["parts"]}
    assert parts["wall"]["blueprint"] is None


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


def test_the_recommendation_carries_what_a_parts_list_needs(
    client, wall_guide, catalog
):
    """Name and a download id, or the page cannot render a part."""
    response = client.get("/api/guides/wall/resolve?method=separate-wall")

    wall = next(p for p in response.json["parts"] if p["role"] == "wall")
    assert wall["blueprint"]["blueprint_name"] == "b openforge wall"
    assert wall["blueprint"]["id"] == str(catalog["openforge"]["id"])
    assert wall["title"] == "Wall"


def test_the_same_url_resolves_the_same_way_twice(client, wall_guide, catalog):
    """The whole reason a guide URL is worth sharing."""
    url = "/api/guides/wall/resolve?method=separate-wall"

    first = client.get(url).json
    second = client.get(url).json

    assert first == second


def test_an_unknown_selection_key_is_refused(client, wall_guide, catalog):
    """A stale link should say so rather than quietly ignoring half of itself."""
    response = client.get("/api/guides/wall/resolve?method=separate-wall&colour=red")

    assert response.status_code == 400
    assert "colour" in response.json["error"]


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
