from __future__ import annotations

import os
import uuid
from pathlib import Path

import structlog
from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from pyflow.core.engine import WorkflowEngine
from pyflow.core.loader import load_all_workflows
from pyflow.nodes import default_registry

logger = structlog.get_logger()


class _ApiKeyMiddleware(BaseHTTPMiddleware):
    """Require Bearer token on /trigger/ endpoints when PYFLOW_API_KEY is set."""

    def __init__(self, app, api_key: str) -> None:  # noqa: ANN001
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        if request.url.path.startswith(("/trigger/", "/reload")):
            auth = request.headers.get("authorization", "")
            if not auth.startswith("Bearer ") or auth[7:] != self._api_key:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key"},
                )
        return await call_next(request)


def create_app(workflows_dir: Path = Path("workflows")) -> FastAPI:
    app = FastAPI(title="PyFlow", version="0.1.0")
    engine = WorkflowEngine(registry=default_registry)

    api_key = os.environ.get("PYFLOW_API_KEY")
    if api_key:
        app.add_middleware(_ApiKeyMiddleware, api_key=api_key)

    workflows = {wf.name: wf for wf in load_all_workflows(workflows_dir)}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/workflows")
    async def list_workflows():
        return [
            {"name": wf.name, "trigger": wf.trigger.type, "nodes": len(wf.nodes)}
            for wf in workflows.values()
        ]

    @app.post("/trigger/{workflow_name}")
    async def trigger_workflow(workflow_name: str, payload: dict | None = None):
        if workflow_name not in workflows:
            raise HTTPException(status_code=404, detail=f"Workflow '{workflow_name}' not found")
        wf = workflows[workflow_name]
        initial_context = {"trigger": payload} if payload else None
        run_id = str(uuid.uuid4())
        try:
            ctx = await engine.run(wf, run_id=run_id, initial_context=initial_context)
        except Exception as exc:
            logger.error("trigger.error", workflow=workflow_name, run_id=run_id, error=str(exc))
            raise HTTPException(
                status_code=500,
                detail=f"Workflow execution failed (run_id={run_id})",
            )
        results = {}
        for node in wf.nodes:
            if ctx.has_result(node.id):
                results[node.id] = "ok"
            elif ctx.has_error(node.id):
                results[node.id] = f"error: {ctx.get_error(node.id)}"
            else:
                results[node.id] = "skipped"
        return {"run_id": ctx.run_id, "results": results}

    @app.post("/reload")
    async def reload_workflows():
        reloaded = {wf.name: wf for wf in load_all_workflows(workflows_dir)}
        workflows.clear()
        workflows.update(reloaded)
        return {"status": "ok", "workflows": len(workflows)}

    return app
