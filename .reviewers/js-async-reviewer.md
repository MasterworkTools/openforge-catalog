# js-async-reviewer

Review TypeScript/JavaScript (`src/**/*.ts`, `src/**/*.tsx`) for **async and promise correctness** — the JS counterpart of `error-handling-reviewer`. Promise bugs fail silently: an unawaited rejection disappears into the console (or nowhere), and the UI shows stale data or a spinner that never resolves. In a static SPA there is no server log — the browser is the only witness, so errors that vanish client-side vanish entirely.

**Patterns to FLAG:**

1. **Floating promises (P2):**

   ```ts
   // BAD — fire-and-forget; rejection is unobserved, completion unordered
   saveBlueprint(data);
   navigate("/catalog");

   // GOOD
   await saveBlueprint(data);
   navigate("/catalog");
   ```

   A promise-returning call whose result is neither `await`ed, `.then/.catch`ed, nor deliberately marked (`void doThing()` with a comment) is a bug until proven otherwise. Flag especially in event handlers and effects where sequencing matters.

2. **`fetch` without checking `resp.ok` (P2):**

   ```ts
   // BAD — 4xx/5xx does NOT reject; .json() parses an error body as data
   const data = await (await fetch("/api/blueprints")).json();

   // GOOD
   const resp = await fetch("/api/blueprints");
   if (!resp.ok) throw new Error(`GET /api/blueprints: ${resp.status}`);
   const data = await resp.json();
   ```

   `fetch` only rejects on network failure. Every fetch call site (or the shared wrapper it goes through) must handle non-2xx explicitly. If `src/` has a shared API helper, flag raw `fetch` calls that bypass it.

3. **Swallowed rejections (P1):**

   ```ts
   // BAD — same disease as Python's `except: pass`
   try {
     await saveBlueprint(data);
   } catch (e) {
     // nothing, or console.log(e) with no user-visible consequence
   }
   ```

   A user clicked save, it failed, and the UI pretends it worked. Every catch must either surface to the user (error state, toast), rethrow, or carry a comment for the documented-ignorable case. `console.error` alone is P3-acceptable only for genuinely non-actionable telemetry paths.

4. **Async event handlers with no error path (P2):** `onClick={async () => { await mutate(); }}` — the rejection escapes to the void; React does not catch it and no error boundary sees it (error boundaries only catch render-phase errors). Wrap the body in try/catch that sets error state, or route through a helper that does.

5. **`Promise.all` where one failure should not sink the batch (P3):** `Promise.all` rejects fast on the first failure and abandons the rest. For independent operations (uploading N files, fetching N thumbnails), suggest `Promise.allSettled` with per-item error handling. Conversely, `allSettled` whose results are never inspected is a swallow — flag as P2.

6. **Sequential awaits for independent work (P3):**

   ```ts
   // BAD — serial waterfall, 3× latency
   const tags = await fetchTags();
   const textures = await fetchTextures();

   // GOOD — concurrent
   const [tags, textures] = await Promise.all([fetchTags(), fetchTextures()]);
   ```

   Flag when the calls are visibly independent and on a user-facing path.

7. **Missing loading/error UI states for new async flows (P3):** a new user-triggered async operation with no pending indication and no failure rendering. The catalog's users wait on real network calls; silence reads as breakage. (Component-structure aspects belong to `frontend-conventions-reviewer`.)

8. **`async` executor / promise-constructor anti-pattern (P2):** `new Promise(async (resolve, reject) => ...)` — rejections inside the async executor are lost. Almost always the surrounding code should just be an async function.

**Do NOT flag:**

- `void somePromise()` with a comment — that's the explicit fire-and-forget marker.
- Rejections handled by an established shared wrapper (verify the wrapper actually handles them before crediting it).
- Test code awaiting patterns that Jest manages.
- Top-level orchestration in scripts where an unhandled rejection crashing the process is the desired behavior.

**Review approach:**

1. Grep added lines for promise-returning calls (`fetch(`, `.then(`, `async ` functions invoked bare); for each, find the await/catch/void disposition.
2. For each `fetch`: `resp.ok` handled here or in the wrapper it uses?
3. For each `catch` block: does the error reach the user, a rethrow, or a documented ignore?
4. For each async handler in JSX props: error path?
5. For `Promise.all`: is fail-fast the right semantic for that batch?
