from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
import structlog

from pyflow.platform.app import PyFlowPlatform
from pyflow.models.platform import PlatformConfig

app = typer.Typer(name="pyflow", help="PyFlow ADK Platform")
logger = structlog.get_logger()

_INIT_AGENT_PY = '''\
"""{name} — ADK-compatible agent package."""
from __future__ import annotations

from pathlib import Path

from pyflow.models.workflow import WorkflowDef
from pyflow.platform.hydration.hydrator import WorkflowHydrator
from pyflow.platform.registry.tool_registry import ToolRegistry

_WORKFLOW_PATH = Path(__file__).parent / "workflow.yaml"


def _build_agent():
    """Hydrate YAML workflow into an ADK agent tree."""
    tools = ToolRegistry()
    tools.discover()
    workflow = WorkflowDef.from_yaml(_WORKFLOW_PATH)
    hydrator = WorkflowHydrator(tools)
    return hydrator.hydrate(workflow)


root_agent = _build_agent()
'''

_INIT_WORKFLOW_YAML = '''\
name: {name}
description: "{name} workflow"

agents:
  - name: main
    type: llm
    model: gemini-2.5-flash
    instruction: "You are a helpful assistant."
    output_key: result

orchestration:
  type: sequential
  agents: [main]

runtime:
  session_service: in_memory
'''

_INIT_CARD_JSON = '''\
{{
  "name": "{name}",
  "description": "{name} workflow",
  "url": "http://localhost:8000/a2a/{name}",
  "version": "1.0.0",
  "protocolVersion": "0.2.6",
  "capabilities": {{}},
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["application/json"],
  "skills": []
}}
'''


@app.command()
def run(
    workflow_name: str = typer.Argument(help="Name of workflow to execute"),
    input_json: str = typer.Option("{}", "--input", "-i", help="JSON input for the workflow"),
    user_id: str = typer.Option("default", "--user-id", "-u", help="User ID for session"),
    workflows_dir: str = typer.Option(
        "agents", "--workflows-dir", "-w", help="Workflows directory"
    ),
) -> None:
    """Run a workflow by name."""
    try:
        input_data = json.loads(input_json)
    except json.JSONDecodeError as e:
        typer.echo(f"Invalid JSON input: {e}", err=True)
        raise typer.Exit(code=1)

    config = PlatformConfig(workflows_dir=workflows_dir)
    platform = PyFlowPlatform(config)

    async def _run():
        await platform.boot()
        try:
            result = await platform.run_workflow(workflow_name, input_data, user_id=user_id)
            data = result.model_dump() if hasattr(result, "model_dump") else result
            typer.echo(json.dumps(data, indent=2))
        finally:
            await platform.shutdown()

    asyncio.run(_run())


@app.command()
def validate(
    yaml_path: str = typer.Argument(help="Path to workflow YAML file"),
) -> None:
    """Validate a workflow YAML file without executing."""
    import yaml as pyyaml
    from pyflow.models.workflow import WorkflowDef

    path = Path(yaml_path)
    if not path.exists():
        typer.echo(f"File not found: {yaml_path}", err=True)
        raise typer.Exit(code=1)

    try:
        data = pyyaml.safe_load(path.read_text())
        workflow = WorkflowDef(**data)
        typer.echo(f"Valid workflow: {workflow.name}")
    except Exception as e:
        typer.echo(f"Validation error: {e}", err=True)
        raise typer.Exit(code=1)


@app.command(name="list")
def list_cmd(
    tools: bool = typer.Option(False, "--tools", "-t", help="List platform tools"),
    workflows: bool = typer.Option(False, "--workflows", "-w", help="List workflows"),
    workflows_dir: str = typer.Option("agents", "--workflows-dir", help="Workflows directory"),
) -> None:
    """List registered tools or discovered workflows."""
    config = PlatformConfig(workflows_dir=workflows_dir)
    platform = PyFlowPlatform(config)

    async def _list():
        await platform.boot()
        try:
            if tools:
                for t in platform.list_tools():
                    typer.echo(f"  {t.name}: {t.description}")
            elif workflows:
                for w in platform.list_workflows():
                    typer.echo(f"  {w.name}: {w.description}")
            else:
                typer.echo("Use --tools or --workflows")
        finally:
            await platform.shutdown()

    asyncio.run(_list())


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Server host"),
    port: int = typer.Option(8000, "--port", "-p", help="Server port"),
    workflows_dir: str = typer.Option(
        "agents", "--workflows-dir", "-w", help="Workflows directory"
    ),
) -> None:
    """Start the FastAPI server."""
    import uvicorn

    uvicorn.run("pyflow.server:app", host=host, port=port, reload=False)


@app.command()
def init(
    name: str = typer.Argument(help="Name for the new agent package"),
    agents_dir: str = typer.Option("agents", "--agents-dir", help="Agents directory"),
) -> None:
    """Scaffold a new agent package."""
    pkg_dir = Path(agents_dir) / name
    if pkg_dir.exists():
        typer.echo(f"Package already exists: {pkg_dir}", err=True)
        raise typer.Exit(code=1)

    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("from .agent import root_agent\n")
    (pkg_dir / "agent.py").write_text(_INIT_AGENT_PY.format(name=name))
    (pkg_dir / "workflow.yaml").write_text(_INIT_WORKFLOW_YAML.format(name=name))
    (pkg_dir / "agent-card.json").write_text(_INIT_CARD_JSON.format(name=name))
    typer.echo(f"Created agent package: {pkg_dir}")


def main() -> None:
    """CLI entrypoint."""
    app()
