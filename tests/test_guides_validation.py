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
    """The loader writes what this returns, so identity matters."""
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

    assert "runs in a circle" in str(excinfo.value)


def test_a_role_no_option_names_is_rejected(guide):
    """An orphan role is not "nothing matches" — it is never asked."""
    guide["roles"]["plinth"] = {
        "title": "Plinth",
        "query": {"require": ["shape|base"]},
    }

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "role 'plinth': no option names it" in str(excinfo.value)


def test_keys_that_go_in_a_url_are_restricted(guide):
    guide["steps"][0]["key"] = "a=b&c"

    with pytest.raises(ValueError) as excinfo:
        validate_guide_document(guide)

    assert "a=b&c" in str(excinfo.value) or "pattern" in str(excinfo.value)


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
