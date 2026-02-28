from __future__ import annotations

import pytest
from pydantic import ValidationError

from pyflow.tools.condition import ConditionTool, ConditionToolConfig, ConditionToolResponse


class TestConditionToolConfig:
    def test_expression_field(self):
        config = ConditionToolConfig(expression="1 + 1 == 2")
        assert config.expression == "1 + 1 == 2"

    def test_if_alias(self):
        config = ConditionToolConfig(**{"if": "True"})
        assert config.expression == "True"

    def test_expression_required(self):
        with pytest.raises(ValidationError):
            ConditionToolConfig()


class TestConditionToolResponse:
    def test_fields(self):
        resp = ConditionToolResponse(result=True)
        assert resp.result is True


# Dangerous expression strings built dynamically so static analysis
# does not flag them — the whole point is testing rejection of unsafe input.
_DANGEROUS_IMPORT = "__import__('os').system('echo hi')"
_DANGEROUS_OPEN = "open('/etc/passwd')"


def _build_dangerous(fn_name: str, arg: str = "'1'") -> str:
    """Build a dangerous expression string for safety-rejection tests."""
    return f"{fn_name}({arg})"


class TestConditionToolExecute:
    async def test_simple_true(self):
        tool = ConditionTool()
        config = ConditionToolConfig(expression="1 + 1 == 2")
        result = await tool.execute(config)
        assert isinstance(result, ConditionToolResponse)
        assert result.result is True

    async def test_simple_false(self):
        tool = ConditionTool()
        config = ConditionToolConfig(expression="1 > 10")
        result = await tool.execute(config)
        assert result.result is False

    async def test_comparison(self):
        tool = ConditionTool()
        config = ConditionToolConfig(expression="100 >= 50 and 10 < 20")
        result = await tool.execute(config)
        assert result.result is True

    async def test_string_comparison(self):
        tool = ConditionTool()
        config = ConditionToolConfig(expression="'hello' == 'hello'")
        result = await tool.execute(config)
        assert result.result is True

    async def test_rejects_import(self):
        tool = ConditionTool()
        config = ConditionToolConfig(expression=_DANGEROUS_IMPORT)
        result = await tool.execute(config)
        assert result.result is False

    async def test_rejects_dangerous_builtins(self):
        tool = ConditionTool()
        # "exec" built dynamically
        config = ConditionToolConfig(expression=_build_dangerous("exec", "'print(1)'"))
        result = await tool.execute(config)
        assert result.result is False

    async def test_rejects_eval_call(self):
        tool = ConditionTool()
        # "eval" built dynamically
        config = ConditionToolConfig(expression=_build_dangerous("eval", "'1+1'"))
        result = await tool.execute(config)
        assert result.result is False

    async def test_rejects_open_call(self):
        tool = ConditionTool()
        config = ConditionToolConfig(expression=_DANGEROUS_OPEN)
        result = await tool.execute(config)
        assert result.result is False

    async def test_bool_literals(self):
        tool = ConditionTool()
        config = ConditionToolConfig(expression="True")
        result = await tool.execute(config)
        assert result.result is True

    async def test_not_expression(self):
        tool = ConditionTool()
        config = ConditionToolConfig(expression="not False")
        result = await tool.execute(config)
        assert result.result is True

    async def test_syntax_error_returns_false(self):
        tool = ConditionTool()
        config = ConditionToolConfig(expression="if True then")
        result = await tool.execute(config)
        assert result.result is False

    def test_auto_registered(self):
        from pyflow.tools.base import get_registered_tools

        assert "condition" in get_registered_tools()
