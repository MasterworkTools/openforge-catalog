"""Pagination utilities for API endpoints."""

from typing import Tuple


def validate_pagination_params(limit: int = 10, offset: int = 0) -> Tuple[int, int]:
    """Validate pagination parameters.

    Args:
        limit: Number of items to return (default: 10)
        offset: Number of items to skip (default: 0)

    Returns:
        Tuple of (limit, offset) if valid

    Raises:
        ValueError: If parameters are invalid
    """
    if limit < 1 or limit > 1000:
        raise ValueError("Limit must be between 1 and 1000")

    if offset < 0:
        raise ValueError("Offset must be non-negative")

    return limit, offset
