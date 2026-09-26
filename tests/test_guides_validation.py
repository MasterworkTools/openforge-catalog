import copy
import re
from pathlib import Path

import pytest
import yaml

from openforge.guides.validation import validate_guide_document

WALL_GUIDE = {
    "key": "wall",
    "title": "How do I make a wall?",
    "summary": "Three ways, and the difference is where the wall meets the floor.",
    "steps": [
        {
            "key": "method",
            "prompt": "How do you want to build it?",
            "options": [
                {
                    "key": "s2w-modular",
                    "title": "Modular (s2w)",
                    "blurb": "Wall, floor and base print separately.",
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
        }
    ],
    "roles": {
        "wall": {
            "title": "Wall",
            "query": {"require": ["shape|wall"], "deny": ["shape|base"]},
            "prefer": ["connection|openforge"],
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
            "when": {"selected": {"method": ["s2w-modular", "separate-wall"]}},
            "on_tags": {"require": ["connection|side|openlock"]},
            "off_tags": {"deny": ["connection|side|openlock"]},
        },
    ],
}


@pytest.fixture
def guide():
    """A sound guide, for tests to break one way at a time."""
    return copy.deepcopy(WALL_GUIDE)


def test_a_sound_guide_validates_and_comes_back_unchanged(guide):
    """Callers use the document they passed in, so it must survive.

    The loader validates and then writes its own `data`, which is the
    same object; anything this function did to the document on the way
    through would land in the database unnoticed.
    """
    before = copy.deepcopy(guide)

    result = validate_guide_document(guide)

    assert result is guide
    assert result == before


def test_schema_error_names_the_offending_step(guide):
    del guide["steps"][0]["options"][0]["title"]

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "step 'method'" in str(excinfo.value)
    assert "option 's2w-modular'" in str(excinfo.value)


def test_schema_error_names_the_offending_role(guide):
    guide["roles"]["wall"]["query"] = {}

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "role 'wall'" in str(excinfo.value)


def test_a_refinement_is_a_namespace_pick_or_a_toggle_not_both(guide):
    guide["refinements"][0]["on_tags"] = {"require": ["texture|cave"]}

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "refinement 'texture'" in str(excinfo.value)


def test_an_option_may_not_name_a_role_that_does_not_exist(guide):
    guide["steps"][0]["options"][0]["roles"] = {"floor": None, "plinth": None}

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "unknown role 'plinth'" in str(excinfo.value)
    assert "option 's2w-modular'" in str(excinfo.value)


def test_a_role_may_not_sit_under_a_role_that_does_not_exist(guide):
    guide["roles"]["base"]["under"] = "terrace"

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "role 'base'" in str(excinfo.value)
    assert "terrace" in str(excinfo.value)


def test_a_refinement_may_not_name_a_role_that_does_not_exist(guide):
    guide["refinements"][1]["role"] = "parapet"

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "refinement 'side-locks'" in str(excinfo.value)
    assert "parapet" in str(excinfo.value)


def test_a_refinement_role_may_be_the_wildcard(guide):
    guide["refinements"][1]["role"] = "*"

    assert validate_guide_document(guide) is guide


def test_when_may_not_name_a_step_that_does_not_exist(guide):
    guide["refinements"][1]["when"] = {"selected": {"approach": ["a"]}}

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "unknown step 'approach'" in str(excinfo.value)


def test_when_may_not_name_an_option_the_step_does_not_offer(guide):
    guide["refinements"][1]["when"] = {"selected": {"method": ["wall-on-tile"]}}

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "unknown option 'wall-on-tile'" in str(excinfo.value)


def test_a_step_may_not_depend_on_a_later_step(guide):
    guide["steps"].append(
        {
            "key": "finish",
            "prompt": "Finish?",
            "options": [{"key": "plain", "title": "Plain", "roles": {"wall": None}}],
        }
    )
    guide["steps"][0]["when"] = {"selected": {"finish": ["plain"]}}

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "step 'method'" in str(excinfo.value)
    assert "does not come before it" in str(excinfo.value)


def test_duplicate_step_keys_are_rejected(guide):
    guide["steps"].append(copy.deepcopy(guide["steps"][0]))

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "duplicate step key 'method'" in str(excinfo.value)


def test_duplicate_option_keys_within_a_step_are_rejected(guide):
    options = guide["steps"][0]["options"]
    options.append(copy.deepcopy(options[0]))

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "duplicate option in step 'method' key 's2w-modular'" in str(excinfo.value)


def test_every_problem_is_reported_not_just_the_first(guide):
    guide["steps"][0]["options"][0]["roles"] = {"plinth": None}
    guide["refinements"][1]["role"] = "parapet"

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "plinth" in str(excinfo.value)
    assert "parapet" in str(excinfo.value)


def test_a_guide_key_must_be_url_safe(guide):
    guide["key"] = "How To Wall"

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "How To Wall" in str(excinfo.value) or "pattern" in str(excinfo.value)


def test_guides_do_not_use_constrain(guide):
    guide["roles"]["base"]["query"]["constrain"] = ["size|width"]

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "role 'base'" in str(excinfo.value)


def test_the_design_documents_example_guide_is_a_valid_guide():
    """The sketch in the design doc is what people will copy from.

    A reviewer caught it referring to an option key that had been
    renamed, which the loader would reject; this keeps the example and
    the validator honest about each other.
    """
    doc = Path("docs/design/guided-builds.md")
    if not doc.exists():
        pytest.skip("design document not in this checkout")
    block = re.search(r"```yaml\n(.*?)```", doc.read_text(), re.S)
    assert block, "the design document no longer contains a guide example"

    validate_guide_document(yaml.safe_load(block.group(1)))


def test_an_option_need_not_name_any_role(guide):
    """A later step may narrow the build without adding to it."""
    guide["steps"].append(
        {
            "key": "width",
            "prompt": "How wide?",
            "when": {"selected": {"method": ["s2w-modular"]}},
            "options": [
                {
                    "key": "2",
                    "title": "2 inch",
                    "tags": {"require": ["size|width|2"]},
                }
            ],
        }
    )

    assert validate_guide_document(guide) is guide


def test_duplicate_refinement_keys_are_rejected(guide):
    guide["refinements"].append(copy.deepcopy(guide["refinements"][0]))

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "duplicate refinement key 'texture'" in str(excinfo.value)


def test_a_refinement_may_not_reuse_a_step_key(guide):
    """One flat namespace: a selection is <key> = <answer>.

    That is what lets the whole state fit in a query string, so a
    refinement sharing a step's key would collide there — and the
    engine would not know which of the two an answer belongs to.
    """
    guide["refinements"][0]["key"] = "method"

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "a step already uses that key" in str(excinfo.value)


def test_a_role_may_not_sit_under_itself(guide):
    guide["roles"]["base"]["under"] = "base"

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "runs in a circle" in str(excinfo.value)


def test_two_roles_may_not_sit_under_each_other(guide):
    guide["roles"]["base"]["under"] = "wall"
    guide["roles"]["wall"]["under"] = "base"

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    message = str(excinfo.value)
    assert "runs in a circle" in message
    # Once, naming both members — not once per role in the document.
    assert message.count("runs in a circle") == 1
    assert "'wall'" in message and "'base'" in message


def test_a_role_downstream_of_a_cycle_is_not_accused(guide):
    """`floor` sits above a cycle; it is not part of one.

    Reporting per role that *reaches* a cycle would name it, which
    sends the author looking at the wrong role.
    """
    guide["roles"]["floor"]["under"] = "wall"
    guide["roles"]["wall"]["under"] = "base"
    guide["roles"]["base"]["under"] = "wall"

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    message = str(excinfo.value)
    assert message.count("runs in a circle") == 1
    assert "'wall'" in message and "'base'" in message
    assert "'floor'" not in message


def test_a_role_no_option_names_is_rejected(guide):
    """An orphan role is not "nothing matches" — it is never asked."""
    guide["roles"]["plinth"] = {
        "title": "Plinth",
        "query": {"require": ["shape|base"]},
    }

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "role 'plinth': no option names it" in str(excinfo.value)


@pytest.mark.parametrize(
    "break_it",
    [
        pytest.param(lambda g: g["steps"][0].__setitem__("key", "a=b&c"), id="step"),
        pytest.param(
            lambda g: g["steps"][0]["options"][0].__setitem__("key", "a b"),
            id="option",
        ),
        pytest.param(
            lambda g: g["refinements"][0].__setitem__("key", "Texture!"),
            id="refinement",
        ),
        pytest.param(
            lambda g: g["roles"].__setitem__("Wall Role", g["roles"]["wall"]),
            id="role",
        ),
    ],
)
def test_keys_that_go_in_a_url_are_restricted(guide, break_it):
    """Each case must fail on the pattern, not on something else.

    Without the match= this passed for three of the four keys on an
    unrelated cross-reference error — renaming a role, for instance,
    also orphans it. Schema errors short-circuit the cross-reference
    pass, so the pattern error is what every case should produce.
    """
    break_it(guide)

    with pytest.raises(ValueError, match="does not match"):
        validate_guide_document(guide)


def test_a_key_may_not_carry_a_trailing_newline(guide):
    """`key: |` in YAML is a block scalar, and yields "wall\n".

    Python's `$` matches before a trailing newline, so the pattern has
    to end with \\Z or a key can arrive with one attached.
    """
    guide["steps"][0]["key"] = "method\n"

    with pytest.raises(ValueError, match="does not match"):
        validate_guide_document(guide)


def test_a_key_may_use_the_underscores_the_catalog_is_full_of(guide):
    """An author names options after tags, and tags are snake_case."""
    guide["steps"][0]["options"][0]["key"] = "wall_on_tile"
    guide["refinements"][1]["when"]["selected"]["method"] = ["wall_on_tile"]

    assert validate_guide_document(guide) is guide


def test_a_namespace_refinement_may_not_also_carry_a_toggle(guide):
    """The schema's oneOf has to forbid the mixture it describes."""
    guide["refinements"][0]["off_tags"] = {"deny": ["texture|cave"]}

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "refinement 'texture'" in str(excinfo.value)


def test_prefer_holds_tags_like_every_other_list(guide):
    guide["roles"]["wall"]["prefer"] = ["not a tag|"]

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "role 'wall'" in str(excinfo.value)


def test_a_choice_must_sit_inside_the_namespace_it_offers(guide):
    """Otherwise it is a button that raises the moment it is clicked.

    Resolve refuses a value from outside `from_namespace`, so a choice
    outside it is offered and then rejected — a fault the author can
    only find by trying every option.
    """
    guide["refinements"][0]["choices"] = [
        {"tag": "texture|cave"},
        {"tag": "connection|pegs"},
    ]

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "refinement 'texture'" in str(excinfo.value)
    assert "connection|pegs" in str(excinfo.value)


def test_choices_need_a_namespace_to_be_choices_of(guide):
    """A toggle already names its own tags, so a list on one reads
    nothing."""
    guide["refinements"][1]["choices"] = [
        {"tag": "connection|pegs"},
        {"tag": "connection|side|openlock"},
    ]

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "`choices` needs `from_namespace`" in str(excinfo.value)


def test_the_same_choice_may_not_be_offered_twice(guide):
    guide["refinements"][0]["choices"] = [
        {"tag": "texture|cave"},
        {"tag": "texture|cave"},
    ]

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "duplicate" in str(excinfo.value)


def test_a_sound_choice_list_validates(guide):
    guide["refinements"][0]["choices"] = [
        {"tag": "texture|cave", "title": "Cave", "blurb": "Rough rock."},
        {"tag": "texture|dungeon_stone"},
    ]

    assert validate_guide_document(guide) is guide


def test_every_clause_of_a_conditional_default_names_a_real_answer(guide):
    """A recommendation is used before anyone clicks anything.

    A conditional one hides its mistakes better than a plain one: the
    misspelled clause is on a branch, so the guide looks right until
    somebody reaches that branch and the parts empty for no visible
    reason. So each clause is checked, not just the first.
    """
    guide["steps"][0]["default"] = [
        {"when": {"selected": {"method": ["separate-wall"]}}, "value": "separate-wall"},
        {"value": "s2w-modualr"},
    ]

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "step 'method'" in str(excinfo.value)
    assert "s2w-modualr" in str(excinfo.value)
