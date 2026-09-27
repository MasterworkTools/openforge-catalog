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
}

/**
 * Why an answer is not on offer.
 *
 * `part` is the piece it would leave empty, and is always known.
 * `prompt` names the earlier question responsible, and is known only
 * when one answer is responsible on its own — two answers can be
 * jointly at fault with neither to blame.
 */
export interface MissingReason {
  part: string;
  question?: string;
  prompt?: string;
}

export interface GuideOption {
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
  /** Option keys with no match, which are not offered at all. */
  unavailable?: string[];
  /** Why each is missing, keyed by option. */
  because?: Record<string, MissingReason>;
  /** The option recommended, and assumed until one is chosen. */
  recommended?: string | null;
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

export interface GuideRefinement {
  key: string;
  role: string;
  prompt: string;
  from_namespace?: string;
  choices?: GuideChoice[];
  /** Roles this question does not reach, out of the ones `role` names. */
  except_roles?: string[];
  /** True when the answer is a preference rather than a fit. */
  browsable?: boolean;
  /** Heading to file this question under, when it is not a main one. */
  group?: string;
  on_tags?: unknown;
  /** Choice tags, or "on"/"off", with no match; not offered at all. */
  unavailable?: string[];
  /** Why each is missing, keyed by answer. */
  because?: Record<string, MissingReason>;
  /** The answer recommended, and assumed until one is chosen. */
  recommended?: string | null;
  /** What to know before answering, as on a step. */
  blurb?: string;
  links?: Record<string, string>;
  selected: string | null;
}

export interface SpriteAngle {
  index: number;
  name: string;
}

export interface GuideSpriteMetadata {
  grid_rows: number;
  grid_cols: number;
  tile_size: number;
  angles?: SpriteAngle[];
  default_angle?: number;
}

export interface GuideImage {
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

export interface GuidePart {
  role: string;
  title: string;
  under: string | null;
  /** The resolved predicate: require, deny, accept, allow, deny_children. */
  query: Partial<Record<string, string[]>>;
  /**
   * The same predicate with the merely-preferred answers taken out,
   * for opening the catalog on this part: narrow enough that what you
   * find still fits the build, wide enough to be worth browsing.
   */
  browse: Partial<Record<string, string[]>>;
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

export async function fetchGuides(): Promise<GuideSummary[]> {
  const response = await fetch('/api/guides');
  // An empty collection is a 404 here by house convention
  // (openforge/CLAUDE.md), not an error.
  if (response.status === 404) {
    return [];
  }
  if (!response.ok) {
    throw new Error(`Failed to fetch guides: ${response.statusText}`);
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
    throw new Error(`Failed to fetch guide: ${response.statusText}`);
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
    throw new Error(body.error || `Failed to resolve: ${response.statusText}`);
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
    throw new Error(`Failed to fetch availability: ${response.statusText}`);
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
 * Only the browsable ones. The rest were not relaxed for the browse
 * in the first place, so whatever was picked already agrees with
 * them, and a question the dialog would not let you cross has no
 * business being rewritten by it.
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
    // A combination answer is several tags at once, joined — it is
    // that combination or it is not, so every part has to be there.
    const answer =
      refinement.choices?.find((choice) =>
        choice.tag.split(',').every((tag) => carried.has(tag))
      )?.tag ?? null;
    if (answer !== refinement.selected) changes[refinement.key] = answer;
  }
  return changes;
}

/** Does this question apply to that role? Same test the engine makes. */
function reaches(refinement: GuideRefinement, role: string): boolean {
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
