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
