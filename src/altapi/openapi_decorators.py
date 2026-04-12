"""
OpenAPI decorators for AltAPI.

Minimal decorator support - main Pydantic integration is in app.py route decorators.
"""

from typing import Any, Dict, Optional


def _merge_openapi_metadata(func, metadata: Dict[str, Any]) -> Any:
    """
    Merge OpenAPI metadata into function, preserving existing metadata.

    Returns the same function object (no wrapper created).
    """
    existing = getattr(func, "_openapi_metadata", {})
    merged = {**existing, **metadata}
    # Remove None values
    merged = {k: v for k, v in merged.items() if v is not None}
    func._openapi_metadata = merged
    func._openapi_decorated = True
    return func


def openapi_summary(summary: str):
    """
    Decorator to add a short summary to a route handler.

    Args:
        summary: Short summary of the operation

    Returns:
        Decorator function
    """
    def decorator(func):
        return _merge_openapi_metadata(func, {"summary": summary})
    return decorator


def openapi_description(description: str):
    """
    Decorator to add a detailed description to a route handler.

    Args:
        description: Detailed description of the operation

    Returns:
        Decorator function
    """
    def decorator(func):
        return _merge_openapi_metadata(func, {"description": description})
    return decorator


def tag(*tag_names: str):
    """
    Decorator to add tags to a route handler.

    Args:
        *tag_names: Tags for the operation

    Returns:
        Decorator function
    """
    def decorator(func):
        return _merge_openapi_metadata(func, {"tags": list(tag_names)})
    return decorator


def deprecated(func):
    """
    Decorator to mark a route handler as deprecated.
    """
    return _merge_openapi_metadata(func, {"deprecated": True})
