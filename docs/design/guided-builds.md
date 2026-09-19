# Guided builds

*Design for the "how do I make a wall?" epic. Written to be picked up by someone with
no memory of the conversation that produced it.*

## The problem

The catalog is good at finding a piece you can already name and bad at telling you what
to print. Someone who wants a wall meets 12,000 STLs and a tag tree, which is a pile of
bricks where they wanted a Lego set.

The site should guide instead: ask a few questions, recommend specific parts, and let
people change any recommendation afterwards rather than forcing every decision up front.

## The inversion

A **blueprint** today says: *here is a part, and here are the slots it can accept,*
expressed as tag predicates over other parts.

A **guide** is the inverse: *here is a thing you want to build, and here are the parts
that make it.* Same tag vocabulary, walked in the other direction.

Guides are data, not code. Adding "how do I make a corner" must never require a deploy
of new component logic.

## What already exists (verified, 2026-09-19)

Reuse this rather than rebuilding it.

*Every count below is over all 21 `.json` and 20 `.yaml` fixture files in
`openforge/db/fixtures/blueprints/`, because the loader reads both. Counts that were
derived from the `.json` files alone are wrong and were wrong in the first two drafts
of this document.*

**Tag vocabulary.** 922 distinct tags across 8,761 fixture records — 8,721 scanned
models plus the 40 hand-authored composition blueprints described below. The namespaces
that matter here:

| Namespace | Distinct tags | Examples |
|---|---|---|
| `build` | 7 | `build\|s2w`, `build\|wall on tile`, `build\|separate wall`, `build\|s-system`, `build\|thick wall` |
| `shape` | 186 | `shape\|wall`, `shape\|floor`, `shape\|base`, `shape\|corner`, `shape\|curved` |
| `connection` | 20 | `connection\|openlock`, `connection\|dragonlock`, `connection\|magnetic`, `connection\|side\|openlock` |
| `texture` | 83 | `texture\|dungeon_stone`, `texture\|cave`, `texture\|towne` |
| `size` | 103 | `size\|width\|1`, `size\|depth\|1`, `size\|angle\|45` |
| `component`, `part`, `interface` | 375 / 25 / 67 | `part\|door\|arched`, `interface\|archway` |

**The three build methods the first guide covers are already tags**, with records
carrying them: `build|s2w` (673), `build|wall on tile` (863), `build|separate wall`
(3,360). The two the first guide does not cover are `build|thick wall` (599) and
`build|s-system` (286). No record carries two of these five.

**Slot predicates.** A blueprint's `config.parts[]` is a list of named slots, each with
`tags: {require, deny, constrain}`. `constrain` means *match the parent's value for this
tag*, which is how a floor's base slot finds a base of the same size and shape. The
predicates are interpreted today in `src/utils/config-processing.ts`; tag search itself
is `openforge/db/sql/tags.py:tag_search_blueprints` behind the `tag_query` OpenAPI schema,
which carries three predicates, not two: `require` and `deny` match a tag exactly, and
`accept` matches a tag or anything below it (`accept: shape|wall` also takes
`shape|wall|corner`). A guide needs all three.

**Slot inventory.** 2,501 records have one slot, 416 have two, 158 have three, one has
four and four have five. By name: `base` (2,499), then `torch` (356), `door` (248),
`lintel` (143), `frame` (71), `shutters` (71), `grate` (66), `portcullis` (65),
`treasure` (55), `floor` (40), `top` (39), `wall` (32), `archway` (29),
`trapdoor` (28). The `floor` and `wall` slots are the composition blueprints'.

**Composition blueprints — the closest thing to a guide that already exists.** 40 of the
8,761 records are `type: blueprint` rather than `type: model`: hand-authored
compositions in the 20 `blueprints.s2w.*.yaml` fixtures, named things like *S2W: Wall on
Tile: Wall: Arrow Slit (Single Piece)*. Each one carries exactly the structure this
document calls a role set — named `wall`, `floor` and `base` parts, each a tag predicate
picking the right piece for that method — and 20 of them use `fulfills` to say the wall
already satisfies the base slot. All 40 are `build|s2w`.

This is prior art, and it is the reason the guide format below has roles rather than a
flat parts list. Two differences matter: a composition blueprint is one fixed
combination authored per variant (arrow slit, boss door, niche...), while a guide is a
question tree that ranks candidates; and the compositions lean on `constrain` to keep
the base the same width as the floor, which guides do not (see below).

**Prose.** `tag_documentation` already keys documents to a *tag array* with a
`document_type` enum that includes `instructions`. Guide prose should live there or
follow its shape rather than inventing a third documentation store.

**Imagery.** `/mnt/d/OpenForge/Sets/` holds curated renders in 17 directories named by
texture and build method — `dungeon_stone.wall_on_tile.wall`,
`cut-stone.separate_wall.primary` — and these are the illustrations a guide needs. The
naming cannot be trusted to give the method, though: the 47 `dungeon_stone.s2w.*.png`
files, including `dungeon_stone.s2w.wall.1.door+arched.png`, live in
`dungeon_stone.separate_wall.primary_wall/`, so directory and filename disagree. Whoever
does `openforge_catalog-eul` picks images per guide option by hand rather than by path.
They are not in R2 yet; blueprint images are served from
`https://objects.openforge.tools/sprites/<prefix>/<md5>.png`.

## The base slot: what is actually true, and what we do about it

The first draft of this document claimed the base slot was a contradiction — that a
wall carries a slot wall-on-tile never uses, because the parser could not know the build
method. **That was wrong, and a reviewer caught it before the epic was built on it.**

The parser does know the build method. `is_openforge_wall` requires `build|separate wall`;
`is_thick_wall` requires `build|thick wall` and keys on `component|wall`, not a shape. The
data follows. Counts are of records tagged `shape|wall`, including the 177 that carry
`shape|floor` as well:

| Build method | Scanned walls with a base slot | Composition blueprints with one |
|---|---|---|
| `build\|separate wall` | 1,220 of 2,913 | none exist |
| `build\|wall on tile` | **0 of 397** | none exist |
| `build\|s2w` | **0 of 356** | 32 of 32 |
| `build\|s-system` | 0 of 41 | none exist |
| `build\|thick wall` | 87 of 337 | none exist |

No record carries two build tags. The 295 wall-on-tile pieces that do carry a base slot
are all floors, 17 of which are corners as well — the base goes under the floor, which
is exactly the model this document prescribes.

**Removing the slot is a simplification rather than a fix, but the reason has to be
stated more narrowly than "openforge implies a base".** Across the catalog that is
false: 4,368 records carry `connection|openforge` and only 2,455 of them have a base
slot. What is true is per method, and it is exact. Under `build|separate wall`, the slot
and the tag are the same fact: of the 1,221 openforge separate-wall walls, 1,220 carry
the slot and the one that does not is a `shape|column|low` piece, not a wall; no
non-openforge separate-wall wall carries one. Under `build|thick wall` the same holds
for the 100 openforge thick walls — the 13 without a slot are `component|slope` pieces,
which is what `is_thick_wall` keys on. Under the other three methods the base belongs to
the floor, and no wall carries one.

So the pair (build method, `connection|openforge`) determines whether a piece takes a
base, and the synthesised slot restates what the piece already says. The decision is
still to remove it — but it is cleanup, it is not urgent, and **it does not block the
rest of the epic.**

Whoever does it should know:

- The three helpers in `openforge/data/metadata.py` are *the only place in the repo that
  knows which pieces take bases under which method*. That knowledge must move somewhere
  the guide can read, not be deleted. Their mechanisms differ: `apply_openforge_wall`
  constrains shape, width and texture, while `apply_openforge_floor` and
  `apply_thick_wall` constrain shape, width and depth and add `deny: build|s2w`.
- Whatever replaces the slot must read the method as well as the connection tag. A UI
  that derives "this takes a base" from `connection|openforge` alone would reintroduce
  the falsehood this section exists to correct — it would promise a base to 391
  wall-on-tile, 308 s2w and 34 s-system walls that have none.
- 2,499 base parts sit on 2,495 records, four of which carry a duplicate. 40 of those
  parts are the composition blueprints' authored slots, and the scanner runs authored
  metadata before it appends defaults, so **some base slots are authored** and will
  survive a parser change. Verify by count afterwards.
- The consumers change meaning: `src/utils/config-processing.ts`, whatever surfaces
  compatible bases on a blueprint page, and `collectDownloadUrls` in
  `src/utils/blueprint-utils.ts`, which walks parts to build a download set.

**Feature slots stay, and the model must not preclude them.** `door`, `torch`, `lintel`,
`grate`, `portcullis`, `shutters`, `frame`, `treasure`, `top`, `archway`, `trapdoor` come
from authored folder metadata, not from the parser — `apply_default_metadata` only ever
appends `base`. They are real choices a person makes, out of scope for the first slice,
and a later guide step should offer them by reading the chosen part's own slots.

## Mechanisms that already exist and must be reconciled

The instruction was to look at blueprints because most of the concepts are already there.
Three that a first draft missed:

- **`fulfills`** — defined in `openforge/openapi/schemas/config.yaml`, implemented in
  `src/components/blueprint/config-section.tsx`, and used 41 times in two positions that
  mean different things: 21 at the root of a blueprint (7 in `cut-stone.json`, 14 in
  `dungeon_stone.json`), saying *this whole piece satisfies a slot of that name*, and 20
  inside a composition blueprint's part, saying *this part satisfies that sibling part's
  slot* — the s2w wall that is its own base. The second is the "an option takes options
  away" mechanic the guide needs. Reconcile with `when:` rather than inventing a parallel
  mechanism.
- **`constrain`** — has **no Python implementation**. It lives in the schema and in
  `src/utils/config-processing.ts`, and its real semantics are richer than "match the
  parent": `parent: false`, `siblings`, and `filter` as an exclusion, with narrowing to
  the most general match. The composition blueprints lean on it to keep a base the same
  width as its floor. **Decision: guides do not use `constrain`.** Porting it would put
  a fixpoint solver inside the resolution engine, and the thing it buys — every role the
  same size — is better asked than inferred: size is a step the person answers, and
  every role's composed query then requires the chosen `size|width|*` outright. The
  guide format therefore carries `require`, `deny` and `accept` only, and
  `openforge/openapi/schemas/guide.yaml` rejects `constrain`.
- **Dual-shape pieces** — 177 records carry both `shape|wall` and `shape|floor`
  (88 s2w, 59 wall on tile, 1 separate wall). These are the combined prints. A role query
  of `require: shape|wall` will pick them up, so the guide needs a stated rule for how a
  method's tags, a role's query and an active refinement compose. The rule, settled in
  `openforge_catalog-7ph`: the composed query is the union of the three predicates, each
  list concatenated, and `deny` beats `require`. Nothing in the engine knows about
  combined prints — a guide that does not want one denies the other shape in that role's
  query, which is a content decision belonging to `openforge_catalog-z76`.

## Shape of the data

Fixtures in the repo, loaded into a table, exactly as `tag_descriptions` works today.
Authoring is a git edit; an admin editor is a later bead once the shape has settled.

```yaml
key: wall
title: How do I make a wall?
summary: |
  Three ways, and the difference is where the wall meets the floor.
steps:
  - key: method
    prompt: How do you want to build it?
    options:
      - key: s2w-modular
        title: Modular (s2w)
        blurb: Wall, floor and base print separately and stack.
        image: sets/dungeon_stone.s2w.wall.1.door+arched.png
        roles: [floor, base, wall]        # what this method is made of
        tags:  {require: ['build|s2w']}
      - key: wall-on-tile
        title: Wall on tile
        roles: [floor, base, wall]        # the base is the floor's, not the wall's
        tags:  {require: ['build|wall on tile']}
      - key: separate-wall
        title: Separate wall
        roles: [floor, wall]              # floor and wall are independent
        tags:  {require: ['build|separate wall']}

roles:
  wall:
    title: Wall
    query:   {require: ['shape|wall'], deny: ['shape|base']}
    prefer:  ['connection|openforge']     # ranks candidates to pick the recommendation
  floor:
    title: Floor
    query:   {require: ['shape|floor']}
  base:
    title: Base
    query:   {require: ['shape|base']}
    under:   floor                        # the base always sits under the floor; the
                                          # method decides whether there is a base at
                                          # all, by listing the role or not

refinements:                              # the "change it afterwards" list
  - key: texture
    role: '*'
    prompt: Texture
    from_namespace: texture
  - key: side-locks
    role: wall
    prompt: Locks on the wall ends?
    when: {selected: {method: [s2w-modular, separate-wall]}}
    on_tags:  {require: ['connection|side|openlock']}
    off_tags: {deny:    ['connection|side|openlock']}
```

The toggle fields are `on_tags` / `off_tags` rather than `on` / `off` because bare `on`
and `off` are booleans in YAML 1.1, which is what `safe_load` parses the fixtures as.

Every key in a guide lives in one namespace: a selection is `<step or refinement key> =
<option key or tag>`, which is what lets the whole state fit in a query string, so a
refinement may not reuse a step's key. The loader rejects that, along with an option
naming a role that does not exist and a `when:` that depends on a later step.

Two mechanics are required by the ask and must survive review:

1. **Options beget options, and take them away.** A step or refinement carries `when:`, a
   predicate over earlier selections. Declarative, so the engine stays a pure function and
   the authoring stays data. Avoid imperative `enables:`/`disables:` lists, which are
   order-dependent and hard to validate.
2. **Recommend, then allow change.** Every role resolves to a concrete part as soon as
   the step that names the role is answered, ranked by `prefer`, so a person sees a
   buildable set after answering one question rather than a filter form. The refinements
   are how they diverge from it, not a gate before they see anything. A role whose
   composed query matches nothing resolves to no part and says so — a guide that
   recommends silence is a content bug, and `openforge_catalog-7ph` makes it visible
   rather than swallowing it.

## Where the logic goes

**Python.** `src/CLAUDE.md` is explicit that the backend is where real logic lives, and
resolution is real logic: predicate composition, candidate ranking, and working out which
steps are now reachable. It is also far easier to test there.

Proposed endpoints:

- `GET /api/guides` — list.
- `GET /api/guides/<key>` — the document, for rendering steps.
- `POST /api/guides/<key>/resolve` — selections in, resolved parts plus newly available
  steps out.

`resolve` keeps payloads small, which matters: `GET /api/blueprints` already exceeds the
ALB's 1 MB cap for Lambda targets and 502s (`openforge_catalog-i7c`). Do not build the
guide on top of an endpoint that returns the whole catalog.

## What the user gets

A parts list: each chosen piece with its thumbnail and STL link, and a shareable URL that
encodes the selections, so "here is the wall I mean" can be sent to someone. URL state
matches the existing `?blueprint_id=` convention and needs no accounts.

Note for whoever builds the frontend: `use-url-parameters.ts` and
`use-blueprint-url-cleanup.ts` rewrite the query string after load. Guide state must not
be silently stripped the way blueprint deep links are.

## Sequence

0. **Drop the synthesised base slot** — cleanup, not a blocker, and it can land in
   parallel with the rest. Parser change in `openforge/data/metadata.py`, fixtures
   regenerated, and the blueprint UI switched to deriving bases from the build method
   and `connection|openforge` together — never from the connection tag alone, which is
   true of 4,368 records and wrong for 1,913 of them.
1. **Schema and loader** — `guides` table, fixture format with an OpenAPI schema beside
   the others, loader wired into the fixtures command, validation errors that name the
   offending step.
2. **Resolution engine** — pure Python over a guide document and a selection map, unit
   tested against the real wall fixture. No HTTP.
3. **API** — the three endpoints above.
4. **Author the wall guide** — content, with Devon. The three methods, their roles, the
   recommendations, the refinements, the prose.
5. **Frontend** — the guide page: steps, recommended parts, change affordances, the parts
   list, the shareable URL.
6. **Later slices** — the catalog-style landing page (Floor, Wall, Corner); feature slots
   (doors, torches); an admin editor for guides; guide imagery into R2.

## Beads

| Bead | Work |
|---|---|
| `openforge_catalog-2i5` | The epic |
| `openforge_catalog-cgi` | Stop the parser synthesising the base slot — cleanup, parallel |
| `openforge_catalog-8zc` | `guides` table, fixture format and loader |
| `openforge_catalog-7ph` | Resolution engine in Python |
| `openforge_catalog-anc` | Guide endpoints |
| `openforge_catalog-z76` | Author the wall guide (content, with Devon) |
| `openforge_catalog-0bz` | The guide page |
| `openforge_catalog-faz` | Catalog-style landing page: Floor, Wall, Corner |
| `openforge_catalog-cku` | Feature slots: doors, torches and the rest |
| `openforge_catalog-eul` | Guide imagery into R2 |
| `openforge_catalog-kcm` | Admin editor for guides |
| `openforge_catalog-hcm` | Audit which pieces carry a base slot and why — **closed**, answered above |

## Open questions

These are for Devon; none of them block slices 1 to 3.

- Recommendation ranking beyond `prefer`: is "most complete texture coverage" or
  "most printed" a better default than a hand-ordered tag list? Start hand-ordered.
- Whether `build|s-system` (286 records) and `build|thick wall` (599) are methods a
  person picks between, or variants inside the three. They are tags today with no guide.
- Whether the 40 s2w composition blueprints should become guide content, stay as they
  are, or be generated from the guide once it exists. They overlap with what the wall
  guide will say about s2w, and two sources for one answer will drift.
- Where guide images live. The Sets renders are the right pictures and are not yet in R2.
