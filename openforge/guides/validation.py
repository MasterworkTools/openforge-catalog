"""Validation for guide documents.

Two passes: the JSON schema (openforge/openapi/schemas/guide.yaml) for
shape, then the cross-references the schema cannot express — an option
naming a role that does not exist, a `when` pointing at a step that
comes later, a duplicate key. Both raise ValueError naming the step,
role or refinement at fault, because guides are hand-authored fixtures
and "does not match schema" at the document root is useless to whoever
is writing one.
"""

from jsonschema.exceptions import ValidationError

from openforge.openapi import validate_schema


def validate_guide_document(data: dict) -> dict:
    """Validate a guide document, returning it unchanged if it is sound.

    Raises:
        ValueError: with one line per problem, each naming its location.
    """
    _validate_shape(data)
    errors = _cross_reference_errors(data)
    if errors:
        key = data.get("key", "<no key>")
        joined = "\n  ".join(errors)
        raise ValueError(f"guide {key!r} is invalid:\n  {joined}")
    return data


def _validate_shape(data: dict):
    try:
        validate_schema("guide.yaml", data)
    except ValidationError as e:
        key = data.get("key", "<no key>") if isinstance(data, dict) else "?"
        where = _describe_path(data, e.absolute_path)
        raise ValueError(f"guide {key!r} {where}: {e.message}") from e


def _describe_path(data: dict, path) -> str:
    """Turn a schema error path into something an author can act on."""
    parts = list(path)
    if not parts:
        return "document root"
    try:
        if parts[0] == "steps" and len(parts) > 1:
            step = data["steps"][parts[1]]
            where = f"step {step.get('key', parts[1])!r}"
            if len(parts) > 3 and parts[2] == "options":
                option = step["options"][parts[3]]
                where += f" option {option.get('key', parts[3])!r}"
            return where
        if parts[0] == "roles" and len(parts) > 1:
            return f"role {parts[1]!r}"
        if parts[0] == "refinements" and len(parts) > 1:
            refinement = data["refinements"][parts[1]]
            return f"refinement {refinement.get('key', parts[1])!r}"
    except (KeyError, IndexError, TypeError, AttributeError):
        # The path came from the document, so it should index into it —
        # but a document malformed enough to fail that walk is exactly
        # the one whose error must still reach the author. Fall back to
        # the raw path rather than raising from the error formatter.
        pass
    return "at " + "/".join(str(p) for p in parts)


def _cross_reference_errors(data: dict) -> list[str]:
    return _duplicate_errors(data) + _role_reference_errors(data) + _when_errors(data)


def _duplicate_errors(data: dict) -> list[str]:
    errors = []
    errors += _duplicates("step", [s["key"] for s in data["steps"]])
    for step in data["steps"]:
        errors += _duplicates(
            f"option in step {step['key']!r}",
            [o["key"] for o in step["options"]],
        )
    refinement_keys = [r["key"] for r in data.get("refinements", [])]
    errors += _duplicates("refinement", refinement_keys)
    # Selections are one flat map (step key or refinement key to the
    # answer), which is what makes a guide's state fit in a query
    # string. A refinement sharing a step's key would collide there.
    step_keys = {s["key"] for s in data["steps"]}
    errors += [
        f"refinement {key!r}: a step already uses that key"
        for key in refinement_keys
        if key in step_keys
    ]
    return errors


def _duplicates(what: str, keys: list[str]) -> list[str]:
    seen = set()
    errors = []
    for key in keys:
        if key in seen:
            errors.append(f"duplicate {what} key {key!r}")
        seen.add(key)
    return errors


def _role_reference_errors(data: dict) -> list[str]:
    roles = data["roles"]
    errors = []
    for step in data["steps"]:
        for option in step["options"]:
            errors += [
                f"step {step['key']!r} option {option['key']!r}: unknown role {role!r}"
                for role in option.get("roles") or {}
                if role not in roles
            ]  # option["roles"] is a map; iterating gives its role names
    errors += [
        f"role {name!r}: `under` names unknown role {role['under']!r}"
        for name, role in roles.items()
        if "under" in role and role["under"] not in roles
    ]
    errors += [
        f"refinement {r['key']!r}: unknown role {r['role']!r}"
        for r in data.get("refinements", [])
        if r["role"] != "*" and r["role"] not in roles
    ]
    return errors


def _when_errors(data: dict) -> list[str]:
    """Check every `when` against the steps it selects on.

    A step may only depend on a step before it: a guide whose third step
    waits on the answer to its fifth is unreachable, and the author
    should hear about it at load time rather than in the browser.
    """
    steps = data["steps"]
    options_by_step = {s["key"]: {o["key"] for o in s["options"]} for s in steps}
    errors = []
    for position, step in enumerate(steps):
        errors += _when_clause_errors(
            f"step {step['key']!r}",
            step.get("when"),
            options_by_step,
            earlier=[s["key"] for s in steps[:position]],
        )
    for refinement in data.get("refinements", []):
        errors += _when_clause_errors(
            f"refinement {refinement['key']!r}",
            refinement.get("when"),
            options_by_step,
            earlier=[s["key"] for s in steps],
        )
    return errors


def _when_clause_errors(
    where: str, when: dict | None, options_by_step: dict, earlier: list[str]
) -> list[str]:
    if not when:
        return []
    errors = []
    for step_key, option_keys in when.get("selected", {}).items():
        if step_key not in options_by_step:
            errors.append(f"{where}: `when` names unknown step {step_key!r}")
            continue
        if step_key not in earlier:
            errors.append(
                f"{where}: `when` depends on step {step_key!r}, "
                "which does not come before it"
            )
        errors += [
            f"{where}: `when` names unknown option {option_key!r} of step {step_key!r}"
            for option_key in option_keys
            if option_key not in options_by_step[step_key]
        ]
    return errors
