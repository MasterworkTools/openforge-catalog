/**
 * Guides: the catalog told the other way round. A guide asks a few
 * questions and answers with the parts to print.
 *
 * The resolution lives in Python (see docs/design/guided-builds.md), so
 * this is a thin fetch layer: selections out, parts back.
 */

export interface GuideSummary {
  guide_key: string;
  title: string;
  summary: string | null;
  /**
   * The card illustration, absolute, or null for a guide without one.
   *
   * A column on `guides`, not a field of the document and not a repo
   * asset: guides will be authored in the interface, and changing a
   * picture should not mean rewriting the document that says how to
   * build the thing. Nullable in earnest — a guide is authorable before
   * anyone has rendered it, and the file a URL names may not be
   * uploaded yet, so the card has to survive both.
   */
  hero_image: string | null;
}

/**
 * Why an answer is not on offer.
 *
 * `part` is the piece it would leave empty, and is always known.
 * `prompt` names the earlier question responsible, and is known only
 * when one answer is responsible on its own — two answers can be
 * jointly at fault with neither to blame.
 *
 * `question` is that question's key, and `prompt` its text. The engine
 * sets both together or neither (`_blame` in `resolve.py`), so they are
 * optional as a pair rather than independently. Nothing reads the key
 * today — it is what a "take me back to that question" affordance
 * would need, and it costs nothing to carry until then.
 */
export interface MissingReason {
  part: string;
  question?: string;
  prompt?: string;
}

interface GuideOption {
  key: string;
  title: string;
  blurb?: string;
  /** Phrases in the blurb to link, mapped to their URLs. */
  links?: Record<string, string>;
  image?: string;
  roles?: Record<string, unknown>;
}

export interface GuideStep {
  key: string;
  prompt: string;
  /** What to know before answering, shown above the options. */
  blurb?: string;
  links?: Record<string, string>;
  /**
   * Option keys with no match, which are not offered at all. Always
   * present: `resolve()` sets it on every step it returns, empty when
   * availability was not asked for.
   */
  unavailable: string[];
  /** Why each is missing, keyed by option. Always present. */
  because: Record<string, MissingReason>;
  /** The option recommended, and assumed until one is chosen. */
  recommended: string | null;
  options: GuideOption[];
  selected: string | null;
}

export interface GuideChoice {
  tag: string;
  title?: string;
  blurb?: string;
  /** How many pieces are behind it, when the answer was derived. */
  count?: number;
}

/**
 * One question that narrows the pieces without choosing a build method.
 *
 * Exactly one of `from_namespace`, `from_combination` and `on_tags` is
 * set: they are what the question is *asked from*, and the three are
 * mutually exclusive. That is enforced where the guide is loaded, by a
 * `oneOf` in `openforge/openapi/schemas/guide.yaml`, rather than in
 * this type — a refinement is only ever read back from an
 * already-validated response, never built here, so the three stay
 * independently optional instead of a union every consumer re-narrows.
 */
export interface GuideRefinement {
  key: string;
  role: string;
  prompt: string;
  from_namespace?: string;
  choices?: GuideChoice[];
  /** Roles this question does not reach, out of the ones `role` names. */
  except_roles?: string[];
  /**
   * Roles this question asks for a *different* tag than the answer.
   *
   * A towne wall stands on a wood base: the catalog has towne walls
   * and no towne base at all, so the guide substitutes the tag per
   * role. Without this the frontend cannot tell that a piece which
   * does not carry the answer's own tag may still be that answer.
   */
  substitute?: Record<string, Record<string, string>>;
  /** Set when the answers are whole tag combinations, not single tags. */
  from_combination?: string;
  /** True when the answer is a preference rather than a fit. */
  browsable?: boolean;
  /** Heading to file this question under, when it is not a main one. */
  group?: string;
  on_tags?: unknown;
  /**
   * Choice tags, or "on"/"off", with no match; not offered at all.
   * Always present, as on a step.
   */
  unavailable: string[];
  /** Why each is missing, keyed by answer. Always present. */
  because: Record<string, MissingReason>;
  /** The answer recommended, and assumed until one is chosen. */
  recommended: string | null;
  /** What to know before answering, as on a step. */
  blurb?: string;
  links?: Record<string, string>;
  selected: string | null;
}

export interface SpriteAngle {
  index: number;
  name: string;
}

interface GuideSpriteMetadata {
  grid_rows: number;
  grid_cols: number;
  tile_size: number;
  angles?: SpriteAngle[];
  default_angle?: number;
}

interface GuideImage {
  id: string;
  image_name: string;
  image_url: string;
  image_type: 'thumbnail' | 'documentation';
  sprite_metadata?: GuideSpriteMetadata | null;
}

export interface GuideBlueprint {
  id: string;
  blueprint_name: string;
  file_md5: string | null;
  storage_address: string | null;
  images?: GuideImage[];
  /** Plain pipe-delimited strings, attached by the resolve endpoint. */
  tags?: string[];
}

/**
 * The predicate terms the engine composes, as `PREDICATES` in
 * resolve.py names them. A closed union rather than a string index,
 * so a typo is a compile error instead of a silent `undefined`.
 */
type PredicateTerm =
  | 'require'
  | 'deny'
  | 'accept'
  | 'allow'
  | 'deny_children';

export interface GuidePart {
  role: string;
  title: string;
  under: string | null;
  /** The resolved predicate the part was found with. */
  query: Partial<Record<PredicateTerm, string[]>>;
  /**
   * Tags of `query` the dialog will let you take off, one at a time.
   * The merely-preferred ones, so browsing starts inside the family
   * you chose and leaving it is a deliberate click.
   */
  relaxable: string[];
  /** True when this part is the one the person picked, not the search's. */
  pinned: boolean;
  blueprint: GuideBlueprint | null;
}

/** The query key that pins a part to a role: `part.wall`. */
export function pinKey(role: string): string {
  return `${PIN}${role}`;
}

const PIN = 'part.';

export interface GuideDocument {
  key: string;
  title: string;
  summary?: string;
  steps: { key: string; prompt: string; options: GuideOption[] }[];
  refinements?: { key: string }[];
  roles: Record<string, unknown>;
}

export interface ResolvedGuide {
  steps: GuideStep[];
  parts: GuidePart[];
  refinements: GuideRefinement[];
}

export type Selections = Record<string, string>;

/** An error carrying the HTTP status that caused it. */
export interface HttpError extends Error {
  status: number;
}

/**
 * A failed response as an Error, with the status kept as a number.
 *
 * The message gets the status too, because HTTP/2 has no reason
 * phrase: over it `statusText` is the empty string, and the one error
 * the page shows rendered as "Failed to resolve: " with nothing after
 * it. But callers that need to *decide* something read `.status` —
 * telling "no such guide" from "not right now" by grepping a
 * human-readable sentence built in another module is a coupling
 * nothing holds in step.
 */
function failed(what: string, response: Response): HttpError {
  const said = response.statusText
    ? `${response.status} ${response.statusText}`
    : `${response.status}`;
  return Object.assign(new Error(`${what}: ${said}`), {
    status: response.status,
  });
}

export async function fetchGuides(): Promise<GuideSummary[]> {
  const response = await fetch('/api/guides');
  // An empty collection is a 404 here by house convention
  // (openforge/CLAUDE.md), not an error.
  if (response.status === 404) {
    return [];
  }
  if (!response.ok) {
    throw failed('Failed to fetch guides', response);
  }
  const body = await response.json();
  return body.guides;
}

/**
 * The whole document, not just its title.
 *
 * The page needs the keys it defines before it can resolve anything —
 * see `selectionKeys` — so fetching the title alone would mean asking
 * twice.
 */
export async function fetchGuide(guideKey: string): Promise<GuideDocument> {
  const response = await fetch(`/api/guides/${encodeURIComponent(guideKey)}`);
  if (!response.ok) {
    throw failed('Failed to fetch guide', response);
  }
  const body = await response.json();
  return body.document;
}

/**
 * Every query key this guide answers to.
 *
 * The API refuses a key it does not recognise, so the page builds its
 * request from these rather than forwarding the browser's query string.
 * A shared link that has been through Facebook or a campaign tracker
 * arrives carrying `fbclid` or `utm_source`, and forwarding it would
 * answer 400 and show the person an error instead of their build.
 *
 * The API stays strict on purpose — ignoring unknown keys there would
 * let a typo'd selection resolve silently against the wrong state — so
 * the filtering belongs here, where the guide's own vocabulary is known.
 */
export function selectionKeys(document: GuideDocument): Set<string> {
  return new Set([
    ...document.steps.map((step) => step.key),
    ...(document.refinements ?? []).map((refinement) => refinement.key),
    // A pin names a role rather than a question — `part.wall` — and
    // is as much a part of a shared link as any answer is.
    ...Object.keys(document.roles ?? {}).map(pinKey),
  ]);
}

/**
 * Resolve selections into parts.
 *
 * A GET, because resolving is a pure function of the key and the
 * selections and the selections are already a query string — that is
 * what the shareable URL is. A 400 means they describe a state this
 * guide cannot be in, most likely a stale shared link, so the message is
 * worth showing rather than swallowing.
 */
export async function resolveGuide(
  guideKey: string,
  selections: Selections
): Promise<ResolvedGuide> {
  const query = new URLSearchParams(selections).toString();
  const path = `/api/guides/${encodeURIComponent(guideKey)}/resolve`;
  const response = await fetch(query ? `${path}?${query}` : path);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw body.error
      ? Object.assign(new Error(body.error), { status: response.status })
      : failed('Failed to resolve', response);
  }
  return response.json();
}

/**
 * The picture to show for a part.
 *
 * Explicitly the thumbnail rather than the first image: a blueprint can
 * carry documentation images too, and `images[0]` would show whichever
 * the query happened to order first. This mirrors
 * `_get_blueprint_thumbnail` in `openforge/app/routes/blueprints.py`,
 * which is the backend's version of the same choice.
 */
export function thumbnailOf(
  blueprint: GuideBlueprint | null
): GuideImage | null {
  return (
    blueprint?.images?.find((image) => image.image_type === 'thumbnail') ?? null
  );
}

/** What is not on offer, and why, by question; and how many each part has. */
export interface Availability {
  unavailable: Record<string, string[]>;
  because: Record<string, Record<string, MissingReason>>;
  /** Matching pieces per role. One means the guide decided; more is a choice. */
  options: Record<string, number>;
}

/**
 * Which offered answers would leave a part with nothing.
 *
 * Its own request because it costs several times what the parts cost:
 * the engine re-composes every role for every answer on offer. The
 * page draws on `resolveGuide` and drops the dead answers when this
 * lands, so nobody waits on it.
 */
export async function fetchAvailability(
  guideKey: string,
  selections: Selections
): Promise<Availability> {
  const query = new URLSearchParams(selections).toString();
  const response = await fetch(
    `/api/guides/${encodeURIComponent(guideKey)}/availability${
      query ? `?${query}` : ''
    }`
  );
  if (!response.ok) {
    throw failed('Failed to fetch availability', response);
  }
  const body = await response.json();
  return {
    unavailable: body.unavailable ?? {},
    because: body.because ?? {},
    options: body.options ?? {},
  };
}

/**
 * The answers a hand-picked part settles.
 *
 * Picking a rough stone wall out of the catalog while the texture
 * question says dungeon stone leaves the page contradicting itself:
 * the piece on screen is rough stone and the answer beside it is not.
 * So the questions that piece *answers* are reset to what it is.
 *
 * Only the browsable ones. The rest were never relaxed in the dialog,
 * so whatever was picked already agrees with them, and a question the
 * dialog would not let you cross has no business being rewritten by
 * it.
 *
 * A question the piece answers with nothing is cleared rather than
 * left: a wall with no peg tag is an answer of "no" to pegs, and
 * leaving "yes" there would be the same contradiction pointing the
 * other way.
 */
export function impliedBy(
  // Only the tags: the catalog's own Blueprint type and the guide's
  // differ in what else they carry, and this reads neither.
  blueprint: { tags?: string[] },
  role: string,
  refinements: GuideRefinement[]
): Record<string, string | null> {
  const carried = new Set(blueprint.tags ?? []);
  const changes: Record<string, string | null> = {};
  for (const refinement of refinements) {
    if (!refinement.browsable || !reaches(refinement, role)) continue;
    const answer = answeredBy(refinement, role, carried);
    if (answer !== refinement.selected) changes[refinement.key] = answer;
  }
  return changes;
}

/**
 * Which of a question's answers this piece is, or null for none.
 *
 * Two things make this more than a lookup. A role may have been asked
 * for a substituted tag — a towne wall stands on a `texture|wood`
 * base — so the tag to look for is the substitution where there is
 * one, not the answer's own. And a combination answer is a *set*, so
 * the piece has to carry all of it; where several match, the most
 * specific wins, because a topless base carries plain OpenLOCK too
 * and reporting the plain one would then deny the topless tag it
 * actually has.
 */
function answeredBy(
  refinement: GuideRefinement,
  role: string,
  carried: Set<string>
): string | null {
  const matched = (refinement.choices ?? []).filter((choice) => {
    const substituted = refinement.substitute?.[choice.tag]?.[role];
    const wanted = substituted ? [substituted] : choice.tag.split(',');
    return wanted.every((tag) => carried.has(tag));
  });
  if (matched.length === 0) return null;
  // The answer already given wins when it is one of the matches.
  // Substitution is many-to-one — a stone brick facade and a mortar
  // and stone wall both stand on a `texture|foundation` base — so the
  // reverse lookup is genuinely ambiguous, and a piece that satisfies
  // the current answer is no evidence for any other. Without this,
  // pinning a foundation base under a stone brick wall reported
  // mortar and stone and changed the wall to match.
  if (matched.some((choice) => choice.tag === refinement.selected)) {
    return refinement.selected;
  }
  // Otherwise most tags first. A subset and its superset both match
  // the piece carrying the superset, and only the superset describes
  // it.
  matched.sort((a, b) => b.tag.split(',').length - a.tag.split(',').length);
  return matched[0].tag;
}

/**
 * The hand-picked parts, their blueprint names by role, and which roles
 * a question on screen admits.
 *
 * A pin just released is gone from here a round trip before the
 * resolution stops reporting it.
 */
export function admissions(
  resolved: ResolvedGuide | null,
  selections: Selections | null,
  unavailable?: Record<string, string[]> | null
): {
  pinned: GuidePart[];
  pinnedByRole: Record<string, string>;
  admitted: string[];
  roles: Record<string, string>;
} {
  const pinned = (resolved?.parts ?? []).filter(
    (part): part is GuidePart & { blueprint: GuideBlueprint } =>
      part.pinned &&
      part.blueprint !== null &&
      (!selections || pinKey(part.role) in selections)
  );
  const asked = askedOf(resolved?.refinements ?? [], unavailable);
  return {
    pinned,
    // Every role this build has a part for, which is the set the pinned
    // ones are drawn from.
    roles: Object.fromEntries(
      (resolved?.parts ?? []).map((part) => [part.role, part.title])
    ),
    // Named by the blueprint: the title is only the role.
    pinnedByRole: Object.fromEntries(
      pinned.map((part) => [part.role, part.blueprint.blueprint_name])
    ),
    admitted: pinned
      .map((part) => part.role)
      .filter((role) => asked.some((r) => reaches(r, role))),
  };
}

/** The answers this question cannot offer, freshest source first. */
export function deadAnswers(
  question: GuideStep | GuideRefinement,
  unavailable?: Record<string, string[]> | null
): string[] {
  // The type says always present; a step from the wire may not be.
  return unavailable?.[question.key] ?? question.unavailable ?? [];
}

/** The questions put to the person: a toggle whose yes is dead is not one. */
export function askedOf(
  refinements: GuideRefinement[],
  unavailable?: Record<string, string[]> | null
): GuideRefinement[] {
  return refinements.filter(
    (refinement) =>
      !refinement.on_tags ||
      refinement.selected !== null ||
      !deadAnswers(refinement, unavailable).includes('on')
  );
}

/** Does this question apply to that role? Same test the engine makes. */
export function reaches(refinement: GuideRefinement, role: string): boolean {
  if (refinement.role !== '*' && refinement.role !== role) return false;
  return !(refinement.except_roles ?? []).includes(role);
}

/**
 * The pins an answer invalidates.
 *
 * A pinned part outranks the questions — that is what pinning is — so
 * without this, going back and answering one of them does nothing
 * visible and the page looks broken. Answering a question is the
 * plainest possible statement that you want the guide to decide that
 * part again, so the pins it reaches are let go.
 *
 * Only the parts the question actually reaches. Changing the floor
 * texture has no business dropping a wall somebody chose by hand.
 */
export function releasedBy(
  question: GuideStep | GuideRefinement,
  pinnedRoles: string[]
): Record<string, null> {
  return Object.fromEntries(
    pinnedRoles
      .filter((role) => narrows(question, role))
      .map((role) => [pinKey(role), null])
  );
}

/**
 * Does this question narrow that role?
 *
 * A refinement says so directly, and `reaches` is the same test the
 * engine makes. A step says it per option: one predicate per role,
 * and an option with no roles of its own — "how wide?" — narrows
 * whatever the earlier answers put in play, which is every role.
 */
export function narrows(question: GuideStep | GuideRefinement, role: string): boolean {
  if (!('options' in question)) return reaches(question, role);
  return question.options.some(
    (option) => !option.roles || role in option.roles
  );
}
