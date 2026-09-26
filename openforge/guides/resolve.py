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
  wanted until something matches. The same selections always produce
  the same part — which is what makes the shareable URL mean anything —
  and that rests on the catalog returning candidates in a *total*
  order. Name alone is not one: 159 blueprint names are shared by two
  or more records, so `tag_search_blueprints` orders by name and id
  together. Without the id, a role's recommendation could change after
  any unrelated write.
- **Silence is visible.** A role whose query matches nothing resolves to
  no part and says so, rather than dropping out of the parts list.

Cost: one candidate query per role, plus one more for each preferred
tag that has to be dropped — at most `len(prefer) + 1` per role, each
*returning* a single row. Each one still builds and sorts the whole
matching set first, and `_query_tags_basics` emits a separate anti-join
per denied tag, which `_compose` accumulates from the role, every
chosen option and every active refinement — so the work grows with how
deep someone is into a guide, not with the number of roles. With three
roles and two preferred tags that is nine such queries per resolve,
which is the price of ranking in the database rather than pulling every
candidate's tags into the Lambda to sort them there. If it ever
matters, the upgrade is one query per role that ranks in SQL, not a
cache.
"""

PREDICATES = ("require", "deny", "accept", "allow", "deny_children")


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

    Every key is always present, so the result can be splatted straight
    into `tag_search_blueprints(curs, **to_tag_query(p))` — that
    function takes `accept`, `require` and `deny` as required
    positional arguments, and omitting the empty ones would make the
    call fail on any predicate that happens not to use one.

    `deny_children` and `allow` are the pair that says "this tag and
    nothing else beneath it". `deny_children: ['component|wall']`
    refuses every tag under `component|wall` — the arrow slits and the
    curved variants — and `allow` names the children that survive it,
    for the cases where one particular child is wanted and the rest are
    not. Anything named in `require` or `allow` is exempt from the
    sweep — by exact tag, not by ordering: every term becomes an AND in
    one WHERE clause, so the sweep is not run *after* the includes, it
    is told about them.
    """
    return {
        name: [{"tag": tag} for tag in predicate.get(name, [])] for name in PREDICATES
    }


def resolve(
    document: dict,
    selections: dict,
    find_candidates,
    exists=None,
    facets=None,
    combinations=None,
) -> dict:
    """Resolve a guide against a person's selections.

    Args:
        document: A validated guide document.
        selections: Map of step or refinement key to the chosen option
            key (for a step) or tag (for a namespace refinement) or
            "on"/"off" (for a toggle).
        find_candidates: Callable taking a predicate and returning
            matching blueprints, ordered, as dicts. Only the first is
            read — see `_recommend`.

    Returns:
        dict with `steps`, `parts` and `refinements`.

    Raises:
        GuideSelectionError: if a selection names something the guide
            does not offer. Selections come from a query string, so a bad one is
            a bad request rather than something to quietly ignore.
    """
    # Two views of the same answers, and the difference is the whole
    # of how defaults work here.
    #
    # `selections` is what the person actually said, and drives what
    # they are asked: the wizard walks from the first question they
    # have not answered, so a default never counts as an answer and
    # never skips a question.
    #
    # `assumed` fills the rest in with each question's recommendation,
    # and drives the parts: the page shows a complete, buildable set
    # from the first screen rather than four empty boxes and an
    # instruction to keep clicking.
    assumed, recommended = _with_defaults(document, selections)
    steps, answered = _available_steps(document, assumed)
    chosen = _chosen_options(steps, answered)
    in_play = _roles_in_play(chosen)
    refinements = _available_refinements(document, answered, in_play)
    # The explicit answers that survived the branch. An answer this
    # branch does not offer counts as no answer — so it neither shows
    # as chosen nor opens the question after it.
    given = {key: value for key, value in answered.items() if key in selections}
    _reject_unknown_selections(document, steps, refinements, selections)
    parts = _parts(document, chosen, refinements, assumed, find_candidates)
    # Availability is opt-in, and the default is off.
    #
    # Working out which answers would empty a part means re-composing
    # every role for every offered answer — around thirty-five of them
    # on this guide — and asking the catalog about each. That is a
    # second or two, against a quarter of a second for the parts
    # themselves, and the parts are what the person is waiting to see.
    # So the page asks for them separately and drops the dead answers
    # when the answer arrives.
    # A namespace refinement with no `choices` of its own offers
    # whatever the parts actually carry, so a connector the catalog
    # gains later shows up without a guide being edited.
    derived = (
        _derive_choices(
            document,
            chosen,
            refinements,
            assumed,
            in_play,
            parts,
            facets,
            combinations,
        )
        if facets is not None
        else {}
    )
    dead, because = (
        _unavailable(document, steps, refinements, assumed, parts, exists)
        if exists is not None
        else ({}, {})
    )
    return {
        "steps": [
            {
                **step,
                # What they said, not what was assumed for them: a
                # defaulted question is still being asked, and shows
                # its options with the recommendation marked.
                "selected": given.get(step["key"]),
                "recommended": recommended.get(step["key"]),
                "unavailable": dead.get(step["key"], []),
                "because": {
                    value: because[f"{step['key']}:{value}"]
                    for value in dead.get(step["key"], [])
                    if f"{step['key']}:{value}" in because
                },
            }
            for step in _up_to_first_unanswered(steps, given)
        ],
        "parts": parts,
        # Held back until the questions are done, for the same reason
        # the questions come one at a time: answering "how do you want
        # to build it?" should open the next question, not the whole
        # form. They still *apply* while hidden — a texture in the URL
        # is the person's answer whether or not its control is on
        # screen, and silently ignoring it would change the parts they
        # are looking at.
        "refinements": []
        if _unanswered(steps, given)
        else [
            {
                **refinement,
                **(
                    {"choices": derived[refinement["key"]]}
                    if refinement["key"] in derived
                    else {}
                ),
                "selected": selections.get(refinement["key"]),
                "recommended": recommended.get(refinement["key"]),
                "unavailable": dead.get(refinement["key"], []),
                "because": {
                    value: because[f"{refinement['key']}:{value}"]
                    for value in dead.get(refinement["key"], [])
                    if f"{refinement['key']}:{value}" in because
                },
            }
            for refinement in _up_to_first_unanswered(refinements, selections)
        ],
    }


def _up_to_first_unanswered(refinements: list, selections: dict) -> list:
    """The refinements to show: answered ones, then the next.

    One at a time, exactly as the steps are. Answering the wall texture
    is what puts the floor texture on the screen, and so on — the
    alternative is finishing the questions and being handed four more
    all at once, which is the form this stopped being.

    Display only. Every refinement still *applies*, answered or hidden,
    because a texture in the URL is the person's answer whether or not
    its control is on screen — a shared link has to resolve to the
    parts it was shared for.
    """
    shown = []
    for refinement in refinements:
        shown.append(refinement)
        if refinement["key"] not in selections:
            break
    return shown


def _unavailable(
    document: dict,
    steps: list,
    refinements: list,
    selections: dict,
    parts: list,
    find_candidates,
) -> dict:
    """For each question, the answers that would empty a part — and
    which earlier answer is responsible for each.

    An answer that matches nothing is not shown at all. It is worth
    saying *why* it is not there, though: "no rough stone floor"
    is baffling on its own and obvious once you know it is the
    separate-wall choice that did it. So each missing answer is
    attributed by removing one other answer at a time and seeing
    whether it comes back — the first removal that revives it is what
    is blamed.

    Optimistic where it is unsure. A role that copies a size from the
    part above it is not checked against that size, because knowing it
    would mean recommending the part above first. So an answer is
    dropped only when it is empty on its own terms, never on a guess,
    and the failure mode is an answer that is offered and turns out
    thin — not one that vanishes and should not have.
    """
    baseline = {
        part["role"]: _predicate_key(part["query"])
        for part in parts
        if part["blueprint"] is not None
    }
    cache: dict = {}
    dead: dict = {}
    because: dict = {}
    offered = list(_offered(steps, refinements))
    # Questions are named to the person by their prompt, not their key.
    prompts = {q["key"]: q["prompt"] for q in [*steps, *refinements]}
    for question, values in offered:
        empty = {}
        for value in values:
            role = _first_empty_role(
                document,
                {**selections, question: value},
                baseline,
                cache,
                find_candidates,
            )
            if role is not None:
                empty[value] = role
        if not empty:
            continue
        dead[question] = list(empty)
        for value, role in empty.items():
            # What it would empty is always knowable and always useful:
            # "no wall base in that texture" says what is missing. Which
            # answer is responsible is knowable only when one answer is
            # responsible, so it is the extra rather than the point.
            reason = {"part": document["roles"][role]["title"]}
            blamed = _blame(
                document,
                selections,
                question,
                value,
                [other for other, _ in offered if other != question],
                baseline,
                cache,
                find_candidates,
            )
            if blamed:
                reason["question"] = blamed
                reason["prompt"] = prompts.get(blamed, blamed)
            because[f"{question}:{value}"] = reason
    return dead, because


def _blame(
    document: dict,
    selections: dict,
    question: str,
    value: str,
    others: list,
    baseline: dict,
    cache: dict,
    find_candidates,
) -> str | None:
    """Which other answer is stopping this one, if any single one is.

    One at a time, and the first that works is the answer: "rough
    stone is not there because of the method you chose" is useful
    where "some combination of your five answers" is not. Two answers
    can be jointly responsible with neither one to blame, and then
    this says nothing rather than pick a scapegoat.
    """
    in_play = _roles_in_play(_chosen_options(*_available_steps(document, selections)))
    for other in others:
        if other not in selections:
            continue
        without = {k: v for k, v in selections.items() if k != other}
        hypothetical = {**without, question: value}
        # Only a removal that still builds the same parts is evidence.
        # Dropping the method unbuilds everything, and a question about
        # no parts is satisfied by any answer — so without this the
        # first question is blamed for every missing answer in the
        # guide, which is both useless and wrong.
        if (
            _roles_in_play(_chosen_options(*_available_steps(document, hypothetical)))
            != in_play
        ):
            continue
        if _holds(document, hypothetical, baseline, cache, find_candidates):
            return other
    return None


def _offered(steps: list, refinements: list):
    """Every question paired with the answers it is offering."""
    for step in steps:
        yield step["key"], [option["key"] for option in step["options"]]
    for refinement in refinements:
        if "on_tags" in refinement:
            yield refinement["key"], ["on", "off"]
        elif refinement.get("choices"):
            yield refinement["key"], [c["tag"] for c in refinement["choices"]]


def _holds(
    document: dict, selections: dict, baseline: dict, cache: dict, find_candidates
) -> bool:
    """Whether every part has something. See `_first_empty_role`."""
    return (
        _first_empty_role(document, selections, baseline, cache, find_candidates)
        is None
    )


def _first_empty_role(
    document: dict, selections: dict, baseline: dict, cache: dict, find_candidates
) -> str | None:
    """The first part these answers would leave with nothing.

    `None` when every part has something.

    Predicates only: no `prefer`, which costs a search per tag it
    drops, and no `match`, which costs the part above. Two more things
    keep the count down, because this runs once per offered answer and
    a guide offers around thirty:

    - a role whose predicate is the one the real resolution already
      used, and already found something for, is not asked again
    - identical predicates are asked once, and most answers leave most
      roles untouched, so the same few recur constantly
    """
    steps, answered = _available_steps(document, selections)
    chosen = _chosen_options(steps, answered)
    in_play = _roles_in_play(chosen)
    refinements = _available_refinements(document, answered, in_play)
    for name in in_play:
        role = document["roles"][name]
        predicate = _compose(role["query"], chosen, refinements, selections, name)
        key = _predicate_key(predicate)
        if baseline.get(name) == key:
            continue
        if key not in cache:
            cache[key] = bool(find_candidates(predicate))
        if not cache[key]:
            return name
    return None


def _derive_choices(
    document: dict,
    chosen: list[dict],
    refinements: list[dict],
    selections: dict,
    in_play: list[str],
    parts: list,
    facets,
    combinations=None,
) -> dict:
    """What each open-ended namespace refinement can actually offer.

    A guide that lists its own answers goes stale: the catalog gains a
    connection system and every guide has to be edited to mention it.
    So a namespace refinement with no `choices` of its own offers
    whatever the parts it applies to actually carry — which is what
    `from_namespace` always meant, and what the free-text box was
    standing in for.

    Derived **per role and intersected**, because the roles it applies
    to are not alike: a 2x2 floor base, a 2x2 s2w base and a 2-wide
    dungeon stone wall base do not offer the same connectors. One
    answer is required of all of them, so offering something only one
    of them has would empty the others.

    Its own answer is excluded from the predicate first — see
    `_compose(without=...)` — or the only answer on offer would be the
    one already chosen.

    `substitute` and derivation do not mix, and a refinement that uses
    one should list its `choices`: substitution means the roles are
    asked for *different* tags, so intersecting what they carry
    describes nothing. The texture question is the live example.
    """
    parts_by_role = {part["role"]: part for part in parts}
    derived = {}
    for refinement in refinements:
        namespace = refinement.get("from_namespace") or refinement.get(
            "from_combination"
        )
        if not namespace or refinement.get("choices"):
            continue
        # Whole combinations rather than one tag at a time. Some
        # pairings simply do not exist — nothing is both topless and
        # unsupported — and asking about each tag separately cannot
        # say so, while asking which combination you want cannot
        # express it in the first place.
        whole = "from_combination" in refinement
        roles = [
            name
            for name in in_play
            if refinement["role"] in ("*", name)
            and name not in refinement.get("except_roles", [])
        ]
        if not roles:
            continue
        offered: set | None = None
        counts: dict = {}
        for name in roles:
            role = document["roles"][name]
            predicate = _compose(
                role["query"],
                chosen,
                refinements,
                selections,
                name,
                without=refinement["key"],
            )
            # The size a base copies from the piece it sits under is
            # part of what narrows it, and a 1-inch wall base has four
            # clip combinations where a 2-inch one has seven. Without
            # this the question offers answers the chosen size does not
            # have.
            inherited = _matched(role, parts_by_role)
            if inherited is None:
                offered = set()
                break
            predicate = _union([predicate, inherited])
            answers = (
                combinations(predicate, namespace, refinement.get("exclude", []))
                if whole
                else facets(predicate, namespace)
            )
            found = {_answer_key(a, whole): a for a in answers}
            offered = set(found) if offered is None else offered & set(found)
            for tag, facet in found.items():
                # The smallest count across the roles, because that is
                # how many builds this answer really leaves you.
                seen = counts.get(tag)
                if seen is None or facet["count"] < seen["count"]:
                    counts[tag] = facet
        derived[refinement["key"]] = [
            {
                "tag": tag,
                "count": counts[tag]["count"],
                **(
                    {
                        "title": _combination_title(
                            counts[tag]["tags"],
                            namespace,
                            refinement.get("titles", {}),
                        )
                    }
                    if whole
                    else {}
                ),
                **({"blurb": counts[tag]["blurb"]} if counts[tag].get("blurb") else {}),
            }
            for tag in sorted(offered or ())
        ]
    return derived


def _answer_key(answer: dict, whole: bool) -> str:
    """One string for one answer, because a URL carries strings.

    A combination is several tags, joined — it has to survive a round
    trip through a query string and come back as the same answer.
    """
    return ",".join(sorted(answer["tags"])) if whole else answer["tag"]


def _combination_title(
    tags: list[str], namespace: str, titles: dict | None = None
) -> str:
    """A combination, said out loud.

    A tag whose child is also in the set is dropped, because the child
    already names it: OpenLOCK *and* OpenLOCK topless is one clip, and
    "openlock + openlock topless" reads as two.

    `titles` names the parts the catalog cannot spell. A tag says
    `openlock` and the product is OpenLOCK; a tag with no entry falls
    back to its own words, so a new sibling still appears.
    """
    names = titles or {}
    kept = [t for t in tags if not any(o.startswith(f"{t}|") for o in tags)]
    depth = len(namespace.split("|"))
    words = []
    for tag in sorted(kept):
        # The parent's display name carries the family, and the child
        # adds what it is: "OpenLOCK topless", not "openlock topless".
        parts = tag.split("|")
        pieces = []
        for i in range(depth, len(parts)):
            head = "|".join(parts[: i + 1])
            pieces.append(names.get(head, parts[i].replace("_", " ")))
        words.append(" ".join(pieces))
    title = " + ".join(words)
    return title[:1].upper() + title[1:]


def _predicate_key(predicate: dict):
    """A predicate's identity, for comparing and for caching.

    Terms are lists whose order carries no meaning, so two predicates
    that ask the same thing have to hash the same however they were
    composed.
    """
    return tuple(
        sorted((term, tuple(sorted(tags))) for term, tags in predicate.items())
    )


def _with_defaults(document: dict, selections: dict) -> tuple[dict, dict]:
    """The person's answers, with each question's recommendation for
    the rest — and the recommendations themselves.

    Walked in document order because both depend on the answers so
    far: defaulting the method to s2w is what makes the wall-print
    question reachable, and only then does its own default apply. A
    question the branch does not reach contributes nothing, and a
    recommendation that reads an earlier answer reads the assumed one,
    so the chain follows the build actually on screen.

    Refinements join the answers as they are walked, which steps do
    not need but they do: the floor to recommend depends on the wall
    texture, and the wall texture is a refinement.

    An explicit answer always wins, including one that happens to
    equal the recommendation — the difference is invisible in the
    parts and very visible in the wizard, where answering is what
    opens the next question.
    """
    assumed = dict(selections)
    answered: dict = {}
    recommended: dict = {}
    for question in [*document["steps"], *document.get("refinements", [])]:
        if not _when_holds(question.get("when"), answered):
            continue
        key = question["key"]
        value = _recommendation(question, answered)
        if value is not None:
            recommended[key] = value
            assumed.setdefault(key, value)
        if key in assumed:
            answered[key] = assumed[key]
    return assumed, recommended


def _recommendation(question: dict, answered: dict):
    """What to recommend for this question, given the answers so far.

    A plain value recommends the same thing whatever else was chosen.
    A list of clauses recommends by branch, the first whose `when`
    holds winning and a clause without one catching the rest. Some
    recommendations simply are conditional — a wall on a tile has
    nothing beside it to clip to, and a wooden wall wants a wooden
    floor — and writing that as one value would mean recommending the
    wrong thing on some branch.
    """
    default = question.get("default")
    if not isinstance(default, list):
        return default
    for clause in default:
        if _when_holds(clause.get("when"), answered):
            return clause["value"]
    return None


def _unanswered(steps: list, answered: dict) -> bool:
    """Is there still a question on the table?

    Reads the answers map rather than the steps, because `selected` is
    put on a step when the response is assembled and these are the
    steps as the engine has them.
    """
    return any(step["key"] not in answered for step in steps)


def _available_steps(document: dict, selections: dict):
    """The reachable steps, and the answers that actually count.

    Steps are walked in document order, and a step's `when` is tested
    against the answers to *reachable* steps only, not against the raw
    selection map. Otherwise a chain does not compose: with `c` waiting
    on `b` and `b` waiting on `a`, changing the answer to `a` drops `b`
    but would leave a stale answer to `c` alive — offering a question
    nobody can see, and narrowing the parts off a branch nobody is on.

    One question at a time, too. A reachable step is offered only if
    every step before it has been answered, so answering one opens the
    next rather than all of them at once. That is the difference
    between a wizard and a form, and it cannot be written as a `when`:
    the chain is not the same on every branch — wall-on-tile has no
    print questions, so its size question follows the method directly,
    while a separate wall's follows two print questions — and `when`
    ANDs across steps, so it cannot say "whichever of these came
    before".

    Returns the reachable steps and the selections belonging to them.
    """
    available = []
    answered = {}
    for step in document["steps"]:
        if not _when_holds(step.get("when"), answered):
            continue
        offered = _with_available_options(step, answered)
        available.append(offered)
        if step["key"] not in selections:
            # Offered, unanswered, and the last one anybody sees: the
            # questions after it depend on this answer, and asking them
            # first invites an answer that this one then throws away.
            break
        # An answer naming an option this branch does not offer counts
        # as no answer, and the step is asked again. It is not a bad
        # request: the key is one this step really has, it is just not
        # on offer here — s2w has no tile shallower than it is wide, so
        # choosing 4x1 and then choosing s2w leaves the size unanswered
        # rather than 400ing a URL the person reached by clicking.
        #
        # Anything else stays in `answered` so that `_chosen_options`
        # can refuse it: a key no option has is still a bad request,
        # and so is a repeated parameter, which arrives as a list.
        if _gated_off(selections[step["key"]], step, offered):
            # Answered with something this branch does not offer, which
            # counts as unanswered — so this is where the wizard stops.
            break
        answered[step["key"]] = selections[step["key"]]
    return available, answered


def _gated_off(chosen, step: dict, offered: dict) -> bool:
    """Is this a real answer to this step that this branch withholds?

    Deliberately narrow. A value that is not a string, or that names no
    option this step has at all, is not gated off — it is wrong, and
    has to reach the check that says so.
    """
    if not isinstance(chosen, str):
        return False
    if chosen not in {option["key"] for option in step["options"]}:
        return False
    return chosen not in {option["key"] for option in offered["options"]}


def _with_available_options(step: dict, answered: dict) -> dict:
    """The step, carrying only the options this branch offers.

    An option's `when` reads exactly like a step's, and for the same
    reason: some answers rule out some of the next answers. Gating the
    whole step is too blunt when it is three of its eight options that
    do not apply.
    """
    offered = [
        option
        for option in step["options"]
        if _when_holds(option.get("when"), answered)
    ]
    if len(offered) == len(step["options"]):
        return step
    return {**step, "options": offered}


def _available_refinements(
    document: dict, answered: dict, in_play: list[str] | None = None
) -> list[dict]:
    """The refinements worth asking about, given what is being built.

    Two filters. `when` is the author's: this question only makes
    sense on that branch. The second is structural — a refinement that
    applies to no part in the build is a question about nothing, and
    asking "how do the bases clip together?" of a build with no bases
    invites an answer that changes nothing and rules out nothing, because
    every choice fits a set of no roles equally well.
    """
    offered = [
        refinement
        for refinement in document.get("refinements", [])
        if _when_holds(refinement.get("when"), answered)
    ]
    if in_play is None:
        return offered
    return [r for r in offered if _applies_to_any(r, in_play)]


def _applies_to_any(refinement: dict, in_play: list[str]) -> bool:
    """Does this refinement reach any role that is actually in play?

    Same test `_compose` applies per role, asked across all of them.
    """
    except_roles = refinement.get("except_roles", [])
    return any(
        refinement["role"] in ("*", name) and name not in except_roles
        for name in in_play
    )


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
        if not isinstance(selected, str):
            # A repeated query parameter arrives as a list, and an
            # unhashable value would raise TypeError from the lookup
            # below — a 500 where the answer is "bad request".
            raise GuideSelectionError(
                f"step {step['key']!r} takes a string, not {selected!r}"
            )
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
    namespace = refinement.get("from_namespace") or refinement.get("from_combination")
    # A combination arrives as its tags joined, so each one is checked.
    if namespace and not all(
        part.startswith(f"{namespace}|") for part in value.split(",")
    ):
        raise GuideSelectionError(
            f"refinement {refinement['key']!r} takes a {namespace!r} tag, not {value!r}"
        )
    choices = [choice["tag"] for choice in refinement.get("choices", [])]
    if choices and value not in choices:
        # A closed list is a promise about what the answers are, and a
        # URL is editable. Refusing here is what keeps the offered
        # buttons and the accepted answers the same set.
        raise GuideSelectionError(
            f"refinement {refinement['key']!r} does not offer {value!r}"
        )


def _parts(
    document: dict,
    chosen: list[dict],
    refinements: list[dict],
    selections: dict,
    find_candidates,
) -> list[dict]:
    in_play = _roles_in_play(chosen)
    parts = {}
    for name in _resolution_order(in_play, document["roles"]):
        role = document["roles"][name]
        predicate = _compose(role["query"], chosen, refinements, selections, name)
        inherited = _matched(role, parts)
        if inherited is not None:
            predicate = _union([predicate, inherited])
        parts[name] = {
            "role": name,
            "title": role["title"],
            "under": role.get("under"),
            "query": predicate,
            # A role matching against a part that resolved to nothing
            # resolves to nothing too. Recommending here would mean
            # sizing a base to fit a piece nobody has: the size it fell
            # back on would be arbitrary, and a 1x1 base under an absent
            # 3x1 floor reads as an answer rather than as the gap it is.
            "blueprint": None
            if inherited is None
            else _recommend(predicate, role.get("prefer", []), find_candidates),
        }
    # Reported in the order the options called for them, not the order
    # they had to be resolved in: a parts list reads floor, wall, base.
    return [parts[name] for name in in_play]


def _roles_in_play(chosen: list[dict]) -> list[str]:
    """Role names the chosen options call for, first mention first."""
    names = []
    for option in chosen:
        for name in option.get("roles") or {}:
            if name not in names:
                names.append(name)
    return names


def _resolution_order(in_play: list[str], roles: dict) -> list[str]:
    """In-play roles, each after the role it matches against.

    Only `match` creates a dependency. `under` alone is a statement
    about where a piece sits, which the frontend uses for layout and
    which does not affect what is chosen.

    The validator refuses `under` cycles, so following the chain
    terminates. A role that matches against one not in play is simply
    unblocked — `_matched` has nothing to copy.
    """
    ordered = []

    def visit(name, seen):
        if name in ordered or name in seen:
            return
        role = roles.get(name)
        above = role.get("under") if role else None
        if role and role.get("match") and above in in_play:
            visit(above, seen | {name})
        if name not in ordered:
            ordered.append(name)

    for name in in_play:
        visit(name, frozenset())
    return ordered


def _matched(role: dict, resolved: dict) -> dict | None:
    """What this role has to copy from the part it sits under.

    A base has to match the footprint of the piece standing on it, and
    that piece's size is not known until it is chosen. So the namespaces
    named in `match` become `require` tags taken from the resolved part.

    `None` means this role cannot be resolved at all, because the part
    it matches against resolved to nothing. An empty dict means it can,
    with nothing extra required — either the role does not match, or the
    part above carries no tag in any named namespace, which is the
    ordinary case for a base matching `size|depth` against a wall, since
    a wall is a line along an edge and has a width and no depth.
    """
    namespaces = role.get("match")
    if not namespaces:
        return {}
    above = resolved.get(role.get("under"))
    if above is None:
        # Matching against a role that is not in play constrains
        # nothing, the same as not matching at all.
        return {}
    if not above["blueprint"]:
        return None
    tags = above["blueprint"].get("tags") or []
    wanted = [tag for tag in tags if _in_namespace(tag, namespaces)]
    return {"require": wanted} if wanted else {}


def _in_namespace(tag: str, namespaces: list[str]) -> bool:
    return any(
        tag == namespace or tag.startswith(f"{namespace}|") for namespace in namespaces
    )


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
    without: str | None = None,
) -> dict:
    """Everything asked of one role, optionally minus one refinement.

    `without` is for working out what a refinement could offer. Its own
    answer has to come out of the predicate first, or the only answer
    on offer is the one already given and no one could ever change
    their mind.
    """
    predicates = [query]
    for option in chosen:
        predicates += _option_predicates(option, role_name)
    predicates += [
        _refinement_predicate(refinement, selections[refinement["key"]], role_name)
        for refinement in refinements
        if refinement["key"] in selections
        and refinement["key"] != without
        and refinement["role"] in ("*", role_name)
        and role_name not in refinement.get("except_roles", [])
    ]
    return _union(predicates)


def _refinement_predicate(refinement: dict, value: str, role_name: str) -> dict:
    """What a refinement asks of one role, given the chosen value.

    A namespace refinement normally asks every role it applies to for
    the tag the person picked. `substitute` is the exception list, and
    it exists because the answer is not always the same tag for every
    part: the catalog has 441 towne walls and no towne base at all,
    because a towne building stands on a wood base. Substituting is
    what makes "towne" mean the right thing for each role rather than
    emptying the ones that have no piece of that name.
    """
    if "on_tags" in refinement:
        key = "on_tags" if value == "on" else "off_tags"
        return refinement.get(key, {})
    namespace = refinement.get("from_combination")
    if namespace:
        # A combination is exact, or it is not a combination: asking
        # for OpenLOCK without magnets has to exclude the magnetic
        # ones. Requiring the set and sweeping the rest of the
        # namespace says that without needing to know what the rest
        # is — the required tags are exempt from the sweep, and
        # `exclude` names the ones that were too noisy to offer and so
        # must not be swept either.
        return {
            "require": value.split(","),
            "deny_children": [namespace],
            "allow": refinement.get("exclude", []),
        }
    substitute = refinement.get("substitute", {}).get(value, {})
    return {"require": [substitute.get(role_name, value)]}


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
        candidates = find_candidates(narrowed)
        if candidates:
            return candidates[0]
    return None
