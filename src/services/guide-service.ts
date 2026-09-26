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
  /** Option keys that would empty a part, for greying out. */
  unavailable?: string[];
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
  /** Heading to file this question under, when it is not a main one. */
  group?: string;
  on_tags?: unknown;
  /** Choice tags, or "on"/"off", that would empty a part. */
  unavailable?: string[];
  /** The answer recommended, and assumed until one is chosen. */
  recommended?: string | null;
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
  blueprint: GuideBlueprint | null;
}

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


/**
 * Which offered answers would leave a part with nothing.
 *
 * Its own request because it costs several times what the parts cost:
 * the engine re-composes every role for every answer on offer. The
 * page draws on `resolveGuide` and greys the buttons when this lands,
 * so nobody waits on it.
 */
export async function fetchAvailability(
  guideKey: string,
  selections: Selections
): Promise<Record<string, string[]>> {
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
  return body.unavailable ?? {};
}
