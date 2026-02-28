from __future__ import annotations

from pydantic import BaseModel


class UsageSummary(BaseModel):
    """Aggregate execution metrics collected by MetricsPlugin."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
    duration_ms: int = 0
    steps: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    model: str | None = None


class RunResult(BaseModel):
    """Result from executing a workflow via WorkflowExecutor."""

    content: str = ""
    author: str = ""
    usage: UsageSummary | None = None
    session_id: str | None = None
