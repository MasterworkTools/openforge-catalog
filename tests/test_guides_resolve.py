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


def find_candidates(predicate):
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
    return found


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
    # before 5, so requiring only the first would pick it. 5 and 6 then
    # tie on both preferred tags and the name decides — a guarantee the
    # engine cannot make, so it is tested where it lives, against the
    # ORDER BY in tests/test_tags_sql.py.
    resolved = resolve(guide, {"method": "separate-wall"}, find_candidates)
    assert parts_by_role(resolved)["wall"]["blueprint"]["id"] == "5"


def test_a_prefer_list_that_matches_nothing_still_recommends(guide):
    """Dropping runs all the way to the bare query, not to silence."""
    guide["roles"]["wall"]["prefer"] = ["texture|nonesuch"]

    resolved = resolve(guide, {"method": "s2w-modular"}, find_candidates)

    assert parts_by_role(resolved)["wall"]["blueprint"]["id"] == "1"


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
    # The floor role accepts a tag its candidates carry exactly, so
    # both halves of `accept` — the exact match and the subtree — are
    # exercised rather than only whichever one the wall needs.
    guide["roles"]["floor"]["query"] = {"accept": ["shape|floor"]}

    resolved = resolve(guide, {"method": "separate-wall"}, find_candidates)

    assert parts_by_role(resolved)["floor"]["blueprint"]["id"] == "7"
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
    assert to_tag_query(
        {
            "require": ["shape|wall"],
            "deny": ["shape|base"],
            "deny_children": ["component|wall"],
            "allow": ["component|wall|arch"],
        }
    ) == {
        "accept": [],
        "require": [{"tag": "shape|wall"}],
        "deny": [{"tag": "shape|base"}],
        "deny_children": [{"tag": "component|wall"}],
        "allow": [{"tag": "component|wall|arch"}],
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


MATCHING_GUIDE = {
    "key": "matching",
    "title": "A guide whose bases match what they carry",
    "steps": [
        {
            "key": "method",
            "prompt": "How?",
            "options": [
                {
                    "key": "separate",
                    "title": "Separate",
                    # Bases named before the parts they sit under, so
                    # that resolving in the order they are mentioned
                    # would ask a base for a size nobody has chosen
                    # yet. The dependency has to drive the order.
                    "roles": {
                        "floor-base": None,
                        "floor": {"require": ["shape|floor"]},
                        "wall-base": None,
                        "wall": {"require": ["shape|wall"]},
                    },
                },
                {
                    # A base with nothing above it in this branch. Not
                    # a mistake: an option chooses which parts a build
                    # has, and "just the bases" is a build the engine
                    # has to answer rather than refuse.
                    "key": "bases-only",
                    "title": "Bases only",
                    "roles": {"wall-base": None},
                },
            ],
        }
    ],
    "roles": {
        # Declared base-first on purpose: a base has to resolve after
        # the part it copies from, whatever order the document lists
        # them in.
        "floor-base": {
            "title": "Base for the floor",
            "query": {"require": ["shape|base"]},
            "under": "floor",
            "match": ["size|width", "size|depth"],
        },
        "wall-base": {
            "title": "Base for the wall",
            "query": {"require": ["shape|base"]},
            "under": "wall",
            "match": ["size|width"],
        },
        "floor": {"title": "Floor", "query": {"require": ["shape|floor"]}},
        "wall": {"title": "Wall", "query": {"require": ["shape|wall"]}},
    },
}

MATCHING_CATALOG = [
    {
        "id": "f1",
        "blueprint_name": "a floor",
        "tags": ["shape|floor", "size|width|2", "size|depth|2"],
    },
    {
        "id": "w1",
        "blueprint_name": "a wall",
        "tags": ["shape|wall", "size|width|2"],
    },
    {
        "id": "b1",
        "blueprint_name": "a 2x2 base",
        "tags": ["shape|base", "size|width|2", "size|depth|2"],
    },
    {
        "id": "b2",
        "blueprint_name": "b 1x1 base",
        "tags": ["shape|base", "size|width|1", "size|depth|1"],
    },
]


def matching_finder(catalog):
    def find_candidates(predicate):
        def matches(blueprint):
            tags = blueprint["tags"]
            if any(tag not in tags for tag in predicate.get("require", [])):
                return False
            return all(tag not in tags for tag in predicate.get("deny", []))

        found = [b for b in catalog if matches(b)]
        found.sort(key=lambda b: b["blueprint_name"])
        return found

    return find_candidates


def test_a_base_takes_the_size_of_the_part_it_sits_under():
    """A base has to fit the footprint of the piece standing on it.

    The size is not knowable when the guide is written — it depends on
    what the floor turned out to be — so the role copies it from the
    resolved part rather than naming it.
    """
    resolved = resolve(
        MATCHING_GUIDE, {"method": "separate"}, matching_finder(MATCHING_CATALOG)
    )
    parts = {p["role"]: p for p in resolved["parts"]}

    # "b 1x1 base" sorts first, so without matching it would win.
    assert parts["floor-base"]["blueprint"]["blueprint_name"] == "a 2x2 base"
    assert "size|width|2" in parts["floor-base"]["query"]["require"]
    assert "size|depth|2" in parts["floor-base"]["query"]["require"]


def test_a_wall_base_matches_the_width_and_asks_for_no_depth():
    """A wall is a line along an edge: it has a width and no depth.

    Matching `size|depth` against it must add nothing rather than
    requiring a depth no wall carries, which would match no base.
    """
    resolved = resolve(
        MATCHING_GUIDE, {"method": "separate"}, matching_finder(MATCHING_CATALOG)
    )
    parts = {p["role"]: p for p in resolved["parts"]}

    required = parts["wall-base"]["query"]["require"]
    assert "size|width|2" in required
    assert not [tag for tag in required if tag.startswith("size|depth")]
    assert parts["wall-base"]["blueprint"]["blueprint_name"] == "a 2x2 base"


def test_a_base_for_a_part_that_resolved_to_nothing_resolves_to_nothing():
    """Otherwise the size it falls back on is arbitrary.

    A 1x1 base sitting under an absent 3x1 floor reads as an answer
    rather than as the gap it is, and it is the wrong base for the
    floor the person actually asked for.
    """
    without_floor = [b for b in MATCHING_CATALOG if b["id"] != "f1"]

    resolved = resolve(
        MATCHING_GUIDE, {"method": "separate"}, matching_finder(without_floor)
    )
    parts = {p["role"]: p for p in resolved["parts"]}

    assert parts["floor"]["blueprint"] is None
    assert parts["floor-base"]["blueprint"] is None
    # The wall is unaffected: only the base that matches against the
    # missing part goes with it.
    assert parts["wall"]["blueprint"]["blueprint_name"] == "a wall"
    assert parts["wall-base"]["blueprint"] is not None


def test_parts_are_listed_in_the_order_the_options_asked_for_them():
    """Resolution order is a dependency, not a reading order.

    This option names the bases first, so they have to resolve last
    and still be reported first. Getting this wrong is invisible in a
    document that happens to name parts before their bases, which is
    why this one deliberately does not.
    """
    resolved = resolve(
        MATCHING_GUIDE, {"method": "separate"}, matching_finder(MATCHING_CATALOG)
    )

    assert [p["role"] for p in resolved["parts"]] == [
        "floor-base",
        "floor",
        "wall-base",
        "wall",
    ]


GATED_GUIDE = {
    "key": "gated",
    "title": "A guide where one answer rules out some of the next",
    "steps": [
        {
            "key": "method",
            "prompt": "How?",
            "options": [
                {"key": "deep", "title": "Deep", "roles": {"floor": None}},
                {"key": "flat", "title": "Flat", "roles": {"floor": None}},
            ],
        },
        {
            "key": "size",
            "prompt": "What size?",
            "options": [
                {
                    "key": "2x1",
                    "title": "2x1",
                    "when": {"selected": {"method": ["flat"]}},
                    "tags": {"require": ["size|2x1"]},
                },
                {"key": "2x2", "title": "2x2", "tags": {"require": ["size|2x2"]}},
            ],
        },
    ],
    "roles": {"floor": {"title": "Floor", "query": {"require": ["shape|floor"]}}},
}

GATED_CATALOG = [
    {"id": "a", "blueprint_name": "a 2x1", "tags": ["shape|floor", "size|2x1"]},
    {"id": "b", "blueprint_name": "b 2x2", "tags": ["shape|floor", "size|2x2"]},
]


def test_an_option_can_be_ruled_out_by_an_earlier_answer():
    """Gating a whole step is too blunt when it is some of its options.

    The catalog has no s2w tile shallower than it is wide, so the
    depth-1 sizes are not offered once s2w is chosen — but the other
    sizes still are, and the question still needs asking.
    """
    finder = matching_finder(GATED_CATALOG)

    flat = resolve(GATED_GUIDE, {"method": "flat"}, finder)
    deep = resolve(GATED_GUIDE, {"method": "deep"}, finder)

    offered = {
        step["key"]: [o["key"] for o in step["options"]] for step in flat["steps"]
    }
    assert offered["size"] == ["2x1", "2x2"]

    offered = {
        step["key"]: [o["key"] for o in step["options"]] for step in deep["steps"]
    }
    assert offered["size"] == ["2x2"]


def test_an_answer_this_branch_does_not_offer_counts_as_unanswered():
    """Rather than 400ing a URL someone reached by clicking.

    Answer the size, then change the method to one that does not offer
    that size: the question is asked again, and the parts resolve
    without it. A bad *key* is still a bad request — this is a real
    key that this branch does not have.
    """
    finder = matching_finder(GATED_CATALOG)

    resolved = resolve(GATED_GUIDE, {"method": "deep", "size": "2x1"}, finder)

    size = [step for step in resolved["steps"] if step["key"] == "size"][0]
    assert size["selected"] is None
    # ...and the narrowing that option would have applied is not in
    # force: the floor is whatever the catalog offers first.
    parts = {p["role"]: p for p in resolved["parts"]}
    assert "size|2x1" not in parts["floor"]["query"].get("require", [])


def test_a_key_no_step_has_is_still_a_bad_request():
    """The leniency above is narrow, and this is the boundary."""
    finder = matching_finder(GATED_CATALOG)

    with pytest.raises(GuideSelectionError, match="nonesuch"):
        resolve(GATED_GUIDE, {"method": "deep", "size": "nonesuch"}, finder)


SUBSTITUTE_GUIDE = {
    "key": "substituting",
    "title": "A guide where one answer means different tags per part",
    "steps": [
        {
            "key": "method",
            "prompt": "How?",
            "options": [
                {
                    "key": "only",
                    "title": "Only",
                    "roles": {"wall": None, "wall-base": None, "floor-base": None},
                }
            ],
        }
    ],
    "roles": {
        "wall": {"title": "Wall", "query": {"require": ["shape|wall"]}},
        "wall-base": {"title": "Wall base", "query": {"require": ["shape|base|wall"]}},
        "floor-base": {
            "title": "Floor base",
            "query": {"require": ["shape|base|square"]},
        },
    },
    "refinements": [
        {
            "key": "texture",
            "role": "*",
            "prompt": "Texture",
            "from_namespace": "texture",
            # The floor base is structurally plain, so the question does
            # not apply to it; the wall base takes wood for towne,
            # because no towne base exists.
            "except_roles": ["floor-base"],
            "substitute": {"texture|towne": {"wall-base": "texture|wood"}},
        }
    ],
}

SUBSTITUTE_CATALOG = [
    {
        "id": "w",
        "blueprint_name": "a towne wall",
        "tags": ["shape|wall", "texture|towne"],
    },
    {
        "id": "wb",
        "blueprint_name": "b wood wall base",
        "tags": ["shape|base|wall", "texture|wood"],
    },
    {
        "id": "wbt",
        "blueprint_name": "c towne wall base",
        "tags": ["shape|base|wall", "texture|towne"],
    },
    {
        "id": "fb",
        "blueprint_name": "d plain square base",
        "tags": ["shape|base|square", "texture|plain"],
    },
]


def test_a_refinement_can_mean_a_different_tag_for_a_different_part():
    """Choosing towne has to mean wood for the base that carries it.

    The catalog has 441 towne walls and no towne base at all, because a
    towne building stands on a wood base. Without the substitution the
    base role asks for a piece that does not exist.
    """
    resolved = resolve(
        SUBSTITUTE_GUIDE,
        {"method": "only", "texture": "texture|towne"},
        matching_finder(SUBSTITUTE_CATALOG),
    )
    parts = {p["role"]: p for p in resolved["parts"]}

    assert parts["wall"]["blueprint"]["blueprint_name"] == "a towne wall"
    # The towne wall base sorts later but would match; the wood one is
    # what the substitution asked for.
    assert parts["wall-base"]["blueprint"]["blueprint_name"] == "b wood wall base"
    assert "texture|wood" in parts["wall-base"]["query"]["require"]


def test_a_role_can_be_outside_the_question_a_refinement_asks():
    """A floor base is plain whatever the walls are made of.

    Every base carrying `shape|base|square` is `texture|plain`, so this
    is not an exception to substitute — it is a part the question does
    not apply to, and asking it would empty the role.
    """
    resolved = resolve(
        SUBSTITUTE_GUIDE,
        {"method": "only", "texture": "texture|towne"},
        matching_finder(SUBSTITUTE_CATALOG),
    )
    parts = {p["role"]: p for p in resolved["parts"]}

    assert parts["floor-base"]["blueprint"]["blueprint_name"] == "d plain square base"
    assert not [
        tag
        for tag in parts["floor-base"]["query"].get("require", [])
        if tag.startswith("texture|")
    ]


def test_a_role_with_no_substitution_is_asked_for_what_was_chosen():
    """The exception list is an exception, not the rule."""
    resolved = resolve(
        SUBSTITUTE_GUIDE,
        {"method": "only", "texture": "texture|wood"},
        matching_finder(SUBSTITUTE_CATALOG),
    )
    parts = {p["role"]: p for p in resolved["parts"]}

    assert "texture|wood" in parts["wall-base"]["query"]["require"]
    assert "texture|wood" in parts["wall"]["query"]["require"]


def test_a_base_whose_part_is_not_in_play_still_resolves():
    """Not in play and resolved-to-nothing are different answers.

    A role the chosen option never named is not a part that failed —
    it is a part this build does not have. Matching against it can add
    no constraint, so the base resolves on its own query. Conflating
    the two empties every base in an option that names bases alone.
    """
    resolved = resolve(
        MATCHING_GUIDE, {"method": "bases-only"}, matching_finder(MATCHING_CATALOG)
    )
    parts = {p["role"]: p for p in resolved["parts"]}

    assert list(parts) == ["wall-base"]
    # No size came from anywhere, so the first base by name wins.
    assert parts["wall-base"]["blueprint"]["blueprint_name"] == "a 2x2 base"
    assert not [
        tag for tag in parts["wall-base"]["query"]["require"] if tag.startswith("size|")
    ]


def test_matching_a_namespace_stops_at_the_separator():
    """`size|width` is not a prefix of `size|widthwise`.

    Without the separator the match would copy a neighbouring
    namespace's tag into `require`, and since no base carries it the
    base would come back empty — a wrong answer that looks like an
    honest "nothing matches".
    """
    catalog = copy.deepcopy(MATCHING_CATALOG)
    wall = next(b for b in catalog if b["id"] == "w1")
    wall["tags"] = wall["tags"] + ["size|widthwise|9"]

    resolved = resolve(MATCHING_GUIDE, {"method": "separate"}, matching_finder(catalog))
    parts = {p["role"]: p for p in resolved["parts"]}

    assert parts["wall-base"]["query"]["require"] == ["shape|base", "size|width|2"]
    assert parts["wall-base"]["blueprint"] is not None


def test_matching_copies_a_tag_that_is_the_namespace_itself():
    """The other half of the same test: an exact tag is in its own
    namespace, and a match that only looked for children would drop it.
    """
    catalog = copy.deepcopy(MATCHING_CATALOG)
    wall = next(b for b in catalog if b["id"] == "w1")
    wall["tags"] = ["shape|wall", "size|width"]
    base = next(b for b in catalog if b["id"] == "b1")
    base["tags"] = base["tags"] + ["size|width"]

    resolved = resolve(MATCHING_GUIDE, {"method": "separate"}, matching_finder(catalog))
    parts = {p["role"]: p for p in resolved["parts"]}

    assert parts["wall-base"]["query"]["require"] == ["shape|base", "size|width"]
