from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext

from pyflow.models.tool import ToolConfig, ToolMetadata, ToolResponse

_TOOL_AUTO_REGISTRY: dict[str, type[BasePlatformTool]] = {}


class BasePlatformTool(ABC):
    """Base class for all platform tools. Subclasses auto-register via __init_subclass__."""

    name: ClassVar[str]
    description: ClassVar[str]
    config_model: ClassVar[type[ToolConfig]]
    response_model: ClassVar[type[ToolResponse]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "name") and isinstance(cls.__dict__.get("name"), str):
            _TOOL_AUTO_REGISTRY[cls.name] = cls

    @abstractmethod
    async def execute(
        self, config: ToolConfig, tool_context: ToolContext | None = None
    ) -> ToolResponse: ...

    def as_function_tool(self) -> FunctionTool:
        """Convert this platform tool to an ADK FunctionTool."""
        tool_instance = self
        config_cls = self.config_model

        async def _wrapper(**kwargs: Any) -> dict:
            config = config_cls(**kwargs)
            result = await tool_instance.execute(config)
            return result.model_dump()

        _wrapper.__name__ = self.name
        _wrapper.__doc__ = self.description
        return FunctionTool(func=_wrapper)

    @classmethod
    def metadata(cls) -> ToolMetadata:
        return ToolMetadata(name=cls.name, description=cls.description)


def get_registered_tools() -> dict[str, type[BasePlatformTool]]:
    """Return a copy of the auto-registration registry."""
    return dict(_TOOL_AUTO_REGISTRY)
