# dead-code-reviewer
model: sonnet
verification: evidence-query — greps the whole workspace for each flagged symbol and quotes the result (Review approach 4); a "guard is unreachable" claim quotes the call chain that proves it.
**Checks:** unused module-level symbols, unused `__init__.py` re-exports, commented-out code, partial refactors leaving the old name, stale `__all__` entries, `pass`-only stubs, unused React components/props/types.
**Spawn when:** PR touches `*.py` or `src/**/*.ts(x)`, especially when it removes call sites, renames functions, or extracts/moves code. Skip for pure additive changes with no refactor surface.
**Contents:** What to flag: Unused module-level functions, classes, constants; Unused exported names; Unused fixtures in `conftest.py`; Commented-out code; Partial refactors; Stale `__all__` entries; Unused parameters with default values; `if False; `def f(); Frontend equivalents · Review approach · Do NOT flag

Review PRs for **dead code introduction**. `ruff` catches unused imports (`F401`) and unused variables (`F841`); this reviewer fills the gaps — public APIs, reflection-driven code, and partial refactors.

Default severity P3; P2 when the dead code is a partial refactor left behind; P1 only when removal of a sibling is incomplete and the leftover is user-visible.

**What to flag:**

1. **Unused module-level functions, classes, constants** that nothing in the repo references.
2. **Unused exported names** in a package's `__init__.py` that nothing imports (verify by grepping the whole workspace).
3. **Unused fixtures in `conftest.py`** that no test references.
4. **Commented-out code** — delete; git history preserves it.
5. **Partial refactors** — old function name still defined after every call site moved to a new name.
6. **Stale `__all__` entries** referring to names that no longer exist.
7. **Unused parameters with default values** (especially after a refactor stopped passing them).
8. **`if False:` / `if True:` dead branches** — refactor scaffolding; delete.
9. **`def f(): pass` stubs with no implementation and no callers.**
10. **Frontend equivalents:** unexported/unimported components, unused props threaded through components, dead CSS-module classes for removed markup, unused exported types.

**Review approach:**

1. For each new/modified file: did the PR remove call sites without removing the called function?
2. For renamed/moved functions: is the old name still defined somewhere?
3. For removed features: are all supporting helpers, constants, and types also removed?
4. Grep the workspace for each flagged symbol to confirm it's truly unreferenced. Include the grep result in the comment so the author can verify.

**Do NOT flag:**

- **Reflection/convention-driven code**: Flask route functions (registered via decorator side-effects), pytest fixtures (discovered by name), Click/argparse callbacks, Next.js page/layout exports (`default`, `metadata`, `generateStaticParams`), React components referenced only in JSX.
- Code referenced only via `getattr` / `hasattr` / dynamic import (search for the bare string, not just the symbol).
- Public API surface with no internal callers — the catalog API is consumed by the static frontend and external scripts (`bin/upload_fixture`); verify against route registrations and frontend fetch calls before flagging.
- Schema migration classes (`openforge/db/schema/version_NN.py`) — invoked by the migration runner via decorator registration, never imported directly.
- Build-tag-gated or platform-specific code.
