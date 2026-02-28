from __future__ import annotations

import pytest
from pydantic import ValidationError

from pyflow.tools.transform import TransformTool, TransformToolConfig, TransformToolResponse


class TestTransformToolConfig:
    def test_fields(self):
        config = TransformToolConfig(input={"items": [1, 2, 3]}, expression="$.items[0]")
        assert config.input == {"items": [1, 2, 3]}
        assert config.expression == "$.items[0]"

    def test_expression_required(self):
        with pytest.raises(ValidationError):
            TransformToolConfig(input={"a": 1})

    def test_input_required(self):
        with pytest.raises(ValidationError):
            TransformToolConfig(expression="$.a")


class TestTransformToolResponse:
    def test_fields(self):
        resp = TransformToolResponse(result=[1, 2, 3])
        assert resp.result == [1, 2, 3]


class TestTransformToolExecute:
    async def test_simple_jsonpath(self):
        tool = TransformTool()
        config = TransformToolConfig(
            input={"name": "pyflow", "version": "1.0"},
            expression="$.name",
        )
        result = await tool.execute(config)
        assert isinstance(result, TransformToolResponse)
        assert result.result == "pyflow"

    async def test_array_index(self):
        tool = TransformTool()
        config = TransformToolConfig(
            input={"items": ["a", "b", "c"]},
            expression="$.items[1]",
        )
        result = await tool.execute(config)
        assert result.result == "b"

    async def test_nested_path(self):
        tool = TransformTool()
        config = TransformToolConfig(
            input={"data": {"nested": {"value": 42}}},
            expression="$.data.nested.value",
        )
        result = await tool.execute(config)
        assert result.result == 42

    async def test_wildcard_returns_list(self):
        tool = TransformTool()
        config = TransformToolConfig(
            input={"items": [{"id": 1}, {"id": 2}, {"id": 3}]},
            expression="$.items[*].id",
        )
        result = await tool.execute(config)
        assert result.result == [1, 2, 3]

    async def test_no_match_returns_none(self):
        tool = TransformTool()
        config = TransformToolConfig(
            input={"a": 1},
            expression="$.nonexistent",
        )
        result = await tool.execute(config)
        assert result.result is None

    async def test_invalid_expression(self):
        tool = TransformTool()
        config = TransformToolConfig(
            input={"a": 1},
            expression="not a valid jsonpath [[[",
        )
        result = await tool.execute(config)
        assert result.result is None

    def test_auto_registered(self):
        from pyflow.tools.base import get_registered_tools

        assert "transform" in get_registered_tools()
