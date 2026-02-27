from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException

from pyflow.core.engine import WorkflowEngine
from pyflow.core.loader import load_all_workflows
from pyflow.nodes import default_registry


def create_app(workflows_dir: Path = Path("workflows")) -> FastAPI:
    app = FastAPI(title="PyFlow", version="0.1.0")
    engine = WorkflowEngine(registry=default_registry)

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
        try:
            ctx = await engine.run(wf)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        results = {}
        for node in wf.nodes:
            if ctx.has_result(node.id):
                results[node.id] = "ok"
            elif ctx.has_error(node.id):
                results[node.id] = f"error: {ctx.get_error(node.id)}"
            else:
                results[node.id] = "skipped"
        return {"run_id": ctx.run_id, "results": results}

    return app
