import copy
import inspect

import pytest

from openforge.db.sql.tags import tag_search_blueprints
from openforge.guides.resolve import (
    GuideSelectionError,
    resolve,
    to_tag_query,
)

GUIDE = {
    "key": "wall",
    "title": "How do I make a wall?",
    "steps": [
        {
            "key": "method",
            "prompt": "How do you want to build it?",
            "options": [
                {
                    "key": "s2w-modular",
                    "title": "Modular (s2w)",
                    "roles": {
                        "floor": {"require": ["build|s2w"]},
                        "base": {"deny": ["build|s2w"]},
                        "wall": {"require": ["build|s2w"]},
                    },
                },
                {
                    "key": "separate-wall",
                    "title": "Separate wall",
                    "roles": {"floor": None, "wall": None},
                    "tags": {"require": ["build|separate wall"]},
                },
            ],
        },
        {
            "key": "size",
            "prompt": "How wide?",
            "when": {"selected": {"method": ["s2w-modular", "separate-wall"]}},
            "options": [
                {
                    "key": "two",
                    "title": "2 inch",
                    "tags": {"require": ["size|width|2"]},
                }
            ],
        },
    ],
    "roles": {
        "wall": {
            "title": "Wall",
            "query": {"require": ["shape|wall"], "deny": ["shape|base"]},
            "prefer": ["connection|openforge", "texture|dungeon_stone"],
        },
        "floor": {"title": "Floor", "query": {"require": ["shape|floor"]}},
        "base": {
            "title": "Base",
            "query": {"require": ["shape|base"]},
            "under": "floor",
        },
    },
    "refinements": [
        {
            "key": "texture",
            "role": "*",
            "prompt": "Texture",
            "from_namespace": "texture",
        },
        {
            "key": "side-locks",
            "role": "wall",
            "prompt": "Locks on the wall ends?",
            "when": {"selected": {"method": ["separate-wall"]}},
            "on_tags": {"require": ["connection|side|openlock"]},
            "off_tags": {"deny": ["connection|side|openlock"]},
        },
    ],
}

CATALOG = [
    {
        "id": "1",
        "blueprint_name": "a s2w wall plain",
        "tags": ["build|s2w", "shape|wall", "texture|cave"],
    },
    {
        "id": "2",
        "blueprint_name": "z s2w wall openforge",
        "tags": [
            "build|s2w",
            "shape|wall",
            "connection|openforge",
            "texture|cave",
        ],
    },
    {
        "id": "3",
        "blueprint_name": "a s2w floor",
        "tags": ["build|s2w", "shape|floor", "texture|cave"],
    },
    {
        "id": "4",
        "blueprint_name": "base square",
        "tags": ["shape|base", "texture|cave"],
    },
    {
        "id": "5",
        "blueprint_name": "m separate wall openlock",
        "tags": [
            "build|separate wall",
            "shape|wall",
            "connection|openforge",
            "connection|side|openlock",
            "texture|dungeon_stone",
        ],
    },
    {
        "id": "6",
        "blueprint_name": "n separate wall plain",
        "tags": [
            "build|separate wall",
            "shape|wall",
            "connection|openforge",
            "texture|dungeon_stone",
        ],
    },
    {
        "id": "9",
        "blueprint_name": "l separate wall openforge only",
        "tags": [
            "build|separate wall",
            "shape|wall",
            "connection|openforge",
            "texture|cave",
        ],
    },
    {
        "id": "8",
        "blueprint_name": "z corner wall",
        "tags": [
            "build|separate wall",
            "shape|wall|corner",
            "connection|openforge",
            "texture|dungeon_stone",
        ],
    },
    {
        "id": "7",
        "blueprint_name": "separate floor",
        "tags": ["build|separate wall", "shape|floor", "texture|cave"],
    },
]


def find_candidates(predicate, limit):
    """Stand-in for tag_search_blueprints, same predicate semantics."""

    def matches(blueprint):
        tags = blueprint["tags"]
        if any(tag not in tags for tag in predicate.get("require", [])):
            return False
        if any(tag in tags for tag in predicate.get("deny", [])):
            return False
        return all(
            any(t == tag or t.startswith(f"{tag}|") for t in tags)
            for tag in predicate.get("accept", [])
        )

    found = [b for b in CATALOG if matches(b)]
    found.sort(key=lambda b: b["blueprint_name"])
    return found[:limit]


@pytest.fixture
def guide():
    return copy.deepcopy(GUIDE)


def parts_by_role(resolved):
    return {part["role"]: part for part in resolved["parts"]}


def test_nothing_selected_resolves_no_parts(guide):
    resolved = resolve(guide, {}, find_candidates)

    assert resolved["parts"] == []
    assert [s["key"] for s in resolved["steps"]] == ["method"]


def test_one_answer_recommends_a_part_for_every_role(guide):
    resolved = resolve(guide, {"method": "s2w-modular"}, find_candidates)

    parts = parts_by_role(resolved)
    assert list(parts) == ["floor", "base", "wall"]
    assert parts["floor"]["blueprint"]["id"] == "3"
    assert parts["base"]["blueprint"]["id"] == "4"
    assert parts["wall"]["blueprint"]["id"] == "2"


def test_the_option_decides_which_roles_exist(guide):
    resolved = resolve(guide, {"method": "separate-wall"}, find_candidates)

    assert list(parts_by_role(resolved)) == ["floor", "wall"]


def test_a_role_carries_what_it_sits_under(guide):
    resolved = resolve(guide, {"method": "s2w-modular"}, find_candidates)

    assert parts_by_role(resolved)["base"]["under"] == "floor"


def test_the_composed_query_is_the_union_of_method_role_and_refinement(guide):
    resolved = resolve(
        guide,
        {"method": "separate-wall", "texture": "texture|dungeon_stone"},
        find_candidates,
    )

    query = parts_by_role(resolved)["wall"]["query"]
    assert query["require"] == [
        "shape|wall",
        "build|separate wall",
        "texture|dungeon_stone",
    ]
    assert query["deny"] == ["shape|base"]


def test_a_wildcard_refinement_reaches_every_role(guide):
    resolved = resolve(
        guide,
        {"method": "s2w-modular", "texture": "texture|cave"},
        find_candidates,
    )

    for part in resolved["parts"]:
        assert "texture|cave" in part["query"]["require"]


def test_prefer_beats_the_name_order(guide):
    """The preferred part wins even though it sorts last.

    Both s2w walls match the query and 'a s2w wall plain' sorts first,
    so a resolver that ignored `prefer` would return it. Ranking is the
    whole reason a shared URL means anything, so this has to be the
    thing under test rather than an accident of the fixture order.
    """
    resolved = resolve(guide, {"method": "s2w-modular"}, find_candidates)

    assert parts_by_role(resolved)["wall"]["blueprint"]["id"] == "2"


def test_prefer_drops_the_least_wanted_tag_until_something_matches(guide):
    # No s2w wall carries texture|dungeon_stone, the second preferred
    # tag, so requiring both matches nothing and the second is dropped.
    # Requiring only connection|openforge then finds one.
    resolved = resolve(guide, {"method": "s2w-modular"}, find_candidates)
    assert parts_by_role(resolved)["wall"]["blueprint"]["id"] == "2"

    # The whole list is required before any of it is dropped. Candidate
    # 9 carries the first preferred tag and not the second and sorts
    # before 5, so requiring only the first would pick it.
    resolved = resolve(guide, {"method": "separate-wall"}, find_candidates)
    assert parts_by_role(resolved)["wall"]["blueprint"]["id"] == "5"


def test_a_prefer_list_that_matches_nothing_still_recommends(guide):
    """Dropping runs all the way to the bare query, not to silence."""
    guide["roles"]["wall"]["prefer"] = ["texture|nonesuch"]

    resolved = resolve(guide, {"method": "s2w-modular"}, find_candidates)

    assert parts_by_role(resolved)["wall"]["blueprint"]["id"] == "1"


def test_equally_preferred_candidates_break_the_tie_on_name(guide):
    """Three separate walls carry the one preferred tag.

    With a single-tag `prefer` that all of them satisfy, ranking can
    separate none of them, so the order the catalog returns decides —
    and it is by name, which is what makes the result reproducible
    from the URL.
    """
    guide["roles"]["wall"]["prefer"] = ["connection|openforge"]

    resolved = resolve(guide, {"method": "separate-wall"}, find_candidates)

    assert (
        parts_by_role(resolved)["wall"]["blueprint"]["blueprint_name"]
        == "l separate wall openforge only"
    )


def test_a_role_that_matches_nothing_says_so(guide):
    guide["roles"]["base"]["query"] = {"require": ["shape|plinth"]}

    resolved = resolve(guide, {"method": "s2w-modular"}, find_candidates)

    assert parts_by_role(resolved)["base"]["blueprint"] is None


def test_a_step_is_unavailable_until_the_step_it_waits_on_is_answered(guide):
    assert [s["key"] for s in resolve(guide, {}, find_candidates)["steps"]] == [
        "method"
    ]

    resolved = resolve(guide, {"method": "s2w-modular"}, find_candidates)
    assert [s["key"] for s in resolved["steps"]] == ["method", "size"]


def test_a_later_answer_narrows_the_roles_it_names(guide):
    resolved = resolve(guide, {"method": "s2w-modular", "size": "two"}, find_candidates)

    assert "size|width|2" in parts_by_role(resolved)["wall"]["query"]["require"]


def test_a_refinement_appears_only_when_its_when_holds(guide):
    resolved = resolve(guide, {"method": "s2w-modular"}, find_candidates)
    assert [r["key"] for r in resolved["refinements"]] == ["texture"]

    resolved = resolve(guide, {"method": "separate-wall"}, find_candidates)
    assert [r["key"] for r in resolved["refinements"]] == [
        "texture",
        "side-locks",
    ]


def test_a_toggle_applies_on_tags_or_off_tags(guide):
    on = resolve(
        guide,
        {"method": "separate-wall", "side-locks": "on"},
        find_candidates,
    )
    assert parts_by_role(on)["wall"]["blueprint"]["id"] == "5"

    off = resolve(
        guide,
        {"method": "separate-wall", "side-locks": "off"},
        find_candidates,
    )
    assert parts_by_role(off)["wall"]["blueprint"]["id"] == "6"


def test_an_unreachable_refinement_is_ignored_not_an_error(guide):
    resolved = resolve(
        guide,
        {"method": "s2w-modular", "side-locks": "on"},
        find_candidates,
    )

    assert [r["key"] for r in resolved["refinements"]] == ["texture"]
    assert "connection|side|openlock" not in parts_by_role(resolved)["wall"][
        "query"
    ].get("require", [])


def test_a_selection_the_guide_has_no_key_for_is_a_bad_request(guide):
    with pytest.raises(GuideSelectionError, match="colour"):
        resolve(guide, {"method": "s2w-modular", "colour": "red"}, find_candidates)


def test_an_option_the_step_does_not_offer_is_a_bad_request(guide):
    with pytest.raises(GuideSelectionError, match="wall-on-tile"):
        resolve(guide, {"method": "wall-on-tile"}, find_candidates)


def test_a_toggle_takes_on_or_off(guide):
    with pytest.raises(GuideSelectionError, match="'on' or 'off'"):
        resolve(
            guide,
            {"method": "separate-wall", "side-locks": "yes"},
            find_candidates,
        )


def test_a_namespace_refinement_takes_a_tag_from_its_namespace(guide):
    with pytest.raises(GuideSelectionError, match="texture"):
        resolve(
            guide,
            {"method": "s2w-modular", "texture": "shape|wall"},
            find_candidates,
        )


def test_the_same_selections_always_resolve_the_same_way(guide):
    selections = {"method": "separate-wall", "texture": "texture|dungeon_stone"}

    first = resolve(guide, selections, find_candidates)
    second = resolve(copy.deepcopy(GUIDE), dict(selections), find_candidates)

    assert first == second


def test_a_chain_of_whens_composes(guide):
    """Answering the first question again drops everything below it.

    The engine tests each `when` against the answers to steps that are
    themselves reachable. Without that, a stale answer from a shared
    URL keeps a grandchild step alive after its parent has fallen away,
    and its tags go on narrowing the recommendation off a branch nobody
    is on any more.
    """
    guide["steps"] = [
        {
            "key": "a",
            "prompt": "a?",
            "options": [
                {"key": "a1", "title": "A1", "roles": {"wall": None}},
                {"key": "a2", "title": "A2", "roles": {"wall": None}},
            ],
        },
        {
            "key": "b",
            "prompt": "b?",
            "when": {"selected": {"a": ["a1"]}},
            "options": [{"key": "b1", "title": "B1", "roles": {"wall": None}}],
        },
        {
            "key": "c",
            "prompt": "c?",
            "when": {"selected": {"b": ["b1"]}},
            "options": [
                {
                    "key": "c1",
                    "title": "C1",
                    "roles": {"wall": {"require": ["texture|cave"]}},
                }
            ],
        },
    ]
    guide["refinements"] = [
        {
            "key": "side-locks",
            "role": "wall",
            "prompt": "Locks?",
            "when": {"selected": {"b": ["b1"]}},
            "on_tags": {"require": ["connection|side|openlock"]},
        }
    ]
    stale = {"a": "a2", "b": "b1", "c": "c1", "side-locks": "on"}

    resolved = resolve(guide, stale, find_candidates)

    assert [step["key"] for step in resolved["steps"]] == ["a"]
    assert resolved["refinements"] == []
    assert parts_by_role(resolved)["wall"]["query"] == {
        "require": ["shape|wall"],
        "deny": ["shape|base"],
    }


def test_the_answers_come_back_with_the_questions(guide):
    """The page renders from this, and the URL is restored through it."""
    resolved = resolve(
        guide,
        {"method": "s2w-modular", "texture": "texture|cave"},
        find_candidates,
    )

    steps = {step["key"]: step for step in resolved["steps"]}
    assert steps["method"]["selected"] == "s2w-modular"
    assert steps["size"]["selected"] is None
    refinements = {r["key"]: r for r in resolved["refinements"]}
    assert refinements["texture"]["selected"] == "texture|cave"


def test_every_part_carries_the_role_title(guide):
    resolved = resolve(guide, {"method": "s2w-modular"}, find_candidates)

    assert parts_by_role(resolved)["wall"]["title"] == "Wall"
    assert parts_by_role(resolved)["base"]["title"] == "Base"


def test_a_tag_asked_for_twice_appears_once(guide):
    """The role and the option can want the same tag."""
    guide["steps"][0]["options"][0]["roles"]["wall"] = {
        "require": ["shape|wall", "build|s2w"]
    }

    resolved = resolve(guide, {"method": "s2w-modular"}, find_candidates)

    assert parts_by_role(resolved)["wall"]["query"]["require"] == [
        "shape|wall",
        "build|s2w",
    ]


def test_a_role_two_options_both_name_is_resolved_once(guide):
    guide["steps"][1]["options"][0]["roles"] = {"wall": None}

    resolved = resolve(guide, {"method": "s2w-modular", "size": "two"}, find_candidates)

    assert [part["role"] for part in resolved["parts"]].count("wall") == 1


def test_accept_matches_a_tag_or_anything_below_it(guide):
    """`accept` is the predicate that reaches into a subtree.

    The corner wall carries `shape|wall|corner` and not `shape|wall`,
    so only an `accept` can see it. Nothing else in the role narrows
    the query, so if `accept` were dropped from the composition the
    role would match every separate wall and pick another part.
    """
    guide["roles"]["wall"]["query"] = {
        "accept": ["shape|wall"],
        "deny": ["shape|wall"],
    }
    guide["roles"]["wall"]["prefer"] = []

    resolved = resolve(guide, {"method": "separate-wall"}, find_candidates)

    wall = parts_by_role(resolved)["wall"]
    assert wall["query"]["accept"] == ["shape|wall"]
    # Only the corner wall survives: `deny` removes everything carrying
    # `shape|wall` exactly, and `accept` still reaches the one that
    # carries `shape|wall|corner` beneath it. That difference between
    # the two predicates is the whole point, and an exact-tag accept
    # would not have exercised it.
    assert wall["blueprint"]["id"] == "8"


def test_a_selection_that_is_not_a_string_is_a_bad_request(guide):
    """A repeated query parameter arrives as a list.

    Both halves matter: the refinement path and the step path each do
    a lookup that raises TypeError on an unhashable value, which would
    be a 500 where the honest answer is 400.
    """
    with pytest.raises(GuideSelectionError, match="takes a string"):
        resolve(
            guide,
            {"method": "s2w-modular", "texture": ["texture|cave"]},
            find_candidates,
        )

    with pytest.raises(GuideSelectionError, match="takes a string"):
        resolve(guide, {"method": ["s2w-modular"]}, find_candidates)


def test_the_catalog_gets_predicates_in_the_shape_it_understands():
    """Bare strings are silently ignored by the tag search.

    `tag_search_blueprints` looks for `{"tag": ...}` dicts and skips
    anything else, so handing it a guide predicate unconverted drops
    every term: a lost `require` matches everything, a lost `deny`
    matches nothing. This is the one conversion point.
    """
    assert to_tag_query({"require": ["shape|wall"], "deny": ["shape|base"]}) == {
        "accept": [],
        "require": [{"tag": "shape|wall"}],
        "deny": [{"tag": "shape|base"}],
    }

    # All three keys are always present, because the search takes them
    # as required positional arguments and a predicate need not use
    # every one.
    # Every argument the search has no default for, other than the
    # cursor, has to come from here — that is the property that makes
    # the result splattable, and it would not survive `accept` being
    # given a default.
    required = {
        name
        for name, p in inspect.signature(tag_search_blueprints).parameters.items()
        if p.default is inspect.Parameter.empty and name != "curs"
    }
    assert required == {"accept", "require", "deny"}
    assert required <= set(to_tag_query({}))
