from __future__ import annotations

from typing import Any, ClassVar

import pytest
from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext

from pyflow.models.tool import ToolMetadata
from pyflow.platform.registry.tool_registry import ToolRegistry
from pyflow.tools.base import BasePlatformTool


# -- Fixtures / helpers -------------------------------------------------------


class _DummyTool(BasePlatformTool):
    name: ClassVar[str] = "dummy_tool"
    description: ClassVar[str] = "A dummy tool for testing"

    async def execute(self, tool_context: ToolContext, **kwargs: Any) -> dict:
        return {"result": "executed"}


@pytest.fixture
def registry() -> ToolRegistry:
    return ToolRegistry()


# -- Tests --------------------------------------------------------------------


def test_discover_finds_all_platform_tools(registry: ToolRegistry) -> None:
    """After discover(), the registry should contain all built-in platform tools."""
    registry.discover()
    expected_tools = {"http_request", "transform", "condition", "alert", "storage"}
    for tool_name in expected_tools:
        assert tool_name in registry, f"Expected '{tool_name}' in registry"
    assert len(registry) >= len(expected_tools)


def test_get_returns_tool_instance(registry: ToolRegistry) -> None:
    """get() should return an instance of the tool class."""
    registry.discover()
    tool = registry.get("http_request")
    assert isinstance(tool, BasePlatformTool)


def test_get_unknown_raises_keyerror(registry: ToolRegistry) -> None:
    """get() should raise KeyError for an unknown tool name."""
    with pytest.raises(KeyError, match="Unknown tool: 'nonexistent'"):
        registry.get("nonexistent")


def test_register_custom_tool(registry: ToolRegistry) -> None:
    """Manually registering a tool makes it available via get()."""
    registry.register(_DummyTool)
    assert "dummy_tool" in registry
    tool = registry.get("dummy_tool")
    assert isinstance(tool, _DummyTool)


def test_get_function_tool_returns_adk_type(registry: ToolRegistry) -> None:
    """get_function_tool() should return an ADK FunctionTool."""
    registry.register(_DummyTool)
    ft = registry.get_function_tool("dummy_tool")
    assert isinstance(ft, FunctionTool)


def test_resolve_tools_batch(registry: ToolRegistry) -> None:
    """resolve_tools() should return a list of FunctionTools for the given names."""
    registry.discover()
    tools = registry.resolve_tools(["http_request", "transform"])
    assert len(tools) == 2
    assert all(isinstance(t, FunctionTool) for t in tools)


def test_list_tools_returns_metadata(registry: ToolRegistry) -> None:
    """list_tools() should return ToolMetadata for all registered tools."""
    registry.discover()
    metadata = registry.list_tools()
    assert len(metadata) > 0
    assert all(isinstance(m, ToolMetadata) for m in metadata)
    names = {m.name for m in metadata}
    assert "http_request" in names


def test_len_and_contains(registry: ToolRegistry) -> None:
    """__len__ and __contains__ work correctly."""
    assert len(registry) == 0
    assert "http_request" not in registry

    registry.discover()
    assert len(registry) > 0
    assert "http_request" in registry


def test_resolve_tools_unknown_raises_keyerror(registry: ToolRegistry) -> None:
    """resolve_tools() should raise KeyError if any tool name is unknown."""
    with pytest.raises(KeyError, match="Unknown tool"):
        registry.resolve_tools(["does_not_exist"])
