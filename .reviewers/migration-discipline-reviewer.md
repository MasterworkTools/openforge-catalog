# migration-discipline-reviewer

Review PRs for **database schema discipline**. All schema changes go through the versioned migration system in `openforge/db/schema/` — never ad-hoc DDL from application code, fixtures, or scripts.

**The pattern (see `openforge/db/schema/version_12.py` as the reference):**

```python
@SchemaVersionDecorator(NN)
class SchemaVersionNN(SchemaBase):
    def up_impl(self, curs: cursor):
        self.add_thing_table(curs)          # small named helper methods
        self.create_thing_indexes(curs)

    def down_impl(self, curs: cursor):      # every up has a working down
        self.drop_thing_indexes(curs)
        self.drop_thing_table(curs)
```

**What to flag:**

1. **DDL outside the migration system (P1):** `CREATE TABLE` / `ALTER TABLE` / `CREATE INDEX` / `DROP ...` in application code, route handlers, fixtures loaders, or scripts. The only home for DDL is a `version_NN.py` migration (and the SQL helper modules it calls).

2. **Missing or stubbed `down_impl` (P2):** every migration must reverse cleanly. A `down_impl` that's `pass` or that doesn't mirror `up_impl` step-for-step (in reverse order) leaves the test↔main promotion path without a rollback. If a step is genuinely irreversible (data-destroying), it must say so in a comment and the docstring.

3. **Version number problems (P1):** duplicate `@SchemaVersionDecorator(NN)` numbers, or a number that doesn't follow the current maximum. Check existing files in `openforge/db/schema/` for the highest version before assigning. (Note: version 15 is historically absent — gaps exist; duplicates are the bug.)

4. **Missing module docstring (P3):** each migration opens with a docstring summarizing every change it makes (see version_12.py). The docstring is the changelog — it must list all tables/columns/indexes/functions touched.

5. **Monolithic `up_impl` (P2):** the house style is small named helper methods per logical step, called in sequence from `up_impl`/`down_impl` — not one giant method of inline SQL. This mirrors the CLAUDE.md one-screen rule.

6. **Schema change without downstream updates (P2):** a new table/column that application code reads must also appear in the relevant SQL helper module (`openforge/db/sql/`); if fixture data populates it, the fixture loader and (when applicable) the API upsert path must handle the new shape. A migration that lands alone with no consumer is fine when explicitly staged — say so in the PR.

7. **Data migrations mixed silently into schema migrations (P3):** backfills/UPDATEs inside a schema migration are allowed but must be called out in the docstring, be idempotent where possible, and be sized for serverless (a full-table rewrite on the production DB should be flagged for discussion, not discovered).

8. **Raw string interpolation in migration SQL (P1):** use `psycopg.sql` composition (`sql.SQL`, `sql.Identifier`) for any dynamic identifiers, matching the existing imports in migration files. Static DDL strings are fine.

**Do NOT flag:**

- `CREATE TEMPORARY TABLE` or session-scoped constructs in query code.
- Test fixtures that build schema in a throwaway test database via the migration runner itself.
- The absence of an Alembic-style framework — this repo's hand-rolled versioning is deliberate; review within its conventions, don't suggest replacing it.

**Review approach:**

1. Grep the diff for DDL keywords outside `openforge/db/schema/`.
2. For each new `version_NN.py`: verify decorator number is max+1 and unique, `down_impl` mirrors `up_impl` reversed, docstring enumerates the changes, helpers are small and named.
3. Cross-check new tables/columns against `openforge/db/sql/` accessors and fixture loaders touched (or explicitly staged) in the same PR.
