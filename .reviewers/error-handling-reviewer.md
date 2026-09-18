# error-handling-reviewer

Review Python code for **error handling correctness**. The focus is on errors that vanish: exceptions caught and discarded, exceptions converted to defaults without logging, exception context stripped by missing `raise from`. Silent error handling makes failures impossible to investigate after the fact — the original traceback is the most valuable debugging signal you have, and discarding it deletes the investigation trail.

This matters doubly here: the backend is a single Lambda where you can't attach a debugger — CloudWatch logs and tracebacks are the only forensics available.

**Patterns to FLAG:**

1. **Silent exception swallowing — the most damaging pattern (P1):**

   ```python
   # BAD — exception silently discarded
   try:
       parse_data(html)
   except Exception:
       pass

   # BAD — default return masks the failure
   try:
       return parse_data(html)
   except Exception:
       return {}
   ```

   If parsing fails, callers see `{}` and assume success. The original error never reaches the operator.

2. **`return` statement inside a `finally` block (P1):** a `return` (or `raise`) in `finally` overrides any pending exception. Almost always a bug.

3. **Generic `except Exception` without re-raise (P2):**

   ```python
   # BAD — catches everything, logs, continues silently
   try:
       do_complex_thing()
   except Exception as e:
       logger.warning(f"Error: {e}")
       # implicit None return
   ```

   Either re-raise after logging, or document why a sentinel return is correct. In Flask routes, prefer letting the error propagate to an error handler that returns a proper 5xx over returning a fake-success payload.

4. **Bare `except:` (catches `BaseException`) (P2):** use `except Exception:` at minimum — bare `except` turns Ctrl-C and `sys.exit()` into silent no-ops.

5. **Missing exception chaining (`raise ... from`) (P3):**

   ```python
   # GOOD — preserves the cause for the traceback
   try:
       value = int(text)
   except ValueError as e:
       raise ParseError(f"invalid number: {text!r}") from e
   ```

   Use `raise ... from None` only when deliberately suppressing the cause is correct (rare).

6. **Custom exception classes for caller-handleable cases (P3):** errors callers branch on programmatically (not-found, already-exists, validation-failure) should be classes inheriting from a meaningful base — flag ad-hoc `raise ValueError("not found")` where the caller clearly needs to detect the case but can't.

7. **`try/finally` for cleanup when a context manager would do (P3):** `with open(path) as f:` over manual `f.close()` in `finally`.

8. **`assert` used for runtime validation (P2):** asserts are stripped under `python -O`. Use real validation (`if x is None: raise ValueError(...)`) for user-facing or API-input checks; `assert` is for internal invariants only.

**Acceptable patterns:**

- Assertions with context for internal invariants: `assert len(children) == 2, f"expected 2, got {len(children)}"`.
- Specific exception handling with `raise ... from`.
- Known-case handling with an explicit comment:

  ```python
  try:
      score = int(stat.strip())
  except ValueError:
      # Known case: legacy fixture rows use "-" for missing values.
      score = None
  ```

- Bare `except` + `raise` for cleanup (re-raises the original).
- `contextlib.suppress(FileNotFoundError)` for genuinely-ignorable cases — intent is explicit.

**Review approach:**

1. Grep for `except` patterns; for each, confirm the handler either logs AND re-raises, returns the correct value for a documented case (with comment), or has another defensible justification.
2. Grep for `pass` immediately after `except`. Flag as P1.
3. Grep for `return` inside `finally`. Flag as P1.
4. Grep for `try` blocks that could be `with` statements.
5. Grep for `raise X(...)` after `except`; verify `from e` (or justified `from None`).
6. For ad-hoc `raise ValueError(...)` where callers need to detect the case, suggest a custom exception class.
