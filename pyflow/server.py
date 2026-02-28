from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from pyflow.models.platform import PlatformConfig
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


@app.get("/health")
async def health():
    return {"status": "ok", "booted": _get_platform().is_booted}


# --- Tools ---


@app.get("/api/tools")
async def list_tools():
    tools = _get_platform().list_tools()
    return {"tools": [t.model_dump() for t in tools]}


# --- Workflows ---


@app.get("/api/workflows")
async def list_workflows():
    workflows = _get_platform().list_workflows()
    return {"workflows": [w.model_dump() for w in workflows]}


class WorkflowInput(BaseModel):
    message: str = ""
    data: dict = {}


@app.post("/api/workflows/{name}/run")
async def run_workflow(name: str, input_data: WorkflowInput):
    platform = _get_platform()
    try:
        result = await platform.run_workflow(name, input_data.model_dump())
        return {"result": result}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found")
    except Exception as e:
        logger.error("workflow.error", workflow=name, error=str(e))
        raise HTTPException(status_code=500, detail="Internal workflow error")


# --- A2A ---


@app.get("/.well-known/agent-card.json")
async def agent_cards():
    cards = _get_platform().agent_cards()
    return cards


@app.post("/a2a/{workflow_name}")
async def a2a_execute(workflow_name: str, input_data: WorkflowInput):
    """A2A execution endpoint."""
    platform = _get_platform()
    try:
        result = await platform.run_workflow(workflow_name, input_data.model_dump())
        return {"result": result}
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Workflow '{workflow_name}' not found"
        )
    except Exception as e:
        logger.error("a2a.error", workflow=workflow_name, error=str(e))
        raise HTTPException(status_code=500, detail="Internal error")
