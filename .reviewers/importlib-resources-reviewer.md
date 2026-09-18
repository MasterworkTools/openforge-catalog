# importlib-resources-reviewer

Review Python code for **correct package data access**. Package data files (fixture JSON/YAML, SQL, templates) must be loaded via `importlib.resources`, not `Path(__file__).parent`. The `__file__` pattern silently breaks when a module moves — and **breaks outright in the Lambda zip deployment**, where the package layout differs from the dev checkout.

This repo already follows the correct convention — see `openforge/db/fixtures/__init__.py` (`from importlib import resources as impresources`). New code must match it.

**FLAG when a file in the `openforge/` package contains:**

- `Path(__file__).parent / "data"` (or any path navigation from `__file__`) used to locate bundled data
- `os.path.dirname(__file__)` for the same purpose
- `__file__.parents[N]` for sibling resources

**Acceptable pattern:**

```python
from importlib import resources as impresources

data_file = impresources.files("openforge.db.fixtures").joinpath("blueprints/cave.json")
data = json.loads(data_file.read_text())
```

**Do NOT flag:**

- `__file__` used for **write paths** (tests writing next to themselves, scripts emitting output) — resources are read-only by definition.
- `__file__` references in `tests/` / `integration_tests/` — tests aren't packaged.
- `__file__` in entry-point scripts under `bin/` that are not part of the package surface.
- Runtime data paths that are *deliberately external* to the package (Dropbox scan roots, `~/.openforge`-style config) — those are configuration, not package data.

**Review approach:**

1. Grep the PR diff for `Path(__file__)`, `dirname(__file__)`, `__file__.parents`.
2. For each hit in package code, check whether the path resolves to a bundled data file. If so, recommend the `impresources` form used by `openforge/db/fixtures/`.
3. For each new package data file added under `openforge/`, verify it will ship in the Lambda package (declared in the packaging config / not excluded), otherwise it 404s only in production.
