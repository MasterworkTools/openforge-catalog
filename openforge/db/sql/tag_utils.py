from typing import List, Union


def tag_to_array(tag: Union[str, List[str]]) -> List[str]:
    """Convert a tag string or array to a tag array.

    Args:
        tag: Either a pipe-delimited string (e.g. "foo|bar") or a list of strings

    Returns:
        List of tag components
    """
    if isinstance(tag, list):
        return tag
    if isinstance(tag, str):
        return tag.split("|")
    return list(tag)


def array_to_tag(tag_array):
    return "|".join(str(x) for x in tag_array)


def convert_tag_dict(tag_dict):
    if tag_dict is None:
        return None
    if "tag" in tag_dict and isinstance(tag_dict["tag"], list):
        tag_dict["tag"] = array_to_tag(tag_dict["tag"])
    return tag_dict


def process_tag(tag, process_func):
    """Process a tag with consistent error handling for different formats.

    Args:
        tag: Either a list of strings or a pipe-delimited string
        process_func: Function to apply to the processed tag array

    Returns:
        Result of applying process_func to the tag array

    Raises:
        TypeError: If tag is neither list nor string
    """
    if isinstance(tag, list):
        # Old format: ["shape", "floor"] -> process directly
        return process_func(tag)
    elif isinstance(tag, str):
        # New format: "shape|floor" -> convert to array, then process
        tag_array = tag_to_array(tag)
        return process_func(tag_array)
    else:
        # Fail fast for unexpected tag types
        raise TypeError(f"Unsupported tag type {type(tag).__name__}: {tag}")
