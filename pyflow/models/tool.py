from __future__ import annotations

from pydantic import BaseModel


class ToolConfig(BaseModel):
    """Base class for all tool configs. Tools extend this with their own fields."""


class ToolResponse(BaseModel):
    """Base class for all tool responses. Tools extend this with their own fields."""


class ToolMetadata(BaseModel):
    """Metadata describing a registered tool."""

    name: str
    description: str
    version: str = "1.0.0"
    tags: list[str] = []
