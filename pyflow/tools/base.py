from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from typing import Any, ClassVar, get_args, get_origin

from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext
from pydantic_core import PydanticUndefined

from pyflow.models.tool import ToolConfig, ToolMetadata, ToolResponse

_TOOL_AUTO_REGISTRY: dict[str, type[BasePlatformTool]] = {}

# Types that ADK can natively handle in function signatures
_ADK_SAFE_TYPES = (str, int, float, bool)


def _is_adk_safe(annotation: Any) -> bool:
    """Check if a type annotation is safe for ADK function schema generation."""
    if annotation in _ADK_SAFE_TYPES:
        return True
    origin = get_origin(annotation)
    if origin is type(None):
        return False
    # Literal types are fine (ADK maps them to enum)
    if origin is not None:
        args = get_args(annotation)
        # Literal["GET", "POST", ...] — safe if all args are simple
        if all(isinstance(a, str) for a in args):
            return True
    return False


def _safe_annotation(annotation: Any) -> type:
    """Convert an annotation to an ADK-safe type, falling back to str."""
    if annotation in _ADK_SAFE_TYPES:
        return annotation
    return str


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
        """Convert this platform tool to an ADK FunctionTool.

        Builds a wrapper function with a proper typed signature derived from the
        Pydantic config_model. Only ADK-compatible types (str, int, float, bool)
        are exposed; complex types (dict, Any, list) are skipped so the LLM sees
        a clean schema.
        """
        tool_instance = self
        config_cls = self.config_model

        # Build parameter list from Pydantic fields (required first, then optional)
        required_params: list[inspect.Parameter] = []
        optional_params: list[inspect.Parameter] = []
        exposed_fields: set[str] = set()

        for field_name, field_info in config_cls.model_fields.items():
            ann = field_info.annotation
            if not _is_adk_safe(ann):
                safe = _safe_annotation(ann)
                # Skip fields that don't make sense as str (dict, list, Any)
                if ann is Any or (get_origin(ann) in (dict, list)):
                    continue
                ann = safe

            is_required = (
                field_info.default is PydanticUndefined and field_info.default_factory is None
            )
            exposed_fields.add(field_name)

            if is_required:
                required_params.append(
                    inspect.Parameter(
                        field_name,
                        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=ann,
                    )
                )
            else:
                default = field_info.default
                if default is PydanticUndefined:
                    default = None
                optional_params.append(
                    inspect.Parameter(
                        field_name,
                        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        default=default,
                        annotation=ann,
                    )
                )

        params = required_params + optional_params

        async def _wrapper(**kwargs: Any) -> dict:
            config = config_cls(**kwargs)
            result = await tool_instance.execute(config)
            return result.model_dump()

        _wrapper.__name__ = self.name
        _wrapper.__doc__ = self.description
        if params:
            _wrapper.__signature__ = inspect.Signature(params)
            _wrapper.__annotations__ = {p.name: p.annotation for p in params}

        return FunctionTool(func=_wrapper)

    @classmethod
    def metadata(cls) -> ToolMetadata:
        return ToolMetadata(name=cls.name, description=cls.description)


def get_registered_tools() -> dict[str, type[BasePlatformTool]]:
    """Return a copy of the auto-registration registry."""
    return dict(_TOOL_AUTO_REGISTRY)
