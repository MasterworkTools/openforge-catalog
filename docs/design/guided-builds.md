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

**Tag vocabulary.** 916 distinct tags across 8,721 blueprints in the fixtures. The
namespaces that matter here:

| Namespace | Count | Examples |
|---|---|---|
| `build` | 5 | `build|s2w`, `build|wall on tile`, `build|separate wall`, `build|s-system`, `build|thick wall` |
| `shape` | 184 | `shape|wall`, `shape|floor`, `shape|base`, `shape|corner`, `shape|curved` |
| `connection` | 20 | `connection|openlock`, `connection|dragonlock`, `connection|magnetic`, `connection|openlock|side`, `connection|openlock|topless` |
| `texture` | 83 | `texture|dungeon_stone`, `texture|cave`, `texture|towne` |
| `size` | 103 | `size|width|1`, `size|depth|1`, `size|angle|45` |
| `component`, `part`, `interface` | 375 / 25 / 67 | `part|door|arched`, `interface|archway` |

**The three build methods the first guide covers are already tags**, with blueprints
carrying them: `build|s2w` (633), `build|wall on tile` (863), `build|separate wall`
(3,360).

**Slot predicates.** A blueprint's `config.parts[]` is a list of named slots, each with
`tags: {require, deny, constrain}`. `constrain` means *match the parent's value for this
tag*, which is how a floor's base slot finds a base of the same size and shape. The
predicates are interpreted today in `src/utils/config-processing.ts`; tag search itself
is `openforge/db/sql/tags.py:tag_search_blueprints` behind the `tag_query` OpenAPI schema
(`require`/`deny`).

**Slot inventory.** 2,501 blueprints have one slot, 416 have two, 122 have three. By
name: `base` (2,459), then `torch` (356), `door` (248), `lintel` (143), `frame` (71),
`shutters` (71), `grate` (66), `portcullis` (65), `treasure` (55), `top` (39),
`archway` (29), `trapdoor` (28).

**Prose.** `tag_documentation` already keys documents to a *tag array* with a
`document_type` enum that includes `instructions`. Guide prose should live there or
follow its shape rather than inventing a third documentation store.

**Imagery.** `/mnt/d/OpenForge/Sets/` holds curated renders already organised by build
method: directories like `dungeon_stone.wall_on_tile.wall` and
`cut-stone.separate_wall.primary`, files like
`dungeon_stone.s2w.wall.1.door+arched.png`. These are the illustrations a guide needs.
They are not in R2 yet; blueprint images are served from
`https://objects.openforge.tools/sprites/<prefix>/<md5>.png`.

## The slot problem, and the decision

A wall blueprint has an optional `base` slot. In **wall on tile** that slot goes unused,
because the wall stands on the floor tile. The slot cannot express that: it is a property
of the part, but whether it is used is a property of the *method*.

Look at where that slot comes from and the contradiction explains itself. It is not
authored — it is synthesised by the parser in `openforge/data/metadata.py`:
`apply_default_metadata()` calls `apply_openforge_wall`, `apply_openforge_floor` and
`apply_thick_wall`, each of which checks for `connection|openforge` plus a shape and then
appends a `base` part requiring `shape|base`, constrained to matching shape, width and
texture. Feature slots are different in kind: `door`, `torch` and the rest come from
authored folder metadata, merged by `get_all_folder_metadata`.

So the `base` slot restates, per blueprint, something the connection tag already says:
**a piece with `connection|openforge` needs a base, and what counts as a base depends on
the build method.** Encoding that on 2,459 parts means encoding it in the one place that
cannot know the method.

**Decision: remove the synthesised base slot from the data, in the parser.** Then:

- `config.parts` means one thing again — genuine feature slots the piece accepts.
- "Does this need a base, and which one?" is answered by `connection|openforge` plus the
  build method, which is what the guide already knows.
- Wall on tile stops being a contradiction, because nothing claims the wall has a base.

**Consequences to plan for**, all mechanical but not small:

- `apply_default_metadata` and its three helpers stop emitting the part. Their tag checks
  still encode real knowledge about which pieces take bases; keep that knowledge where the
  guide can use it rather than deleting it outright.
- 2,459 blueprints in the fixtures lose a part, so the fixtures regenerate. Expect a large
  diff and verify by count, not by eye.
- Anything that reads the base slot changes meaning, in particular
  `src/utils/config-processing.ts` and whatever surfaces compatible bases on a blueprint
  page today. That UI must derive bases from the connection tag instead, or it silently
  stops offering them.

**Feature slots stay, and the model must not preclude them.** `door`, `torch`, `lintel`,
`grate`, `portcullis`, `shutters`, `frame`, `treasure`, `top`, `archway`, `trapdoor` are
real choices a person makes, out of scope for the first slice, and a later guide step
should be able to offer them by reading the chosen part's own slots.

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
        image: sets/dungeon_stone.s2w.wall.1.png
        roles: [floor, base, wall]        # what this method is made of
        tags:  {require: ['build|s2w']}
      - key: wall-on-tile
        roles: [floor, base, wall]        # one base, under the floor, not under the wall
        tags:  {require: ['build|wall on tile']}
      - key: separate-wall
        roles: [floor, wall]              # floor and wall are independent
        tags:  {require: ['build|separate wall']}

roles:
  wall:
    title: Wall
    query:   {require: ['shape|wall'], deny: ['shape|base']}
    prefer:  ['connection|openforge']     # ranks candidates to pick the recommendation
  base:
    title: Base
    query:   {require: ['shape|base']}
    under:   floor                        # which role it sits beneath, per method

refinements:                              # the "change it afterwards" list
  - key: texture
    role: '*'
    prompt: Texture
    from_namespace: texture
  - key: side-locks
    role: wall
    prompt: Locks on the wall ends?
    when: {selected: {method: [s2w-modular, separate-wall]}}
    on:   {require: ['connection|openlock|side']}
    off:  {deny:    ['connection|openlock|side']}
```

Two mechanics are required by the ask and must survive review:

1. **Options beget options, and take them away.** A step or refinement carries `when:`, a
   predicate over earlier selections. Declarative, so the engine stays a pure function and
   the authoring stays data. Avoid imperative `enables:`/`disables:` lists, which are
   order-dependent and hard to validate.
2. **Recommend, then allow change.** Every role resolves to a concrete part immediately
   using `prefer`, so a person sees a buildable set after answering one question. The
   refinements are how they diverge from it, not a gate before they see anything.

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

0. **Drop the synthesised base slot** — parser change in `openforge/data/metadata.py`,
   fixtures regenerated, and the blueprint UI switched to deriving bases from the
   connection tag. Do this first: it is the change that makes the rest coherent, and
   doing it after the guide exists means writing the guide against a model that is
   about to move.
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
| `openforge_catalog-cgi` | Stop the parser synthesising the base slot — **do this first** |
| `openforge_catalog-8zc` | `guides` table, fixture format and loader |
| `openforge_catalog-7ph` | Resolution engine in Python |
| `openforge_catalog-anc` | Guide endpoints |
| `openforge_catalog-z76` | Author the wall guide (content, with Devon) |
| `openforge_catalog-0bz` | The guide page |
| `openforge_catalog-faz` | Catalog-style landing page: Floor, Wall, Corner |
| `openforge_catalog-cku` | Feature slots: doors, torches and the rest |
| `openforge_catalog-eul` | Guide imagery into R2 |
| `openforge_catalog-kcm` | Admin editor for guides |

## Open questions

- Recommendation ranking beyond `prefer`: is "most complete texture coverage" or
  "most printed" a better default than a hand-ordered tag list? Start hand-ordered.
- Whether `build|s-system` and `build|thick wall` are methods a person picks between, or
  variants inside the three. They are tags today with no guide.
- Where guide images live. The Sets renders are the right pictures and are not yet in R2.
