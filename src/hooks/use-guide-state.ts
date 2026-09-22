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
  // Stamped with its key for the same reason the document is: an
  // answer that arrives for the guide you have just left is not this
  // guide's answer, and showing it means one guide's title over
  // another's parts, with a working Download button under them.
  const [answer, setAnswer] = useState<ResolvedAnswer | null>(null);
  const mine = answer && answer.key === guideKey ? answer : null;

  // Only the parameters this guide defines. Everything else in the URL
  // — `fbclid`, `utm_source`, another guide's leftover answers — is
  // dropped rather than forwarded, because the API answers 400 to a key
  // it does not know.
  const selections = useMemo(
    () => (guide ? ownedBy(guide, search) : null),
    [guide, search]
  );

  useEffect(() => {
    // `selections === null` is also the lag guard: it is derived from
    // `guide`, which `useGuideDocument` withholds until the document
    // in hand is this key's. So there is no tick where the new guide
    // is asked about the old one's answers.
    if (!guideKey || selections === null) return;
    let current = true;
    resolveGuide(guideKey, selections)
      .then((result) => {
        if (!current) return;
        setAnswer({ key: guideKey, resolved: result, error: null });
      })
      .catch((e: Error) => {
        if (!current) return;
        console.error('Error resolving guide:', e);
        setAnswer({ key: guideKey, resolved: null, error: e.message });
      });
    return () => {
      current = false;
    };
  }, [guideKey, selections]);

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

  return {
    guide,
    resolved: mine?.resolved ?? null,
    error: mine?.error ?? guideError,
    select,
  };
}

interface ResolvedAnswer {
  key: string;
  resolved: ResolvedGuide | null;
  error: string | null;
}

/**
 * The guide document, and only ever the one this key asked for.
 *
 * State is stamped with the key it was fetched for, because a fetch
 * takes a tick and the key can change inside it. Handing back a
 * document under a key it does not belong to is what let the page
 * paint one guide's title over another guide's questions.
 */
function useGuideDocument(guideKey: string | null | undefined) {
  const [fetched, setFetched] = useState<FetchedDocument | null>(null);

  useEffect(() => {
    if (!guideKey) return;
    let current = true;
    fetchGuide(guideKey)
      .then((result) => {
        if (!current) return;
        setFetched({ key: guideKey, guide: result, error: null });
      })
      .catch((e: Error) => {
        if (!current) return;
        // Without this the page renders its heading and nothing else,
        // so a dead `?guide=` link looks like a page that failed rather
        // than a guide that is not there.
        console.error('Error fetching guide:', e);
        setFetched({
          key: guideKey,
          guide: null,
          error: `No guide called '${guideKey}'.`,
        });
      });
    return () => {
      current = false;
    };
  }, [guideKey]);

  const mine = fetched && fetched.key === guideKey ? fetched : null;
  return { guide: mine?.guide ?? null, guideError: mine?.error ?? null };
}

interface FetchedDocument {
  key: string;
  guide: GuideDocument | null;
  error: string | null;
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
 * `replaceState` fires nothing — `popstate` is for someone moving
 * through history, not for us writing to it — so a store reading
 * `window.location.search` would not see our own write. Announcing it
 * on our own event is what lets the URL be the single source of truth
 * rather than one of two copies that can disagree. Why our own and not
 * `popstate`: see `URL_CHANGED` below.
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
