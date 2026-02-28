from __future__ import annotations

import json
from unittest.mock import MagicMock

from pyflow.tools.transform import TransformTool


class TestTransformToolExecute:
    async def test_simple_property(self):
        tool = TransformTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            input_data=json.dumps({"name": "pyflow", "version": "1.0"}),
            expression="$.name",
        )
        assert isinstance(result, dict)
        assert result["result"] == "pyflow"

    async def test_array_indexing(self):
        tool = TransformTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            input_data=json.dumps({"items": ["a", "b", "c"]}),
            expression="$.items[1]",
        )
        assert result["result"] == "b"

    async def test_wildcard_returns_list(self):
        tool = TransformTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            input_data=json.dumps({"items": [{"id": 1}, {"id": 2}, {"id": 3}]}),
            expression="$.items[*].id",
        )
        assert result["result"] == [1, 2, 3]

    async def test_nested_path(self):
        tool = TransformTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            input_data=json.dumps({"data": {"nested": {"value": 42}}}),
            expression="$.data.nested.value",
        )
        assert result["result"] == 42

    async def test_no_match_returns_none(self):
        tool = TransformTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            input_data=json.dumps({"a": 1}),
            expression="$.nonexistent",
        )
        assert result["result"] is None
        assert "error" not in result

    async def test_invalid_expression_returns_error(self):
        tool = TransformTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            input_data=json.dumps({"a": 1}),
            expression="not a valid jsonpath [[[",
        )
        assert result["result"] is None
        assert "error" in result
        assert "JSONPath error" in result["error"]

    async def test_invalid_json_input_returns_error(self):
        tool = TransformTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            input_data="not valid json{{{",
            expression="$.name",
        )
        assert result["result"] is None
        assert result["error"] == "Invalid JSON input"

    def test_auto_registered(self):
        from pyflow.tools.base import get_registered_tools

        assert "transform" in get_registered_tools()
