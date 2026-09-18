"""Tests for openforge.thingiverse.manifest (loading and validation)."""

import pytest

from openforge.thingiverse.manifest import ManifestError, load_manifest


def write_manifest(tmp_path, content):
    path = tmp_path / "thing.yaml"
    path.write_text(content)
    return path


MINIMAL = """
name: Cave Floors
"""

FULL = """
name: Cave Floors
template: openforge2
description: |
  Cave floors for OpenForge 2.0.
category: Custom Category
license: CC-BY-SA
tags: [cave, floors]
files:
  models:
    - select:
        require: ["texture|cave", "shape|floor"]
        deny: ["build|s2w"]
    - md5: 0805ce8aae75eb8b2c8b95be3eab15d9
    - full_name: tiles/cave/floors/special.stl
  images:
    - path: photos/shot.jpg
  zips:
    - path: out/set.zip
"""


def test_minimal_manifest_gets_defaults(tmp_path):
    manifest = load_manifest(write_manifest(tmp_path, MINIMAL))
    assert manifest["name"] == "Cave Floors"
    assert manifest["template"] == "openforge2"
    assert manifest["description"] == ""
    assert manifest["tags"] == []
    assert manifest["files"] == {
        "models": [],
        "images": [],
        "zips": [],
        "others": [],
    }
    assert manifest["manifest_dir"] == str(tmp_path)


def test_full_manifest_round_trip(tmp_path):
    manifest = load_manifest(write_manifest(tmp_path, FULL))
    assert manifest["category"] == "Custom Category"
    assert manifest["license"] == "CC-BY-SA"
    assert manifest["tags"] == ["cave", "floors"]
    models = manifest["files"]["models"]
    assert models[0] == {
        "select": {
            "accept": [],
            "require": ["texture|cave", "shape|floor"],
            "deny": ["build|s2w"],
        }
    }
    assert models[1] == {"md5": "0805ce8aae75eb8b2c8b95be3eab15d9"}
    assert models[2] == {"full_name": "tiles/cave/floors/special.stl"}
    assert manifest["files"]["images"] == [{"path": "photos/shot.jpg"}]


def test_missing_file_raises(tmp_path):
    with pytest.raises(ManifestError, match="not found"):
        load_manifest(tmp_path / "nope.yaml")


def test_invalid_yaml_raises(tmp_path):
    path = write_manifest(tmp_path, "name: [unclosed")
    with pytest.raises(ManifestError, match="not valid YAML"):
        load_manifest(path)


def test_non_mapping_raises(tmp_path):
    path = write_manifest(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(ManifestError, match="must be a YAML mapping"):
        load_manifest(path)


def test_missing_name_raises(tmp_path):
    path = write_manifest(tmp_path, "tags: [cave]\n")
    with pytest.raises(ManifestError, match="requires a non-empty string 'name'"):
        load_manifest(path)


def test_unknown_top_level_key_raises(tmp_path):
    path = write_manifest(tmp_path, "name: X\ndescriptoin: typo\n")
    with pytest.raises(ManifestError, match="unknown keys.*descriptoin"):
        load_manifest(path)


def test_unknown_file_section_raises(tmp_path):
    path = write_manifest(tmp_path, "name: X\nfiles:\n  sculptures: []\n")
    with pytest.raises(ManifestError, match="unknown file sections"):
        load_manifest(path)


def test_model_entry_needs_exactly_one_kind(tmp_path):
    path = write_manifest(
        tmp_path,
        "name: X\nfiles:\n  models:\n    - md5: abc\n      full_name: def\n",
    )
    with pytest.raises(ManifestError, match="exactly one of"):
        load_manifest(path)


def test_empty_select_raises(tmp_path):
    path = write_manifest(
        tmp_path,
        "name: X\nfiles:\n  models:\n    - select:\n        deny: [a]\n",
    )
    with pytest.raises(ManifestError, match="at least one 'accept' or 'require'"):
        load_manifest(path)


def test_select_unknown_key_raises(tmp_path):
    path = write_manifest(
        tmp_path,
        "name: X\nfiles:\n  models:\n    - select:\n        needs: [a]\n",
    )
    with pytest.raises(ManifestError, match="unknown select keys"):
        load_manifest(path)


def test_image_entry_must_be_path_mapping(tmp_path):
    path = write_manifest(
        tmp_path, "name: X\nfiles:\n  images:\n    - photos/shot.jpg\n"
    )
    with pytest.raises(ManifestError, match="exactly a 'path' key"):
        load_manifest(path)


def test_tags_must_be_strings(tmp_path):
    path = write_manifest(tmp_path, "name: X\ntags: [1, 2]\n")
    with pytest.raises(ManifestError, match="must be a list of strings"):
        load_manifest(path)
