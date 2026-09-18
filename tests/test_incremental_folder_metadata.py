"""Test folder metadata processing in incremental scanner."""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import yaml

from openforge.data.incremental import IncrementalScanner, parse_files_incremental


class TestIncrementalFolderMetadata(unittest.TestCase):
    """Test folder metadata processing in incremental scanner."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            "FILE_DOMAIN": "https://example.com",
            "SKIP_S3_CACHE": True,
        }

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)

    def test_folder_metadata_applied_in_incremental(self):
        """Test that folder metadata is applied during incremental scanning."""
        # Create directory structure
        tiles_dir = os.path.join(self.test_dir, "tiles")
        dungeon_dir = os.path.join(tiles_dir, "dungeon_stone")
        floors_dir = os.path.join(dungeon_dir, "floors")
        os.makedirs(floors_dir)

        # Create root metadata with edit_all
        root_metadata = {".": {"edit_all": {"tags": {"add": ["category|terrain"]}}}}
        with open(os.path.join(self.test_dir, "metadata.yaml"), "w") as f:
            yaml.dump(root_metadata, f)

        # Create tiles metadata
        tiles_metadata = {
            ".": {
                "edit_all": {
                    "tags": {"add": ["category|tiles", "license|CC-BY-SA-4.0"]}
                }
            }
        }
        with open(os.path.join(tiles_dir, "metadata.yaml"), "w") as f:
            yaml.dump(tiles_metadata, f)

        # Create dungeon_stone metadata
        dungeon_metadata = {
            ".": {
                "edit_all": {
                    "tags": {
                        "add": ["texture|dungeon_stone"],
                        "remove": ["category|terrain"],
                    }
                }
            }
        }
        with open(os.path.join(dungeon_dir, "metadata.yaml"), "w") as f:
            yaml.dump(dungeon_metadata, f)

        # Create a test STL file with naming that won't cause parsing errors
        # Using metadata to set tags instead of relying on filename parsing
        test_file = os.path.join(floors_dir, "test.stl")
        with open(test_file, "wb") as f:
            f.write(b"solid test\nendsolid")

        # Create file-specific metadata to avoid filename parsing
        file_metadata = {
            "test.stl": {
                "auto": False,  # Disable automatic filename parsing
                "tags": ["shape|floor", "size|width|1", "size|depth|1"],
            }
        }
        with open(os.path.join(floors_dir, "metadata.yaml"), "w") as f:
            yaml.dump(file_metadata, f)

        # Create initial fixture data with a dummy entry to avoid empty fixture error
        fixture_data = [
            {
                "type": "model",
                "file_metadata": {
                    "full_name": "dummy.stl",
                    "file": "dummy.stl",
                    "md5": "dummy",
                    "size": 0,
                    "file_modified_at": "2024-01-01T00:00:00Z",
                },
                "tags": [],
                "config": {},
            }
        ]
        fixture_path = os.path.join(self.test_dir, "fixture.json")
        with open(fixture_path, "w") as f:
            json.dump(fixture_data, f)

        # Create incremental scanner
        scanner = IncrementalScanner(fixture_path, verbose=True)

        # List of files to process (relative to test_dir)
        files = ["tiles/dungeon_stone/floors/test.stl"]

        # Process files
        with patch("openforge.data.incremental.upload_file"):
            results = parse_files_incremental(
                self.test_dir,
                files,
                scanner,
                verbose=True,
                upload=False,
                config=self.config,
                dry_run=True,
                incremental=True,
            )

        # Check results (should have the test file and deprecated dummy)
        self.assertEqual(len(results), 2)

        # Find the non-deprecated result
        result = None
        for r in results:
            if not r.get("deprecated", False):
                result = r
                break

        self.assertIsNotNone(result, "Should have found non-deprecated result")

        # Check that all folder metadata was applied
        tags = result["tags"]

        # Should have tags from tiles metadata
        self.assertIn("category|tiles", tags)
        self.assertIn("license|CC-BY-SA-4.0", tags)

        # Should have texture from dungeon_stone metadata
        self.assertIn("texture|dungeon_stone", tags)

        # Should NOT have category|terrain (removed by dungeon_stone metadata)
        self.assertNotIn("category|terrain", tags)

        # Should have tags from filename parsing
        self.assertIn("shape|floor", tags)
        self.assertIn("size|width|1", tags)
        self.assertIn("size|depth|1", tags)

    def test_folder_metadata_with_existing_file(self):
        """Test folder metadata applied to existing files in incremental scan."""
        # Create directory structure
        floors_dir = os.path.join(self.test_dir, "floors")
        os.makedirs(floors_dir)

        # Create folder metadata
        folder_metadata = {
            ".": {"edit_all": {"tags": {"add": ["project|openforge", "version|2.0"]}}}
        }
        with open(os.path.join(self.test_dir, "metadata.yaml"), "w") as f:
            yaml.dump(folder_metadata, f)

        # Create a test STL file
        test_file = os.path.join(floors_dir, "test.stl")
        with open(test_file, "wb") as f:
            f.write(b"solid test\nendsolid")

        # Create file metadata to disable automatic parsing
        file_metadata = {"test.stl": {"auto": False, "tags": ["shape|floor"]}}
        with open(os.path.join(floors_dir, "metadata.yaml"), "w") as f:
            yaml.dump(file_metadata, f)

        # Create initial fixture data with existing entry
        existing_entry = {
            "type": "model",
            "file_metadata": {
                "full_name": "floors/test.stl",
                "file": "test.stl",
                "md5": "abc123",
                "size": 100,
                "file_modified_at": "2024-01-01T00:00:00Z",
            },
            "tags": ["shape|floor"],
            "config": {},
        }
        fixture_data = [existing_entry]
        fixture_path = os.path.join(self.test_dir, "fixture.json")
        with open(fixture_path, "w") as f:
            json.dump(fixture_data, f)

        # Create incremental scanner
        scanner = IncrementalScanner(fixture_path, verbose=True)

        # List of files to process
        files = ["floors/test.stl"]

        # Process files
        with patch("openforge.data.incremental.upload_file"):
            results = parse_files_incremental(
                self.test_dir,
                files,
                scanner,
                verbose=True,
                upload=False,
                config=self.config,
                dry_run=True,
                incremental=True,
            )

        # Check results (may have 2 if MD5 changed: deprecation + new)
        self.assertGreaterEqual(len(results), 1)

        # Find the non-deprecated result
        result = None
        for r in results:
            if not r.get("deprecated", False):
                result = r
                break

        self.assertIsNotNone(result, "Should have found non-deprecated result")

        # Check that folder metadata was applied
        tags = result["tags"]

        # The basic requirement is that folder metadata was applied
        self.assertIn("project|openforge", tags)
        self.assertIn("version|2.0", tags)

        # File-specific tags from metadata.yaml are applied when a file is reprocessed
        self.assertIn("shape|floor", tags)


if __name__ == "__main__":
    unittest.main()
