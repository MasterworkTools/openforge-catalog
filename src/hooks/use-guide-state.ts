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
 * The query string is the whole state: `?guide=wall&method=s2w` is a
 * shareable link to a specific wall. The main page's URL hooks strip
 * parameters after load; this page deliberately does not.
 *
 * The document is fetched first because the API refuses a query key it
 * does not recognise, so the page has to know the guide's vocabulary
 * before it can ask anything — see `selectionKeys`.
 */
export function useGuideState(guideKey: string | null) {
  const document = useGuideDocument(guideKey);
  // The arrival URL, captured once. The same trick the environment
  // banner uses: reading `window.location` during a later render would
  // see a URL this page has since rewritten.
  const [arrived] = useState(readUrlParams);
  const [chosen, setChosen] = useState<Selections | null>(null);
  const [resolved, setResolved] = useState<ResolvedGuide | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Derived rather than seeded in an effect: until the document says
  // which keys are ours, there is no answer, and once it does the
  // answer is a function of what arrived.
  const selections = useMemo(() => {
    if (chosen) return chosen;
    if (!document) return null;
    return ownedBy(document, arrived);
  }, [chosen, document, arrived]);

  useEffect(() => {
    if (!guideKey || selections === null) return;
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
  }, [guideKey, selections]);

  const select = useCallback(
    (key: string, value: string | null) => {
      const next = { ...(selections ?? {}) };
      if (value === null) {
        delete next[key];
      } else {
        next[key] = value;
      }
      writeUrl(guideKey, next);
      setChosen(next);
    },
    [guideKey, selections]
  );

  return { document, selections: selections ?? {}, resolved, error, select };
}

function useGuideDocument(guideKey: string | null) {
  const [document, setDocument] = useState<GuideDocument | null>(null);

  useEffect(() => {
    if (!guideKey) return;
    let current = true;
    fetchGuide(guideKey)
      .then((result) => {
        if (current) setDocument(result);
      })
      .catch((e) => console.error('Error fetching guide:', e));
    return () => {
      current = false;
    };
  }, [guideKey]);

  return document;
}

/**
 * Which guide the URL is asking for.
 *
 * Read through useSyncExternalStore rather than an effect: the page is
 * statically exported, so the prerendered HTML cannot know the query
 * string, and this is the hook React provides for exactly that — server
 * snapshot first, client snapshot on hydration, with `popstate` for the
 * back button.
 */
export function useGuideKey(): string | null {
  return useSyncExternalStore(
    subscribeToUrl,
    () => new URLSearchParams(window.location.search).get('guide'),
    () => null
  );
}

function subscribeToUrl(onChange: () => void) {
  window.addEventListener('popstate', onChange);
  return () => window.removeEventListener('popstate', onChange);
}

function readUrlParams(): Selections {
  if (typeof window === 'undefined') return {};
  const params: Selections = {};
  new URLSearchParams(window.location.search).forEach((value, key) => {
    params[key] = value;
  });
  return params;
}

/**
 * The arrived parameters this guide actually defines.
 *
 * Anything else is dropped rather than forwarded: a link that has been
 * shared through Facebook or a mail campaign carries `fbclid` or
 * `utm_source`, and the API answers 400 to a key it does not know.
 * Dropping them here is what keeps a shared link working.
 */
function ownedBy(document: GuideDocument, params: Selections): Selections {
  const known = selectionKeys(document);
  return Object.fromEntries(
    Object.entries(params).filter(([key]) => known.has(key))
  );
}

function writeUrl(guideKey: string | null, selections: Selections) {
  if (typeof window === 'undefined' || !guideKey) return;
  const params = new URLSearchParams({ guide: guideKey, ...selections });
  window.history.replaceState(
    {},
    '',
    `${window.location.pathname}?${params.toString()}`
  );
}
