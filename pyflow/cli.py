from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from pyflow.core.engine import WorkflowEngine
from pyflow.core.loader import load_all_workflows, load_workflow
from pyflow.nodes import default_registry

app = typer.Typer(name="pyflow", help="PyFlow — Workflow Automation Engine")


@app.command()
def run(workflow_path: Path) -> None:
    """Execute a workflow from a YAML file."""
    wf = load_workflow(workflow_path)
    typer.echo(f"Running workflow: {wf.name}")
    engine = WorkflowEngine(registry=default_registry)
    ctx = asyncio.run(engine.run(wf))
    typer.echo(f"Completed. Run ID: {ctx.run_id}")
    for node_id in [n.id for n in wf.nodes]:
        if ctx.has_result(node_id):
            typer.echo(f"  {node_id}: OK")
        elif ctx.has_error(node_id):
            typer.echo(f"  {node_id}: ERROR — {ctx.get_error(node_id)}")
        else:
            typer.echo(f"  {node_id}: SKIPPED")


@app.command()
def validate(workflow_path: Path) -> None:
    """Validate a workflow YAML file."""
    try:
        wf = load_workflow(workflow_path)
        typer.echo(f"Valid: {wf.name} ({len(wf.nodes)} nodes)")
    except Exception as exc:
        typer.echo(f"Invalid: {exc}", err=True)
        raise typer.Exit(code=1)


@app.command(name="list")
def list_workflows(directory: Path = typer.Argument(default=Path("workflows"))) -> None:
    """List all workflows in a directory."""
    workflows = load_all_workflows(directory)
    if not workflows:
        typer.echo("No workflows found.")
        return
    for wf in workflows:
        trigger = wf.trigger.type
        typer.echo(f"  {wf.name} [{trigger}] ({len(wf.nodes)} nodes)")


@app.command()
def serve(
    workflows_dir: Path = typer.Argument(default=Path("workflows")),
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
) -> None:
    """Start PyFlow server with webhook listeners and schedulers."""
    import uvicorn
    from pyflow.server import create_app

    fastapi_app = create_app(workflows_dir)
    typer.echo(f"Starting PyFlow server on {host}:{port}")
    uvicorn.run(fastapi_app, host=host, port=port)
