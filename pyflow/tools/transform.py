from __future__ import annotations

from typing import Any, ClassVar

from google.adk.tools.tool_context import ToolContext

from pyflow.models.tool import ToolConfig, ToolResponse
from pyflow.tools.base import BasePlatformTool


class TransformToolConfig(ToolConfig):
    """Configuration for JSONPath transform operations."""

    input: Any
    expression: str


class TransformToolResponse(ToolResponse):
    """Response from a transform operation."""

    result: Any


class TransformTool(BasePlatformTool):
    """Transform data using JSONPath expressions."""

    name: ClassVar[str] = "transform"
    description: ClassVar[str] = "Transform and extract data using JSONPath expressions"
    config_model: ClassVar[type[ToolConfig]] = TransformToolConfig
    response_model: ClassVar[type[ToolResponse]] = TransformToolResponse

    async def execute(
        self, config: TransformToolConfig, tool_context: ToolContext | None = None
    ) -> TransformToolResponse:
        try:
            from jsonpath_ng import parse

            expr = parse(config.expression)
            matches = expr.find(config.input)
            if not matches:
                return TransformToolResponse(result=None)
            if len(matches) == 1:
                return TransformToolResponse(result=matches[0].value)
            return TransformToolResponse(result=[m.value for m in matches])
        except Exception:
            return TransformToolResponse(result=None)
