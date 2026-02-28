from __future__ import annotations

from typing import Callable

CALLBACK_REGISTRY: dict[str, Callable] = {}


def register_callback(name: str, fn: Callable) -> None:
    """Register a named callback function."""
    CALLBACK_REGISTRY[name] = fn


def resolve_callback(name: str | None) -> Callable | None:
    """Resolve a callback name to its function. Returns None if not found."""
    if name is None:
        return None
    return CALLBACK_REGISTRY.get(name)
