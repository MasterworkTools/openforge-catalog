import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from 'react';
import {
  GuideDocument,
  ResolvedGuide,
  Selections,
  fetchGuide,
  resolveGuide,
  selectionKeys,
} from '@/services/guide-service';

/**
 * Holds a guide's selections, keeps them in the query string, and asks
 * the backend to resolve them into parts.
 *
 * The query string is not a copy of the state, it *is* the state:
 * `?guide=wall&method=s2w` is a shareable link to a specific wall, and
 * everything here derives from it. Keeping a second copy in React state
 * is what made the first version of this hook leak one guide's answers
 * into the next: the selections were never keyed to the guide, so
 * moving from `?guide=wall&method=s2w` to `?guide=floor` asked the
 * floor guide about a method it has never heard of, got the 400 the
 * strict API owes it, and no further input could clear it.
 *
 * The main page's URL hooks strip parameters after load; this page
 * deliberately does not.
 *
 * The document is fetched first because the API refuses a query key it
 * does not recognise, so the page has to know the guide's vocabulary
 * before it can ask anything — see `selectionKeys`.
 */
export function useGuideState(guideKey: string | null | undefined) {
  const { guide, guideError } = useGuideDocument(guideKey);
  const search = useSearch();
  const [resolved, setResolved] = useState<ResolvedGuide | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Only the parameters this guide defines. Everything else in the URL
  // — `fbclid`, `utm_source`, another guide's leftover answers — is
  // dropped rather than forwarded, because the API answers 400 to a key
  // it does not know.
  const selections = useMemo(
    () => (guide ? ownedBy(guide, search) : null),
    [guide, search]
  );

  useEffect(() => {
    // `guide` lags `guideKey` by a fetch, so for one tick after the key
    // changes the document in hand is still the previous guide's. Its
    // vocabulary is what filters the selections, so resolving here
    // would ask the new guide about the old one's answers — the exact
    // 400 this hook exists to prevent, arriving from the other side.
    if (!guideKey || selections === null || guide?.key !== guideKey) return;
    let current = true;
    resolveGuide(guideKey, selections)
      .then((result) => {
        if (!current) return;
        setResolved(result);
        setError(null);
      })
      .catch((e: Error) => {
        if (!current) return;
        console.error('Error resolving guide:', e);
        setError(e.message);
      });
    return () => {
      current = false;
    };
  }, [guideKey, selections, guide?.key]);

  const select = useCallback(
    (key: string, value: string | null) => {
      const next = { ...(selections ?? {}) };
      if (value === null) {
        delete next[key];
      } else {
        next[key] = value;
      }
      writeUrl(guideKey ?? null, next);
    },
    [guideKey, selections]
  );

  return { guide, resolved, error: error ?? guideError, select };
}

function useGuideDocument(guideKey: string | null | undefined) {
  const [guide, setGuide] = useState<GuideDocument | null>(null);
  const [guideError, setGuideError] = useState<string | null>(null);

  useEffect(() => {
    if (!guideKey) return;
    let current = true;
    fetchGuide(guideKey)
      .then((result) => {
        if (!current) return;
        setGuide(result);
        setGuideError(null);
      })
      .catch((e: Error) => {
        if (!current) return;
        // Without this the page renders its heading and nothing else,
        // so a dead `?guide=` link looks like a page that failed rather
        // than a guide that is not there.
        console.error('Error fetching guide:', e);
        setGuideError(`No guide called '${guideKey}'.`);
      });
    return () => {
      current = false;
    };
  }, [guideKey]);

  return { guide, guideError };
}

/**
 * The query string, as a value that changes when it changes.
 *
 * Read through useSyncExternalStore rather than an effect: the page is
 * statically exported, so the prerendered HTML cannot know the query
 * string, and this is the hook React provides for exactly that. The
 * snapshot is the raw string, so `Object.is` compares it cheaply and
 * parsing happens above.
 *
 * `undefined` before hydration means "not known yet", which is a
 * different thing from a URL with no guide in it. Without that
 * distinction the first client render shows the guide list, and every
 * view of a guide fetches `/api/guides` it will never display.
 */
function useSearch(): string | undefined {
  return useSyncExternalStore(
    subscribeToUrl,
    () => window.location.search,
    () => undefined
  );
}

export function useGuideKey(): string | null | undefined {
  const search = useSearch();
  return useMemo(
    () =>
      search === undefined
        ? undefined
        : new URLSearchParams(search).get('guide'),
    [search]
  );
}

/**
 * Our own event, not `popstate`.
 *
 * `replaceState` fires nothing, so answering a question has to
 * announce itself or `useSyncExternalStore` never re-reads the URL.
 * Announcing it as `popstate` would be a lie with a consequence: the
 * part-selection modal mounts BlueprintContainer, which listens for
 * `popstate` and calls `location.reload()` when it fires with a
 * blueprint selected and no blueprint_id in the URL. Every click on a
 * guide option with that modal open would reload the page.
 *
 * Real back/forward still has to be heard, so both are subscribed.
 */
const URL_CHANGED = 'guide-url-changed';

function subscribeToUrl(onChange: () => void) {
  window.addEventListener('popstate', onChange);
  window.addEventListener(URL_CHANGED, onChange);
  return () => {
    window.removeEventListener('popstate', onChange);
    window.removeEventListener(URL_CHANGED, onChange);
  };
}

/**
 * The query parameters this guide actually defines.
 *
 * A link shared through Facebook or a mail campaign carries `fbclid` or
 * `utm_source`, and someone moving between guides carries the previous
 * guide's answers. Neither belongs in the request.
 */
function ownedBy(guide: GuideDocument, search: string | undefined): Selections {
  const known = selectionKeys(guide);
  const selections: Selections = {};
  new URLSearchParams(search ?? '').forEach((value, key) => {
    if (known.has(key)) {
      selections[key] = value;
    }
  });
  return selections;
}

/**
 * Write the selections to the URL, and tell the store we did.
 *
 * `replaceState` does not fire `popstate` — that event is for someone
 * moving through history, not for us writing to it — so a store reading
 * `window.location.search` would not see our own write. Dispatching it
 * here is what lets the URL be the single source of truth rather than
 * one of two copies that can disagree.
 */
function writeUrl(guideKey: string | null, selections: Selections) {
  if (typeof window === 'undefined' || !guideKey) return;
  const params = new URLSearchParams({ guide: guideKey, ...selections });
  window.history.replaceState(
    {},
    '',
    `${window.location.pathname}?${params.toString()}`
  );
  window.dispatchEvent(new Event(URL_CHANGED));
}
