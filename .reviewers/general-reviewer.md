# general-reviewer
model: sonnet
verification: mixed — logic, contract and doc-command claims are demonstrated by running the code, query or command and quoting output (evidence-query); design-soundness against upcoming tickets is judgement and says so.
**Checks:** the whole PR, generalist pass — logic correctness against claims/docs (verified empirically, not by plausibility), domain/design soundness against upcoming beads tickets, contract fidelity against authoritative sources, cross-cutting interactions between the PR's parts, runnable docs, design-level house style, and the PR's base branch. Explicitly does NOT duplicate the specialist reviewers' dimensions, re-litigate comment wording, or restate what CI enforces.
**Spawn when:** **every PR, every round** — this repo has no Gemini/Cursor, so this reviewer is the broad-coverage pass. Never skipped for scope; last to retire under diminishing returns.
**Contents:** What to check: Logic correctness; Domain/design soundness; Contract fidelity; Cross-cutting integration; Runnable docs; House style at the design level; Base branch · Do NOT flag · Running things · Severity

Whole-PR generalist review. This repo has no Gemini Code Assist or Cursor Bugbot, so this reviewer is the broad-coverage pass: it reviews the change **as a whole** for problems the specialist reviewers don't own.

**What to check:**

1. **Logic correctness** — does the code do what its docstrings, comments, PR description and cited docs say it does? Trace non-trivial logic and run it.
2. **Domain/design soundness** — is the data model / API shape / control flow right for what the next tickets need? Read the tickets this PR feeds into (`bd show <id>`) and quote the line a design conflicts with.
3. **Contract fidelity** — request/response shapes, field names and casing, status codes, schema/constraint semantics, checked against the authoritative source (`openforge/openapi/`, the schema in `openforge/db/schema/`, the dependency's actual source), not assumption.
4. **Cross-cutting integration** — interactions between the PR's parts, and between the PR and existing code, that no single-file review sees (a CHECK constraint against an FK's ON DELETE; a helper's semantics differing from the API shape it feeds).
5. **Runnable docs** — run every command a changed doc tells the reader to run.
6. **House style at the design level** — `CLAUDE.md` and `openforge/CLAUDE.md` philosophy (fail-fast, functional-procedural, cost-conscious serverless) where no specialist rule covers it.
7. **Base branch** — `gh pr view <PR> --json baseRefName`. PRs target `test`; a PR against `main` that is not an explicit production release is a P1.

**Do NOT flag:**

- Anything a specialist owns: complexity, exception handling, test coverage, resource leaks, dead code, logging, package-data loading, migration mechanics, serverless cost, frontend conventions, hooks/async, credentials.
- Comment and docstring wording — `comment-analyzer` owns it. A docstring that contradicts the code is in scope as a *logic* finding about the code.
- A design the PR body, a ticket or `CLAUDE.md` states as Devon's decision. Evidence that the code does not do what the decision says is a finding; an argument that the decision is wrong is not.
- What CI enforces: ruff, ESLint, `tsc`, the test suites.
- A future-ticket conflict you cannot quote from the ticket.

**Running things:** reviewers run in parallel. Mutate only inside your own `git worktree add` under a temp dir, and run pytest only against your own Postgres container on a free port — `conftest` truncates the schema, so a shared `openforge_test` poisons every concurrent run. Never touch a deployed database.

**Severity:** P1 a bug that ships wrong behaviour or a PR against `main`; P2 a contract or design defect that forces rework; P3 everything else. Each finding is a line comment at the line it concerns.
