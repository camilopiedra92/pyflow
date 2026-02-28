from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

import pytest
from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext

from pyflow.models.agent import OpenApiToolConfig
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


# -- Built-in tool catalog tests ----------------------------------------------


class TestBuiltinToolCatalog:
    def test_resolve_exit_loop(self) -> None:
        """exit_loop ADK built-in should be resolvable via resolve_tools."""
        registry = ToolRegistry()
        registry.discover()
        tools = registry.resolve_tools(["exit_loop"])
        assert len(tools) == 1

    def test_custom_takes_priority_over_builtin(self) -> None:
        """Custom tools should resolve normally and take priority over built-in."""
        registry = ToolRegistry()
        registry.discover()
        # http_request is custom, should resolve normally
        tool = registry.get_function_tool("http_request")
        assert tool is not None

    def test_resolve_google_search(self) -> None:
        """google_search ADK built-in should be resolvable via get_function_tool."""
        registry = ToolRegistry()
        registry.discover()
        tool = registry.get_function_tool("google_search")
        assert tool is not None

    def test_resolve_load_memory(self) -> None:
        """load_memory ADK built-in should be resolvable via get_function_tool."""
        registry = ToolRegistry()
        registry.discover()
        tool = registry.get_function_tool("load_memory")
        assert tool is not None

    def test_resolve_google_maps_grounding(self) -> None:
        """google_maps_grounding ADK built-in should be resolvable."""
        registry = ToolRegistry()
        registry.discover()
        tool = registry.get_function_tool("google_maps_grounding")
        assert tool is not None

    def test_resolve_enterprise_web_search(self) -> None:
        """enterprise_web_search ADK built-in should be resolvable."""
        registry = ToolRegistry()
        registry.discover()
        tool = registry.get_function_tool("enterprise_web_search")
        assert tool is not None

    def test_resolve_url_context(self) -> None:
        """url_context ADK built-in should be resolvable."""
        registry = ToolRegistry()
        registry.discover()
        tool = registry.get_function_tool("url_context")
        assert tool is not None

    def test_resolve_preload_memory(self) -> None:
        """preload_memory ADK built-in should be resolvable."""
        registry = ToolRegistry()
        registry.discover()
        tool = registry.get_function_tool("preload_memory")
        assert tool is not None

    def test_resolve_load_artifacts(self) -> None:
        """load_artifacts ADK built-in should be resolvable."""
        registry = ToolRegistry()
        registry.discover()
        tool = registry.get_function_tool("load_artifacts")
        assert tool is not None

    def test_resolve_get_user_choice(self) -> None:
        """get_user_choice ADK built-in should be resolvable."""
        registry = ToolRegistry()
        registry.discover()
        tool = registry.get_function_tool("get_user_choice")
        assert tool is not None

    def test_resolve_transfer_to_agent(self) -> None:
        """transfer_to_agent ADK built-in should be resolvable."""
        registry = ToolRegistry()
        registry.discover()
        tool = registry.get_function_tool("transfer_to_agent")
        assert tool is not None

    def test_unknown_tool_raises(self) -> None:
        """get_function_tool() should raise KeyError for unknown tool name."""
        registry = ToolRegistry()
        registry.discover()
        with pytest.raises(KeyError):
            registry.get_function_tool("nonexistent_tool")


class TestFQNToolResolution:
    def test_fqn_resolves_callable(self) -> None:
        """FQN like 'json.dumps' should resolve to a FunctionTool."""
        registry = ToolRegistry()
        tool = registry.get_function_tool("json.dumps")
        assert isinstance(tool, FunctionTool)

    def test_fqn_resolves_stdlib_function(self) -> None:
        """FQN for a stdlib function should resolve."""
        registry = ToolRegistry()
        tool = registry.get_function_tool("os.path.exists")
        assert isinstance(tool, FunctionTool)

    def test_fqn_non_callable_raises(self) -> None:
        """FQN pointing to a non-callable should raise KeyError."""
        registry = ToolRegistry()
        with pytest.raises(KeyError, match="does not resolve to a callable"):
            registry.get_function_tool("os.sep")

    def test_fqn_bad_module_raises(self) -> None:
        """FQN with non-existent module should raise."""
        registry = ToolRegistry()
        with pytest.raises((KeyError, ModuleNotFoundError)):
            registry.get_function_tool("nonexistent_module.func")

    def test_fqn_does_not_shadow_custom_tools(self) -> None:
        """Custom tools should take priority over FQN resolution."""
        registry = ToolRegistry()
        registry.register(_DummyTool)
        tool = registry.get_function_tool("dummy_tool")
        assert isinstance(tool, FunctionTool)


# -- OpenAPI tool registration tests ------------------------------------------


class TestOpenApiToolRegistration:
    def test_register_openapi_tools(self, tmp_path) -> None:
        """register_openapi_tools() stores toolset instances keyed by name."""
        spec_file = tmp_path / "specs" / "test.yaml"
        spec_file.parent.mkdir(parents=True)
        spec_file.write_text("openapi: '3.0.0'")

        registry = ToolRegistry()
        configs = {"myapi": OpenApiToolConfig(spec="specs/test.yaml")}

        with patch(
            "google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset.OpenAPIToolset"
        ) as MockToolset:
            MockToolset.return_value = MagicMock()
            registry.register_openapi_tools(configs, base_dir=tmp_path)

        assert "myapi" in registry
        MockToolset.assert_called_once()

    def test_len_includes_openapi(self, tmp_path) -> None:
        """__len__ includes both custom and OpenAPI tools."""
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text("openapi: '3.0.0'")

        registry = ToolRegistry()
        registry.register(_DummyTool)
        configs = {"api1": OpenApiToolConfig(spec="spec.yaml")}

        with patch(
            "google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset.OpenAPIToolset"
        ) as MockToolset:
            MockToolset.return_value = MagicMock()
            registry.register_openapi_tools(configs, base_dir=tmp_path)

        assert len(registry) == 2  # dummy_tool + api1

    def test_contains_openapi(self, tmp_path) -> None:
        """__contains__ finds OpenAPI tools."""
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text("openapi: '3.0.0'")

        registry = ToolRegistry()
        configs = {"ynab": OpenApiToolConfig(spec="spec.yaml")}

        with patch(
            "google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset.OpenAPIToolset"
        ) as MockToolset:
            MockToolset.return_value = MagicMock()
            registry.register_openapi_tools(configs, base_dir=tmp_path)

        assert "ynab" in registry
        assert "nonexistent" not in registry

    def test_all_tool_names(self, tmp_path) -> None:
        """all_tool_names() returns merged sorted list."""
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text("openapi: '3.0.0'")

        registry = ToolRegistry()
        registry.register(_DummyTool)
        configs = {"ynab": OpenApiToolConfig(spec="spec.yaml")}

        with patch(
            "google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset.OpenAPIToolset"
        ) as MockToolset:
            MockToolset.return_value = MagicMock()
            registry.register_openapi_tools(configs, base_dir=tmp_path)

        names = registry.all_tool_names()
        assert "dummy_tool" in names
        assert "ynab" in names
        assert names == sorted(names)

    def test_get_tool_union_openapi(self, tmp_path) -> None:
        """get_tool_union() returns OpenAPIToolset for registered OpenAPI tools."""
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text("openapi: '3.0.0'")

        registry = ToolRegistry()
        mock_toolset = MagicMock()
        configs = {"ynab": OpenApiToolConfig(spec="spec.yaml")}

        with patch(
            "google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset.OpenAPIToolset"
        ) as MockToolset:
            MockToolset.return_value = mock_toolset
            registry.register_openapi_tools(configs, base_dir=tmp_path)

        result = registry.get_tool_union("ynab")
        assert result is mock_toolset

    def test_get_tool_union_custom(self) -> None:
        """get_tool_union() returns FunctionTool for custom platform tools."""
        registry = ToolRegistry()
        registry.register(_DummyTool)
        result = registry.get_tool_union("dummy_tool")
        assert isinstance(result, FunctionTool)

    def test_get_tool_union_builtin(self) -> None:
        """get_tool_union() resolves ADK built-in tools."""
        registry = ToolRegistry()
        result = registry.get_tool_union("exit_loop")
        assert result is not None

    def test_get_tool_union_unknown_raises(self) -> None:
        """get_tool_union() raises KeyError for unknown tools."""
        registry = ToolRegistry()
        with pytest.raises(KeyError, match="Unknown tool"):
            registry.get_tool_union("nonexistent")

    def test_resolve_tools_mixed(self, tmp_path) -> None:
        """resolve_tools() returns mixed list of FunctionTool and OpenAPIToolset."""
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text("openapi: '3.0.0'")

        registry = ToolRegistry()
        registry.register(_DummyTool)
        mock_toolset = MagicMock()
        configs = {"ynab": OpenApiToolConfig(spec="spec.yaml")}

        with patch(
            "google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset.OpenAPIToolset"
        ) as MockToolset:
            MockToolset.return_value = mock_toolset
            registry.register_openapi_tools(configs, base_dir=tmp_path)

        tools = registry.resolve_tools(["dummy_tool", "ynab"])
        assert len(tools) == 2
        assert isinstance(tools[0], FunctionTool)
        assert tools[1] is mock_toolset

    def test_custom_takes_priority_over_openapi(self, tmp_path) -> None:
        """Custom tools take priority over OpenAPI tools with same name."""
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text("openapi: '3.0.0'")

        registry = ToolRegistry()
        registry.register(_DummyTool)
        configs = {"dummy_tool": OpenApiToolConfig(spec="spec.yaml")}

        with patch(
            "google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset.OpenAPIToolset"
        ) as MockToolset:
            MockToolset.return_value = MagicMock()
            registry.register_openapi_tools(configs, base_dir=tmp_path)

        # Custom tool should win
        result = registry.get_tool_union("dummy_tool")
        assert isinstance(result, FunctionTool)
