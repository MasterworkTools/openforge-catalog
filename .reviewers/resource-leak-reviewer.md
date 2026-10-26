# resource-leak-reviewer
model: sonnet
verification: evidence-query — for each connection acquisition quotes the return or exception path that skips release; a growth claim names the unbounded structure and its key space.
**Checks:** psycopg connections/cursors not released (P1 — serverless Postgres connection cap), unbounded caches and `/tmp` files in the warm-Lambda process, per-call boto3/R2 client construction.
**Spawn when:** diff in `openforge/**/*.py` acquires a DB connection or cursor, builds a boto3/R2 client, or adds a module-level cache or `/tmp` file. Skip otherwise.
**Contents:** Patterns to FLAG: Database connections/cursors not closed or returned; `functools.lru_cache` without `maxsize=` on unbounded key spaces; Long-lived module-level dicts/sets as caches without eviction; `tempfile.NamedTemporaryFile(delete=False)` without explicit cleanup; boto3/R2 clients constructed per call · Do NOT flag · Review approach

Review Python code for **resource leaks**. Two contexts matter in this repo, and the second raises the stakes:

- **CLI tools / scanner runs** — batch processes where leaked fds pile up across thousands of files (the catalog manages 12,000+ STLs).
- **The Flask Lambda** — a warm Lambda container reuses the process across invocations, so anything leaked per-request accumulates exactly like a daemon. **Serverless Postgres has a hard connection cap** — a leaked connection isn't just memory, it's a production outage vector. Connection discipline is P1 here.

**Patterns to FLAG:**

1. **Database connections/cursors not closed or returned (P1):**

   ```python
   # BAD — connection leaked; warm Lambda accumulates until Postgres refuses connections
   conn = psycopg.connect(dsn)
   curs = conn.cursor()
   curs.execute(query)

   # GOOD
   with psycopg.connect(dsn) as conn:
       with conn.cursor() as curs:
           curs.execute(query)
   ```

   Follow the existing connection-handling pattern in `openforge/app/` — new code must not invent its own connection lifecycle. Every code path (including exception paths) must release the connection.

2. **`functools.lru_cache` without `maxsize=` on unbounded key spaces:** set a cap when keys derive from external input. In Lambda, module-level caches survive across invocations.

3. **Long-lived module-level dicts/sets as caches without eviction:** grows for the life of the warm container. Use `lru_cache` with maxsize or explicit eviction.

4. **`tempfile.NamedTemporaryFile(delete=False)` without explicit cleanup:** pair with `finally: os.unlink(name)` or use `tempfile.TemporaryDirectory()`. Lambda's `/tmp` is limited and persists across warm invocations.

5. **boto3/R2 clients constructed per call:** construct S3-compatible clients once (module/app level) and reuse — per-call construction defeats connection pooling and slows every invocation.

**Do NOT flag:**

- Bounded `lru_cache` with explicit `maxsize`.
- One-shot scripts that exit within seconds — EXCEPT database connections, which are always in scope given the serverless Postgres cap.

**Review approach:**

1. For each `psycopg.connect` / cursor acquisition: verify release on every return path, and that it follows the app's established pattern. P1 on violation.
2. For each module-level cache: ask about eviction; remember Lambda containers are long-lived.
