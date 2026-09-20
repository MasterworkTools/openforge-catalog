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
| `build` | 7 | the five methods — `build\|s2w`, `build\|wall on tile`, `build\|separate wall`, `build\|s-system`, `build\|thick wall` — plus `build\|s2w\|modular` and `build\|s2w\|single_piece` |
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
Tile: Wall: Arrow Slit (Single Piece)*. Each carries exactly the structure this document
calls a role set — named parts, each a tag predicate picking the right piece for that
method. 32 of them are `wall` + `floor` + `base`; the other eight are corners, four with
`column` + `floor` + `base` and four adding `left wall` and `right wall`. All 40 carry a
`base` part, and all 40 are `build|s2w`. Eighteen of them use `fulfills` — 20 entries,
on the `wall` part in sixteen records and on `left wall` / `right wall` in two — to say
that part already satisfies the base slot.

This is prior art, and it is the reason the guide format below has roles rather than a
flat parts list. Three differences matter. A composition blueprint is one fixed
combination authored per variant (arrow slit, boss door, niche...), while a guide is a
question tree that ranks candidates. The compositions lean on `constrain` to keep the
base the same width as the floor, which guides do not (see below). And they are the
evidence that **a build method is not one tag**: inside a single `build|s2w`
composition the `floor` part requires `build|s2w` (all 40) while the `wall` part
requires `build|separate wall` (all 32 that have one), and the `base` part denies
`build|s2w` in 20 of them and requires it in 17 — the variation is the point, and it
is why an option
in the guide format carries a predicate per role rather than one predicate for the
whole method. Their names and tags say the same thing twice over: *S2W: Wall on Tile*,
tagged both `build|s2w` and `object|tile|wall_on_tile`. Whether a guide "method" should
be a build tag at all, or a named combination like these, is content for
`openforge_catalog-z76`.

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
are all floors, 17 of which are corners as well — under *this* method the base goes
under the floor. Under the others it does not, which is the subject of the two base
roles further down.

**Removing the slot is a simplification rather than a fix, but the reason has to be
stated more narrowly than "openforge implies a base".** Across the catalog that is
false: 4,368 records carry `connection|openforge` and only 2,455 of them have a base
slot. What is true is per method, and it is exact. Under `build|separate wall`, the slot
and the tag are the same fact: of the 1,221 openforge separate-wall walls, 1,220 carry
the slot and the one that does not carries `shape|floor` as well as `shape|wall`, which
`is_openforge_wall` denies outright (along with `shape|base` and `build|s2w`); no
non-openforge separate-wall wall carries one. Under `build|thick wall` the same holds
for the 100 openforge thick walls — `is_thick_wall` also requires `component|wall`, and
not one of the 13 without a slot carries it; they are wooden, slope and transition
pieces. Under the other three methods no wall carries a synthesised base at all, and
where the base goes differs: under `build|wall on tile` it is the floors that carry
one (295 of them, and none of the walls), under `build|s2w` neither does — none of the
176 s2w floors carries a slot, and the only s2w records that do are the 40 composition
blueprints, where it is the **wall** part that declares `fulfills: base` — and under
`build|s-system` nothing carries one.

So the pair (build method, `connection|openforge`) determines whether a piece takes a
base, and the synthesised slot restates what the piece already says. The decision is
still to remove it — but it is cleanup, it is not urgent, and **it does not block the
rest of the epic.**

Whoever does it should know:

- The three helpers in `openforge/data/metadata.py` are *the only place in the repo that
  knows which pieces take bases under which method*. That knowledge must move somewhere
  the guide can read, not be deleted. Their mechanisms differ: `apply_openforge_wall`
  constrains shape, width and texture, while `apply_openforge_floor` and
  `apply_thick_wall` constrain shape, width and depth and add `deny: build|s2w` —
  and `apply_openforge_floor` alone adds two `constrain` filters excluding
  `shape|floor` and `shape|wall`, which is what keeps a floor's base from being
  another floor.
- Whatever replaces the slot must read the method as well as the connection tag. A UI
  that derives "this takes a base" from `connection|openforge` alone would reintroduce
  the falsehood this section exists to correct — it would promise a base to 391
  wall-on-tile, 308 s2w and 34 s-system walls that have none.
- 2,499 base parts sit on 2,495 records, four of which carry a duplicate. Running the
  three predicates over the fixtures accounts for 2,452 of those records; **the other
  47 base parts are authored and must survive the parser change** — 40 in the
  composition blueprints, three on `dungeon_stone` infinite-hallway pieces, and four in
  `sewers.json` where an authored slot sits beside the synthesised one, which is
  exactly where the four duplicates come from. 47 is the verify-by-count number.
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
  `src/components/blueprint/config-section.tsx`, and used in two positions that mean
  different things: 27 entries at the root of 21 blueprints (7 records in
  `cut-stone.json`, 14 in `dungeon_stone.json`), saying *this whole piece satisfies a
  slot of that name*, and 20 entries inside the parts of 18 composition blueprints,
  saying *this part satisfies that sibling part's slot* — the s2w wall that is its own
  base. 47 entries across 39 records in total. The second is the "an option takes options
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
  (88 s2w, 59 wall on tile, 1 separate wall, and 29 carrying no build tag at all).
  These are the combined prints. A role query of `require: shape|wall` will pick them
  up, so the guide needs a stated rule for how a
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
      - key: s2w
        title: Modular (s2w)
        blurb: Wall, floor and base print separately and stack.
        image: sets/dungeon_stone.s2w.wall.1.door+arched.png
        roles:                                  # copied from what the s2w
          floor: {require: ['build|s2w', 'shape|floor|wall']}   # composition
          wall: {require: ['build|separate wall', 'component|wall']}
          wall-base: {require: ['build|s2w', 'shape|base|wall']} # blueprints
      - key: wall-on-tile                                       # already say
        title: Wall on tile
        roles:
          floor: {require: ['build|wall on tile'], deny: ['shape|wall']}
          wall: {require: ['build|wall on tile']}
          floor-base: {deny: ['build|s2w']}
      - key: separate-wall
        title: Separate wall
        roles:
          floor: {deny: ['shape|wall']}         # no floor tile carries
          wall: {require: ['build|separate wall']}   # build|separate wall
          wall-base: {require: ['build|separate wall', 'shape|base|wall']}

roles:
  floor:
    title: Floor
    query:
      require: ['shape|floor']
      deny: &intact                             # a YAML anchor: the wall
        - 'shape|base'                          # role reuses this list
        - 'component|collapsed'
        - 'component|broken'
        - 'component|collapsing_blocks'
        - 'texture|dungeon_stone|ruined'
        - 'texture|rough_stone|ruined'
        - 'texture|cut-stone|ruined'
        - 'texture|towne|ruined_stucco'
    prefer: ['connection|openforge', 'texture|dungeon_stone']
  wall:
    title: Wall
    query:
      require: ['shape|wall']
      deny: *intact
    prefer: ['connection|openforge', 'texture|dungeon_stone']
  floor-base:                                   # two base roles, because
    title: Base                                 # which part the base goes
    query:                                      # under is the method's
      require: ['shape|base']                   # choice
      deny: ['shape|base|wall', 'shape|base|s2w']
    prefer: ['texture|plain']
    under: floor
  wall-base:
    title: Base
    query: {require: ['shape|base']}
    prefer: ['connection|magnetic']
    under: wall

refinements:                                    # the "change it afterwards" list
  - key: texture
    role: '*'
    prompt: Texture
    from_namespace: texture
  - key: side-locks
    role: wall
    prompt: Locks on the wall ends?
    when: {selected: {method: [s2w, separate-wall]}}
    on_tags: {require: ['connection|side|openlock']}
    off_tags: {deny: ['connection|side|openlock']}
```

The seven tags under the `&intact` anchor are what marks a piece as damaged: three
`component` tags and the four ruined textures. **Devon's decision is that a guide never
recommends a damaged piece by default** — someone who wants one asks through the
texture refinement. They have to be listed rather than matched by prefix because
**`deny` is an exact tag match**: `deny: component|collapsed` catches only the 265
records carrying that exact tag, which happens to be every `component|collapsed|*`
piece because they all carry the parent as well. `accept` is the predicate that matches
a subtree; there is no denying one. The anchor is ordinary YAML and the loader resolves
it before validation, so a guide can share a list like this without repeating it.

With those denies every role of every method resolves to an intact piece: the s2w set
is a `dungeon_stone` floor-and-wall tile, a straight openforge wall and an s2w wall
base; separate wall gets a plain `dungeon_stone` floor, an arched-door wall and an
aztlan wall base.

Three things in that block are worth reading twice, because each cost a review round.

**The s2w roles are copied from the composition blueprints, not guessed.** There is no
straight s2w wall in the catalog: of the 220 records that are `shape|wall` and
`build|s2w` and neither base nor floor, 219 are corner halves. All 32 wall composites
take their wall from `build|separate wall` with `component|wall`, their floor from the
88 `shape|floor|wall` s2w tiles, and their base from `shape|base|wall`. The guide says
the same thing.

**A role-level `deny` is absolute.** Composition is a union with `deny` beating
`require`, so no option can opt back into something the role denied. The floor role
therefore cannot deny `shape|wall` — that would remove exactly the 88 combined tiles
the s2w method is built from — and the two methods that do want a plain floor deny it
in their own option instead. This is the one place where the union rule constrains
authoring, and it is worth knowing before writing a role.

**The separate-wall option is the case for the per-role map.** Its wall and its base
want `build|separate wall` and its floor must not have it, because no floor tile
carries that tag: of the 1,319 records that are a floor and neither base nor wall, 295
are wall on tile, 88 are s2w, and 936 carry no build tag at all. A single option-wide
predicate would recommend a base as the floor, which an earlier draft of this document
did.


Every role/method pair above resolves to a part of the right kind against the current
fixtures, which is not something to take on faith: an earlier draft of this block gave
wall-on-tile a base query no wall-on-tile record could satisfy, and gave separate wall
a floor role that matched only bases. The `deny` lists are doing that work. The floor
role denies `shape|base` and `shape|wall` because 114 of the 115 records carrying both
`shape|floor` and `build|separate wall` are bases, and 177 records are both wall and
floor.

The separate-wall option is the clearest case for the per-role map: its wall and its
base want `build|separate wall`, and its floor must not — **no floor tile carries that
tag.** Of the 1,319 records that are a floor and neither a base nor a wall, 295 are
wall on tile, 88 are s2w and 936 carry no build tag at all, so a separate wall stands
on an ordinary floor. A single `tags` predicate for the whole option would have put
`build|separate wall` on the floor role and recommended a base.


The toggle fields are `on_tags` / `off_tags` rather than `on` / `off` because bare `on`
and `off` are booleans in YAML 1.1, which is what `safe_load` parses the fixtures as.

Every key in a guide lives in one namespace: a selection is `<step or refinement key> =
<option key or tag>`, which is what lets the whole state fit in a query string, so a
refinement may not reuse a step's key. The loader rejects that, along with an option
naming a role that does not exist and a `when:` that depends on a later step.

`roles` is a map rather than a list because the composition blueprints prove a method
is not one tag: an option says what each role it names takes, and `tags` is the
shorthand for the part that is true of every role it names. An option says nothing
about a role it does not name. Leaving `roles` out altogether is a different thing
from naming none of them, and the schema keeps them apart: a `roles` map must have at
least one entry, and an option without the key at all adds no roles and narrows every
role already in play. That second form is what a later step like "how wide?" wants —
it answers for whatever the method turned out to be made of, instead of naming roles
that method may not have.

The two base roles are the same point from the other side. **Which part a base sits
under is the method's choice, not the base's:** of the 1,221 openforge separate-wall
walls 1,220 carry a base slot and none of the 115 records that are both a floor and a
separate wall does — and 114 of those are bases anyway, which is the same fact from the
other side: there is no separate-wall floor tile. Meanwhile
under wall on tile it is the 295 floors that carry one and no wall does. Under s2w it
is the wall again — no s2w floor carries a slot, and in the composition blueprints the
`wall` part is the one that declares `fulfills: base`. One role
called `base` with a single `under` would have to be wrong for one of them, so the
wall guide has `floor-base` and `wall-base` and each method lists the one it uses.
The queries differ too: 95 bases carry `shape|base|s2w`, 263 carry `shape|base|wall`
under `build|separate wall`, and **no base at all carries `build|wall on tile`** — the
base under a wall-on-tile floor is an untagged one, which is exactly what the
synthesised slot asks for (`require: shape|base`, `deny: build|s2w`). Getting that
wrong is the easiest way to author a guide that recommends nothing, so the real
queries are `openforge_catalog-z76`'s work against the data, not guesses.

Three mechanics are required by the ask and must survive review:

1. **Options beget options, and take them away.** A step or refinement carries `when:`, a
   predicate over earlier selections. Declarative, so the engine stays a pure function and
   the authoring stays data. Avoid imperative `enables:`/`disables:` lists, which are
   order-dependent and hard to validate.
2. **The same selections always give the same parts.** `prefer` is required outright
   and then dropped from the least wanted until something matches, and candidates
   arrive ordered by `blueprint_name`, which is the final tie-break. Without that the
   shareable URL would not reproduce what the person saw.
3. **Recommend, then allow change.** Every role resolves to a concrete part as soon as
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
6. **Drop the synthesised base slot** — cleanup, and Devon's decision is that it lands
   last in this epic rather than in parallel, while the base rules are fresh. Parser
   change in `openforge/data/metadata.py`, fixtures regenerated, and the blueprint UI
   switched to deriving bases from the build method and `connection|openforge`
   together — never from the connection tag alone, which is true of 4,368 records and
   wrong for 1,913 of them. The verification number is 47 authored base parts that
   must survive.
7. **Retire the composition blueprints** — Devon's decision is that the guide replaces
   the 40 `blueprints.s2w.*.yaml` compositions rather than living beside them, so that
   s2w has one source. The guide's s2w content is copied from them first (slice 4), so
   this is a deprecation, not a rewrite.
8. **Later slices** — the catalog-style landing page (Floor, Wall, Corner); feature slots
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
| `openforge_catalog-yan` | Retire the s2w composition blueprints once the guide covers them |
| `openforge_catalog-hcm` | Audit which pieces carry a base slot and why — **closed**, answered above |

## Open questions

Four were open when this document was written. Devon answered three of them on
2026-09-19, and they are recorded above rather than here:

- **Ranking.** Damaged pieces are denied outright in the role queries rather than
  ranked down, so a guide never recommends a ruined or collapsed variant by default.
- **`build|thick wall` (599 records) and `build|s-system` (286).** Not in the wall
  guide. They can have their own guide later.
- **The 40 s2w composition blueprints.** The guide replaces them; see slice 7.

What is still open:

- Recommendation ranking *within* the intact pieces: `prefer` is a hand-ordered tag
  list and runs out before it totally orders, so the tie-break is filename. "Most
  printed" would be better and the catalog does not know it.
- Where guide images live. The Sets renders are the right pictures and are not yet in
  R2, and their directory names cannot be trusted to give the build method.
