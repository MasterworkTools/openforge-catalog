# logging-reviewer

Review Python code for **logging discipline**. Logging is observability infrastructure — it determines what operators see in CloudWatch when the Lambda misbehaves — and it's a security boundary (logs are shipped off-host and indexed by tools that don't redact secrets). Two contexts with different rules:

- **The Flask app and library code** (`openforge/`) — logs ship to CloudWatch.
- **CLI tools** (`bin/`, script entry points) — Unix rule of silence: terse by default, verbose on request.

### Patterns to FLAG — universal

1. **Sensitive data in log messages (P1 — security leak):**

   ```python
   # BAD — credentials in logs that ship off-host
   logger.info(f"user={user}, token={token}")
   logger.debug(f"request headers: {request.headers}")  # includes Authorization
   ```

   Flag interpolation of variables named `token`, `password`, `secret`, `api_key`, `credential`, `auth`, `cookie`, `session`, `jwt`, `refresh`, `bearer`, `client_secret` into any log call. Also flag dumping entire request/response objects without redaction. **This repo handles Thingiverse JWTs/refresh tokens and API tokens — none may ever appear in a log line.**

   Acceptable: explicit redaction (`token[:8] + "..."`) or logging a hash/fingerprint.

2. **`logger.error(...)` inside `except` without traceback:** use `logger.exception("work failed")` (shorthand for `error` + `exc_info=True`) inside `except` blocks unless there's a specific reason to omit the traceback. In Lambda, the traceback in CloudWatch is often the only forensic evidence.

3. **`logging.basicConfig()` called from library code:** libraries call `logging.getLogger(__name__)`; `basicConfig` belongs in entry points only.

4. **Eager formatting in hot paths:** `logger.debug(f"processed {item.expensive_repr()}")` formats unconditionally. Use lazy `%s` formatting (`logger.debug("processed %s", item)`) in loops over blueprint/file collections (scanner code iterates 12,000+ files).

### Patterns to FLAG — CLI entry points only

A file is a CLI entry point when it contains `if __name__ == "__main__":`, builds an `argparse.ArgumentParser` / uses Click decorators, or lives under `bin/`.

5. **Default log level too verbose:** CLIs default to WARNING; INFO/DEBUG belong behind verbosity flags.

6. **No verbosity flag:** a CLI that logs without a `-v`/`-q` ladder gives the user no dial. Canonical: `-v` INFO, `-vv` DEBUG, `-q` ERROR, via `action="count"` / `count=True`.

7. **Verbosity flag that doesn't stack:** `action="store_true"` for `-v` means `-vv` does nothing. Use `action="count"`.

8. **`print()` for diagnostics in CLI tools:** stdout is for the data the user asked for; diagnostics go to stderr via the logger. Mixing them breaks pipelines (`mycli | jq`). Note `bin/load_all.sh`-style scripts redirect stdout to fixture files — stray diagnostic prints corrupt the output.

### Patterns to FLAG — library / service only

9. **`print()` in library or Flask code:** bypasses the logger, can't be filtered, no timestamps. Flag in any module that isn't a CLI entry point.

10. **Log-level discipline:** DEBUG = fine-grained detail; INFO = milestones; WARNING = recoverable (retry, fallback); ERROR = actionable failures. Flag `logger.info` in hot loops (should be DEBUG) and `logger.error` on recoverable retries (should be WARNING).

### Do NOT flag

- `print()` in tests and ad-hoc scripts.
- `print()` as the *data output* of a CLI (e.g., emitting fixture JSON to stdout by design).
- Logging configuration in a canonical entry point.
- Eager formatting in cold paths (once-at-startup lines).

### Review approach

1. Classify each `*.py` file in the diff: CLI entry point, library, or Flask service code.
2. Grep for `logger.` / `logging.` / `print(` calls.
3. For each log call: sensitive names interpolated? `logger.error` inside `except`? eager f-string in a hot path?
4. For CLI files: default level, verbosity ladder, stdout/stderr discipline.
5. For library files: flag any `basicConfig` (P2) and any `print()` (P2).
