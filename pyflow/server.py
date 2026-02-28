from __future__ import annotations

import json
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pyflow.models.a2a import AgentCard
from pyflow.models.platform import PlatformConfig
from pyflow.models.server import (
    HealthResponse,
    ToolListResponse,
    WorkflowListResponse,
    WorkflowRunResponse,
)
from pyflow.platform.app import PyFlowPlatform

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Boot platform on startup, shutdown on exit."""
    platform = PyFlowPlatform(PlatformConfig())
    await platform.boot()
    app.state.platform = platform
    logger.info("server.started")
    yield
    await platform.shutdown()
    logger.info("server.stopped")


app = FastAPI(title="PyFlow Platform", lifespan=lifespan)


def _get_platform() -> PyFlowPlatform:
    return app.state.platform


# --- Health ---


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(booted=_get_platform().is_booted)


# --- Tools ---


@app.get("/api/tools", response_model=ToolListResponse)
async def list_tools():
    return ToolListResponse(tools=_get_platform().list_tools())


# --- Workflows ---


@app.get("/api/workflows", response_model=WorkflowListResponse)
async def list_workflows():
    return WorkflowListResponse(workflows=_get_platform().list_workflows())


class WorkflowInput(BaseModel):
    message: str = ""
    data: dict = {}
    user_id: str = "default"


@app.post("/api/workflows/{name}/run", response_model=WorkflowRunResponse)
async def run_workflow(name: str, input_data: WorkflowInput):
    platform = _get_platform()
    try:
        result = await platform.run_workflow(
            name,
            input_data.model_dump(exclude={"user_id"}),
            user_id=input_data.user_id,
        )
        return WorkflowRunResponse(result=result)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found")
    except Exception as e:
        logger.error("workflow.error", workflow=name, error=str(e))
        raise HTTPException(status_code=500, detail="Internal workflow error")


@app.post("/api/workflows/{name}/stream")
async def stream_workflow(name: str, input_data: WorkflowInput):
    """Stream workflow execution events as server-sent events."""
    platform = _get_platform()
    try:
        hw = platform.workflows.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found")

    if hw.agent is None:
        raise HTTPException(status_code=500, detail=f"Workflow '{name}' not hydrated")

    runtime = hw.definition.runtime
    runner = platform.executor.build_runner(hw.agent, runtime)

    async def _event_stream():
        async for event in platform.executor.run_streaming(
            runner,
            user_id=input_data.user_id,
            message=input_data.message,
        ):
            payload = {
                "author": getattr(event, "author", ""),
                "is_final": event.is_final_response(),
            }
            if event.content and event.content.parts:
                payload["content"] = event.content.parts[0].text or ""
            else:
                payload["content"] = ""
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


# --- A2A ---


@app.get("/.well-known/agent-card.json", response_model=list[AgentCard])
async def agent_cards():
    return _get_platform().agent_cards()


@app.post("/a2a/{workflow_name}", response_model=WorkflowRunResponse)
async def a2a_execute(workflow_name: str, input_data: WorkflowInput):
    """A2A execution endpoint."""
    platform = _get_platform()
    try:
        result = await platform.run_workflow(
            workflow_name,
            input_data.model_dump(exclude={"user_id"}),
            user_id=input_data.user_id,
        )
        return WorkflowRunResponse(result=result)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_name}' not found")
    except Exception as e:
        logger.error("a2a.error", workflow=workflow_name, error=str(e))
        raise HTTPException(status_code=500, detail="Internal error")
