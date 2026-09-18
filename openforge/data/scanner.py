"""
OpenForge file scanner library.

This module provides functionality for scanning and parsing OpenForge STL files,
extracting metadata, tags, and generating database records.
"""

import datetime
import hashlib
import json
import os
import re
import sys

import sh
from yaml import safe_load

from openforge.openapi import validate_schema

from . import sizes
from .io import (
    create_and_upload_thumbnail,
    get_s3_client,
    get_s3_key_cache,
    upload_file,
)
from .metadata import (
    apply_default_metadata,
    apply_folder_metadata_edit_all,
    apply_metadata,
    get_all_folder_metadata,
    get_metadata_file,
    metadata_auto,
    metadata_ignore,
)


def parse_texture(texture, tags):
    parts = texture.split("%")
    main = parts.pop(0)
    for m in main.split(","):
        s = []
        if m.find("+") > 0:
            s = m.split("+")
            m = s.pop(0)
        tags.add(("texture", m))
        for x in s:
            tags.add(("texture", m, x))
    if len(parts) == 0:
        return
    subtex = parts.pop(0)
    for o in subtex.split(","):
        s = []
        if o.find("+") > 0:
            s = o.split("+")
            o = s.pop(0)
        tags.add(("texture", m, o))
        for x in s:
            tags.add(("texture", m, o, x))


def parse_form(form, tags):
    texture, form = form.split("#")
    parse_texture(texture, tags)
    parts = form.split(",")
    for part in parts:
        parse_form_part(part, tags)


def parse_form_part(part, tags):
    parts = part.split("+")
    form = parts.pop(0)
    t = []
    t.append(("component", form))
    tags.add(("component", form))
    for fp in parts:
        t.append(("component", form, fp))
        tags.add(("component", form, fp))


def parse_size(size, tags):
    for tag in sizes[size]:
        tags.add(tag)


def _normalize_size(size):
    """Normalize size strings by converting whole decimal numbers to integers.

    Examples:
        "2.0x2.0" -> "2x2"
        "1.5x1.5" -> "1.5x1.5" (unchanged)
        "2.0" -> "2"
        "2.5" -> "2.5" (unchanged)
    """
    # Split by 'x' to handle compound sizes
    parts = size.split("x")
    normalized_parts = []

    for part in parts:
        try:
            # Try to convert to float
            num = float(part)
            # Check if it's a whole number
            if num.is_integer():
                normalized_parts.append(str(int(num)))
            else:
                normalized_parts.append(part)
        except ValueError:
            # Not a number, keep as is
            normalized_parts.append(part)

    return "x".join(normalized_parts)


def parse_connection(connection, tags):
    def _add_connections(connections):
        to_add = set()
        for connection in connections:
            if "+" in connection:
                options = connection.split("+")
                connection = options.pop(0)
                for option in options:
                    to_add.add(("connection", connection, option))
            to_add.add(("connection", connection))
        _handle_side(to_add)
        tags.update(to_add)

    def _handle_side(to_add):
        has_side = False
        has_side_option = False
        side = None
        for tag in to_add:
            if tag[0] == "connection" and tag[1] == "side":
                has_side = True
                if len(tag) > 2:
                    has_side_option = True
                else:
                    side = tag

        if has_side and not has_side_option:
            to_add.add((side[0], side[1], "openlock"))

    parts = connection.split(",")
    _add_connections(parts)


def parse_filename(file, tags):
    try:
        parts = file["file"].split(".")
        parts.pop()  # Remove .stl
        form = parts.pop(0)
        size = parts.pop(0)
        connection = None

        # Get the last part as connection
        if len(parts) > 0:
            connection = parts.pop()

        # Handle compound decimal sizes (e.g., 1.5x1.5, 2.0x2.0)
        # Join remaining parts that start with digits to handle cases like:
        # - "1.5x1.5" split into ["1", "5x1", "5"]
        # - "2.5" split into ["2", "5"]
        # - "2.0x2.0" split into ["2", "0x2", "0"]
        while len(parts) > 0 and re.match(r"^\d", parts[0]):
            size = f"{size}.{parts.pop(0)}"

        # Normalize size: convert "2.0x2.0" to "2x2"
        # This handles cases where whole numbers are written as decimals
        size = _normalize_size(size)

        assert connection is not None, f"No connection found in {file['file']}"
        assert len(parts) == 0, f"Extra parts after connection: {parts}"

        parse_form(form, tags)
        parse_size(size, tags)
        parse_connection(connection, tags)
    except Exception as e:
        sys.stderr.write(f"Can't parse: {file['full_name']}\n")
        sys.stderr.write(f"{e}\n")
        raise e


def parse_path(file, tags):
    def _component_filter(builds, tags):
        components = set()
        for build in builds:
            components.add(("component", build[0]))
            components.add(("component", build[1]))
        for component in components:
            tags.discard(component)

    path = file["path"]
    builds = [
        ("s2w", "s2w"),
        ("separate_wall", "separate wall"),
        ("wall_on_tile", "wall on tile"),
        ("s_system", "s-system"),
        ("thick_wall", "thick wall"),
    ]
    for build in builds:
        if build[0] in path:
            tags.add(("build", build[1]))
    _component_filter(builds, tags)

    components = [("bases", "base")]
    for component in components:
        if component[0] in path:
            tags.add(("component", component[1]))

    if "floor" in path:
        tags.add(("shape", "floor"))
    if "floor+special" in path:
        tags.add(("shape", "floor"))
    if "wall" in path:
        tags.add(("shape", "wall"))
    if "wall+special" in path:
        tags.add(("shape", "wall"))
    if "curved_floors" in path:
        tags.add(("shape", "floor"))
        tags.add(("shape", "curved"))
    if "curved_walls" in path:
        tags.add(("shape", "wall"))
        tags.add(("shape", "curved"))
    if "primary_floors" in path:
        tags.add(("shape", "floor"))
        tags.add(("shape", "square"))
    if "primary_walls" in path:
        tags.add(("shape", "wall"))
        tags.add(("shape", "square"))


def filter_s_system(tags):
    if ("build", "s-system") not in tags:
        return
    addtags = set()
    removetags = set()
    for tag in tags:
        if tag[0] == "component" and tag[1].startswith("s_"):
            removetags.add(tag)
            addtags.add(("component", tag[1].replace("s_", "")))
    tags.update(addtags)
    for tag in removetags:
        tags.discard(tag)


def filter_shape(tags):
    def _check_wall_alone(tags):
        count = 0
        for tag in tags:
            if tag[0] == "component":
                if tag != ("component", "wall"):
                    count += 1
        if count == 0:
            return True
        return False

    def _check_floor_alone(tags):
        count = 0
        for tag in tags:
            if tag[0] == "component":
                count += 1
        if count == 1:
            return True
        return False

    def _check_wall_low(tags):
        if ("component", "wall", "low") in tags:
            tags.discard(("component", "wall"))
            tags.add(("shape", "wall", "low"))
            tags.discard(("shape", "wall"))

    def _check_columns(tags):
        tags.discard(("component", "column"))
        if ("component", "column", "low") in tags:
            tags.add(("shape", "column", "low"))
            tags.discard(("shape", "column"))
            tags.discard(("component", "column", "low"))

    def _copy_base_shapes(tags):
        copy_tags = [
            "square",
            "angled",
            "curved",
            "convex",
            "concave",
            "radial",
            "corner",
            "wall",
        ]
        for tag in copy_tags:
            if ("shape", "base", tag) in tags:
                tags.add(("shape", tag))

    def _check_floor_shapes(tags):
        if ("shape", "floor") not in tags:
            return
        count = 0
        for tag in tags:
            if tag[0] == "shape":
                count += 1
        if count != 1:
            return
        tags.add(("shape", "square"))

    def _move_tag_chain(tags, old, new):
        def _compare_old(tag, old):
            if len(tag) < len(old):
                return False
            for i, v in enumerate(old):
                if tag[i] != v:
                    return False
            return True

        def _swap_tag(tag, old, new):
            # Replace the prefix of tag (length of old) with new,
            # then append the rest of tag
            return tuple(new) + tag[len(old) :]

        swap_tags = []
        for tag in tags:
            if _compare_old(tag, old):
                swap_tags.append(tag)
        replacements = []
        for tag in swap_tags:
            replacements.append(_swap_tag(tag, old, new))
        tags.update(replacements)
        for tag in swap_tags:
            tags.discard(tag)
        return tags

    def _handle_decorations(tags):
        _move_tag_chain(tags, ["component", "air"], ["decoration", "symbol", "air"])
        _move_tag_chain(
            tags, ["component", "air_symbol"], ["decoration", "symbol", "air"]
        )
        _move_tag_chain(
            tags, ["shape", "floor", "air_symbol"], ["decoration", "symbol", "air"]
        )
        _move_tag_chain(
            tags, ["component", "beezlebub"], ["decoration", "symbol", "beezlebub"]
        )
        _move_tag_chain(
            tags,
            ["component", "beezlebub_symbol"],
            ["decoration", "symbol", "beezlebub"],
        )
        _move_tag_chain(
            tags,
            ["shape", "floor", "beezlebub_symbol"],
            ["decoration", "symbol", "beezlebub"],
        )
        _move_tag_chain(
            tags, ["component", "celtic_knot"], ["decoration", "celtic_knot"]
        )
        _move_tag_chain(tags, ["component", "demon"], ["decoration", "demon"])
        _move_tag_chain(
            tags, ["component", "dragon_skulls"], ["decoration", "dragon_skulls"]
        )
        _move_tag_chain(tags, ["component", "earth"], ["decoration", "symbol", "earth"])
        _move_tag_chain(
            tags, ["component", "earth_symbol"], ["decoration", "symbol", "earth"]
        )
        _move_tag_chain(
            tags, ["shape", "floor", "earth_symbol"], ["decoration", "symbol", "earth"]
        )
        _move_tag_chain(tags, ["component", "fire"], ["decoration", "symbol", "fire"])
        _move_tag_chain(
            tags, ["component", "fire_symbol"], ["decoration", "symbol", "fire"]
        )
        _move_tag_chain(
            tags, ["shape", "floor", "fire_symbol"], ["decoration", "symbol", "fire"]
        )
        _move_tag_chain(
            tags, ["component", "lamashtu"], ["decoration", "symbol", "lamashtu"]
        )
        _move_tag_chain(
            tags, ["component", "lamashtu_symbol"], ["decoration", "symbol", "lamashtu"]
        )
        _move_tag_chain(
            tags,
            ["shape", "floor", "lamashtu_symbol"],
            ["decoration", "symbol", "lamashtu"],
        )
        _move_tag_chain(
            tags, ["component", "spirit_symbol"], ["decoration", "symbol", "spirit"]
        )
        _move_tag_chain(
            tags,
            ["shape", "floor", "spirit_symbol"],
            ["decoration", "symbol", "spirit"],
        )
        _move_tag_chain(tags, ["component", "water"], ["decoration", "symbol", "water"])
        _move_tag_chain(
            tags, ["component", "water_symbol"], ["decoration", "symbol", "water"]
        )
        _move_tag_chain(
            tags, ["shape", "floor", "water_symbol"], ["decoration", "symbol", "water"]
        )

    _move_tag_chain(tags, ["component", "corner"], ["shape", "corner"])
    if ("shape", "wall") in tags:
        if not _check_wall_alone(tags):
            tags.discard(("component", "wall"))
        else:
            tags.add(("component", "wall"))
    if ("shape", "floor") in tags:
        if not _check_floor_alone(tags):
            tags.discard(("component", "floor"))
        else:
            tags.add(("component", "floor"))
    _move_tag_chain(tags, ["component", "floor"], ["shape", "floor"])
    _move_tag_chain(tags, ["component", "curved"], ["shape", "curved"])
    _move_tag_chain(tags, ["component", "base"], ["shape", "base"])
    _move_tag_chain(tags, ["component", "angled"], ["shape", "angled"])
    _move_tag_chain(tags, ["component", "riser"], ["shape", "riser"])
    _move_tag_chain(tags, ["component", "stairs"], ["shape", "stairs"])
    _move_tag_chain(tags, ["component", "column"], ["shape", "column"])
    _handle_decorations(tags)
    if ("shape", "column") in tags:
        _check_columns(tags)
    _check_wall_low(tags)
    if ("shape", "base") in tags:
        _copy_base_shapes(tags)
    _check_floor_shapes(tags)


def parse_file_tags(file_info, tags, metadata):
    """Parse filename and path to extract tags from file information.

    This function contains the core parsing logic that extracts tags from
    filename and path information, without the post-processing steps.

    Args:
        file_info: Dictionary containing file information with 'file' and 'path' keys
        tags: Set to populate with parsed tags
        metadata: Metadata dictionary for the file
    """
    if metadata_auto(metadata):
        parse_filename(file_info, tags)
        parse_path(file_info, tags)
    filter_s_system(tags)
    filter_shape(tags)


def _convert_tags_to_pipe_delimited(tags_set):
    """Convert a set of tag tuples to a list of pipe-delimited strings."""
    return ["|".join(str(item) for item in tag) for tag in sorted(tags_set)]


def parse_files(path, files, md5, verbose, upload, config):
    def _get_metadata(path, fn):
        data = get_metadata_file(path)
        if data:
            if fn in data:
                return data[fn]
        return None

    newfiles = []
    s3_client = get_s3_client(config)
    # S3 key cache - pre-fetch for efficient upload checking
    s3_key_cache = get_s3_key_cache(s3_client, config, verbose) if upload else set()
    for file in files:
        if verbose:
            sys.stderr.write(f"Processing: {file}\n")
        full_file = os.path.join(path, file)
        local_path = os.path.dirname(full_file)
        fn = os.path.basename(full_file)
        f = {}
        t = set()
        o = {"type": "model", "file_metadata": f, "tags": t, "metadata": False}
        parts = file.split("/")
        f["full_name"] = file
        f["file"] = fn
        f["path"] = parts
        metadata = _get_metadata(local_path, fn)
        if metadata_ignore(metadata):
            continue
        # Calculate MD5 hash of the file
        if md5:
            with open(full_file, "rb") as fh:
                md5hash = hashlib.md5(fh.read()).hexdigest()
                f["md5"] = md5hash
        stat = os.stat(full_file)
        f["size"] = stat.st_size
        f["file_modified_at"] = datetime.datetime.fromtimestamp(
            stat.st_mtime
        ).isoformat()
        if upload:
            if not md5:
                raise Exception("MD5 is required for upload")
            model_address = upload_file(
                f, full_file, s3_client, "models", s3_key_cache, config, verbose
            )
            f["storage_address"] = f"{config['FILE_DOMAIN']}/{model_address}"

            # Generate and upload thumbnail (sprite or single based on config)
            use_sprites = config.get("ENABLE_SPRITE_THUMBNAILS", True)
            try:
                thumbnail_image = create_and_upload_thumbnail(
                    f, full_file, s3_client, s3_key_cache, config, verbose, use_sprites
                )
                images = o.get("images", [])
                images.append(thumbnail_image)
                o["images"] = images
            except Exception as e:
                # Don't block scan if thumbnail generation fails
                if verbose:
                    sys.stderr.write(
                        f"WARNING: Thumbnail generation failed for {full_file}: {e}\n"
                    )
        parse_file_tags(f, t, metadata)
        if metadata:
            o["metadata"] = True
        apply_metadata(metadata, o)
        apply_default_metadata(o)

        # Apply folder-level edit_all rules (after all other tag processing)
        folder_metadata_list = get_all_folder_metadata(path, full_file)
        apply_folder_metadata_edit_all(folder_metadata_list, o)

        # Convert tags from set of tuples to list of pipe-delimited strings
        o["tags"] = _convert_tags_to_pipe_delimited(t)
        validate(o)
        del f["path"]
        newfiles.append(o)
    return newfiles


def validate(o):
    if "config" in o:
        validate_schema("config.yaml", o["config"])


def clean_files(path, files):
    newfiles = []
    for file in files:
        parts = file.split(path)
        if len(parts) == 1:
            continue
        assert len(parts) == 2, parts
        # Strip leading slash so os.path.join works correctly
        newfiles.append(parts[1].lstrip("/"))
    return newfiles


def _extract_skip(metadata_files: list[str]) -> set[str]:
    skip = set()
    for metadata_file in metadata_files:
        try:
            path, _ = os.path.split(metadata_file)
            with open(metadata_file, "r") as f:
                metadata = safe_load(f)
            for key, value in metadata.items():
                if value.get("ignore", False):
                    skip.add(os.path.join(path, key))
        except Exception as e:
            sys.stderr.write(f"Error reading metadata file: {metadata_file}\n")
            raise e
    return skip


def find_files(path, subset):
    metadata_files = [
        f
        for f in sh.find(
            os.path.join(path, subset), "-type", "f", "-name", "metadata.yaml"
        ).split("\n")
        if f
    ]
    skip = _extract_skip(metadata_files)
    files = [
        f
        for f in sh.find(
            os.path.join(path, subset), "-type", "f", "-name", "*.stl"
        ).split("\n")
        if f
    ]

    retfiles = []
    for f in files:
        add = True
        for s in skip:
            if f.startswith(s):
                add = False
                break
        if add:
            retfiles.append(f)

    return retfiles


def _sort_and_clean_recursively(obj, exclude_paths=None, current_path=""):
    """Recursively sort all lists and dictionary keys in a JSON-serializable object.

    For consistent output. Also removes empty arrays and hashes in a single pass
    for performance.

    Args:
        obj: The object to sort and clean
        exclude_paths: Optional list of JSON paths to exclude from sorting
            (e.g., ["config.parts"])
        current_path: Current JSON path for checking exclusions
    """
    if exclude_paths is None:
        exclude_paths = []

    if isinstance(obj, dict):
        return _process_dict(obj, exclude_paths, current_path)
    elif isinstance(obj, list):
        return _process_list(obj, exclude_paths, current_path)
    elif isinstance(obj, (set, tuple)):
        return _process_sequence(obj, exclude_paths, current_path)
    else:
        return obj


def _process_dict(obj, exclude_paths, current_path):
    """Process dictionary objects - sort keys and recursively process values."""
    result = {}
    for k, v in sorted(obj.items()):
        next_path = f"{current_path}.{k}" if current_path else k
        processed_v = _sort_and_clean_recursively(v, exclude_paths, next_path)
        # Only include non-empty values
        if processed_v is not None and processed_v != {} and processed_v != []:
            result[k] = processed_v
    return result


def _process_list(obj, exclude_paths, current_path):
    """Process list objects - sort unless excluded."""
    # Check if current path should be excluded from sorting
    should_exclude = current_path in exclude_paths

    # Process items recursively
    processed_items = [
        _sort_and_clean_recursively(item, exclude_paths, current_path) for item in obj
    ]
    filtered_items = [
        item
        for item in processed_items
        if item is not None and item != {} and item != []
    ]

    if should_exclude:
        # Don't sort this list, preserve original order
        return filtered_items
    else:
        # Sort the list, passing current_path for special case handling
        return _sort_list_items(filtered_items, current_path)


def _process_sequence(obj, exclude_paths, current_path):
    """Process set/tuple objects - convert to sorted list."""
    processed_items = [
        _sort_and_clean_recursively(item, exclude_paths, current_path) for item in obj
    ]
    filtered_items = [
        item
        for item in processed_items
        if item is not None and item != {} and item != []
    ]
    return sorted(filtered_items, key=str)


def _sort_list_items(items, current_path=""):
    """Sort list items using a stable sort key.

    Args:
        items: List of items to sort
        current_path: Current JSON path for special case handling
    """

    def sort_key(item):
        # Special case: top-level blueprint array should be sorted by full_name
        if current_path == "" and isinstance(item, dict) and "file_metadata" in item:
            # Sort by: full_name, deprecated (False first), then md5 for stability
            full_name = item.get("file_metadata", {}).get("full_name", "")
            deprecated = item.get("deprecated", False)
            md5 = item.get("file_metadata", {}).get("md5", "")
            # Return tuple: non-deprecated (False=0) sorts before deprecated (True=1)
            return (full_name, deprecated, md5)
        # Special case: sprite_metadata.angles should be sorted by index field
        elif current_path.endswith("sprite_metadata.angles") and isinstance(item, dict):
            return item.get("index", 0)
        elif isinstance(item, dict):
            # Create a stable, sortable representation of the dictionary
            return json.dumps(item, sort_keys=True)
        elif isinstance(item, (list, tuple, set)):
            # For nested sequences, use the first element as sort key
            return str(item[0]) if item else ""
        else:
            return str(item)

    return sorted(items, key=sort_key)


def print_files(files):
    from .utils import set_handler

    # Sort all lists recursively for consistent git diffs
    # Exclude config.parts from sorting to preserve order
    # Top-level array will be sorted by full_name in _sort_list_items
    sorted_files = _sort_and_clean_recursively(files, exclude_paths=["config.parts"])
    print(json.dumps(sorted_files, default=set_handler, indent=4, sort_keys=True))
