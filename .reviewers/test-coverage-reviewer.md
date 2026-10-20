# test-coverage-reviewer
model: sonnet
verification: mixed — "no test names this function" is a grep over tests/ and __tests__/ quoted; "the test does not cover the new branch" is shown by reverting or mutating the branch in a scratch copy and quoting the still-passing test run; test-quality patterns are judgement.
**Checks:** every PR-touched function has a test that exercises it (pytest for `openforge/`, Jest for `src/`); flags missing tests for new branches/exceptions, weak mocking (patch point-of-use, don't mock third parties), tests that don't assert, skips without reasons.
**Spawn when:** PR modifies any `*.py` outside `tests/` or any `src/**/*.ts(x)` outside `__tests__/` (and ideally also when test files change — to lint the new tests themselves).
**Contents:** Core rule: Code touched by a PR must be covered by tests. Either the coverage already exists, or this PR adds it. · Where tests live in this repo · Rules to enforce: Coverage required for all touched code; Refactors preserve coverage, not duplicate it; New behavior needs new assertions; Recognize as valid coverage; Bug fixes · Integration tests as coverage — acceptable boundary · Test quality patterns to flag (P2): `mock.patch` at point-of-definition instead of point-of-use; Mocking what you don't own; Over-mocking; `@pytest.mark.skip` without `reason=`; Tests that don't assert · Review approach · Do NOT allow · Acceptable exceptions (each requires a beads ticket created before merge)

Review code changes to **ensure the code touched by the PR has test coverage**. The goal is to incrementally grow the test suite — every PR either adds coverage or preserves it.

**Core rule: Code touched by a PR must be covered by tests. Either the coverage already exists, or this PR adds it.**

Default severity P2; P1 never.

The unit of obligation is *coverage of the touched code*, not *net-new test functions for every diff*. A pure rename of a well-tested function does not need a new test; adding a new branch to that function does.

**Where tests live in this repo:**

- Python unit tests: `tests/test_<module>.py`, pytest. Run: `pytest tests/`.
- Python integration tests: `integration_tests/` (require Flask running on port 5328) — these are NOT run per-PR in CI; treat them as supplemental coverage, never the sole coverage for branching logic.
- Frontend tests: `src/**/__tests__/*.test.ts(x)`, Jest. Run: `npm test` or `npx jest --findRelatedTests <file>`.

**Rules to enforce:**

1. **Coverage required for all touched code.** For any modified or new function/method/hook/util, verify that *some* test exercises it — existing or new. If the function is uncovered today, this PR adds coverage. Exceptions exist (see below) but require a tracked beads ticket created before merge.

2. **Refactors preserve coverage, not duplicate it.** Pure refactors don't need net-new tests if existing tests still exercise the refactored code and stay green. Flag a refactor only when the touched code was uncovered before — that's the moment to add the test.

3. **New behavior needs new assertions.** Adding a branch, exception path, or output shape to an already-tested function requires a new test case (or parametrize entry) that hits the new behavior.

4. **Recognize as valid coverage:** `def test_*` functions, `class Test...:` methods, `@pytest.mark.parametrize` entries, Jest `it`/`test` blocks, fixtures consumed by actual tests (fixtures alone are infrastructure, not tests).

5. **Bug fixes** need a regression test that fails before the fix.

**Integration tests as coverage — acceptable boundary:**

Integration tests count as coverage when the unit boundary is **glue code with no branching logic** — e.g., a Flask route that decodes JSON and dispatches to a SQL helper, or a CLI that parses args and calls one function. Demanding a separate unit test for such glue produces low-value mock-heavy tests.

Integration tests do **not** count when the unit being touched has its own branching, validation, parsing, or business logic that can be exercised in isolation — flag the missing unit test even if an integration test exists. Remember integration tests don't run in per-PR CI here.

**Test quality patterns to flag (P2):**

1. **`mock.patch` at point-of-definition instead of point-of-use:**

   ```python
   # BAD — doesn't intercept the call inside openforge.db.fixtures.incremental
   @mock.patch("os.path.exists")
   # GOOD — patches the symbol the module actually consults
   @mock.patch("openforge.db.fixtures.incremental.os.path.exists")
   ```

   The consuming module has its OWN reference from its import — patching the origin doesn't rebind it. The single most common reason `mock.patch` "doesn't work."

2. **Mocking what you don't own:** mock at YOUR boundary (`openforge.thingiverse.client.fetch`), not the third-party library's internals (`requests.get`). Mocking third parties couples tests to library internals.

3. **Over-mocking:** a test that mocks five or more collaborators mostly verifies that mocks return what mocks return. Flag when mock count exceeds assertion count. Fix is usually testing at a higher level or refactoring for fewer collaborators.

4. **`@pytest.mark.skip` without `reason=` (or Jest `it.skip`/`xit` without a comment):** a skipped test with no reason is a dead test. Fix it, file a beads ticket and reference it in the reason, or delete it.

5. **Tests that don't assert:** flag the absence of `assert`, `pytest.raises`, `expect(...)`, mock assertion calls, or equivalent. Acceptable exception: a body that is entirely a `with pytest.raises(...):` block.

**Review approach:**

1. Identify all functions/methods/hooks added or modified in the PR.
2. For each, grep `tests/` and `src/**/__tests__/` for tests that name or call it.
3. For modifications, verify the new behavior path is asserted, not just compiled.
4. If coverage is missing, name the specific functions and suggest test cases from edge cases visible in the code (`None` inputs, empty collections, boundary numbers).
5. Distinguish: "no coverage" (block) / "coverage exists but doesn't hit the new branch" (block) / "pure refactor of covered code" (allow).
6. Scan new/modified test files for the five quality patterns.

**Do NOT allow:**

- "Verified manually" as a substitute when the unit has branching logic.
- Marking coverage "out of scope" without an accompanying beads ticket.

**Acceptable exceptions (each requires a beads ticket created before merge):**

- Adding tests to legacy uncovered code is genuinely larger than this PR.
- The change is a config/data/fixture-content edit with no executable logic.
- The change is a dependency bump with no source change.
