"""Test data for documentation system

This module provides test data for:
- Blueprint documentation (instructions and changelogs)
- Tag documentation
- Documentation images
"""

import uuid
from typing import Any, Dict, List

# Test blueprint documentation
TEST_BLUEPRINT_DOCUMENTATION = [
    {
        "id": str(uuid.uuid4()),
        "blueprint_id": "test-blueprint-1",
        "document": """# Dungeon Stone Wall Instructions

This is a basic dungeon stone wall tile for OpenForge.

## Assembly Instructions

1. Print the wall piece
2. Print the base piece
3. Glue the wall to the base
4. Allow to dry completely

## Tips

- Use super glue for best results
- Sand the contact surfaces for better adhesion
- Print with 20% infill for strength

![Wall Assembly](wall_assembly.jpg)
""",
        "document_type": "instructions",
        "is_live": True,
        "created_at": "2023-01-01T12:00:00+00:00",
        "updated_at": "2023-01-01T12:00:00+00:00",
    },
    {
        "id": str(uuid.uuid4()),
        "blueprint_id": "test-blueprint-1",
        "document": """# Version 2.1 Changelog

## Changes Made

- Improved wall thickness for better durability
- Added reinforcement ribs on the back
- Reduced print time by 15%
- Fixed minor geometry issues

## Breaking Changes

None - this version is fully compatible with previous versions.
""",
        "document_type": "changelog",
        "is_live": True,
        "created_at": "2023-01-01T12:00:00+00:00",
        "updated_at": "2023-01-01T12:00:00+00:00",
    },
    {
        "id": str(uuid.uuid4()),
        "blueprint_id": "test-blueprint-2",
        "document": """# Cave Floor Tile Instructions

This cave floor tile features natural stone textures.

## Printing Tips

- Use 0.2mm layer height for best detail
- Enable supports for overhangs
- Print with 25% infill for optimal strength/weight ratio

## Assembly

This tile is self-contained and requires no assembly.

![Cave Floor](cave_floor_detail.jpg)
""",
        "document_type": "instructions",
        "is_live": True,
        "created_at": "2023-01-01T12:00:00+00:00",
        "updated_at": "2023-01-01T12:00:00+00:00",
    },
]

# Test tag documentation
TEST_TAG_DOCUMENTATION = [
    {
        "id": str(uuid.uuid4()),
        "tag": ["texture", "dungeon_stone"],
        "document": """# Dungeon Stone Texture

The dungeon stone texture is the flagship texture for OpenForge tiles.

## Characteristics

- Rough, weathered stone appearance
- Dark gray color scheme
- Suitable for underground environments
- Compatible with all connection systems

## Usage

This texture is used for:
- Walls and floors
- Doors and windows
- Decorative elements
- Scatter terrain

![Dungeon Stone Sample](dungeon_stone_sample.jpg)
""",
        "document_type": "instructions",
        "is_live": True,
        "created_at": "2023-01-01T12:00:00+00:00",
        "updated_at": "2023-01-01T12:00:00+00:00",
    },
    {
        "id": str(uuid.uuid4()),
        "tag": ["texture", "cave"],
        "document": """# Cave Texture

The cave texture features natural stone formations.

## Characteristics

- Organic, irregular stone patterns
- Light to medium gray tones
- Natural weathering effects
- Suitable for cavern environments

## Usage

This texture is used for:
- Cave floors and walls
- Natural rock formations
- Underground passages
- Cavern entrances

![Cave Texture Sample](cave_texture_sample.jpg)
""",
        "document_type": "instructions",
        "is_live": True,
        "created_at": "2023-01-01T12:00:00+00:00",
        "updated_at": "2023-01-01T12:00:00+00:00",
    },
    {
        "id": str(uuid.uuid4()),
        "tag": ["connection", "openforge"],
        "document": """# OpenForge Connection System

The OpenForge connection system provides secure, magnetic connections.

## Features

- Magnetic attraction for easy assembly
- Snap-fit design for secure connections
- Compatible with all OpenForge textures
- Reusable and durable

## Assembly

1. Align the connection points
2. The magnets will automatically attract
3. Press firmly to engage the snap-fit
4. To disconnect, pull apart with moderate force

![OpenForge Connection](openforge_connection.jpg)
""",
        "document_type": "instructions",
        "is_live": True,
        "created_at": "2023-01-01T12:00:00+00:00",
        "updated_at": "2023-01-01T12:00:00+00:00",
    },
    {
        "id": str(uuid.uuid4()),
        "tag": ["shape", "wall"],
        "document": """# Wall Shape

Walls are vertical barriers that create room boundaries.

## Types

- Straight walls
- Corner walls
- Door walls
- Window walls

## Assembly

Walls typically require:
- A base piece for stability
- Optional decorative elements
- Connection system compatibility

![Wall Assembly](wall_assembly.jpg)
""",
        "document_type": "instructions",
        "is_live": True,
        "created_at": "2023-01-01T12:00:00+00:00",
        "updated_at": "2023-01-01T12:00:00+00:00",
    },
]

# Test documentation images
TEST_DOCUMENTATION_IMAGES = [
    {
        "id": str(uuid.uuid4()),
        "image_name": "wall_assembly",
        "image_url": "https://example.com/images/wall_assembly.jpg",
        "image_type": "documentation",
        "created_at": "2023-01-01T12:00:00+00:00",
        "updated_at": "2023-01-01T12:00:00+00:00",
    },
    {
        "id": str(uuid.uuid4()),
        "image_name": "cave_floor_detail",
        "image_url": "https://example.com/images/cave_floor_detail.jpg",
        "image_type": "documentation",
        "created_at": "2023-01-01T12:00:00+00:00",
        "updated_at": "2023-01-01T12:00:00+00:00",
    },
    {
        "id": str(uuid.uuid4()),
        "image_name": "dungeon_stone_sample",
        "image_url": "https://example.com/images/dungeon_stone_sample.jpg",
        "image_type": "documentation",
        "created_at": "2023-01-01T12:00:00+00:00",
        "updated_at": "2023-01-01T12:00:00+00:00",
    },
    {
        "id": str(uuid.uuid4()),
        "image_name": "cave_texture_sample",
        "image_url": "https://example.com/images/cave_texture_sample.jpg",
        "image_type": "documentation",
        "created_at": "2023-01-01T12:00:00+00:00",
        "updated_at": "2023-01-01T12:00:00+00:00",
    },
    {
        "id": str(uuid.uuid4()),
        "image_name": "openforge_connection",
        "image_url": "https://example.com/images/openforge_connection.jpg",
        "image_type": "documentation",
        "created_at": "2023-01-01T12:00:00+00:00",
        "updated_at": "2023-01-01T12:00:00+00:00",
    },
]

# Test deprecated blueprints
TEST_DEPRECATED_BLUEPRINTS = [
    {
        "id": "deprecated-blueprint-1",
        "blueprint_name": "Old Dungeon Wall v1.0",
        "deprecated": True,
        "successor_id": "test-blueprint-1",
        "successor_name": "Dungeon Stone Wall v2.1",
        "created_at": "2023-01-01T12:00:00+00:00",
        "updated_at": "2023-01-01T12:00:00+00:00",
    },
    {
        "id": "deprecated-blueprint-2",
        "blueprint_name": "Basic Cave Floor v1.0",
        "deprecated": True,
        "successor_id": "test-blueprint-2",
        "successor_name": "Cave Floor Tile v1.5",
        "created_at": "2023-01-01T12:00:00+00:00",
        "updated_at": "2023-01-01T12:00:00+00:00",
    },
]


def get_test_blueprint_documentation() -> List[Dict[str, Any]]:
    """Get test blueprint documentation data."""
    return TEST_BLUEPRINT_DOCUMENTATION


def get_test_tag_documentation() -> List[Dict[str, Any]]:
    """Get test tag documentation data."""
    return TEST_TAG_DOCUMENTATION


def get_test_documentation_images() -> List[Dict[str, Any]]:
    """Get test documentation images data."""
    return TEST_DOCUMENTATION_IMAGES


def get_test_deprecated_blueprints() -> List[Dict[str, Any]]:
    """Get test deprecated blueprints data."""
    return TEST_DEPRECATED_BLUEPRINTS


def get_all_test_data() -> Dict[str, List[Dict[str, Any]]]:
    """Get all test data for the documentation system."""
    return {
        "blueprint_documentation": get_test_blueprint_documentation(),
        "tag_documentation": get_test_tag_documentation(),
        "documentation_images": get_test_documentation_images(),
        "deprecated_blueprints": get_test_deprecated_blueprints(),
    }
