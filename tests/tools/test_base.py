from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from google.adk.tools import FunctionTool

from pyflow.models.tool import ToolConfig, ToolMetadata, ToolResponse


class DummyConfig(ToolConfig):
    value: str = "hello"


class DummyResponse(ToolResponse):
    output: str = ""


class TestAutoRegistration:
    """Test that subclassing BasePlatformTool auto-registers the tool."""

    def test_subclass_registers_in_registry(self):
        from pyflow.tools.base import BasePlatformTool, _TOOL_AUTO_REGISTRY

        class _RegTestTool(BasePlatformTool):
            name = "reg_test_tool"
            description = "test tool"
            config_model = DummyConfig
            response_model = DummyResponse

            async def execute(self, config, tool_context=None):
                return DummyResponse(output="ok")

        assert "reg_test_tool" in _TOOL_AUTO_REGISTRY
        assert _TOOL_AUTO_REGISTRY["reg_test_tool"] is _RegTestTool

    def test_abstract_base_not_registered(self):
        from pyflow.tools.base import _TOOL_AUTO_REGISTRY

        assert "BasePlatformTool" not in _TOOL_AUTO_REGISTRY

    def test_subclass_without_name_not_registered(self):
        from pyflow.tools.base import BasePlatformTool, _TOOL_AUTO_REGISTRY

        class _NoNameTool(BasePlatformTool):
            description = "no name"
            config_model = DummyConfig
            response_model = DummyResponse

            async def execute(self, config, tool_context=None):
                return DummyResponse()

        # Should not appear because 'name' was never set as a string class var
        assert "_NoNameTool" not in _TOOL_AUTO_REGISTRY


class TestGetRegisteredTools:
    def test_returns_dict_copy(self):
        from pyflow.tools.base import get_registered_tools

        registry = get_registered_tools()
        assert isinstance(registry, dict)
        # Mutating the copy should not affect the original
        registry["fake"] = None
        assert "fake" not in get_registered_tools()

    def test_contains_builtin_tools(self):
        # Import the tools package to trigger auto-registration
        import pyflow.tools  # noqa: F401
        from pyflow.tools.base import get_registered_tools

        registry = get_registered_tools()
        expected = {"http_request", "transform", "condition", "alert", "storage"}
        assert expected.issubset(set(registry.keys()))


class TestAsFunctionTool:
    def test_returns_function_tool(self):
        from pyflow.tools.base import BasePlatformTool

        class _FTTestTool(BasePlatformTool):
            name = "ft_test"
            description = "function tool test"
            config_model = DummyConfig
            response_model = DummyResponse

            async def execute(self, config, tool_context=None):
                return DummyResponse(output=config.value)

        tool = _FTTestTool()
        ft = tool.as_function_tool()
        assert isinstance(ft, FunctionTool)

    async def test_function_tool_callable(self):
        from pyflow.tools.base import BasePlatformTool

        class _CallTestTool(BasePlatformTool):
            name = "call_test"
            description = "callable test"
            config_model = DummyConfig
            response_model = DummyResponse

            async def execute(self, config, tool_context=None):
                return DummyResponse(output=config.value)

        tool = _CallTestTool()
        ft = tool.as_function_tool()
        # The underlying func should be callable
        assert callable(ft.func)


class TestMetadata:
    def test_metadata_returns_tool_metadata(self):
        from pyflow.tools.base import BasePlatformTool

        class _MetaTestTool(BasePlatformTool):
            name = "meta_test"
            description = "metadata test tool"
            config_model = DummyConfig
            response_model = DummyResponse

            async def execute(self, config, tool_context=None):
                return DummyResponse()

        meta = _MetaTestTool.metadata()
        assert isinstance(meta, ToolMetadata)
        assert meta.name == "meta_test"
        assert meta.description == "metadata test tool"
