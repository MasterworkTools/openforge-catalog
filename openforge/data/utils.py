"""Utility functions for the data module."""


def set_handler(obj):
    """JSON serializer handler for set and tuple objects.

    Args:
        obj: Object to serialize

    Returns:
        List representation of the object

    Raises:
        TypeError: If object is not a set or tuple
    """
    if isinstance(obj, (set, tuple)):
        return list(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
