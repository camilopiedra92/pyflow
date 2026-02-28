from __future__ import annotations

import importlib
from collections.abc import Callable

from google.adk.tools import FunctionTool
from google.adk.tools.exit_loop_tool import exit_loop

from pyflow.models.tool import ToolMetadata
from pyflow.tools.base import BasePlatformTool

# ADK built-in tools available by name in workflow YAML.
# Most are pre-instantiated tool objects (not FunctionTool), returned directly via lazy import.
_ADK_BUILTIN_TOOLS: dict[str, Callable] = {
    "exit_loop": lambda: FunctionTool(func=exit_loop),
    # Grounding tools (Gemini invokes automatically when listed in tools)
    "google_search": lambda: _lazy_import_builtin("google.adk.tools", "google_search"),
    "google_maps_grounding": lambda: _lazy_import_builtin("google.adk.tools", "google_maps_grounding"),
    "enterprise_web_search": lambda: _lazy_import_builtin("google.adk.tools", "enterprise_web_search"),
    "url_context": lambda: _lazy_import_builtin("google.adk.tools", "url_context"),
    # Memory & artifact tools
    "load_memory": lambda: _lazy_import_builtin("google.adk.tools", "load_memory"),
    "preload_memory": lambda: _lazy_import_builtin("google.adk.tools", "preload_memory"),
    "load_artifacts": lambda: _lazy_import_builtin("google.adk.tools", "load_artifacts"),
    # Interactive tools
    "get_user_choice": lambda: _lazy_import_builtin("google.adk.tools", "get_user_choice"),
    # Agent transfer (useful for llm_routed orchestration)
    "transfer_to_agent": lambda: FunctionTool(
        func=_lazy_import_builtin("google.adk.tools", "transfer_to_agent")
    ),
}


def _lazy_import_builtin(module_path: str, attr: str):
    """Lazy-import an ADK built-in tool. Returns None if not available."""
    mod = importlib.import_module(module_path)
    return getattr(mod, attr)


class ToolRegistry:
    """Registry for platform tools with auto-discovery and ADK integration."""

    def __init__(self) -> None:
        self._tools: dict[str, type[BasePlatformTool]] = {}

    def discover(self) -> None:
        """Import pyflow.tools to trigger auto-registration, then collect all registered tools."""
        import pyflow.tools  # noqa: F401 — triggers __init_subclass__

        from pyflow.tools.base import get_registered_tools

        self._tools.update(get_registered_tools())

    def register(self, tool_cls: type[BasePlatformTool]) -> None:
        """Manually register a tool class."""
        self._tools[tool_cls.name] = tool_cls

    def get(self, name: str) -> BasePlatformTool:
        """Get a tool instance by name. Raises KeyError if not found."""
        if name not in self._tools:
            raise KeyError(f"Unknown tool: '{name}'. Available: {list(self._tools.keys())}")
        return self._tools[name]()

    def get_function_tool(self, name: str) -> FunctionTool:
        """Get an ADK FunctionTool by tool name.

        Resolution order: custom tools > ADK built-in tools > FQN import.
        """
        if name in self._tools:
            return self._tools[name]().as_function_tool()
        if name in _ADK_BUILTIN_TOOLS:
            return _ADK_BUILTIN_TOOLS[name]()
        # FQN fallback: try to import as 'module.callable'
        if "." in name:
            return self._resolve_fqn_tool(name)
        raise KeyError(f"Unknown tool: '{name}'. Available: {list(self._tools.keys())}")

    @staticmethod
    def _resolve_fqn_tool(fqn: str) -> FunctionTool:
        """Resolve a fully-qualified Python name to an ADK FunctionTool."""
        module_path, obj_name = fqn.rsplit(".", 1)
        module = importlib.import_module(module_path)
        obj = getattr(module, obj_name)
        if callable(obj):
            return FunctionTool(func=obj)
        raise KeyError(f"FQN '{fqn}' does not resolve to a callable.")

    def resolve_tools(self, names: list[str]) -> list:
        """Batch resolve tool names to ADK FunctionTools."""
        return [self.get_function_tool(n) for n in names]

    def list_tools(self) -> list[ToolMetadata]:
        """Return metadata for all registered tools."""
        return [cls.metadata() for cls in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
