from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext

from pyflow.models.tool import ToolMetadata

_TOOL_AUTO_REGISTRY: dict[str, type[BasePlatformTool]] = {}


class BasePlatformTool(ABC):
    """Base class for auto-registering platform tools.

    Subclasses define name, description, and implement execute() with
    typed parameters. ADK's FunctionTool inspects the function signature directly.
    """

    name: ClassVar[str]
    description: ClassVar[str]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "name") and isinstance(cls.__dict__.get("name"), str):
            _TOOL_AUTO_REGISTRY[cls.name] = cls

    @abstractmethod
    async def execute(self, tool_context: ToolContext, **kwargs: Any) -> dict:
        """Execute the tool. Subclasses define their own typed parameters."""
        ...

    @classmethod
    def as_function_tool(cls) -> FunctionTool:
        """Convert to ADK FunctionTool via native function inspection."""
        instance = cls()
        return FunctionTool(func=instance.execute)

    @classmethod
    def metadata(cls) -> ToolMetadata:
        """Return tool metadata for registry listing."""
        return ToolMetadata(name=cls.name, description=cls.description)


def get_registered_tools() -> dict[str, type[BasePlatformTool]]:
    """Return a copy of the auto-registration registry."""
    return dict(_TOOL_AUTO_REGISTRY)
