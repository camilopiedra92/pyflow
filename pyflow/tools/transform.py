from __future__ import annotations

from google.adk.tools.tool_context import ToolContext

from pyflow.tools.base import BasePlatformTool
from pyflow.tools.parsing import safe_json_parse


class TransformTool(BasePlatformTool):
    name = "transform"
    description = "Apply a JSONPath expression to extract or transform data from JSON input."

    async def execute(
        self,
        tool_context: ToolContext,
        input_data: str,
        expression: str,
    ) -> dict:
        """Apply JSONPath expression to input data.

        Args:
            input_data: JSON string to transform.
            expression: JSONPath expression (e.g. '$.name', '$.items[*].id').
        """
        parsed = safe_json_parse(input_data)
        if parsed is None:
            return {"result": None, "error": "Invalid JSON input"}

        try:
            from jsonpath_ng import parse as jp_parse
            matches = jp_parse(expression).find(parsed)
        except Exception as exc:
            return {"result": None, "error": f"JSONPath error: {exc}"}

        if not matches:
            return {"result": None}
        if len(matches) == 1:
            return {"result": matches[0].value}
        return {"result": [m.value for m in matches]}
