# guide-document-reviewer
model: sonnet
verification: evidence-query — resolves the guide against the local test database and quotes counts; greps the base ref for reader support and quotes the miss; wording of blurbs is judgement.
**Checks:** guide fixtures whose predicates select the wrong parts (unreachable parts, mismatched blurb counts), a new guide or blueprint `config` construct that ships in the same PR as the reader that understands it, schema edits that let unknown keys through.
**Spawn when:** diff touches `openforge/db/fixtures/guides/**`, `openforge/guides/**`, `openforge/openapi/schemas/guide.yaml` or `config.yaml`, `src/services/guide-service.ts`, `src/hooks/use-guide-state.ts` or `src/components/guides/**`. Skip otherwise.
**Contents:** Your focus · What to flag: Code must lead, data follow; Predicates that miss parts; Blurbs that disagree with the set; Silent ignore of unknown constructs · Do NOT flag · Proof

**Your focus:** a stored guide document and a blueprint `config` are validated only on write, by the loader on the new image; nothing validates them on read, and a reader that does not know a construct ignores it (200, wrong parts). Check that the data a PR adds is understood by every reader that is live while it is served, and that the selection it expresses is the one the guide's text claims.

**What to flag:**

1. **Data and its reader in one PR (P1).** A fixture or schema edit introduces a key, step, refinement, role or `config` construct, and the Python reader (`openforge/guides/resolve.py`, `validation.py`) or the bundle reader (`src/services/guide-service.ts`, `src/components/guides/**`) that interprets it is added in the same diff. The old reader serves the new document during a deploy and drops the construct. Prove it: `git show origin/test:<reader file> | grep -n '<construct>'` returns nothing at the base ref while the diff's fixture uses it. Fix: split into two releases, reader first. A guide construct needs both readers at base; a `config` construct needs only the bundle.
2. **A choice, role or predicate that leaves parts unreachable (P2).** Resolve each changed choice against the local test database (call shape in `tests/test_guides_resolve.py`, or `GET /api/guides/<slug>/resolve`) and report: parts the role selects, parts reachable through some answer, parts reachable through none. Quote the numbers. Unreachable parts that a user could reasonably want are the finding.
3. **Blurb and label counts that do not describe the selected set (P3).** Text that states a count or a property ("durable", "one-piece") is checked against the same resolve output.
4. **Schema loosening (P1).** `guide.yaml` / `config.yaml` change that adds `additionalProperties: true` or removes a `required` entry, so write-time validation stops catching an unknown construct.
5. **Unknown construct dropped on read (P2).** New reader code that skips an unrecognised key silently (continue, default, `.get` with fallback) where the guide engine should reject on write. Show the construct and the line that ignores it.

**Do NOT flag:**

- Guide copy and wording that is accurate against the resolve output.
- Reader-only changes that add support with no fixture using it yet: that is the correct first release.
- Fixture JSON for blueprints (parts) that adds rows or tags only; rows and tags are additive.
- Pre-existing unreachable parts the PR did not touch (note once, P3).

**Proof:** state which query you ran and quote its output. If the test database is not available say so and label the finding a hypothesis.
