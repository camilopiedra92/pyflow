from __future__ import annotations

from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext

from pyflow.tools.base import BasePlatformTool, get_registered_tools, _TOOL_AUTO_REGISTRY


class _DummyTool(BasePlatformTool):
    name = "dummy"
    description = "A dummy tool for testing"

    async def execute(self, tool_context: ToolContext, value: str) -> dict:
        return {"result": value}


class TestAutoRegistration:
    def test_subclass_auto_registers(self):
        assert "dummy" in _TOOL_AUTO_REGISTRY

    def test_abstract_base_not_registered(self):
        assert "BasePlatformTool" not in _TOOL_AUTO_REGISTRY


class TestGetRegisteredTools:
    def test_returns_dict_copy(self):
        tools = get_registered_tools()
        assert isinstance(tools, dict)
        assert "dummy" in tools

    def test_includes_builtin_tools(self):
        import pyflow.tools  # noqa: F401

        tools = get_registered_tools()
        assert "http_request" in tools
        assert "transform" in tools
        assert "condition" in tools
        assert "alert" in tools
        assert "storage" in tools


class TestAsFunctionTool:
    def test_returns_function_tool(self):
        tool = _DummyTool.as_function_tool()
        assert isinstance(tool, FunctionTool)


class TestMetadata:
    def test_returns_tool_metadata(self):
        meta = _DummyTool.metadata()
        assert meta.name == "dummy"
        assert meta.description == "A dummy tool for testing"
