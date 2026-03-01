from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from google.adk.tools import FunctionTool

from pyflow.models.tool import ToolMetadata
from pyflow.platform.openapi_auth import resolve_openapi_auth
from pyflow.tools.base import BasePlatformTool

if TYPE_CHECKING:
    from google.adk.tools import BaseTool
    from google.adk.tools.base_toolset import BaseToolset
    from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset

    from pyflow.models.agent import OpenApiToolConfig

# ADK built-in tools available by name in workflow YAML.
# Most are pre-instantiated tool objects (not FunctionTool), returned directly via lazy import.
_ADK_BUILTIN_TOOLS: dict[str, Callable] = {
    "exit_loop": lambda: _lazy_import_builtin("google.adk.tools", "exit_loop"),
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
    "transfer_to_agent": lambda: _lazy_import_builtin("google.adk.tools", "transfer_to_agent"),
}


def _lazy_import_builtin(module_path: str, attr: str):
    """Lazy-import an ADK built-in tool. Returns None if not available."""
    mod = importlib.import_module(module_path)
    return getattr(mod, attr)


class ToolRegistry:
    """Registry for platform tools with auto-discovery and ADK integration."""

    def __init__(self) -> None:
        self._tools: dict[str, type[BasePlatformTool]] = {}
        self._openapi_tools: dict[str, OpenAPIToolset] = {}

    def discover(self) -> None:
        """Import pyflow.tools to trigger auto-registration, then collect all registered tools."""
        import pyflow.tools  # noqa: F401 — triggers __init_subclass__

        from pyflow.tools.base import get_registered_tools

        self._tools.update(get_registered_tools())

    def register(self, tool_cls: type[BasePlatformTool]) -> None:
        """Manually register a tool class."""
        self._tools[tool_cls.name] = tool_cls

    def register_openapi_tools(
        self, configs: dict[str, OpenApiToolConfig], base_dir: Path
    ) -> None:
        """Pre-build OpenAPIToolset instances from workflow-level configs.

        Each config is keyed by tool name (e.g. 'ynab') and contains the spec
        path and auth settings. The spec is read once and the toolset is cached
        for resolution via get_tool_union().
        """
        from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import (
            OpenAPIToolset,
        )

        for name, cfg in configs.items():
            spec_path = base_dir / cfg.spec
            spec_str = spec_path.read_text()
            spec_type = "json" if spec_path.suffix == ".json" else "yaml"
            auth_scheme, auth_credential = resolve_openapi_auth(cfg.auth)
            kwargs: dict = {
                "spec_str": spec_str,
                "spec_str_type": spec_type,
            }
            if auth_scheme is not None:
                kwargs["auth_scheme"] = auth_scheme
            if auth_credential is not None:
                kwargs["auth_credential"] = auth_credential
            self._openapi_tools[name] = OpenAPIToolset(**kwargs)

    def get(self, name: str) -> BasePlatformTool:
        """Get a tool instance by name. Raises KeyError if not found."""
        if name not in self._tools:
            raise KeyError(f"Unknown tool: '{name}'. Available: {list(self._tools.keys())}")
        return self._tools[name]()

    def get_function_tool(self, name: str) -> FunctionTool | BaseTool | Callable:
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

    def get_tool_union(self, name: str) -> FunctionTool | BaseTool | BaseToolset | Callable:
        """Resolve a tool name to an ADK-compatible tool (FunctionTool or BaseToolset).

        4-tier resolution: custom tools > OpenAPI toolsets > ADK built-ins > FQN import.
        """
        if name in self._tools:
            return self._tools[name]().as_function_tool()
        if name in self._openapi_tools:
            return self._openapi_tools[name]
        if name in _ADK_BUILTIN_TOOLS:
            return _ADK_BUILTIN_TOOLS[name]()
        if "." in name:
            return self._resolve_fqn_tool(name)
        raise KeyError(f"Unknown tool: '{name}'. Available: {self.all_tool_names()}")

    @staticmethod
    def _resolve_fqn_tool(fqn: str) -> FunctionTool:
        """Resolve a fully-qualified Python name to an ADK FunctionTool."""
        module_path, obj_name = fqn.rsplit(".", 1)
        module = importlib.import_module(module_path)
        obj = getattr(module, obj_name)
        if callable(obj):
            return FunctionTool(func=obj)
        raise KeyError(f"FQN '{fqn}' does not resolve to a callable.")

    def resolve_tools(
        self, tool_refs: list[str | dict[str, list[str]]]
    ) -> list[FunctionTool | BaseTool | BaseToolset | Callable]:
        """Batch resolve tool references to ADK tools (FunctionTool, BaseToolset, or FilteredToolset).

        Each ref is either a string (resolved via get_tool_union) or a dict
        like ``{"ynab": ["get*"]}`` which wraps the named OpenAPI toolset
        in a FilteredToolset with fnmatch glob patterns.
        """
        from pyflow.platform.filtered_toolset import FilteredToolset

        result = []
        for ref in tool_refs:
            if isinstance(ref, str):
                result.append(self.get_tool_union(ref))
            elif isinstance(ref, dict):
                name, patterns = next(iter(ref.items()))
                if name not in self._openapi_tools:
                    raise KeyError(
                        f"Filtered tool '{name}' is not a registered OpenAPI tool. "
                        f"Available: {self.all_tool_names()}"
                    )
                result.append(FilteredToolset(self._openapi_tools[name], patterns))
        return result

    def all_tool_names(self) -> list[str]:
        """Return all registered tool names (custom + OpenAPI)."""
        return sorted(set(self._tools) | set(self._openapi_tools))

    def list_tools(self) -> list[ToolMetadata]:
        """Return metadata for all registered tools."""
        return [cls.metadata() for cls in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools) + len(self._openapi_tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools or name in self._openapi_tools
