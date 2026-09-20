"""Resolution: a guide document plus a selection map in, parts out.

Pure. The only way this module reaches the catalog is `find_candidates`,
a callable the caller injects, so the whole engine is testable against a
list of fake blueprints. See docs/design/guided-builds.md.

The three rules the design settled:

- **Composition.** A role's query is the union of the role's own
  predicate, what each chosen option asks of *that* role, and every
  active refinement that applies to it. An option reaches a role only
  when it names that role, or when it names no roles at all. Lists
  concatenate; `deny` beats `require`, which the tag search already
  enforces, so a role-level deny is absolute — no option can opt back
  in. Nothing here knows about combined
  wall-and-floor prints — a guide that does not want one denies the
  other shape in that role's query.
- **Determinism.** `prefer` is a list of tags, most wanted first. The
  recommendation is the first candidate of the most specific non-empty
  query: require every preferred tag, and drop them from the least
  wanted until something matches. Candidates arrive ordered by name, so
  the same selections always produce the same part — which is what makes
  the shareable URL mean anything.
- **Silence is visible.** A role whose query matches nothing resolves to
  no part and says so, rather than dropping out of the parts list.

Cost: one candidate query per role, plus one more for each preferred
tag that has to be dropped — at most `len(prefer) + 1` per role, each
asking for a single row. With three roles and two preferred tags that
is nine small queries per resolve, which is the price of ranking in the
database rather than pulling every candidate's tags into the Lambda to
sort them there. If it ever matters, the upgrade is one query per role
that ranks in SQL, not a cache.
"""

PREDICATES = ("require", "deny", "accept")


class GuideSelectionError(ValueError):
    """A selection this guide cannot act on.

    Selections arrive from a query string someone can edit or share, so
    this is a bad request rather than a bug, and callers catch it to
    answer 400. It subclasses ValueError so a caller catching that
    still works.
    """


def to_tag_query(predicate: dict) -> dict:
    """Convert a guide predicate into the shape the catalog speaks.

    A guide writes tags as plain strings; `tag_search_blueprints` wants
    the `tag_query` shape, `[{"tag": "shape|wall"}]`, and **silently
    ignores an item that is not a dict**. Hand it bare strings and a
    dropped `require` matches everything while a dropped `deny` matches
    nothing — a wrong answer rather than an error. Every caller
    converts here, so there is one place to get it right.
    """
    return {
        name: [{"tag": tag} for tag in predicate[name]]
        for name in PREDICATES
        if predicate.get(name)
    }


def resolve(document: dict, selections: dict, find_candidates) -> dict:
    """Resolve a guide against a person's selections.

    Args:
        document: A validated guide document.
        selections: Map of step or refinement key to the chosen option
            key (for a step) or tag (for a namespace refinement) or
            "on"/"off" (for a toggle).
        find_candidates: Callable taking (predicate, limit) and
            returning matching blueprints, ordered, as dicts.

    Returns:
        dict with `steps`, `parts` and `refinements`.

    Raises:
        GuideSelectionError: if a selection names something the guide
            does not offer. Selections come from a query string, so a bad one is
            a bad request rather than something to quietly ignore.
    """
    steps, answered = _available_steps(document, selections)
    chosen = _chosen_options(steps, answered)
    refinements = _available_refinements(document, answered)
    _reject_unknown_selections(document, steps, refinements, selections)
    return {
        "steps": [{**step, "selected": answered.get(step["key"])} for step in steps],
        "parts": _parts(document, chosen, refinements, selections, find_candidates),
        "refinements": [
            {**refinement, "selected": selections.get(refinement["key"])}
            for refinement in refinements
        ],
    }


def _available_steps(document: dict, selections: dict):
    """The reachable steps, and the answers that actually count.

    Steps are walked in document order, and a step's `when` is tested
    against the answers to *reachable* steps only, not against the raw
    selection map. Otherwise a chain does not compose: with `c` waiting
    on `b` and `b` waiting on `a`, changing the answer to `a` drops `b`
    but would leave a stale answer to `c` alive — offering a question
    nobody can see, and narrowing the parts off a branch nobody is on.

    Returns the reachable steps and the selections belonging to them.
    """
    available = []
    answered = {}
    for step in document["steps"]:
        if not _when_holds(step.get("when"), answered):
            continue
        available.append(step)
        if step["key"] in selections:
            answered[step["key"]] = selections[step["key"]]
    return available, answered


def _available_refinements(document: dict, answered: dict) -> list[dict]:
    return [
        refinement
        for refinement in document.get("refinements", [])
        if _when_holds(refinement.get("when"), answered)
    ]


def _when_holds(when: dict | None, selections: dict) -> bool:
    if not when:
        return True
    return all(
        selections.get(step_key) in option_keys
        for step_key, option_keys in when.get("selected", {}).items()
    )


def _chosen_options(steps: list[dict], selections: dict) -> list[dict]:
    chosen = []
    for step in steps:
        selected = selections.get(step["key"])
        if selected is None:
            continue
        options = {option["key"]: option for option in step["options"]}
        if selected not in options:
            raise GuideSelectionError(
                f"step {step['key']!r} has no option {selected!r}"
            )
        chosen.append(options[selected])
    return chosen


def _reject_unknown_selections(
    document: dict, steps: list[dict], refinements: list[dict], selections: dict
) -> None:
    """Fail on a selection this guide has no key for.

    A selection whose key the guide does not define is a bad request. A
    selection for a key the guide does define but that the current
    answers have not made reachable is not: someone who shares a URL and
    then changes the first answer should see the later ones fall away,
    not a broken page. Those are ignored, and only the reachable ones
    are validated and composed.
    """
    known = {step["key"] for step in document["steps"]}
    known |= {r["key"] for r in document.get("refinements", [])}
    unknown = sorted(set(selections) - known)
    if unknown:
        raise GuideSelectionError(
            f"guide {document['key']!r} has no {', '.join(unknown)}"
        )
    for refinement in refinements:
        _reject_bad_refinement_value(refinement, selections)


def _reject_bad_refinement_value(refinement: dict, selections: dict) -> None:
    value = selections.get(refinement["key"])
    if value is None:
        return
    if not isinstance(value, str):
        raise GuideSelectionError(
            f"refinement {refinement['key']!r} takes a string, not {value!r}"
        )
    if "on_tags" in refinement and value not in ("on", "off"):
        raise GuideSelectionError(
            f"refinement {refinement['key']!r} takes 'on' or 'off', not {value!r}"
        )
    namespace = refinement.get("from_namespace")
    if namespace and not value.startswith(f"{namespace}|"):
        raise GuideSelectionError(
            f"refinement {refinement['key']!r} takes a {namespace!r} tag, not {value!r}"
        )


def _parts(
    document: dict,
    chosen: list[dict],
    refinements: list[dict],
    selections: dict,
    find_candidates,
) -> list[dict]:
    parts = []
    for name in _roles_in_play(chosen):
        role = document["roles"][name]
        predicate = _compose(role["query"], chosen, refinements, selections, name)
        parts.append(
            {
                "role": name,
                "title": role["title"],
                "under": role.get("under"),
                "query": predicate,
                "blueprint": _recommend(
                    predicate, role.get("prefer", []), find_candidates
                ),
            }
        )
    return parts


def _roles_in_play(chosen: list[dict]) -> list[str]:
    """Role names the chosen options call for, first mention first."""
    names = []
    for option in chosen:
        for name in option.get("roles") or {}:
            if name not in names:
                names.append(name)
    return names


def _option_predicates(option: dict, role_name: str) -> list[dict]:
    """What a chosen option asks of one role.

    An option carries a predicate for every role it names, because a
    build method is not a single tag: the s2w floor requires
    `build|s2w` while the base under it denies exactly that. `tags` is
    the shorthand for the part that is true of every role the option
    names, and an option says nothing about a role it does not name.
    """
    roles = option.get("roles")
    if roles is None:
        # An option with no roles of its own narrows whatever the
        # earlier answers put in play: "how wide?" applies to every
        # part, without knowing which parts the method needs.
        return [option["tags"]] if "tags" in option else []
    if role_name not in roles:
        return []
    predicates = []
    if "tags" in option:
        predicates.append(option["tags"])
    if roles[role_name]:
        predicates.append(roles[role_name])
    return predicates


def _compose(
    query: dict,
    chosen: list[dict],
    refinements: list[dict],
    selections: dict,
    role_name: str,
) -> dict:
    predicates = [query]
    for option in chosen:
        predicates += _option_predicates(option, role_name)
    predicates += [
        _refinement_predicate(refinement, selections[refinement["key"]])
        for refinement in refinements
        if refinement["key"] in selections and refinement["role"] in ("*", role_name)
    ]
    return _union(predicates)


def _refinement_predicate(refinement: dict, value: str) -> dict:
    if "on_tags" in refinement:
        key = "on_tags" if value == "on" else "off_tags"
        return refinement.get(key, {})
    return {"require": [value]}


def _union(predicates: list[dict]) -> dict:
    composed = {}
    for predicate in predicates:
        for name in PREDICATES:
            for tag in predicate.get(name, []):
                tags = composed.setdefault(name, [])
                if tag not in tags:
                    tags.append(tag)
    return composed


def _recommend(predicate: dict, prefer: list[str], find_candidates):
    """The best candidate, or None when the query matches nothing.

    Preferred tags are required outright and then dropped one at a time
    from the least wanted, so the recommendation is the most preferred
    part that exists rather than the best of an arbitrary page of
    candidates.
    """
    for kept in range(len(prefer), -1, -1):
        narrowed = _union([predicate, {"require": prefer[:kept]}])
        candidates = find_candidates(narrowed, 1)
        if candidates:
            return candidates[0]
    return None
