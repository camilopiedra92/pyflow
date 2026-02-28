from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RunResult(BaseModel):
    """Result from executing a workflow via PlatformRunner."""

    content: str = ""
    author: str = ""
    usage_metadata: Any = None
