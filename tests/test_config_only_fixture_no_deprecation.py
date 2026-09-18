"""Test that configuration-only fixtures don't trigger deprecation."""

from unittest.mock import MagicMock

from openforge.db.fixtures.incremental import IncrementalFixturesLoader


class TestConfigOnlyFixtureNoDeprecation:
    """Test that fixtures with only configuration blueprints don't deprecate files."""

    def test_config_only_fixture_no_deprecation(self):
        """Test that config-only fixtures don't deprecate any files."""
        # Create a mock connection
        mock_conn = MagicMock()
        mock_curs = MagicMock()

        # Create loader
        loader = IncrementalFixturesLoader(mock_conn, verbose=False)

        # Mock existing blueprints - mix of file-based and config blueprints
        existing_blueprints = {
            "tiles/dungeon_stone/floor.stl": {
                "id": "file-123",
                "full_name": "tiles/dungeon_stone/floor.stl",
                "file_md5": "abc123",
                "blueprint_type": "model",
                "deprecated": False,
                "tags": [],
                "images": [],
            },
            "tiles/cave/wall.stl": {
                "id": "file-456",
                "full_name": "tiles/cave/wall.stl",
                "file_md5": "def456",
                "blueprint_type": "model",
                "deprecated": False,
                "tags": [],
                "images": [],
            },
            "Existing Config Blueprint": {
                "id": "config-789",
                "blueprint_name": "Existing Config Blueprint",
                "blueprint_type": "blueprint",
                "deprecated": False,
                "tags": [],
                "images": [],
            },
        }

        # Mock _load_existing_blueprints to return our test data
        loader._load_existing_blueprints = MagicMock(return_value=existing_blueprints)

        # Configuration-only fixture data (like blueprints.s2w.internal_corner.yaml)
        fixture_data = [
            {
                "name": "S2W: Wall on Tile: Internal Corner (Single Piece)",
                "type": "blueprint",
                "tags": [
                    "object|tile",
                    "object|tile|wall_on_tile",
                    "build|s2w",
                    "build|s2w|single_piece",
                    "shape|internal_corner",
                ],
                "config": {
                    "parts": [
                        {
                            "name": "column",
                            "tags": {
                                "require": [
                                    {"tag": "shape|column|corner"},
                                    {"tag": "build|s2w"},
                                ]
                            },
                        }
                    ]
                },
            },
            {
                "name": "S2W: Wall on Tile: Internal Corner (Modular)",
                "type": "blueprint",
                "tags": [
                    "object|tile",
                    "object|tile|wall_on_tile",
                    "build|s2w",
                    "build|s2w|modular",
                ],
                "config": {"parts": []},
            },
        ]

        # Call compare_fixture_data
        result = loader.compare_fixture_data(fixture_data, curs=mock_curs)

        # Verify that NO blueprints were marked for deprecation
        assert len(result.deprecated) == 0
        assert len(result.added) == 2  # The two new config blueprints

    def test_mixed_fixture_only_deprecates_in_namespace(self):
        """Test that a mixed fixture only deprecates files in its namespace."""
        # Create a mock connection
        mock_conn = MagicMock()
        mock_curs = MagicMock()

        # Create loader
        loader = IncrementalFixturesLoader(mock_conn, verbose=False)

        # Mock existing blueprints
        existing_blueprints = {
            "tiles/dungeon_stone/floor.stl": {
                "id": "file-123",
                "full_name": "tiles/dungeon_stone/floor.stl",
                "file_md5": "abc123",
                "file_size": 1000,
                "file_modified_at": "2024-01-01",
                "blueprint_type": "model",
                "deprecated": False,
                "tags": [],
                "images": [],
            },
            "tiles/dungeon_stone/missing.stl": {
                "id": "file-missing",
                "full_name": "tiles/dungeon_stone/missing.stl",
                "file_md5": "missing123",
                "file_size": 2000,
                "file_modified_at": "2024-01-01",
                "blueprint_type": "model",
                "deprecated": False,
                "tags": [],
                "images": [],
            },
            "tiles/cave/wall.stl": {
                "id": "file-456",
                "full_name": "tiles/cave/wall.stl",
                "file_md5": "def456",
                "file_size": 3000,
                "file_modified_at": "2024-01-01",
                "blueprint_type": "model",
                "deprecated": False,
                "tags": [],
                "images": [],
            },
        }

        # Mock _load_existing_blueprints to return our test data
        loader._load_existing_blueprints = MagicMock(return_value=existing_blueprints)

        # Mock _find_deprecated_blueprint_by_md5 to return None (no existing deprecated)
        loader._find_deprecated_blueprint_by_md5 = MagicMock(return_value=None)

        # Mixed fixture with both file and config blueprints
        fixture_data = [
            {
                "file_metadata": {
                    "full_name": "tiles/dungeon_stone/floor.stl",
                    "file_name": "floor.stl",
                    "md5": "abc123",
                    "size": 1000,
                    "file_modified_at": "2024-01-01",
                },
                "tags": ["shape|floor"],
                "images": [],
            },
            {
                "name": "Dungeon Stone Config",
                "type": "blueprint",
                "tags": ["config|dungeon_stone"],
                "config": {},
            },
        ]

        # Call compare_fixture_data
        result = loader.compare_fixture_data(fixture_data, curs=mock_curs)

        # Should only deprecate the missing dungeon_stone file, not the cave file
        assert len(result.deprecated) == 1
        assert result.deprecated[0]["id"] == "file-missing"
        assert result.deprecated[0]["full_name"] == "tiles/dungeon_stone/missing.stl"
