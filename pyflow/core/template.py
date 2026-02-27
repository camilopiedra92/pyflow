from __future__ import annotations

import re
from typing import Any

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from pyflow.core.context import ExecutionContext


_env = SandboxedEnvironment(undefined=StrictUndefined)
_PURE_VAR_RE = re.compile(r"^\{\{\s*(\w+)\s*\}\}$")


def resolve_templates(value: Any, context: ExecutionContext) -> Any:
    """Recursively resolve Jinja2 templates in *value* using context results.

    Supports strings, dicts, and lists.  Non-template values are returned
    unchanged.  Uses ``StrictUndefined`` so that referencing a missing
    variable raises an exception immediately.

    Pure variable references like ``{{ node_id }}`` are resolved directly
    from context to preserve the original Python type (dict, list, number).
    Jinja2 render() always returns a string, which would break downstream
    consumers like jsonpath.
    """
    if isinstance(value, str):
        if "{{" not in value:
            return value
        match = _PURE_VAR_RE.match(value)
        if match:
            var_name = match.group(1)
            results = context.all_results()
            if var_name in results:
                return results[var_name]
        template = _env.from_string(value)
        return template.render(context.all_results())
    if isinstance(value, dict):
        return {k: resolve_templates(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_templates(item, context) for item in value]
    return value
