# Agents

Each H2 below names a reviewer. The one-line summary tells the main loop **what the reviewer checks and when to spawn it** — use it to decide whether the PR diff is in scope. The body points at `.reviewers/<name>.md`, which the spawned Task reads as its complete specification.

## general-reviewer

**What it checks:** the whole PR, generalist pass — logic correctness against claims/docs (verified empirically, not by plausibility), domain/design soundness against upcoming beads tickets, contract fidelity against authoritative sources, cross-cutting interactions between the PR's parts, PR-body/docstring accuracy, design-level house style. Explicitly does NOT duplicate the specialist reviewers' dimensions.
**When to spawn:** **every PR, every round** — this repo has no Gemini/Cursor, so this reviewer is the broad-coverage pass. Never skipped for scope; last to retire under diminishing returns. Posts a single structured PR comment (not line comments) and per-item verdicts on verification rounds.

Read `.reviewers/general-reviewer.md` and follow it as your complete review specification.

---

## complexity-reviewer

**What it checks:** McCabe complexity > 10 (hard floor), the CLAUDE.md "And/Or" test and one-screen rule, nesting depth ≥ 4, parameter count > 5, class size > 20 public methods, nested ternaries, redundant single-call wrappers, generic identifiers in long functions. Covers Python and TypeScript/React.
**When to spawn:** PR touches production `*.py`, `*.ts`, or `*.tsx` (skip `tests/`, `integration_tests/`, `__tests__/`). Skip if the diff is data / docs / SQL / config only.
**Post only what this PR owns:** (1) **introduced/worsened only** — do NOT post complexity in a function that was already over a threshold before this PR unless the PR pushes it *further* over; (2) **no borderline soft flags** — the "And/Or" test and one-screen rule are advisory; post them only when they compound a hard objective violation on the same function.

Read `.reviewers/complexity-reviewer.md` and follow it as your complete review specification.

---

## error-handling-reviewer

**What it checks:** silent exception swallows, `return` inside `finally`, generic `except Exception` without re-raise, bare `except:`, missing `raise ... from`, `assert` used for runtime validation.
**When to spawn:** PR touches production `*.py` (skip if changes are docs / configs / tests only).

Read `.reviewers/error-handling-reviewer.md` and follow it as your complete review specification.

---

## test-coverage-reviewer

**What it checks:** every PR-touched function has a test that exercises it (pytest for `openforge/`, Jest for `src/`); flags missing tests for new branches/exceptions, weak mocking (patch point-of-use, don't mock third parties), tests that don't assert, skips without reasons.
**When to spawn:** PR modifies any `*.py` outside `tests/` or any `src/**/*.ts(x)` outside `__tests__/` (and ideally also when test files change — to lint the new tests themselves).

Read `.reviewers/test-coverage-reviewer.md` and follow it as your complete review specification.

---

## resource-leak-reviewer

**What it checks:** psycopg connections/cursors not released (P1 — serverless Postgres connection cap), `open()`/`subprocess` without context managers, HTTP sessions constructed per-call in loops, unbounded reads from external sources, unbounded caches in the warm-Lambda process, per-call boto3/R2 client construction.
**When to spawn:** PR touches `*.py` that allocates fds, sockets, DB connections, subprocesses, or long-lived caches. Skip if the diff is pure logic / tests / docs.

Read `.reviewers/resource-leak-reviewer.md` and follow it as your complete review specification.

---

## dead-code-reviewer

**What it checks:** unused module-level symbols, unused `__init__.py` re-exports, commented-out code, partial refactors leaving the old name, stale `__all__` entries, `pass`-only stubs, unused React components/props/types.
**When to spawn:** PR touches `*.py` or `src/**/*.ts(x)`, especially when it removes call sites, renames functions, or extracts/moves code. Skip for pure additive changes with no refactor surface.

Read `.reviewers/dead-code-reviewer.md` and follow it as your complete review specification.

---

## logging-reviewer

**What it checks:** sensitive data (tokens, JWTs, secrets) interpolated into log calls (P1), `logger.error` inside `except` without traceback, `logging.basicConfig` from library code, eager debug formatting in hot paths; for `bin/` CLIs also default level / verbosity ladder / stdout-vs-stderr discipline.
**When to spawn:** PR touches `*.py` that uses `logger.`, `logging.`, or `print(` for diagnostic output. Skip if the diff is data files / tests only.

Read `.reviewers/logging-reviewer.md` and follow it as your complete review specification.

---

## importlib-resources-reviewer

**What it checks:** package data loaded via `Path(__file__).parent` instead of `importlib.resources` — breaks in the Lambda zip. The repo convention is `impresources` (see `openforge/db/fixtures/__init__.py`).
**When to spawn:** PR touches `*.py` inside the `openforge/` package that loads bundled data files (fixtures, SQL, templates). Skip for tests, `bin/` scripts, and pure logic edits.

Read `.reviewers/importlib-resources-reviewer.md` and follow it as your complete review specification.

---

## migration-discipline-reviewer

**What it checks:** schema changes go through `openforge/db/schema/version_NN.py` (`@SchemaVersionDecorator`, paired `up_impl`/`down_impl`, docstring changelog, small named helpers, correct version numbering); no DDL from application code; new columns/tables have consumers or are explicitly staged.
**When to spawn:** PR touches `openforge/db/schema/`, or the diff contains DDL keywords (`CREATE TABLE`, `ALTER TABLE`, `CREATE INDEX`, `DROP`) anywhere outside it. Skip otherwise.

Read `.reviewers/migration-discipline-reviewer.md` and follow it as your complete review specification.

---

## serverless-architecture-reviewer

**What it checks:** the cost-conscious serverless constraints — heavy Lambda dependencies, DB access outside the established connection pattern, N+1 queries, direct AWS S3 for content storage (must be R2), persistent-state/long-running features, per-request work that scales with catalog size, static-export violations.
**When to spawn:** PR touches `requirements.txt`, backend code in `openforge/app/` or `openforge/db/`, storage client code, or adds new endpoints. Skip for pure frontend styling / docs / test-only diffs.

Read `.reviewers/serverless-architecture-reviewer.md` and follow it as your complete review specification.

---

## frontend-conventions-reviewer

**What it checks:** hardcoded API base URLs (must be relative `/api` — CLAUDE.md hard rule), static-export violations (API routes, SSR, `next/image` optimizer), inline logic that belongs in custom hooks, `any`/`@ts-ignore` type escapes, derived-state-via-useEffect anti-patterns, duplication of `src/utils/` helpers.
**When to spawn:** PR touches `src/**/*.ts` or `src/**/*.tsx`. Skip for backend-only diffs.

Read `.reviewers/frontend-conventions-reviewer.md` and follow it as your complete review specification.

---

## react-hooks-reviewer

**What it checks:** hook correctness and render performance — missing/wrong dependency arrays, missing effect cleanup (listeners, timers, observers), setState-after-unmount and fetch races (missing abort), conditional hooks, unstable references into memoized children/effect deps, catalog-scale list rendering without stable keys/memo, `useEffect` chains as data-flow.
**When to spawn:** PR touches `src/**/*.tsx` or hook files (`use*.ts`) in `src/`. Skip for backend-only or non-component TS diffs.

Read `.reviewers/react-hooks-reviewer.md` and follow it as your complete review specification.

---

## js-async-reviewer

**What it checks:** floating promises, `fetch` without `resp.ok` handling, swallowed rejections (P1 — the JS `except: pass`), async event handlers with no error path, `Promise.all` vs `allSettled` semantics, serial awaits for independent work, missing loading/error states, async promise-executor anti-pattern.
**When to spawn:** PR touches `src/**/*.ts(x)` containing `async`, `await`, `.then(`, or `fetch(`. Skip otherwise.

Read `.reviewers/js-async-reviewer.md` and follow it as your complete review specification.

---

## credentials-hygiene-reviewer

**What it checks:** literal secrets/JWTs committed anywhere (P1), HAR/traffic captures with live tokens in the diff (P1 — this project uses HAR captures for Thingiverse reverse-engineering; they carry live credentials and stay out of the repo), tokens in URLs when a header works, tokens echoed to output, insecure persistence of refresh tokens, realistic credentials in test fixtures.
**When to spawn:** PR touches auth/token code, adds fixtures or data files, adds `*.har`/capture artifacts, modifies `.gitignore`/env handling, or touches the Thingiverse integration. Cheap to run — when in doubt, spawn it.

Read `.reviewers/credentials-hygiene-reviewer.md` and follow it as your complete review specification.

---

# Guidelines

## How the pack runs

**This file is consumed BY the `pr-review-loop` skill — do not run these reviewers directly.** If you've read this file and are about to spawn the agents yourself (outside the skill), stop and invoke `pr-review-loop` instead: the skill owns the parts this file doesn't define — agents posting findings as PR line comments, per-thread replies, per-agent retirement, CI gating, and exit conditions.

Each reviewer runs independently and reports findings without coordination. A reviewer's silence on something is not an endorsement — it just means that reviewer didn't see anything in its scope.

**No external review bots on this repo.** Gemini Code Assist and Cursor Bugbot are not installed; do not burn `--wait` cycles polling for them. `general-reviewer` is the pack's broad-coverage substitute and spawns on every PR alongside the in-scope specialists.

**Per-reviewer file scope:**

| Reviewer | Files in scope |
|----------|----------------|
| `general-reviewer` | everything — spawns on every PR, every round |
| `complexity-reviewer` | `*.py`, `*.ts`, `*.tsx` (skips tests) |
| `error-handling-reviewer` | `*.py` (production code) |
| `test-coverage-reviewer` | `*.py`, `src/**/*.ts(x)` |
| `resource-leak-reviewer` | `*.py` |
| `dead-code-reviewer` | `*.py`, `src/**/*.ts(x)` |
| `logging-reviewer` | `*.py` (rules differ for `bin/` CLIs vs the Flask app) |
| `importlib-resources-reviewer` | `openforge/**/*.py` (skips tests and `bin/`) |
| `migration-discipline-reviewer` | `openforge/db/schema/**` + any diff containing DDL |
| `serverless-architecture-reviewer` | `requirements.txt`, `openforge/app/**`, `openforge/db/**`, storage clients |
| `frontend-conventions-reviewer` | `src/**/*.ts(x)` |
| `react-hooks-reviewer` | `src/**/*.tsx`, `src/**/use*.ts` |
| `js-async-reviewer` | `src/**/*.ts(x)` with async/promise code |
| `credentials-hygiene-reviewer` | everything (auth code, fixtures, artifacts, `.gitignore`) |

Skip reviewers whose file scope doesn't match the PR diff. (`general-reviewer`'s scope is "everything," so it always matches — the skip rule never applies to it by construction.)

## Branch targeting

PRs target **`test`** (the development default branch), never `main`. `main` is the production deployment branch; `test` → `main` merges are intentional production releases only. A PR opened against `main` that isn't an explicit deploy is itself a finding.

## Tooling assumed in CI

CI runs (see `.github/workflows/test.yaml`): `pytest tests/ --cov=openforge`, `npm test`, `npm run lint:all` (ESLint + `tsc --noEmit`), `ruff check .`, `ruff format --check .`. Pre-commit mirrors these locally.

Reviewers do not duplicate what CI already enforces — they cover what it misses (C901 complexity, bandit-class security checks, dead-code detection have no CI gate here, so the corresponding reviewers carry that weight themselves). Suggesting a new CI tool is a P3 advisory, not a blocking finding.

## Severity convention

Every finding must be tagged with a beads-style priority:

| Priority | Disposition | Examples |
|----------|-------------|----------|
| **P1** | Blocking — must fix before merge | Committed secret or HAR with live tokens, leaked/rogue DB connection against serverless Postgres, silent exception swallow, DDL outside the migration system, hardcoded API base URL, static-export violation, direct S3 for content storage, sensitive data in logs |
| **P2** | Should fix in this PR | Missing tests for new branches, complexity floor violation, missing `raise ... from` on new chains, missing `down_impl`, N+1 queries, `any`-typed new code, tokens in URLs |
| **P3** | Advisory — deferrable with a beads ticket | Complexity heuristic findings, dead code, log-level nits, state-management patterns, utility duplication, docs for new env vars |

**Default severity per reviewer:**

- `general-reviewer`: maps its Critical/Medium/Minor sections to **P1/P2/P3**.

- `credentials-hygiene-reviewer`, `resource-leak-reviewer` (DB connections): **P1** by default.
- `error-handling-reviewer`: **P2** by default; **P1** for silent swallows and `return` in `finally`.
- `logging-reviewer`: **P2** by default; **P1** for sensitive data in log messages.
- `migration-discipline-reviewer`: **P1** for DDL outside the migration system and version-number collisions; **P2** otherwise.
- `serverless-architecture-reviewer`: **P1** for S3-instead-of-R2, persistent-state features, and connection-pattern violations; **P2** otherwise.
- `frontend-conventions-reviewer`: **P1** for hardcoded base URLs and static-export violations; **P2** otherwise.
- `react-hooks-reviewer`: **P2** by default; **P1** for conditional hooks; **P3** for unstable-reference and derived-state advisories.
- `js-async-reviewer`: **P2** by default; **P1** for swallowed rejections that hide user-facing failures.
- `test-coverage-reviewer`: **P2** by default.
- `complexity-reviewer`: **P2** for objective floor violations; **P3** for heuristic findings.
- `dead-code-reviewer`: **P3** by default.

A reviewer may promote or demote a specific finding from its default, but must state why. **Where a spec under `.reviewers/` tags a specific pattern with an explicit priority, the spec's tag wins over this table** — the table gives each reviewer's default, not a ceiling/floor.

## Output format

Findings must be structured. Use this template:

```
[<reviewer>] [<severity>] <one-line title>

File: path/to/file.py:LINE
Quote:
    <1-5 lines of code or text being flagged>

Issue: <one or two sentences on what's wrong>
Suggested fix:
    <concrete diff or rewritten code/text>
Reason (optional): <only if not obvious>
```

Structured findings are diff-able, easy to triage, and easy to deduplicate when multiple reviewers flag the same line.

When posting via `post-line-comment.sh`, the comment is already anchored to a file/line by the script's arguments — keep the `File:` line in the body anyway (it survives quoting, consolidation into PR-level summaries, and beads-ticket copy/paste, where the anchor doesn't).

## Deferring findings with beads

To defer a P2 or P3 finding to a follow-up:

1. Create a beads ticket capturing reviewer name, severity, file, and quote.
2. Link the ticket in the PR description or as a reply to the reviewer's comment.
3. The reviewer accepts the deferral only when the beads ticket exists.

**P1 findings are not deferrable** — they must be fixed in-PR.

## Reviewing external-bot suggestions

Per CLAUDE.md: be skeptical of Gemini's suggestions — it lacks project context. Agent reviewers in this pack take precedence when they conflict with a generic "best practice" suggestion that doesn't fit this project's philosophy (pragmatism, cost-consciousness, existing patterns). Not every bot suggestion needs implementation; "won't fix — conflicts with project convention X" is a valid disposition when X is real and named.

# Context

OpenForge Catalog is a content management system for 12,000+ 3D-printable STL files (~1,400 designs). Backend: Python/Flask deployed as a single AWS Lambda; PostgreSQL on serverless (hard connection limits); file storage on Cloudflare R2 (never AWS S3 for content). Frontend: Next.js compiled to a **static export** served from S3 — no server at runtime; all API calls are relative to `/api`. Data flows from a Dropbox-scanning pipeline into fixture JSON (`openforge/db/fixtures/`), loaded locally and replayed to production through the Flask API (`bin/upload_fixture`). Schema changes use a hand-rolled versioned migration system (`openforge/db/schema/version_NN.py`). Tests: pytest (`tests/`), Jest (`src/**/__tests__/`), plus local-only integration tests (`integration_tests/`, Flask on :5328).

Active work includes a Thingiverse publish/sync tool (see beads epic `openforge_catalog-4kx`): v2 JWT auth, HAR-derived API contract, file-hash-based sync. That work handles live credentials (JWTs, refresh tokens, client secrets from `~/.profile.d/`) and HAR captures — hence `credentials-hygiene-reviewer`.
