from __future__ import annotations

from pyflow.models.tool import ToolMetadata
from pyflow.tools.base import BasePlatformTool


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

    def get_function_tool(self, name: str):
        """Get an ADK FunctionTool by tool name."""
        return self.get(name).as_function_tool()

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
