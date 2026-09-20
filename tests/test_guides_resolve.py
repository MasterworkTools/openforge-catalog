import copy

import pytest

from openforge.guides.resolve import resolve

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
        "blueprint_name": "s2w wall plain",
        "tags": ["build|s2w", "shape|wall", "texture|cave"],
    },
    {
        "id": "2",
        "blueprint_name": "s2w wall openforge",
        "tags": [
            "build|s2w",
            "shape|wall",
            "connection|openforge",
            "texture|cave",
        ],
    },
    {
        "id": "3",
        "blueprint_name": "s2w floor",
        "tags": ["build|s2w", "shape|floor", "texture|cave"],
    },
    {
        "id": "4",
        "blueprint_name": "base square",
        "tags": ["shape|base", "texture|cave"],
    },
    {
        "id": "5",
        "blueprint_name": "separate wall openlock",
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
        "blueprint_name": "separate wall plain",
        "tags": [
            "build|separate wall",
            "shape|wall",
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


def test_prefer_picks_the_preferred_candidate(guide):
    resolved = resolve(guide, {"method": "s2w-modular"}, find_candidates)

    # Both s2w walls match; the openforge one wins on prefer even though
    # the plain one sorts first by name.
    assert parts_by_role(resolved)["wall"]["blueprint"]["id"] == "2"


def test_prefer_drops_the_least_wanted_tag_until_something_matches(guide):
    # No s2w wall carries texture|dungeon_stone, so the second preferred
    # tag is dropped and the openforge one is still chosen.
    resolved = resolve(guide, {"method": "s2w-modular"}, find_candidates)
    assert parts_by_role(resolved)["wall"]["blueprint"]["id"] == "2"

    # Every separate wall carries both preferred tags, so the tie breaks
    # on name and is therefore stable.
    resolved = resolve(guide, {"method": "separate-wall"}, find_candidates)
    assert parts_by_role(resolved)["wall"]["blueprint"]["id"] == "5"


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
    with pytest.raises(ValueError, match="colour"):
        resolve(guide, {"method": "s2w-modular", "colour": "red"}, find_candidates)


def test_an_option_the_step_does_not_offer_is_a_bad_request(guide):
    with pytest.raises(ValueError, match="wall-on-tile"):
        resolve(guide, {"method": "wall-on-tile"}, find_candidates)


def test_a_toggle_takes_on_or_off(guide):
    with pytest.raises(ValueError, match="'on' or 'off'"):
        resolve(
            guide,
            {"method": "separate-wall", "side-locks": "yes"},
            find_candidates,
        )


def test_a_namespace_refinement_takes_a_tag_from_its_namespace(guide):
    with pytest.raises(ValueError, match="texture"):
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
