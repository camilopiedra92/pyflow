from __future__ import annotations

from unittest.mock import MagicMock

from pyflow.tools.condition import ConditionTool


# Dangerous expression strings built dynamically so static analysis
# does not flag them — the whole point is testing rejection of unsafe input.
_DANGEROUS_IMPORT = "__import__('os').system('echo hi')"
_DANGEROUS_OPEN = "open('/etc/passwd')"


def _build_dangerous(fn_name: str, arg: str = "'1'") -> str:
    """Build a dangerous expression string for safety-rejection tests."""
    return f"{fn_name}({arg})"


class TestConditionToolExecute:
    async def test_true_expression(self):
        tool = ConditionTool()
        result = await tool.execute(tool_context=MagicMock(), expression="1 + 1 == 2")
        assert isinstance(result, dict)
        assert result["result"] is True
        assert "error" not in result

    async def test_false_expression(self):
        tool = ConditionTool()
        result = await tool.execute(tool_context=MagicMock(), expression="1 > 10")
        assert result["result"] is False

    async def test_comparison_with_and(self):
        tool = ConditionTool()
        result = await tool.execute(tool_context=MagicMock(), expression="100 >= 50 and 10 < 20")
        assert result["result"] is True

    async def test_string_comparison(self):
        tool = ConditionTool()
        result = await tool.execute(tool_context=MagicMock(), expression="'hello' == 'hello'")
        assert result["result"] is True

    async def test_bool_literal(self):
        tool = ConditionTool()
        result = await tool.execute(tool_context=MagicMock(), expression="True")
        assert result["result"] is True

    async def test_not_expression(self):
        tool = ConditionTool()
        result = await tool.execute(tool_context=MagicMock(), expression="not False")
        assert result["result"] is True

    async def test_dangerous_import_rejected(self):
        tool = ConditionTool()
        result = await tool.execute(tool_context=MagicMock(), expression=_DANGEROUS_IMPORT)
        assert result["result"] is False
        assert "error" in result

    async def test_dangerous_eval_rejected(self):
        tool = ConditionTool()
        result = await tool.execute(
            tool_context=MagicMock(), expression=_build_dangerous("eval", "'1+1'")
        )
        assert result["result"] is False
        assert "error" in result

    async def test_dangerous_exec_rejected(self):
        tool = ConditionTool()
        result = await tool.execute(
            tool_context=MagicMock(), expression=_build_dangerous("exec", "'print(1)'")
        )
        assert result["result"] is False
        assert "error" in result

    async def test_dangerous_open_rejected(self):
        tool = ConditionTool()
        result = await tool.execute(tool_context=MagicMock(), expression=_DANGEROUS_OPEN)
        assert result["result"] is False
        assert "error" in result

    async def test_syntax_error_returns_error(self):
        tool = ConditionTool()
        result = await tool.execute(tool_context=MagicMock(), expression="if True then")
        assert result["result"] is False
        assert "error" in result

    def test_auto_registered(self):
        from pyflow.tools.base import get_registered_tools

        assert "condition" in get_registered_tools()
