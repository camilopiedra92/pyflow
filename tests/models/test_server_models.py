from __future__ import annotations

import pytest

from pyflow.models.runner import RunResult
from pyflow.models.server import (
    HealthResponse,
    ToolListResponse,
    WorkflowListResponse,
    WorkflowRunResponse,
)
from pyflow.models.tool import ToolMetadata
from pyflow.models.workflow import WorkflowDef


class TestHealthResponse:
    def test_creation(self):
        resp = HealthResponse(booted=True)
        assert resp.status == "ok"
        assert resp.booted is True

    def test_not_booted(self):
        resp = HealthResponse(booted=False)
        assert resp.status == "ok"
        assert resp.booted is False

    def test_custom_status(self):
        resp = HealthResponse(status="degraded", booted=True)
        assert resp.status == "degraded"

    def test_booted_required(self):
        with pytest.raises(Exception):
            HealthResponse()

    def test_serialization(self):
        resp = HealthResponse(booted=True)
        data = resp.model_dump()
        assert data == {"status": "ok", "booted": True}


class TestToolListResponse:
    def test_creation(self):
        tools = [ToolMetadata(name="http", description="HTTP requests")]
        resp = ToolListResponse(tools=tools)
        assert len(resp.tools) == 1
        assert resp.tools[0].name == "http"

    def test_empty_list(self):
        resp = ToolListResponse(tools=[])
        assert resp.tools == []

    def test_tools_required(self):
        with pytest.raises(Exception):
            ToolListResponse()

    def test_serialization(self):
        resp = ToolListResponse(
            tools=[ToolMetadata(name="t1", description="Tool 1")]
        )
        data = resp.model_dump()
        assert data["tools"][0]["name"] == "t1"


class TestWorkflowListResponse:
    def _make_workflow(self, name: str = "wf1") -> WorkflowDef:
        return WorkflowDef(
            name=name,
            agents=[
                {
                    "name": "a",
                    "type": "llm",
                    "model": "gemini-2.5-flash",
                    "instruction": "test",
                }
            ],
            orchestration={"type": "sequential", "agents": ["a"]},
        )

    def test_creation(self):
        resp = WorkflowListResponse(workflows=[self._make_workflow()])
        assert len(resp.workflows) == 1
        assert resp.workflows[0].name == "wf1"

    def test_empty_list(self):
        resp = WorkflowListResponse(workflows=[])
        assert resp.workflows == []

    def test_workflows_required(self):
        with pytest.raises(Exception):
            WorkflowListResponse()

    def test_serialization(self):
        resp = WorkflowListResponse(workflows=[self._make_workflow()])
        data = resp.model_dump()
        assert data["workflows"][0]["name"] == "wf1"


class TestWorkflowRunResponse:
    def test_creation(self):
        result = RunResult(content="done", author="bot")
        resp = WorkflowRunResponse(result=result)
        assert resp.result.content == "done"
        assert resp.result.author == "bot"

    def test_result_required(self):
        with pytest.raises(Exception):
            WorkflowRunResponse()

    def test_serialization(self):
        result = RunResult(content="hi", author="agent", usage_metadata={"t": 1})
        resp = WorkflowRunResponse(result=result)
        data = resp.model_dump()
        assert data["result"]["content"] == "hi"
        assert data["result"]["author"] == "agent"
        assert data["result"]["usage_metadata"] == {"t": 1}
