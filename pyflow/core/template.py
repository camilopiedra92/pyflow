from __future__ import annotations

from typing import Any

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from pyflow.core.context import ExecutionContext


_env = SandboxedEnvironment(undefined=StrictUndefined)


def resolve_templates(value: Any, context: ExecutionContext) -> Any:
    """Recursively resolve Jinja2 templates in *value* using context results.

    Supports strings, dicts, and lists.  Non-template values are returned
    unchanged.  Uses ``StrictUndefined`` so that referencing a missing
    variable raises an exception immediately.
    """
    if isinstance(value, str):
        if "{{" not in value:
            return value
        template = _env.from_string(value)
        return template.render(context.all_results())
    if isinstance(value, dict):
        return {k: resolve_templates(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_templates(item, context) for item in value]
    return value
