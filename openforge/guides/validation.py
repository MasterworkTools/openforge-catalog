"""Validation for guide documents.

Two passes: the JSON schema (openforge/openapi/schemas/guide.yaml) for
shape, then the cross-references the schema cannot express — an option
naming a role that does not exist, a `when` pointing at a step that
comes later, a duplicate key, a cycle in `under`. Both raise ValueError
locating the fault, because guides are hand-authored fixtures and a
bare "does not match schema" is useless to whoever is writing one.

"Locating" means the step, role or refinement wherever the error is
inside one. A fault in the document itself — a missing `roles`, say —
reports "document root" plus the schema's own message, which names the
missing property, and that is as specific as the location gets.
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
    return (
        _duplicate_errors(data)
        + _role_reference_errors(data)
        + _refinement_role_errors(data)
        + _choice_errors(data)
        + _default_errors(data)
        + _match_errors(data)
        + _when_errors(data)
    )


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
    errors += _under_cycle_errors(roles)
    errors += _orphan_role_errors(data, roles)
    return errors


def _refinement_role_errors(data: dict) -> list[str]:
    """`except_roles` and `substitute` name roles too.

    `role` was already checked; these two were not, and both fail
    silently rather than loudly. A misspelled `except_roles` entry
    excepts nothing, so the refinement is asked of a part that cannot
    answer it and the part comes back empty. A misspelled `substitute`
    role gets the chosen tag instead of its exception — which is the
    bug the substitution exists to prevent, reappearing under a typo.
    """
    roles = data["roles"]
    errors = []
    for refinement in data.get("refinements", []):
        where = f"refinement {refinement['key']!r}"
        errors += [
            f"{where}: `except_roles` names unknown role {name!r}"
            for name in refinement.get("except_roles", [])
            if name not in roles
        ]
        for tag, by_role in (refinement.get("substitute") or {}).items():
            errors += [
                f"{where}: `substitute` for {tag!r} names unknown role {name!r}"
                for name in by_role
                if name not in roles
            ]
    return errors


def _choice_errors(data: dict) -> list[str]:
    """A refinement's `choices` have to be answers it can accept.

    The namespace check at resolve time refuses a tag from outside
    `from_namespace`, so a choice outside it is an option that raises
    the moment someone clicks it. And a toggle has no namespace to sit
    in, so `choices` on one is a list nothing would ever read.
    """
    errors = []
    for refinement in data.get("refinements", []):
        choices = refinement.get("choices") or []
        if not choices:
            continue
        where = f"refinement {refinement['key']!r}"
        namespace = refinement.get("from_namespace")
        if not namespace:
            errors.append(f"{where}: `choices` needs `from_namespace`")
            continue
        errors += [
            f"{where}: choice {choice['tag']!r} is not under {namespace!r}"
            for choice in choices
            if not choice["tag"].startswith(f"{namespace}|")
        ]
        errors += _duplicates(
            f"choice in {where}", [choice["tag"] for choice in choices]
        )
    return errors


def _default_errors(data: dict) -> list[str]:
    """A recommendation has to name an answer that exists.

    It is used before anyone clicks anything, so a misspelled one is
    not a button that misbehaves — it is a predicate asking for a tag
    nothing has, on the first screen, with no way to tell from the
    page that a default is what did it.
    """
    errors = []
    for step in data["steps"]:
        if "default" not in step:
            continue
        keys = {option["key"] for option in step["options"]}
        if step["default"] not in keys:
            errors.append(
                f"step {step['key']!r}: `default` names unknown option "
                f"{step['default']!r}"
            )
    for refinement in data.get("refinements", []):
        if "default" not in refinement:
            continue
        where = f"refinement {refinement['key']!r}"
        value = refinement["default"]
        if "on_tags" in refinement:
            if value not in ("on", "off"):
                errors.append(f"{where}: `default` takes 'on' or 'off', not {value!r}")
            continue
        namespace = refinement.get("from_namespace") or refinement.get(
            "from_combination"
        )
        if namespace and not all(
            part.startswith(f"{namespace}|") for part in value.split(",")
        ):
            errors.append(f"{where}: `default` {value!r} is not under {namespace!r}")
        choices = [choice["tag"] for choice in refinement.get("choices", [])]
        if choices and value not in choices:
            errors.append(f"{where}: `default` {value!r} is not one of its choices")
    return errors


def _match_errors(data: dict) -> list[str]:
    """`match` copies from the role above, so there has to be one.

    Without `under` there is nothing to copy from and the role silently
    takes no constraint at all — a base that was meant to match the
    footprint above it matches every footprint instead.
    """
    return [
        f"role {name!r}: `match` requires `under`, which it does not have"
        for name, role in data["roles"].items()
        if role.get("match") and "under" not in role
    ]


def _under_cycle_errors(roles: dict) -> list[str]:
    """`under` must describe a stack, not a loop.

    Nothing walks the chain yet — the parts list that lays a build out
    is the obvious future caller — but a role sitting under itself, or
    two roles sitting under each other, would loop forever when
    something does, and it is not a thing an author can mean.

    One error per cycle, naming its members: reporting it once for
    every role that happens to reach the cycle would accuse roles that
    are merely downstream of it.
    """
    errors = []
    reported = set()
    for name in roles:
        seen = [name]
        below = roles[name].get("under")
        while below in roles and below not in seen:
            seen.append(below)
            below = roles[below].get("under")
        if below not in seen:
            continue
        cycle = seen[seen.index(below) :]
        if frozenset(cycle) in reported:
            continue
        reported.add(frozenset(cycle))
        errors.append(
            "roles "
            + ", ".join(repr(r) for r in cycle)
            + ": `under` runs in a circle "
            + f"({' -> '.join(cycle + [below])})"
        )
    return errors


def _orphan_role_errors(data: dict, roles: dict) -> list[str]:
    """A role no option ever names can never be resolved.

    The engine only builds the roles the chosen options call for, so an
    orphan is not a part that says "nothing matches" — it is a part
    nobody ever sees. That is an authoring mistake, not a choice.
    """
    named = {
        role
        for step in data["steps"]
        for option in step["options"]
        for role in option.get("roles") or {}
    }
    return [f"role {name!r}: no option names it" for name in roles if name not in named]


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
        # An option carries a `when` of its own, read by the same
        # helper the step's is, and gating one option of eight rather
        # than the whole step. It answers to the same rule: the step it
        # reads has to come before the step the option belongs to.
        for option in step["options"]:
            errors += _when_clause_errors(
                f"step {step['key']!r} option {option['key']!r}",
                option.get("when"),
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
