# react-hooks-reviewer

Review React code (`src/**/*.tsx`, hook files in `src/**/*.ts`) for **hook correctness and render performance**. Hooks bugs are the SPA's equivalent of concurrency bugs: they compile clean, pass type-check, work in the happy path, and fail as stale UI, phantom re-renders, or memory leaks. The catalog renders large collections (1,400+ designs, sprite sheets, tag trees), so render performance is a correctness concern, not a nicety.

**Patterns to FLAG:**

1. **Missing or wrong dependency arrays (P2):**

   ```tsx
   // BAD — stale closure: filter changes but effect never re-runs
   useEffect(() => {
     fetchBlueprints(filter).then(setResults);
   }, []);
   ```

   Every value from component scope used inside the effect/callback belongs in the deps array. Flag deps arrays that omit used values, and `// eslint-disable-next-line react-hooks/exhaustive-deps` without a comment explaining why the omission is safe.

2. **Missing effect cleanup (P2):** subscriptions, event listeners (`window.addEventListener`), timers (`setInterval`/`setTimeout`), and observers (`IntersectionObserver`, `ResizeObserver`) registered in an effect must be released in the cleanup function. A sprite viewer that adds a keydown listener per mount and never removes it leaks a listener per navigation.

3. **State updates after unmount / unaborted fetches (P2):**

   ```tsx
   // BAD — setState fires after unmount if navigation happens mid-fetch
   useEffect(() => {
     fetch(`/api/blueprints/${id}`).then(r => r.json()).then(setData);
   }, [id]);

   // GOOD — abort on cleanup
   useEffect(() => {
     const ctrl = new AbortController();
     fetch(`/api/blueprints/${id}`, { signal: ctrl.signal })
       .then(r => r.json()).then(setData)
       .catch(e => { if (e.name !== "AbortError") throw e; });
     return () => ctrl.abort();
   }, [id]);
   ```

   Also the race variant: two rapid `id` changes resolve out of order and the stale response wins. Abort or a staleness guard fixes both.

4. **Conditional hooks (P1):** hooks called inside `if`/loops/early-return paths violate the Rules of Hooks and corrupt hook state across renders. ESLint usually catches this; flag it if the disable comment shows up instead.

5. **Derived state stored in state (P3):** `useState` + `useEffect` to keep a computed value in sync with props/state. Compute during render, or `useMemo` if expensive. (Shared with `frontend-conventions-reviewer` — post under whichever found it first.)

6. **Unstable references re-triggering children (P3 — P2 in list-rendering paths):** new object/array/function literals passed as props to memoized children or used as effect deps (`style={{...}}`, `onSelect={() => ...}` into a 1,400-row list). Flag when the receiver is memoized, is an effect dep, or renders in a large list; don't flag for cheap leaf components.

7. **Expensive list rendering without keys/memo (P2):** catalog-scale lists (blueprints, tags, files) rendered without stable `key`s (or keyed by array index while reorderable/filterable), or re-mapped with heavy per-item computation each render without `useMemo`. Suggest virtualization only when the list is genuinely unbounded — match existing patterns in `src/` first.

8. **`useEffect` as a data-flow bus (P3):** chains where effect A sets state that triggers effect B that sets more state. Usually one event handler or one derived computation. Flag chains ≥ 2 hops.

9. **Custom hooks that break the contract (P2):** hooks that conditionally call other hooks, return unstable identities every render (fresh callbacks/objects without `useCallback`/`useMemo`) while documented as stable, or hide required cleanup from the consumer.

**Do NOT flag:**

- Intentionally-empty deps (`[]`) for genuinely mount-only effects with cleanup, when nothing from component scope is used inside.
- Unstable props into cheap unmemoized leaves — memoizing everything is its own disease.
- Existing patterns in `src/` that already work — match the codebase's conventions (this repo delegates event handling to custom hooks per CLAUDE.md; recommend that shape).

**Review approach:**

1. For each `useEffect`/`useCallback`/`useMemo` in the diff: deps complete? cleanup present when it registers anything? disable-comments justified?
2. For each fetch-in-effect: abort/staleness handling on param change and unmount?
3. For each list render: stable keys, per-item cost, memo boundaries.
4. For each new custom hook: stable return identity, cleanup ownership, no conditional hooks.
