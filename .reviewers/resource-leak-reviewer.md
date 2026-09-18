# resource-leak-reviewer

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

2. **`open()` without a context manager:** `with open(path) as f:` — always. In scanner code iterating thousands of files, a leaked handle per file exhausts the fd limit mid-run.

3. **HTTP responses/sessions not closed:** for `requests`, use a `requests.Session` reused across calls (module/app level) rather than per-call construction in loops; use `with requests.get(url, stream=True) as resp:` for streamed downloads (STL files are large).

4. **`subprocess.Popen` without `.wait()` or context manager:** use `subprocess.run(...)` for one-shot commands.

5. **Unbounded `resp.content` / `.read()` from external sources:** an API or R2 object can be gigabytes. Check `Content-Length` or stream with bounded chunks when the size isn't controlled by us.

6. **`functools.lru_cache` without `maxsize=` on unbounded key spaces:** set a cap when keys derive from external input. In Lambda, module-level caches survive across invocations.

7. **Long-lived module-level dicts/sets as caches without eviction:** grows for the life of the warm container. Use `lru_cache` with maxsize or explicit eviction.

8. **`tempfile.NamedTemporaryFile(delete=False)` without explicit cleanup:** pair with `finally: os.unlink(name)` or use `tempfile.TemporaryDirectory()`. Lambda's `/tmp` is limited and persists across warm invocations.

9. **Manual `try/finally` chains protecting two or more resources:** use `contextlib.ExitStack`.

10. **boto3/R2 clients constructed per call:** construct S3-compatible clients once (module/app level) and reuse — per-call construction defeats connection pooling and slows every invocation.

**Do NOT flag:**

- `pathlib.Path.read_text()` / `read_bytes()` — closes internally.
- `with` blocks that close resources in normal flow.
- Bounded `lru_cache` with explicit `maxsize`.
- One-shot scripts that exit within seconds — EXCEPT database connections, which are always in scope given the serverless Postgres cap.

**Review approach:**

1. For each `psycopg.connect` / cursor acquisition: verify release on every return path, and that it follows the app's established pattern. P1 on violation.
2. For each `open()`, `subprocess.Popen`, `requests.*`: verify a `with` block or explicit close.
3. For each `.read()` / `.content` from external input: verify a size bound.
4. For each module-level cache: ask about eviction; remember Lambda containers are long-lived.
