"""
I/O utilities for OpenForge file processing.

This module provides shared functionality for S3 operations, file uploads,
and thumbnail creation used by both scanner.py and incremental.py.
"""

import os
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, Set, Tuple

import boto3
import sh
from botocore.client import Config
from botocore.exceptions import ClientError
from PIL import Image


def get_s3_client(config: Dict) -> boto3.client:
    """Create S3 client for Cloudflare R2.

    Args:
        config: Configuration dictionary with AWS credentials and endpoint

    Returns:
        Configured boto3 S3 client

    Raises:
        KeyError: If required credentials are missing from both config and environment
    """
    # Get credentials from config or environment variables
    endpoint_url = config.get("CLOUDFLARE_ENDPOINT") or os.environ.get(
        "CLOUDFLARE_ENDPOINT"
    )
    access_key_id = config.get("AWS_ACCESS_KEY_ID") or os.environ.get(
        "AWS_ACCESS_KEY_ID"
    )
    secret_access_key = config.get("AWS_SECRET_ACCESS_KEY") or os.environ.get(
        "AWS_SECRET_ACCESS_KEY"
    )

    # Validate required credentials
    if not endpoint_url:
        raise KeyError(
            "CLOUDFLARE_ENDPOINT not found in config or environment variables"
        )
    if not access_key_id:
        raise KeyError("AWS_ACCESS_KEY_ID not found in config or environment variables")
    if not secret_access_key:
        raise KeyError(
            "AWS_SECRET_ACCESS_KEY not found in config or environment variables"
        )

    s3_client = boto3.client(
        service_name="s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    return s3_client


def create_image(name: str, url: str, sprite_metadata: Optional[Dict] = None) -> Dict:
    """Create image object for fixture.

    Args:
        name: Image name
        url: Image URL
        sprite_metadata: Optional sprite sheet metadata (grid layout, camera angles)

    Returns:
        Image object dictionary
    """
    image = {"image_name": name, "image_url": url}
    if sprite_metadata:
        image["sprite_metadata"] = sprite_metadata
    return image


def get_s3_key_cache(
    s3_client: boto3.client, config: Dict, verbose: bool = False
) -> Set[str]:
    """Pre-fetch all S3 object keys for efficient upload checking.

    Performance testing showed this approach is significantly faster than
    individual head_object calls for each file, especially for buckets with
    many objects. This prevents excessive back-and-forth API calls.

    Args:
        s3_client: Configured S3 client
        config: Configuration dictionary containing S3_BUCKET_NAME
        verbose: Whether to print debug statements

    Returns:
        Set of existing S3 object keys
    """
    bucket = config.get("S3_BUCKET_NAME", "openforge-models")
    if verbose:
        sys.stderr.write(f"DEBUG: Pre-fetching S3 keys from bucket: {bucket}\n")

    s3_key_cache = set()

    paginator = s3_client.get_paginator("list_objects_v2")
    page_count = 0
    for page in paginator.paginate(Bucket=bucket):
        page_count += 1
        for obj in page.get("Contents", []):
            s3_key_cache.add(obj["Key"])

    return s3_key_cache


def upload_file(
    file_metadata: Dict,
    file_path: str,
    s3_client: boto3.client,
    object_path: str,
    s3_key_cache: Optional[Set[str]] = None,
    config: Optional[Dict] = None,
    verbose: bool = False,
) -> str:
    """Upload file to S3 storage.

    Args:
        file_metadata: File metadata dictionary
        file_path: Path to file to upload
        s3_client: Configured S3 client
        object_path: S3 object path prefix
        s3_key_cache: Optional cache of existing S3 keys
            (use get_s3_key_cache for best performance)
        config: Configuration dictionary containing S3_BUCKET_NAME
        verbose: Whether to print debug statements

    Returns:
        S3 object name
    """
    bucket = (
        config.get("S3_BUCKET_NAME", "openforge-models")
        if config
        else "openforge-models"
    )
    _, fn = os.path.split(file_path)
    parts = fn.split(".")
    extension = parts.pop()
    object_name = (
        f"{object_path}/{file_metadata['md5'][:6]}/{file_metadata['md5']}.{extension}"
    )

    # Check cache first
    if s3_key_cache is not None and object_name in s3_key_cache:
        return object_name

    try:
        s3_client.head_object(Bucket=bucket, Key=object_name)
    except ClientError as ce:
        if ce.response["Error"]["Code"] == "404":
            sys.stderr.write(f"Uploading: {file_path}\n")
            with open(file_path, "rb") as file_handle:
                s3_client.upload_fileobj(file_handle, bucket, object_name)
        else:
            raise ce

    return object_name


def create_thumbnail(file_path: str) -> str:
    """Create thumbnail for STL file.

    Args:
        file_path: Path to STL file

    Returns:
        Path to created thumbnail
    """
    path, fn = os.path.split(file_path)
    parts = fn.split(".")
    _ = parts.pop()
    base = ".".join(parts)
    thumb_path = os.path.join(path, f"{base}-thumb.png")
    sh.stl_thumb(file_path, thumb_path)
    return thumb_path


# Sprite sheet camera angles configuration
# 10 isometric-perspective angles: 4 cardinal + 4 diagonal + 2 vertical
# Arranged in 45-degree increments around the model for even coverage
SPRITE_ANGLES = [
    {"index": 0, "name": "front", "camera_pos": [0, -4, 2]},  # Front view
    {"index": 1, "name": "front-right", "camera_pos": [3, -3, 2]},  # 45° from front
    {"index": 2, "name": "right", "camera_pos": [4, 0, 2]},  # Right view
    {"index": 3, "name": "back-right", "camera_pos": [3, 3, 2]},  # 45° from right
    {"index": 4, "name": "back", "camera_pos": [0, 4, 2]},  # Back view
    {"index": 5, "name": "back-left", "camera_pos": [-3, 3, 2]},  # 45° from back
    {"index": 6, "name": "left", "camera_pos": [-4, 0, 2]},  # Left view
    {"index": 7, "name": "front-left", "camera_pos": [-3, -3, 2]},  # 45° from left
    {"index": 8, "name": "top", "camera_pos": [0, -2, 5]},  # Top view
    {"index": 9, "name": "bottom", "camera_pos": [0, -2, -3]},  # Bottom view
]


def _generate_angle_tile(
    stl_path: str, output_path: str, camera_pos: List[float], size: int = 512
) -> None:
    """Generate a single thumbnail tile at specified camera position.

    Args:
        stl_path: Path to STL file
        output_path: Path to save the generated tile
        camera_pos: Camera position [x, y, z]
        size: Size of square tile (default 512)

    Raises:
        subprocess.CalledProcessError: If stl-thumb command fails
    """
    # Use subprocess to properly handle negative camera position values
    # stl-thumb now has allow_hyphen_values(true) to handle negative values
    # Run in /tmp to avoid permission issues with temp files
    cmd = [
        "stl-thumb",
        stl_path,
        output_path,
        "-s",
        str(size),
        "-c",
        str(camera_pos[0]),
        str(camera_pos[1]),
        str(camera_pos[2]),
    ]
    subprocess.run(
        cmd, check=True, capture_output=True, text=True, cwd=tempfile.gettempdir()
    )


def _combine_tiles_to_sprite(
    tile_paths: List[str], sprite_path: str, rows: int = 2, cols: int = 5
) -> None:
    """Combine individual tiles into a sprite sheet.

    Args:
        tile_paths: List of paths to tile images (must match rows * cols)
        sprite_path: Path to save the combined sprite sheet
        rows: Number of rows in grid (default 2)
        cols: Number of columns in grid (default 5)

    Raises:
        ValueError: If number of tiles doesn't match grid dimensions
    """
    if len(tile_paths) != rows * cols:
        raise ValueError(
            f"Expected {rows * cols} tiles for {rows}x{cols} grid, "
            f"got {len(tile_paths)}"
        )

    # Load first tile to get dimensions
    first_tile = Image.open(tile_paths[0])
    tile_width, tile_height = first_tile.size
    first_tile.close()

    # Create sprite sheet
    sprite_width = cols * tile_width
    sprite_height = rows * tile_height
    sprite = Image.new("RGBA", (sprite_width, sprite_height), (0, 0, 0, 0))

    # Paste each tile into the sprite
    for idx, tile_path in enumerate(tile_paths):
        row = idx // cols
        col = idx % cols
        x = col * tile_width
        y = row * tile_height

        tile = Image.open(tile_path)
        sprite.paste(tile, (x, y))
        tile.close()

    # Save sprite sheet
    sprite.save(sprite_path, "PNG")
    sprite.close()


def create_sprite_sheet(file_path: str, tile_size: int = 512) -> Tuple[str, Dict]:
    """Create multi-angle sprite sheet for STL file.

    Generates 10 isometric-perspective angles and combines them into a
    single sprite sheet PNG. Temporary tile files are cleaned up after
    sprite generation.

    Args:
        file_path: Path to STL file
        tile_size: Size of each square tile (default 512)

    Returns:
        Tuple of (sprite_path, sprite_metadata):
        - sprite_path: Path to generated sprite sheet PNG
        - sprite_metadata: Dictionary containing grid layout and camera angles
    """
    path, fn = os.path.split(file_path)
    parts = fn.split(".")
    _ = parts.pop()
    base = ".".join(parts)

    # Create temporary directory for tiles
    with tempfile.TemporaryDirectory() as temp_dir:
        tile_paths = []

        # Generate each angle tile
        for angle in SPRITE_ANGLES:
            tile_path = os.path.join(temp_dir, f"{base}-angle-{angle['index']}.png")
            _generate_angle_tile(file_path, tile_path, angle["camera_pos"], tile_size)
            tile_paths.append(tile_path)

        # Combine tiles into sprite sheet (use temp dir - not useful in Dropbox)
        sprite_path = os.path.join(tempfile.gettempdir(), f"{base}-sprite.png")
        _combine_tiles_to_sprite(tile_paths, sprite_path, rows=2, cols=5)

        # Temporary tile files are automatically cleaned up when context exits

    # Build sprite metadata
    sprite_metadata = {
        "grid_rows": 2,
        "grid_cols": 5,
        "tile_size": tile_size,
        "angles": SPRITE_ANGLES,
        "default_angle": 0,
    }

    return sprite_path, sprite_metadata


def create_and_upload_thumbnail(
    file_metadata: Dict,
    stl_path: str,
    s3_client,
    s3_key_cache: Set[str],
    config: Dict,
    verbose: bool = False,
    use_sprites: bool = True,
) -> Dict:
    """Create and upload thumbnail or sprite sheet for an STL file.

    Handles both legacy single thumbnails and new multi-angle sprite sheets
    based on the use_sprites flag. Uploads to R2 and cleans up local files.

    Args:
        file_metadata: File metadata dictionary (must include 'md5')
        stl_path: Path to STL file
        s3_client: Configured S3 client
        s3_key_cache: Set of existing S3 keys for upload optimization
        config: Configuration dictionary
        verbose: Enable verbose output
        use_sprites: If True, generate sprite sheet; if False, single thumbnail

    Returns:
        Image dictionary for fixture (with sprite_metadata if applicable)

    Raises:
        Exception: If thumbnail/sprite generation or upload fails
    """
    if use_sprites:
        # Generate multi-angle sprite sheet
        sprite_path, sprite_metadata = create_sprite_sheet(stl_path)

        try:
            # Upload sprite to R2
            sprite_address = upload_file(
                file_metadata,
                sprite_path,
                s3_client,
                "sprites",
                s3_key_cache,
                config,
                verbose,
            )

            # Create image entry with sprite metadata
            sprite_url = f"{config['FILE_DOMAIN']}/{sprite_address}"
            return create_image("thumbnail", sprite_url, sprite_metadata)

        except Exception as e:
            if verbose:
                sys.stderr.write(f"ERROR: Failed to upload sprite sheet: {e}\n")
            raise
        finally:
            # Clean up local sprite file (even on error)
            if os.path.exists(sprite_path):
                os.remove(sprite_path)

    else:
        # Generate legacy single thumbnail
        thumb_path = create_thumbnail(stl_path)

        try:
            # Upload thumbnail to R2
            thumb_address = upload_file(
                file_metadata,
                thumb_path,
                s3_client,
                "thumbnails",
                s3_key_cache,
                config,
                verbose,
            )

            # Create image entry without sprite metadata
            thumb_url = f"{config['FILE_DOMAIN']}/{thumb_address}"
            return create_image("thumbnail", thumb_url)

        except Exception as e:
            if verbose:
                sys.stderr.write(f"ERROR: Failed to upload thumbnail: {e}\n")
            raise
        finally:
            # Clean up local thumbnail file (even on error)
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
