from __future__ import annotations

import re

from jsonpath_ng.ext import parse as jsonpath_parse

from pyflow.core.context import ExecutionContext
from pyflow.core.node import BaseNode
from pyflow.core.template import resolve_templates

# Pattern matching a pure template variable reference like "{{ var_name }}"
_PURE_VAR_RE = re.compile(r"^\{\{\s*(\w+)\s*\}\}$")


class TransformNode(BaseNode):
    node_type = "transform"

    async def execute(self, config: dict, context: ExecutionContext) -> object:
        input_data = config.get("input")

        if isinstance(input_data, str):
            # If input is a pure variable reference (e.g. "{{ prev }}"), resolve
            # it directly from the context to preserve the original Python object.
            # Jinja2's render() would stringify dicts/lists, breaking jsonpath.
            match = _PURE_VAR_RE.match(input_data)
            if match:
                var_name = match.group(1)
                input_data = context.get_result(var_name)
            elif "{{" in input_data:
                input_data = resolve_templates(input_data, context)

        expression = config["expression"]
        matches = jsonpath_parse(expression).find(input_data)

        if len(matches) == 1:
            return matches[0].value
        return [m.value for m in matches]
