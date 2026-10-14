# serverless-architecture-reviewer
model: sonnet
verification: evidence-query — measures what it claims (wheel size, query count from a counted run, Max Memory Used from REPORT lines) and quotes it; cost-fit is judgement and says so.
**Checks:** the cost-conscious serverless constraints — heavy Lambda dependencies, DB access outside the established connection pattern, N+1 queries, direct AWS S3 for content storage (must be R2), persistent-state/long-running features, per-request work that scales with catalog size, package data located via `__file__`.
**Spawn when:** PR touches `requirements.txt`, backend code in `openforge/app/` or `openforge/db/`, storage client code, adds new endpoints, or uses `__file__` in `openforge/**/*.py`. Skip for pure frontend styling / docs / test-only diffs.
**Contents:** What to flag: Heavy new dependencies in `requirements.txt`; Per-request or per-call database connections without going through the app's connection handling; N+1 query patterns and chatty DB access; Direct S3 usage for file storage; Features requiring persistent state or long-running processes; Work that scales with catalog size inside a single request; Package data located via `__file__`; Unbounded Lambda invocation patterns · Do NOT flag

Review PRs against this project's **cost-conscious serverless architecture** (CLAUDE.md: Patreon-funded, small budget). The backend is a single Flask Lambda; the database is serverless Postgres with a hard connection cap; files live in Cloudflare R2 (free egress); the frontend is a static React build on S3. Design decisions that are harmless on a beefy VPS are outages or bills here.

**What to flag:**

1. **Heavy new dependencies in `requirements.txt` (P2):** every megabyte in the Lambda package slows cold starts. Flag additions of large libraries (pandas, numpy, scipy, pillow-heavy stacks, ML/vision packages) or anything with big native wheels when a lighter tool or a few lines of stdlib would do. Ask: does this need to be in the *Lambda* at all, or only in local CLI tooling? (Local-only tools can live in a dev/optional dependency group that the Lambda package excludes.)

2. **Per-request or per-call database connections without going through the app's connection handling (P1):** serverless Postgres connection limits are the system's scarcest resource. New code must use the app's established connection acquisition pattern — no private `psycopg.connect` sprinkled through business logic, no per-request pool construction. (Leak shapes are `resource-leak-reviewer`'s beat; this reviewer flags *architecturally wrong acquisition*, even leak-free.)

3. **N+1 query patterns and chatty DB access (P2):** a loop issuing one query per blueprint/file/tag when a single batched query (`WHERE id = ANY(...)`, joined fetch, `executemany`, or `COPY`) would do. With ~1,400 designs and 12,000+ files, per-item queries are both slow and expensive. The same applies to R2: batch object operations where the API allows.

4. **Direct S3 usage for file storage (P1):** file/object storage goes to **Cloudflare R2** (S3-compatible API, free egress) — never AWS S3 directly. Flag new `boto3` clients pointed at AWS S3 endpoints for content storage. (The static website deploy buckets are the existing exception — they're deployment infrastructure, not content storage.)

5. **Features requiring persistent state or long-running processes (P1):** background threads, in-process schedulers, websockets, sticky in-memory session state, anything that assumes the process outlives the request. Lambda containers are disposable; state lives in Postgres or R2. Long-running work belongs in local CLI tooling, not the Lambda.

6. **Work that scales with catalog size inside a single request (P2):** a request handler that scans all 12,000 files or recomputes catalog-wide aggregates per call. Precompute at fixture-load/scan time, store the result, or paginate.

7. **Package data located via `__file__` (P2):** `Path(__file__).parent`, `os.path.dirname(__file__)` or `__file__.parents[N]` used to find bundled data in `openforge/**/*.py`. It breaks in the Lambda image; use `importlib.resources` as `openforge/db/fixtures/__init__.py` does (`from importlib import resources as impresources`). A new data file type under `openforge/` must also be matched by `package_data` in `setup.py`. Not flagged: write paths, tests, `bin/`, external config paths.

8. **Unbounded Lambda invocation patterns (P3):** client code that polls an endpoint in a tight loop, or fan-out that turns one user action into many invocations, where batching or caching would do.

**Do NOT flag:**

- Local CLI tooling (`bin/`, scanner, the Thingiverse sync tool) doing long-running or memory-hungry work — that runs on Devon's machine by design; only its *Lambda-deployed* surface is constrained.
- Dev-only dependencies that don't ship in the Lambda package.
- Reasonable in-request caching (module-level memoization of static lookups) — that's a warm-container win, not persistent state.
