from __future__ import annotations

from pydantic import BaseModel

from pyflow.models.runner import RunResult
from pyflow.models.tool import ToolMetadata
from pyflow.models.workflow import WorkflowDef


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    booted: bool


class ToolListResponse(BaseModel):
    """Response listing all registered tools."""

    tools: list[ToolMetadata]


class WorkflowListResponse(BaseModel):
    """Response listing all registered workflows."""

    workflows: list[WorkflowDef]


class WorkflowRunResponse(BaseModel):
    """Response from running a workflow."""

    result: RunResult
