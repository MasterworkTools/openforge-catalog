"""Tests for openforge.thingiverse.assembler."""

import pytest
from psycopg.rows import dict_row

import openforge.db.sql.blueprints as blueprint_sql
import openforge.db.sql.tags as tag_sql
from openforge.thingiverse.assembler import (
    AssemblyError,
    assemble_thing,
    load_template,
    metadata_hash,
)
from openforge.thingiverse.manifest import load_manifest

from .test_helpers import create_test_blueprint


def make_manifest(tmp_path, content):
    path = tmp_path / "thing.yaml"
    path.write_text(content)
    return load_manifest(path)


def insert_model(curs, name, md5, tags, full_name=None):
    data = create_test_blueprint(
        blueprint_name=name,
        blueprint_type="model",
        file_md5=md5,
        full_name=full_name or f"tiles/test/{name}.stl",
        file_name=f"{name}.stl",
    )
    row = blueprint_sql.insert_blueprint(curs, data)
    for tag in tags:
        tag_sql.insert_tag(curs, row["id"], tag)
    return row


class TestTemplates:
    def test_openforge2_template_loads(self):
        template = load_template("openforge2")
        assert template["license"] == "Creative Commons - Attribution - Share Alike"
        assert template["category"] == "Toy & Game Accessories"
        assert "OpenForge" in template["tags"]
        assert "patreon.com/masterworktools" in template["description_boilerplate"]

    def test_unknown_template_raises(self):
        with pytest.raises(AssemblyError, match="unknown template"):
            load_template("does-not-exist")


class TestMetadataAssembly:
    def test_defaults_from_template(self, test_db, tmp_path):
        manifest = make_manifest(tmp_path, "name: Cave Floors\n")
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                thing = assemble_thing(curs, manifest)
        metadata = thing["metadata"]
        assert metadata["name"] == "Cave Floors"
        assert metadata["license"] == "Creative Commons - Attribution - Share Alike"
        assert metadata["category"] == "Toy & Game Accessories"
        assert "dnd" in metadata["tags"]
        # boilerplate footer present even with no per-thing description
        assert "patreon.com/masterworktools" in metadata["description"]

    def test_manifest_overrides_template(self, test_db, tmp_path):
        manifest = make_manifest(
            tmp_path,
            "name: X\nlicense: CC0\ncategory: Other\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                thing = assemble_thing(curs, manifest)
        assert thing["metadata"]["license"] == "CC0"
        assert thing["metadata"]["category"] == "Other"

    def test_description_composes_prose_then_boilerplate(self, test_db, tmp_path):
        manifest = make_manifest(tmp_path, "name: X\ndescription: Per-thing prose.\n")
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                thing = assemble_thing(curs, manifest)
        description = thing["metadata"]["description"]
        assert description.startswith("Per-thing prose.")
        assert description.index("Per-thing prose.") < description.index("patreon")

    def test_tags_merge_dedupes_case_insensitively(self, test_db, tmp_path):
        manifest = make_manifest(tmp_path, "name: X\ntags: [cave, openforge, DND]\n")
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                thing = assemble_thing(curs, manifest)
        tags = thing["metadata"]["tags"]
        assert "cave" in tags
        # template already has OpenForge and dnd; no duplicates added
        assert len([t for t in tags if t.lower() == "openforge"]) == 1
        assert len([t for t in tags if t.lower() == "dnd"]) == 1

    def test_metadata_hash_is_stable_and_sensitive(self):
        a = {"name": "X", "tags": ["a", "b"]}
        assert metadata_hash(a) == metadata_hash({"tags": ["a", "b"], "name": "X"})
        assert metadata_hash(a) != metadata_hash({"name": "Y", "tags": ["a", "b"]})


class TestModelResolution:
    def test_select_by_tags(self, test_db, tmp_path):
        manifest = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  models:\n"
            "    - select:\n        require: ['texture|cave', 'shape|floor']\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                insert_model(
                    curs, "cave_floor_1", "md5a", ["texture|cave", "shape|floor"]
                )
                insert_model(
                    curs, "cave_floor_2", "md5b", ["texture|cave", "shape|floor"]
                )
                insert_model(curs, "cave_wall", "md5c", ["texture|cave", "shape|wall"])
                thing = assemble_thing(curs, manifest)
        md5s = {m["file_md5"] for m in thing["files"]["models"]}
        assert md5s == {"md5a", "md5b"}

    def test_select_deny_excludes(self, test_db, tmp_path):
        manifest = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  models:\n"
            "    - select:\n"
            "        require: ['texture|cave']\n"
            "        deny: ['build|s2w']\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                insert_model(curs, "plain", "md5a", ["texture|cave"])
                insert_model(curs, "s2w", "md5b", ["texture|cave", "build|s2w"])
                thing = assemble_thing(curs, manifest)
        md5s = {m["file_md5"] for m in thing["files"]["models"]}
        assert md5s == {"md5a"}

    def test_select_matching_nothing_raises(self, test_db, tmp_path):
        manifest = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  models:\n"
            "    - select:\n        require: ['texture|unobtainium']\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                with pytest.raises(AssemblyError, match="matched no models"):
                    assemble_thing(curs, manifest)

    def test_explicit_md5_and_missing_md5(self, test_db, tmp_path):
        manifest = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  models:\n    - md5: md5a\n",
        )
        missing = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  models:\n    - md5: nope\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                insert_model(curs, "one", "md5a", [])
                thing = assemble_thing(curs, manifest)
                assert [m["file_md5"] for m in thing["files"]["models"]] == ["md5a"]
                with pytest.raises(AssemblyError, match="no blueprint with md5"):
                    assemble_thing(curs, missing)

    def test_explicit_full_name(self, test_db, tmp_path):
        manifest = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  models:\n    - full_name: tiles/test/special.stl\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                insert_model(
                    curs, "special", "md5s", [], full_name="tiles/test/special.stl"
                )
                thing = assemble_thing(curs, manifest)
        assert [m["file_md5"] for m in thing["files"]["models"]] == ["md5s"]

    def test_missing_full_name_raises(self, test_db, tmp_path):
        manifest = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  models:\n    - full_name: tiles/nope.stl\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                with pytest.raises(AssemblyError, match="no blueprint with full_name"):
                    assemble_thing(curs, manifest)

    def test_accept_matches_by_hierarchical_prefix(self, test_db, tmp_path):
        manifest = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  models:\n"
            "    - select:\n        accept: ['shape|floor']\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                insert_model(curs, "corner", "md5a", ["shape|floor|corner"])
                insert_model(curs, "plain", "md5b", ["shape|floor"])
                insert_model(curs, "wall", "md5c", ["shape|wall"])
                thing = assemble_thing(curs, manifest)
        md5s = {m["file_md5"] for m in thing["files"]["models"]}
        assert md5s == {"md5a", "md5b"}

    def test_multiple_accepts_are_any_not_all(self, test_db, tmp_path):
        # each model carries only ONE of the two accept subtrees; ANY
        # semantics must match both (the engine ANDs accepts natively —
        # the assembler unions per-accept queries to get ANY)
        manifest = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  models:\n"
            "    - select:\n"
            "        accept: ['texture|cave', 'texture|dungeon_stone']\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                insert_model(curs, "cave", "md5a", ["texture|cave|smooth"])
                insert_model(curs, "stone", "md5b", ["texture|dungeon_stone"])
                insert_model(curs, "other", "md5c", ["texture|tudor"])
                thing = assemble_thing(curs, manifest)
        md5s = {m["file_md5"] for m in thing["files"]["models"]}
        assert md5s == {"md5a", "md5b"}

    def test_model_rows_have_stable_shape_across_paths(self, test_db, tmp_path):
        manifest = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  models:\n"
            "    - select:\n        require: ['texture|cave']\n"
            "    - md5: md5x\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                insert_model(curs, "selected", "md5a", ["texture|cave"])
                insert_model(curs, "explicit", "md5x", [])
                thing = assemble_thing(curs, manifest)
        models = thing["files"]["models"]
        assert len(models) == 2
        assert set(models[0].keys()) == set(models[1].keys())
        assert "file_md5" in models[0] and "storage_address" in models[0]

    def test_explicit_ref_to_non_model_raises(self, test_db, tmp_path):
        manifest = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  models:\n    - md5: md5comp\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                data = create_test_blueprint(
                    blueprint_name="composite",
                    blueprint_type="blueprint",
                    file_md5="md5comp",
                )
                blueprint_sql.insert_blueprint(curs, data)
                with pytest.raises(AssemblyError, match="not a model"):
                    assemble_thing(curs, manifest)

    def test_model_without_md5_raises(self, test_db, tmp_path):
        manifest = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  models:\n    - full_name: tiles/test/no_md5.stl\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                data = create_test_blueprint(
                    blueprint_name="no_md5",
                    blueprint_type="model",
                    full_name="tiles/test/no_md5.stl",
                )
                # the helper generates an md5 when given None; force NULL
                data["file_md5"] = None
                blueprint_sql.insert_blueprint(curs, data)
                with pytest.raises(AssemblyError, match="has no file_md5"):
                    assemble_thing(curs, manifest)

    def test_ambiguous_full_name_raises(self, test_db, tmp_path):
        manifest = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  models:\n    - full_name: tiles/test/dupe.stl\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                dupe = "tiles/test/dupe.stl"
                insert_model(curs, "dupe_a", "md5a", [], full_name=dupe)
                insert_model(curs, "dupe_b", "md5b", [], full_name=dupe)
                with pytest.raises(AssemblyError, match="ambiguous"):
                    assemble_thing(curs, manifest)

    def test_select_limit_ceiling_raises(self, test_db, tmp_path, monkeypatch):
        import openforge.thingiverse.assembler as assembler_mod

        monkeypatch.setattr(assembler_mod, "SELECT_LIMIT", 2)
        manifest = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  models:\n"
            "    - select:\n        require: ['texture|cave']\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                insert_model(curs, "one", "md5a", ["texture|cave"])
                insert_model(curs, "two", "md5b", ["texture|cave"])
                with pytest.raises(AssemblyError, match="ceiling"):
                    assemble_thing(curs, manifest)

    def test_overlapping_entries_dedupe_by_md5(self, test_db, tmp_path):
        manifest = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  models:\n"
            "    - select:\n        require: ['texture|cave']\n"
            "    - md5: md5a\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                insert_model(curs, "cave_floor", "md5a", ["texture|cave"])
                thing = assemble_thing(curs, manifest)
        assert [m["file_md5"] for m in thing["files"]["models"]] == ["md5a"]


class TestLocalFiles:
    def test_relative_paths_resolve_against_manifest_dir(self, test_db, tmp_path):
        (tmp_path / "photos").mkdir()
        (tmp_path / "photos" / "shot.jpg").write_bytes(b"jpg")
        manifest = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  images:\n    - path: photos/shot.jpg\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                thing = assemble_thing(curs, manifest)
        assert thing["files"]["images"] == [
            {"path": str(tmp_path / "photos" / "shot.jpg")}
        ]

    def test_missing_local_file_raises(self, test_db, tmp_path):
        manifest = make_manifest(
            tmp_path,
            "name: X\nfiles:\n  zips:\n    - path: out/nope.zip\n",
        )
        with test_db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                with pytest.raises(AssemblyError, match="zips file not found"):
                    assemble_thing(curs, manifest)
