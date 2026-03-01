from __future__ import annotations

import importlib
from collections.abc import Callable


def resolve_callback(fqn: str | None) -> Callable | None:
    """Resolve a fully-qualified Python name to a callable.

    Example: 'mypackage.callbacks.log_request' -> function object.
    Returns None if fqn is None or empty.
    """
    if not fqn:
        return None
    module_path, obj_name = fqn.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, obj_name)


def resolve_tool_predicate(fqn: str) -> Callable:
    """Resolve a FQN to a ToolPredicate callable.

    Raises TypeError if the resolved object is not callable.
    """
    obj = resolve_callback(fqn)
    if obj is None or not callable(obj):
        raise TypeError(f"ToolPredicate FQN '{fqn}' did not resolve to a callable")
    return obj


