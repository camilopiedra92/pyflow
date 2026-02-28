from __future__ import annotations

from pydantic import BaseModel


class ToolMetadata(BaseModel):
    """Metadata describing a registered tool."""

    name: str
    description: str
    version: str = "1.0.0"
    tags: list[str] = []
