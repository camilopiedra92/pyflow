"""Example — ADK-compatible agent package."""
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
