# logging-reviewer
model: sonnet
verification: mixed — `print(`, `basicConfig`, `logger.error` in `except` and f-string log calls are greps quoted (evidence-query); level choice and verbosity-ladder findings are judgement.
**Checks:** `logger.error` inside `except` without traceback, `logging.basicConfig` from library code, eager debug formatting in hot paths; for `bin/` CLIs also default level / verbosity ladder / stdout-vs-stderr discipline.
**Spawn when:** PR touches `*.py` that uses `logger.`, `logging.`, or `print(` for diagnostic output. Skip if the diff is data files / tests only.
**Contents:** Patterns to FLAG — universal: `logger.error(...)` inside `except` without traceback; `logging.basicConfig()` called from library code; Eager formatting in hot paths · Patterns to FLAG — CLI entry points only: Default log level too verbose; No verbosity flag; Verbosity flag that doesn't stack; `print()` for diagnostics in CLI tools · Patterns to FLAG — library / service only: `print()` in library or Flask code; Log-level discipline · Do NOT flag

Review Python code for **logging discipline**. Logging is observability infrastructure — it determines what operators see in CloudWatch when the Lambda misbehaves — and it's a security boundary (logs are shipped off-host and indexed by tools that don't redact secrets). Two contexts with different rules:

- **The Flask app and library code** (`openforge/`) — logs ship to CloudWatch.
- **CLI tools** (`bin/`, script entry points) — Unix rule of silence: terse by default, verbose on request.

Default severity P2; P3 for level and eager-formatting nits.

### Patterns to FLAG — universal

1. **`logger.error(...)` inside `except` without traceback:** use `logger.exception("work failed")` (shorthand for `error` + `exc_info=True`) inside `except` blocks unless there's a specific reason to omit the traceback. In Lambda, the traceback in CloudWatch is often the only forensic evidence.

2. **`logging.basicConfig()` called from library code:** libraries call `logging.getLogger(__name__)`; `basicConfig` belongs in entry points only.

3. **Eager formatting in hot paths:** `logger.debug(f"processed {item.expensive_repr()}")` formats unconditionally. Use lazy `%s` formatting (`logger.debug("processed %s", item)`) in loops over blueprint/file collections (scanner code iterates 12,000+ files).

### Patterns to FLAG — CLI entry points only

A file is a CLI entry point when it contains `if __name__ == "__main__":`, builds an `argparse.ArgumentParser` / uses Click decorators, or lives under `bin/`.

4. **Default log level too verbose:** CLIs default to WARNING; INFO/DEBUG belong behind verbosity flags.

5. **No verbosity flag:** a CLI that logs without a `-v`/`-q` ladder gives the user no dial. Canonical: `-v` INFO, `-vv` DEBUG, `-q` ERROR, via `action="count"` / `count=True`.

6. **Verbosity flag that doesn't stack:** `action="store_true"` for `-v` means `-vv` does nothing. Use `action="count"`.

7. **`print()` for diagnostics in CLI tools:** stdout is for the data the user asked for; diagnostics go to stderr via the logger. Mixing them breaks pipelines (`mycli | jq`). Note `bin/load_all.sh`-style scripts redirect stdout to fixture files — stray diagnostic prints corrupt the output.

### Patterns to FLAG — library / service only

8. **`print()` in library or Flask code:** bypasses the logger, can't be filtered, no timestamps. Flag in any module that isn't a CLI entry point.

9. **Log-level discipline:** DEBUG = fine-grained detail; INFO = milestones; WARNING = recoverable (retry, fallback); ERROR = actionable failures. Flag `logger.info` in hot loops (should be DEBUG) and `logger.error` on recoverable retries (should be WARNING).

### Do NOT flag

- `print()` in tests and ad-hoc scripts.
- `print()` as the *data output* of a CLI (e.g., emitting fixture JSON to stdout by design).
- Logging configuration in a canonical entry point.
- Eager formatting in cold paths (once-at-startup lines).
