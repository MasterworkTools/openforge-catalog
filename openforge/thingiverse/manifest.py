"""Per-thing manifest loading and validation.

A manifest is a YAML file describing one Thingiverse thing: its metadata
overrides and the set of files that belong in it. Metadata defaults come
from the catalog and a named template (see templates.py); the manifest
curates on top — per the project's zero-manual-entry philosophy, most
fields are optional.

Example:

    name: OpenForge 2.0 Cave Floors
    template: openforge2
    description: |
      Cave floors for the OpenForge 2.0 system.
    tags: [cave]
    files:
      models:
        - select:
            require: ["texture|cave", "shape|floor"]
            deny: ["build|s2w"]
        - full_name: tiles/cave/floors/special_floor.stl
        - md5: 0805ce8aae75eb8b2c8b95be3eab15d9
      images:
        - path: photos/cave_floors.jpg
      zips:
        - path: out/cave_floors.zip

Model entries are either a tag `select` query (resilient: newly scanned
files matching the query flow into the thing on the next sync) or an
explicit reference by `full_name` or `md5`.

Select semantics (matching the catalog's tag search engine):
- `require`: model must carry EVERY listed tag, matched exactly
  ("shape|floor" does not match a model tagged "shape|floor|corner")
- `accept`: model must carry at least one tag in the listed subtree,
  matched by hierarchical prefix ("shape|floor" matches
  "shape|floor|corner")
- `deny`: excludes models carrying any listed tag (exact match)
"""

from pathlib import Path
from typing import Dict, List

from yaml import YAMLError, safe_load

TOP_LEVEL_KEYS = {
    "name",
    "template",
    "description",
    "category",
    "license",
    "tags",
    "files",
}
FILE_SECTION_KEYS = {"models", "images", "zips", "others"}
MODEL_ENTRY_KEYS = {"select", "full_name", "md5"}
SELECT_KEYS = {"accept", "require", "deny"}

DEFAULT_TEMPLATE = "openforge2"


class ManifestError(Exception):
    """The manifest file is missing, malformed, or fails validation."""


def load_manifest(path: Path) -> Dict:
    """Load and validate a thing manifest.

    Args:
        path: Path to the manifest YAML file

    Returns:
        Validated manifest dict with defaults applied; includes
        "manifest_dir" (for resolving relative file paths) and
        "manifest_path"

    Raises:
        ManifestError: On missing file, bad YAML, or validation failure
    """
    path = Path(path)
    try:
        raw = safe_load(path.read_text())
    except FileNotFoundError as e:
        raise ManifestError(f"manifest not found: {path}") from e
    except (YAMLError, UnicodeDecodeError) as e:
        # narrow on purpose: PermissionError/IsADirectoryError etc. keep
        # their real type instead of being mislabeled as YAML problems
        raise ManifestError(f"manifest {path} is not valid YAML: {e}") from e
    if not isinstance(raw, dict):
        raise ManifestError(f"manifest {path} must be a YAML mapping")

    _validate_top_level(raw, path)
    manifest = {
        "name": raw["name"],
        "template": raw.get("template", DEFAULT_TEMPLATE),
        "description": raw.get("description", ""),
        "category": raw.get("category"),
        "license": raw.get("license"),
        "tags": _validate_string_list(raw.get("tags", []), "tags", path),
        "files": _validate_files(raw.get("files", {}), path),
        "manifest_path": str(path),
        "manifest_dir": str(path.parent),
    }
    return manifest


def _validate_top_level(raw: Dict, path: Path):
    unknown = set(raw) - TOP_LEVEL_KEYS
    if unknown:
        raise ManifestError(
            f"manifest {path} has unknown keys: {sorted(unknown)} "
            f"(allowed: {sorted(TOP_LEVEL_KEYS)})"
        )
    name = raw.get("name")
    if not name or not isinstance(name, str):
        raise ManifestError(f"manifest {path} requires a non-empty string 'name'")


def _validate_string_list(value, field: str, path: Path) -> List[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ManifestError(f"manifest {path}: '{field}' must be a list of strings")
    return value


def _validate_files(files, path: Path) -> Dict:
    if not isinstance(files, dict):
        raise ManifestError(f"manifest {path}: 'files' must be a mapping")
    unknown = set(files) - FILE_SECTION_KEYS
    if unknown:
        raise ManifestError(
            f"manifest {path}: unknown file sections {sorted(unknown)} "
            f"(allowed: {sorted(FILE_SECTION_KEYS)})"
        )
    validated = {
        "models": [_validate_model_entry(e, path) for e in files.get("models", [])],
        "images": [
            _validate_path_entry(e, "images", path) for e in files.get("images", [])
        ],
        "zips": [_validate_path_entry(e, "zips", path) for e in files.get("zips", [])],
        "others": [
            _validate_path_entry(e, "others", path) for e in files.get("others", [])
        ],
    }
    return validated


def _validate_model_entry(entry, path: Path) -> Dict:
    if not isinstance(entry, dict):
        raise ManifestError(f"manifest {path}: model entries must be mappings")
    keys = set(entry) & MODEL_ENTRY_KEYS
    if len(keys) != 1 or set(entry) - MODEL_ENTRY_KEYS:
        raise ManifestError(
            f"manifest {path}: each model entry needs exactly one of "
            f"{sorted(MODEL_ENTRY_KEYS)}, got {sorted(entry)}"
        )
    if "select" in entry:
        return {"select": _validate_select(entry["select"], path)}
    return dict(entry)


def _validate_select(select, path: Path) -> Dict:
    if not isinstance(select, dict):
        raise ManifestError(f"manifest {path}: 'select' must be a mapping")
    unknown = set(select) - SELECT_KEYS
    if unknown:
        raise ManifestError(
            f"manifest {path}: unknown select keys {sorted(unknown)} "
            f"(allowed: {sorted(SELECT_KEYS)})"
        )
    validated = {
        key: _validate_string_list(select.get(key, []), f"select.{key}", path)
        for key in SELECT_KEYS
    }
    if not (validated["accept"] or validated["require"]):
        raise ManifestError(
            f"manifest {path}: a select query needs at least one "
            "'accept' or 'require' tag"
        )
    return validated


def _validate_path_entry(entry, section: str, path: Path) -> Dict:
    if not isinstance(entry, dict) or set(entry) != {"path"}:
        raise ManifestError(
            f"manifest {path}: '{section}' entries must be mappings "
            "with exactly a 'path' key"
        )
    if not isinstance(entry["path"], str) or not entry["path"]:
        raise ManifestError(
            f"manifest {path}: '{section}' path must be a non-empty string"
        )
    return dict(entry)
