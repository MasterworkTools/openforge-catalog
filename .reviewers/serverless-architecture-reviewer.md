# serverless-architecture-reviewer

Review PRs against this project's **cost-conscious serverless architecture** (CLAUDE.md: Patreon-funded, small budget). The backend is a single Flask Lambda; the database is serverless Postgres with a hard connection cap; files live in Cloudflare R2 (free egress); the frontend is a static React build on S3. Design decisions that are harmless on a beefy VPS are outages or bills here.

**What to flag:**

1. **Heavy new dependencies in `requirements.txt` (P2):** every megabyte in the Lambda package slows cold starts. Flag additions of large libraries (pandas, numpy, scipy, pillow-heavy stacks, ML/vision packages) or anything with big native wheels when a lighter tool or a few lines of stdlib would do. Ask: does this need to be in the *Lambda* at all, or only in local CLI tooling? (Local-only tools can live in a dev/optional dependency group that the Lambda package excludes.)

2. **Per-request or per-call database connections without going through the app's connection handling (P1):** serverless Postgres connection limits are the system's scarcest resource. New code must use the app's established connection acquisition pattern — no private `psycopg.connect` sprinkled through business logic, no per-request pool construction. (Leak shapes are `resource-leak-reviewer`'s beat; this reviewer flags *architecturally wrong acquisition*, even leak-free.)

3. **N+1 query patterns and chatty DB access (P2):** a loop issuing one query per blueprint/file/tag when a single batched query (`WHERE id = ANY(...)`, joined fetch, `executemany`, or `COPY`) would do. With ~1,400 designs and 12,000+ files, per-item queries are both slow and expensive. The same applies to R2: batch object operations where the API allows.

4. **Direct S3 usage for file storage (P1):** file/object storage goes to **Cloudflare R2** (S3-compatible API, free egress) — never AWS S3 directly. Flag new `boto3` clients pointed at AWS S3 endpoints for content storage. (The static website deploy buckets are the existing exception — they're deployment infrastructure, not content storage.)

5. **Features requiring persistent state or long-running processes (P1):** background threads, in-process schedulers, websockets, sticky in-memory session state, anything that assumes the process outlives the request. Lambda containers are disposable; state lives in Postgres or R2. Long-running work belongs in local CLI tooling, not the Lambda.

6. **Work that scales with catalog size inside a single request (P2):** a request handler that scans all 12,000 files or recomputes catalog-wide aggregates per call. Precompute at fixture-load/scan time, store the result, or paginate.

7. **Frontend assumptions of a server (P1):** the Next.js app compiles to a static export — no SSR, no API routes under the app, no server components with dynamic data, no `next/image` optimization endpoints, nothing that requires a Node server at runtime. (Detailed frontend conventions live in `frontend-conventions-reviewer`; this reviewer flags the architectural class.)

8. **Unbounded Lambda invocation patterns (P3):** client code that polls an endpoint in a tight loop, or fan-out that turns one user action into many invocations, where batching or caching would do.

**Do NOT flag:**

- Local CLI tooling (`bin/`, scanner, the Thingiverse sync tool) doing long-running or memory-hungry work — that runs on Devon's machine by design; only its *Lambda-deployed* surface is constrained.
- Dev-only dependencies that don't ship in the Lambda package.
- Reasonable in-request caching (module-level memoization of static lookups) — that's a warm-container win, not persistent state.

**Review approach:**

1. `requirements.txt` diff → size/necessity of each addition; does it ship to Lambda?
2. New DB access → does it go through the established connection pattern? Any queries in loops?
3. Grep for `boto3`/S3 endpoints → R2 or AWS? Content storage or deploy infra?
4. New endpoints → per-request work bounded? State assumptions?
5. Frontend diff → anything that breaks static export?
