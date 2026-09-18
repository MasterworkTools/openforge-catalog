# complexity-reviewer

Review **production code only** for function complexity. **Skip all files in `tests/`, `integration_tests/`, and `__tests__/`** — test files often have long fixtures, parametrize tables, and assertion blocks that don't need the same complexity constraints.

This reviewer enforces the project's Code Organization Philosophy (CLAUDE.md): *"Functions should be describable with as few uses of 'and' or 'or' as possible."* It applies to both Python (`*.py`) and TypeScript/React (`*.ts`, `*.tsx`).

## Posting gates (read before flagging anything)

1. **Introduced or worsened only — not pre-existing.** Flag complexity this PR *creates* or *materially worsens*. If a function was already over a threshold before this PR (it was long/complex on the base branch) and this PR only edits a few lines inside it without pushing it further over, it is **out of scope** — do not post it. (You may note it once as a P3 defer-to-beads suggestion, but not as a finding that blocks the PR.) Check the diff: is the threshold breach in *added* lines, or did the PR push an already-borderline function past the limit? If neither, skip.
2. **Hard violations always; soft heuristics only when they compound.** The objective complexity floor and unambiguous structural smells (depth ≥ 4, > 5 params, > 20 public methods, nested ternaries ≥ 2 levels) post on every occurrence. The **"And/Or" test** and the **one-screen rule** are *advisory*: do **not** post them as standalone findings for a function that passes the objective floor and sits within ~50–60 lines. Raise a soft heuristic only when it compounds a hard violation on the same function.

**Objective floor (Python): McCabe complexity > 10.** Run `ruff check --select C901 .` against the PR head (never a stale local checkout) and flag every function that exceeds it. (Ruff's mccabe `max-complexity` defaults to 10; it is a `pyproject.toml` setting — `[tool.ruff.lint.mccabe]` — not a CLI flag.) For TypeScript, apply the same threshold by inspection (or `eslint` `complexity` rule output if configured).

Apply these heuristics on top of the objective floor:

1. **"And/Or" test** (from CLAUDE.md): minimize the number of "and"/"or" needed to describe what a function does. If you need multiple conjunctions, the function is doing too much.
   - Good: "This function validates and saves user data" (validation is a prerequisite for saving — cohesive).
   - Bad: "This component handles state AND rendering AND keyboard events AND mouse drag events."

2. **One-screen rule** (from CLAUDE.md): functions should fit on one screen (~50–60 lines).
   - **Internal functions don't count**: lines of nested helper `def`s / inner closures do NOT count against the parent's limit — only the main body lines.
   - Pragmatic exception (also from CLAUDE.md): larger functions are acceptable when breaking them up would genuinely complicate rather than simplify. If invoking this exception, say so and why.

3. **Extractable inner structures**: if a block has a clear purpose, suggest extraction:
   - Python: module-level `_helper()` first; sibling helper module second.
   - React: extract event handling and stateful logic into **custom hooks**; extract render fragments into components.

4. **Nesting depth**: flag functions with indent depth ≥ 4 inside the body. Use early returns to flatten (`if not x: return` / `if (!x) return`).

5. **Parameter count**: flag more than **5 positional parameters**. Refactor to a config object (dataclass / TypedDict / props object) or keyword-only args.

6. **Class size (public method count)**: flag classes with **more than 20 public methods**. Private helpers (`_foo`) do NOT count — extracting helpers as private methods is exactly what this reviewer encourages. Advisory (P3): ask whether the public methods cluster around a single responsibility.

7. **Nested ternaries**: chained `x if a else y if b else z` (or JSX `a ? x : b ? y : z`) is hard to read past one level. Recommend `if/elif/else`, a dict-dispatch lookup, or in JSX an early-return / lookup-map pattern. A single ternary is fine; flag at the second level.

8. **Redundant single-call wrappers**: a function that exists only to call one other function with no added validation, normalization, error context, or naming benefit. Single-call, single-caller, no-added-meaning → flag.

9. **Generic identifiers in long functions**: `data`, `temp`, `result`, `value`, `obj` reused for different things in a long function. Flag only when the function is long enough that the generic name actively misleads. Short helpers (≤10 lines) can use generic names.

**Do NOT flag:**

- Test files.
- Long-but-linear functions (no branching, sequential transformations) up to ~100 lines. Beyond that, still recommend extraction.
- `match` / `if-elif-else` / `switch` chains where each branch is a short value→action mapping (dispatch tables are inherently flat).
- Functions whose length comes from a single long literal data structure.
- JSX render bodies that are long but flat markup — flag only when logic (conditionals, mapping, state juggling) is interleaved with the markup and could move to hooks/helpers.

**DO flag (dispatch-specific):** `match`/`elif`/`switch` chains with multi-statement branch bodies that do their own branching — the flatness exemption applies to dispatch tables, not chains of mini-functions in disguise.

**Note:** It is acceptable to acknowledge complexity and defer refactoring by creating a beads ticket rather than fixing in the current PR. This applies to heuristic findings; objective floor violations should be resolved in-PR unless there's a documented reason.
