import os

from yaml import safe_load

from openforge.db.sql.tag_utils import tag_to_array
from openforge.openapi import validate_schema


def get_folder_metadata(path):
    """Get folder-level metadata (the '.' entry) from a metadata.yaml file."""
    metadata_file = os.path.join(path, "metadata.yaml")
    if os.path.exists(metadata_file):
        with open(metadata_file, "r") as f:
            metadata = safe_load(f)
            if metadata and isinstance(metadata, dict) and "." in metadata:
                return metadata["."]
    return None


def get_metadata_file(path):
    metadata_file = os.path.join(path, "metadata.yaml")
    if os.path.exists(metadata_file):
        with open(metadata_file, "r") as f:
            metadata = safe_load(f)
            # Validate that the metadata file is a dictionary
            if metadata is not None and not isinstance(metadata, dict):
                raise ValueError(
                    f"Metadata file '{metadata_file}' must contain a dictionary, "
                    f"but found type {type(metadata).__name__}"
                )

            # Validate schema for each individual metadata entry
            if metadata is not None:
                for filename, entry in metadata.items():
                    if not isinstance(filename, str):
                        raise ValueError(
                            f"In metadata file '{metadata_file}', found non-string "
                            f"key: {filename}"
                        )
                    if not isinstance(entry, dict):
                        raise ValueError(
                            f"In metadata file '{metadata_file}', entry for key "
                            f"'{filename}' must be a dictionary, but found type "
                            f"{type(entry).__name__}"
                        )
                    # Validate individual metadata entry
                    if filename == ".":
                        # Folder-level metadata
                        validate_schema("folder_metadata.yaml", entry)
                    else:
                        # File-level metadata
                        validate_schema("metadata.yaml", entry)

            return metadata
    return None


def metadata_ignore(metadata):
    if metadata is None:
        return False
    if "ignore" in metadata:
        return metadata["ignore"]
    return False


def metadata_auto(metadata):
    if metadata is None:
        return True
    if "auto" in metadata:
        return metadata["auto"]
    return True


def apply_metadata(metadata, o):
    if metadata is None:
        return
    if "ignore" in metadata:
        del metadata["ignore"]
    if "auto" in metadata:
        del metadata["auto"]
    if "tags" in metadata:
        for tag in metadata["tags"]:
            add_tag(o, tag)
        del metadata["tags"]
    if "config" in metadata:
        o["config"] = metadata["config"]
        del metadata["config"]
    if "edit" in metadata:
        apply_metadata_edit(metadata["edit"], o)
        del metadata["edit"]
    assert len(metadata) == 0, metadata


def get_all_folder_metadata(base_path, file_path):
    """Collect all folder metadata from base_path to file_path's directory.

    Returns a list of folder metadata objects from root to leaf.
    """
    folder_metadata_list = []

    # Get relative path from base to file
    rel_path = os.path.relpath(file_path, base_path)
    dir_path = os.path.dirname(rel_path)

    # Build list of directories from root to file's directory
    path_parts = []
    if dir_path and dir_path != ".":
        path_parts = dir_path.split(os.sep)

    # Check each directory level for folder metadata
    current_path = base_path

    # Check base path first
    folder_meta = get_folder_metadata(current_path)
    if folder_meta:
        folder_metadata_list.append(folder_meta)

    # Check each subdirectory
    for part in path_parts:
        current_path = os.path.join(current_path, part)
        folder_meta = get_folder_metadata(current_path)
        if folder_meta:
            folder_metadata_list.append(folder_meta)

    return folder_metadata_list


def apply_folder_metadata_edit_all(folder_metadata_list, o):
    """Apply edit_all rules from a list of folder metadata objects."""
    for folder_meta in folder_metadata_list:
        if "edit_all" in folder_meta:
            edit_all = folder_meta["edit_all"]
            if "tags" in edit_all:
                if "add" in edit_all["tags"]:
                    for tag in edit_all["tags"]["add"]:
                        add_tag(o, tag)
                if "remove" in edit_all["tags"]:
                    for tag in edit_all["tags"]["remove"]:
                        remove_tag(o, tag, error_if_missing=False)


def apply_metadata_edit(edit, o):
    if "tags" in edit:
        if "add" in edit["tags"]:
            for tag in edit["tags"]["add"]:
                add_tag(o, tag)
        if "remove" in edit["tags"]:
            for tag in edit["tags"]["remove"]:
                remove_tag(o, tag)
        del edit["tags"]
    assert len(edit) == 0, edit


def has_tag(o, tag):
    return tag in o["tags"]


def has_tags(o, tags):
    for tag in tags:
        if not has_tag(o, tag):
            return False
    return True


def has_no_tags(o, tags):
    for tag in tags:
        if has_tag(o, tag):
            return False
    return True


def apply_default_metadata(o):
    apply_openforge_wall(o)
    apply_openforge_floor(o)
    apply_thick_wall(o)


def is_openforge_wall(o):
    tags = [("shape", "wall"), ("connection", "openforge"), ("build", "separate wall")]
    neg_tags = [("build", "s2w"), ("shape", "floor"), ("shape", "base")]
    if has_tags(o, tags) and has_no_tags(o, neg_tags):
        return True
    tags = [
        ("shape", "wall", "low"),
        ("connection", "openforge"),
        ("build", "separate wall"),
    ]
    if has_tags(o, tags) and has_no_tags(o, neg_tags):
        return True
    return False


def is_openforge_floor(o):
    tags = [("shape", "floor"), ("connection", "openforge")]
    neg_tags = [("build", "s2w"), ("shape", "wall"), ("shape", "base")]
    if has_tags(o, tags) and has_no_tags(o, neg_tags):
        return True
    return False


def is_thick_wall(o):
    tags = [("build", "thick wall"), ("connection", "openforge"), ("component", "wall")]
    neg_tags = [("build", "s2w"), ("shape", "base")]
    if has_tags(o, tags) and has_no_tags(o, neg_tags):
        return True
    return False


def apply_openforge_wall(o):
    if not is_openforge_wall(o):
        return
    config = o.setdefault("config", {})
    parts = config.setdefault("parts", [])
    parts.append(
        {
            "name": "base",
            "tags": {
                "require": [
                    {"tag": "shape|base"},
                ],
                "constrain": [
                    {"tag": "shape", "siblings": []},
                    {"tag": "size|width", "siblings": []},
                    {"tag": "texture", "siblings": []},
                ],
            },
            "optional": True,
        }
    )
    config["parts"] = parts
    o["config"] = config


def apply_openforge_floor(o):
    if not is_openforge_floor(o):
        return
    config = o.setdefault("config", {})
    parts = config.setdefault("parts", [])
    parts.append(
        {
            "name": "base",
            "tags": {
                "require": [
                    {"tag": "shape|base"},
                ],
                "deny": [
                    {"tag": "build|s2w"},
                ],
                "constrain": [
                    {"tag": "shape"},
                    {"tag": "size|width"},
                    {"tag": "size|depth"},
                    {"filter": "shape|floor"},
                    {"filter": "shape|wall"},
                ],
            },
            "optional": True,
        }
    )
    config["parts"] = parts
    o["config"] = config


def apply_thick_wall(o):
    if not is_thick_wall(o):
        return
    config = o.setdefault("config", {})
    parts = config.setdefault("parts", [])
    parts.append(
        {
            "name": "base",
            "tags": {
                "require": [
                    {"tag": "shape|base"},
                ],
                "deny": [
                    {"tag": "build|s2w"},
                ],
                "constrain": [
                    {"tag": "shape"},
                    {"tag": "size|width"},
                    {"tag": "size|depth"},
                ],
            },
            "optional": True,
        }
    )
    config["parts"] = parts
    o["config"] = config


def convert_tags_for_metadata(tags):
    """Convert tags from list of strings to set of tuples for metadata processing.

    Args:
        tags: List of tag strings or arrays

    Returns:
        Set of tag tuples
    """
    tag_set = set()
    for tag_item in tags:
        if isinstance(tag_item, str):
            tag_parts = tag_item.split("|")
            tag_set.add(tuple(tag_parts))
        elif isinstance(tag_item, list):
            tag_set.add(tuple(tag_item))
        else:
            raise TypeError(
                f"Unsupported tag type: {type(tag_item)}. Expected list or str, "
                f"got {type(tag_item)} with value: {tag_item}"
            )
    return tag_set


def add_tag(o: dict, tag: str):
    if "tags" not in o:
        o["tags"] = set()
    o["tags"].add(tuple(tag_to_array(tag)))


def remove_tag(o: dict, tag: str, error_if_missing: bool = True):
    if "tags" in o:
        tag_tuple = tuple(tag_to_array(tag))
        try:
            o["tags"].remove(tag_tuple)
        except KeyError:
            if error_if_missing:
                raise ValueError(f"Tag {tag} not found in object")
