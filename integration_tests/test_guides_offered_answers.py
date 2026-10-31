"""What a guide documents, a patron must be able to reach and build.

Two promises, and they fail in opposite directions. A guide withholds
an answer that would leave a part empty, so whatever it does offer has
to resolve complete. And an answer it documents has to be reachable
somewhere, or the guide is advertising something nothing can use.

Driven the way the page drives it: answer each published question with
the engine's own recommendation, then look at what is left on offer.
Three sources, none interchangeable. The document says what is
*documented*; the resolve payload says what is *published* at a state;
and the availability endpoint says what is *refused* there.
"""

#: The guides the empty-part invariant holds for today. A guide joins
#: once it has no offered answer that resolves empty.
# Not `wall`: it offers mortar_and_stone at its widest sizes with no
# wall base of that texture to stand on, which is a gap in the catalog
# rather than in the guide.
GUARDED = ("corner", "door", "floor")

#: Reachability is the weaker claim and holds for more guides: it asks
#: only that a documented answer be reachable somewhere, which a guide
#: can satisfy while still having a state that resolves empty.
REACHABLE = GUARDED


def _resolve(client, key, state):
    response = client.get(f"/api/guides/{key}/resolve", params=state)
    assert response.status_code == 200, (key, state)
    return response.json()


def _refused(client, key, state):
    """What the guide greys out at this state, per question.

    The resolve payload carries an `unavailable` list per step, but the
    sweep that fills it runs in the availability endpoint, so that is
    what has to be asked.
    """
    response = client.get(f"/api/guides/{key}/availability", params=state)
    assert response.status_code == 200, (key, state)
    return response.json().get("unavailable") or {}


def _document(client, key):
    response = client.get(f"/api/guides/{key}")
    assert response.status_code == 200, key
    return response.json()["document"]


def _guide_keys(client, guarded=GUARDED):
    """The guarded guides, confirmed to be guides this server serves."""
    response = client.get("/api/guides")
    assert response.status_code == 200
    body = response.json()
    guides = body["guides"] if isinstance(body, dict) else body
    served = {g["guide_key"] for g in guides if g.get("guide_key")}
    missing = sorted(set(guarded) - served)
    assert not missing, f"guarded guide not served: {missing}"
    return [key for key in guarded if key in served]


def _documented_options(document):
    """Each step's full option list, as written in the guide."""
    return {
        step["key"]: [o["key"] for o in step.get("options") or []]
        for step in document.get("steps") or []
        if step.get("options")
    }


def _texture_tags(document):
    """The texture refinement's listed choices, or [None] if derived."""
    for refinement in document.get("refinements") or []:
        if refinement.get("key") != "texture":
            continue
        tags = [c["tag"] for c in refinement.get("choices") or []]
        if tags:
            return tags
    return [None]


def _answer_for(step):
    """What the page would put in this question without being told.

    `recommended` is the engine's own answer and is always a concrete
    option; `default` is the raw rule list when the answer depends on
    earlier ones, so it is only usable when it is a bare value.
    """
    recommended = step.get("recommended")
    if isinstance(recommended, str):
        return recommended
    default = step.get("default")
    return default if isinstance(default, str) else None


def _walked(client, key, state):
    """Answer every question the guide reveals, until it reveals none.

    Each answer can publish a further question, which is why this loops
    rather than reading the document's step list once.
    """
    state = dict(state)
    while True:
        payload = _resolve(client, key, state)
        added = False
        for step in payload.get("steps") or []:
            if step["key"] in state:
                continue
            answer = _answer_for(step)
            if answer is None:
                continue
            state[step["key"]] = answer
            added = True
        if not added:
            return state, payload


def _published(payload):
    """Each published question's options, as the page would show them."""
    return {
        step["key"]: [o["key"] for o in step.get("options") or []]
        for step in payload.get("steps") or []
    }


def _empty_roles(payload):
    parts = payload.get("parts") or []
    return [p["role"] for p in parts if not p.get("blueprint")]


#: Settled states, keyed by what produced them. A walk is several round
#: trips and both guards want the same ones.
_SETTLED: dict = {}


def _states(client, key, document):
    """Every texture and build method, walked to a settled state.

    Both dimensions, because an answer can be specific to one method —
    a clip only the glued build uses is not missing when the modular
    build declines to publish it.
    """
    methods = _documented_options(document).get("method") or [None]
    for tag in _texture_tags(document):
        for method in methods:
            start = {}
            if tag:
                start["texture"] = tag
            if method:
                start["method"] = method
            settled = _SETTLED.get((key, tag, method))
            if settled is None:
                settled = _walked(client, key, start)
                _SETTLED[(key, tag, method)] = settled
            state, payload = settled
            label = f"{tag or 'default texture'} / {method or 'any method'}"
            yield label, state, payload


class TestOfferedAnswersResolve:
    """Every answer on offer fills every part it puts in play."""

    def test_offered_answers_resolve_without_an_empty_part(self, api_client_no_auth):
        client = api_client_no_auth
        checked = 0
        failures = []
        for key in _guide_keys(client):
            document = _document(client, key)
            for label, state, payload in _states(client, key, document):
                refused = _refused(client, key, state)
                for question, options in _published(payload).items():
                    skip = set(refused.get(question) or [])
                    for option in options:
                        if option in skip:
                            continue
                        asked = dict(state)
                        asked[question] = option
                        empty = _empty_roles(_resolve(client, key, asked))
                        checked += 1
                        if empty:
                            failures.append(
                                f"{key} {label} {question}={option} "
                                f"left empty: {', '.join(empty)}"
                            )
        assert checked, "no guide offered an answer to check"
        assert not failures, "\n".join(failures)


class TestDocumentedAnswersAreReachable:
    """A documented answer is usable somewhere, not advertised dead."""

    def test_every_documented_answer_is_reachable_somewhere(self, api_client_no_auth):
        client = api_client_no_auth
        for key in _guide_keys(client, REACHABLE):
            document = _document(client, key)
            documented = _documented_options(document)
            reachable = {question: set() for question in documented}
            seen = []
            for label, state, payload in _states(client, key, document):
                seen.append(label)
                refused = _refused(client, key, state)
                published = _published(payload)
                for question in documented:
                    skip = set(refused.get(question) or [])
                    live = set(published.get(question) or []) - skip
                    reachable[question] |= live
            assert seen, f"no state walked for {key}"
            dead = [
                f"{key} {question}={option} is documented but refused "
                f"or withheld in every state tried"
                for question, options in documented.items()
                for option in options
                if option not in reachable[question]
            ]
            assert not dead, "\n".join(dead)
