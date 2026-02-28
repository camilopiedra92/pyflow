from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RunResult(BaseModel):
    """Result from executing a workflow via WorkflowExecutor."""

    content: str = ""
    author: str = ""
    usage_metadata: Any = None
    session_id: str | None = None
