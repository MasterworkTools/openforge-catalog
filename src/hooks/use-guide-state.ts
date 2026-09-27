import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from 'react';
import {
  GuideDocument,
  HttpError,
  ResolvedGuide,
  Selections,
  fetchGuide,
  resolveGuide,
  selectionKeys,
  Availability,
  fetchAvailability,
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
  // Which answers would empty a part. Separate from the resolution
  // because it arrives later: the buttons are all usable the whole
  // time, and the ones that lead nowhere go away once this lands.
  //
  // Keyed by the *selections* as well as the guide, not just the
  // guide. This started out greying buttons, where a stale payload
  // was merely late; it now hides answers outright and drives the
  // "N options" bar, so applying one answer's dead-set to the next
  // answer's resolution removes options that are really there.
  //
  // Matched against the resolution's selections, not the URL's. The
  // page draws the dead-set over `mine.resolved`, and that is allowed
  // to lag — a failed resolve deliberately keeps the last good one —
  // so comparing against the URL let the *new* dead-set land on the
  // *old* parts. With a resolve error that pairing is not a flicker,
  // it stays.
  const [dead, setDead] = useState<DeadAnswers | null>(null);

  // Only the parameters this guide defines. Everything else in the URL
  // — `fbclid`, `utm_source`, another guide's leftover answers — is
  // dropped rather than forwarded, because the API answers 400 to a key
  // it does not know.
  const selections = useMemo(
    () => (guide ? ownedBy(guide, search) : null),
    [guide, search]
  );
  // The identity of a selection map, for deciding whether availability
  // describes the answers now on screen. Sorted, because the URL's key
  // order is not meaningful and two orderings are the same state.
  const asked = useMemo(
    () =>
      selections === null
        ? null
        : JSON.stringify(Object.entries(selections).sort()),
    [selections]
  );
  const myDead =
    dead && mine && dead.key === guideKey && dead.asked === mine.asked
      ? dead
      : null;

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
        setAnswer({
          key: guideKey,
          asked,
          resolved: result,
          error: null,
          status: null,
        });
      })
      .catch((e: Error) => {
        if (!current) return;
        console.error('Error resolving guide:', e);
        // Keep the last good resolution alongside the error. The page
        // renders its whole body behind `resolved`, and the selections
        // live only in the URL — so dropping it leaves a heading, a red
        // line, and no control on screen that can change the state that
        // caused the failure. A stale shared link would be a dead end,
        // and so would one dropped connection on an ordinary click.
        setAnswer((prev) => {
          const kept = prev?.key === guideKey ? prev : null;
          return {
            key: guideKey,
            // The selections the *kept* parts answer, so a dead-set
            // for the new ones is not applied to them.
            asked: kept?.asked ?? asked,
            resolved: kept?.resolved ?? null,
            error: e.message,
            status: (e as Partial<HttpError>).status ?? null,
          };
        });
      });
    return () => {
      current = false;
    };
    // `asked` is derived from `selections`, so it adds no re-runs; it
    // is here because the effect stamps it onto the resolution.
  }, [guideKey, selections, asked]);

  // Its own effect, and deliberately not awaited by the one above: a
  // second of narrowing the answers must not hold up the parts.
  useEffect(() => {
    if (!guideKey || selections === null) return;
    let current = true;
    fetchAvailability(guideKey, selections)
      .then((result) => {
        if (current) setDead({ key: guideKey, asked, ...result });
      })
      .catch((e: Error) => {
        // Nothing to show the person: dropping dead answers is an
        // improvement on a working page, not a part of it. Every
        // answer stays on offer and tells them the honest "nothing
        // matches" instead.
        if (current) console.error('Error fetching availability:', e);
      });
    return () => {
      current = false;
    };
  }, [guideKey, selections, asked]);

  // Several answers at once, because some changes are not one answer.
  // Picking a part by hand settles the questions that part answers,
  // and `select`-ing them one after another would not work: each call
  // reads the selections this render closed over, so the second would
  // be written on top of a map that never saw the first.
  const selectAll = useCallback(
    (changes: Record<string, string | null>) => {
      const next = { ...(selections ?? {}) };
      for (const [key, value] of Object.entries(changes)) {
        if (value === null) {
          delete next[key];
        } else {
          next[key] = value;
        }
      }
      writeUrl(guideKey ?? null, next);
    },
    [guideKey, selections]
  );

  const select = useCallback(
    (key: string, value: string | null) => selectAll({ [key]: value }),
    [selectAll]
  );

  return {
    guide,
    resolved: mine?.resolved ?? null,
    unavailable: myDead?.unavailable ?? null,
    because: myDead?.because ?? null,
    options: myDead?.options ?? null,
    error: mine?.error ?? guideError,
    // Which failure it was, so the page can offer a way out that has
    // some chance of working.
    status: mine?.status ?? null,
    select,
    selectAll,
  };
}

interface DeadAnswers extends Availability {
  key: string;
  /** The selections this describes, so a stale one is not applied. */
  asked: string | null;
}

interface ResolvedAnswer {
  key: string;
  /** The selections these parts answer — see `myDead`. */
  asked: string | null;
  resolved: ResolvedGuide | null;
  error: string | null;
  /**
   * The status behind `error`, when there was one.
   *
   * The page needs it to choose a way out: dropping the selections
   * fixes a 400 about them, and cannot fix a 500 about the stored
   * document — where sending the same request again is the one thing
   * guaranteed not to work.
   */
  status: number | null;
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
        //
        // Only a 404 means the guide is not there, though. A 500 or a
        // dropped connection told the person their guide did not
        // exist, which sends them off to check a URL that was fine.
        console.error('Error fetching guide:', e);
        setFetched({
          key: guideKey,
          guide: null,
          error: missing(e)
            ? `No guide called '${guideKey}'.`
            : `Could not load '${guideKey}': ${e.message}`,
        });
      });
    return () => {
      current = false;
    };
  }, [guideKey]);

  const mine = fetched && fetched.key === guideKey ? fetched : null;
  return { guide: mine?.guide ?? null, guideError: mine?.error ?? null };
}

/** Did this failure mean "no such guide", or merely "not right now"? */
function missing(e: Error): boolean {
  // The status, not the sentence. This used to grep the message that
  // `guide-service` formats, which is a coupling across a module
  // boundary with nothing holding the two ends in step — and the
  // `/not found/i` arm it also carried could never match anything the
  // 404 test had not already caught.
  return (e as Partial<HttpError>).status === 404;
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
