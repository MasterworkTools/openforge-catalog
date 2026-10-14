# Configuration notes

Neither Gemini Code Assist nor Cursor Bugbot is installed on this repository.
The agent pack is the whole review, so the loop must not trigger either
bot or wait for one.

# Guidelines

## How the pack runs

Each reviewer runs independently and reports findings without coordination. A reviewer's silence on something is not an endorsement — it just means that reviewer didn't see anything in its scope.

`code-reviewer`, `silent-failure-hunter`, `pr-test-analyzer` and `code-simplifier` are intentionally not loaded: they overlap `general-reviewer`, `error-handling-reviewer`, `test-coverage-reviewer` and `complexity-reviewer` respectively.

**Comment and docstring findings belong to `comment-analyzer`.** Other reviewers don't file them unless the comment is a symptom of their own finding (e.g. dead code whose docstring still describes it).

**No external review bots on this repo.** Gemini Code Assist and Cursor Bugbot are not installed; do not burn `--wait` cycles polling for them. `general-reviewer` is the pack's broad-coverage substitute and spawns on every PR alongside the in-scope specialists.

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

Each spec states its own default severity.

**Comment, docstring and PR-body wording (any reviewer):** **P3**, and the fix is deleting or shortening the text. **P2** only if the text would lead a reader to write a bug. Never P1. This rule overrides any spec under `.reviewers/`.

A reviewer may promote or demote a specific finding from its default, but must state why. **Where a spec under `.reviewers/` tags a specific pattern with an explicit priority, the spec's tag wins over this table.**

## Deferring findings with beads

To defer a P2 or P3 finding to a follow-up:

1. Create a beads ticket capturing reviewer name, severity, file, and quote.
2. Link the ticket in the PR description or as a reply to the reviewer's comment.
3. The reviewer accepts the deferral only when the beads ticket exists.

**P1 findings are not deferrable** — they must be fixed in-PR.

# Context

OpenForge Catalog is a content management system for 12,000+ 3D-printable STL files (~1,400 designs). Backend: Python/Flask deployed as a single AWS Lambda; PostgreSQL on serverless (hard connection limits); file storage on Cloudflare R2 (never AWS S3 for content). Frontend: Next.js compiled to a **static export** served from S3 — no server at runtime; all API calls are relative to `/api`. Data flows from a Dropbox-scanning pipeline into fixture JSON (`openforge/db/fixtures/`), loaded locally, and in a release by the fixtures Lambda. Schema changes use a hand-rolled versioned migration system (`openforge/db/schema/version_NN.py`). Tests: pytest (`tests/`), Jest (`src/**/__tests__/`), plus local-only integration tests (`integration_tests/`, Flask on :5328).

Active work includes a Thingiverse publish/sync tool (see beads epic `openforge_catalog-4kx`): v2 JWT auth, HAR-derived API contract, file-hash-based sync. That work handles live credentials (JWTs, refresh tokens, client secrets from `~/.profile.d/`) and HAR captures — hence `credentials-hygiene-reviewer`.
