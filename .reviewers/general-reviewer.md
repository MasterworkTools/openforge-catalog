# general-reviewer
model: sonnet
verification: mixed — logic, contract and doc-command claims are demonstrated by running the code, query or command and quoting output (evidence-query); design-soundness against upcoming tickets is judgement and says so.
**Checks:** the whole PR, generalist pass — logic correctness against claims/docs (verified empirically, not by plausibility), domain/design soundness against upcoming beads tickets, contract fidelity against authoritative sources, cross-cutting interactions between the PR's parts, docstrings that contradict the code, design-level house style. Does not check PR-body wording or counts. Explicitly does NOT duplicate the specialist reviewers' dimensions.
**Spawn when:** **every PR, every round** — this repo has no Gemini/Cursor, so this reviewer is the broad-coverage pass. Never skipped for scope; last to retire under diminishing returns.
**Contents:** What to review (the generalist's beat): Logic correctness; Domain/design soundness; Contract fidelity; Cross-cutting integration; Docs and metadata accuracy; House style at the design level · Explicitly NOT this reviewer's beat · Method

Whole-PR generalist review. This repo has no Gemini Code Assist or Cursor Bugbot installed, so this reviewer stands in for the broad-coverage bot pass: it reviews the change **as a whole** for problems the specialist reviewers don't own.

**What to review (the generalist's beat):**

1. **Logic correctness** — does the code do what it claims? Trace the actual behavior of non-trivial logic against its docstrings, comments, PR description, and any docs it cites. Claims that don't match code are findings; verify empirically (run the code, run the query, decode the example) when practical rather than reasoning from plausibility.
2. **Domain/design soundness** — is the data model / API shape / control flow right for what the surrounding tickets need next? Read the relevant beads tickets (`bd show <id>`) for the work this PR feeds into; flag designs that force a rework one ticket later.
3. **Contract fidelity** — request/response shapes, field names and casing, status-code handling, schema/constraint semantics checked against the authoritative source (spec docs, the live DB, the dependency's actual source) rather than assumption.
4. **Cross-cutting integration** — interactions between the PR's parts, and between the PR and existing code, that no single-file review sees (e.g. a CHECK constraint interacting with an FK's ON DELETE action; a helper's semantics differing from the API-level shape it feeds).
5. **Docs and metadata accuracy** — PR body claims, docstrings, counts, commands. Run any command a doc tells the reader to run.
6. **House style at the design level** — openforge/CLAUDE.md and repo CLAUDE.md philosophy (fail-fast, functional-procedural, Unix tools, cost-conscious serverless), where the specialists' rules don't already cover it.

**Explicitly NOT this reviewer's beat** (the specialists own these — do not duplicate):
complexity thresholds, exception-handling patterns, test coverage/quality, resource leaks, dead code, logging discipline, package-data loading, migration mechanics, serverless cost rules, frontend conventions, hooks/async patterns, credentials hygiene. If a finding belongs to a specialist's spec, leave it to them; post it only if that specialist is not spawned for this PR and the issue is P1/P2.

**Severity:** P1 for a defect that ships wrong behaviour or breaks a deploy, P2 for one a reader or caller would trip on, P3 otherwise. Comment, docstring and doc wording is P3, and P2 only if the text would lead a reader to write a bug.

**Method:**

1. Read the PR body and every changed file IN FULL (not just hunks), plus enough surrounding code and referenced docs/tickets to judge intent.
2. Verify, don't vibe: run tests, run cited commands, query the live schema, trace call paths.
3. On verification rounds, check each claimed fix in the actual code, not the reply text.
