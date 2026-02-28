from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from pyflow.models.workflow import WorkflowDef
from pyflow.platform.registry.tool_registry import ToolRegistry
from pyflow.platform.registry.workflow_registry import HydratedWorkflow, WorkflowRegistry

# -- Helpers -------------------------------------------------------------------

_VALID_WORKFLOW_YAML = """\
name: test_workflow
description: A test workflow
agents:
  - name: fetcher
    type: llm
    model: gemini-2.5-flash
    instruction: Fetch data
    tools: [http_request]
    output_key: data
orchestration:
  type: sequential
  agents: [fetcher]
"""

_SECOND_WORKFLOW_YAML = """\
name: second_workflow
description: Another test workflow
agents:
  - name: analyzer
    type: llm
    model: anthropic/claude-sonnet-4-20250514
    instruction: Analyze data
    tools: [condition]
orchestration:
  type: sequential
  agents: [analyzer]
"""

_INVALID_WORKFLOW_YAML = """\
name: bad_workflow
description: Missing required orchestration field
agents:
  - name: agent1
    type: llm
    instruction: Do stuff
"""


@pytest.fixture
def registry() -> WorkflowRegistry:
    return WorkflowRegistry()


# -- Tests --------------------------------------------------------------------


def test_discover_loads_yaml_files(tmp_path: Path, registry: WorkflowRegistry) -> None:
    """discover() should load all YAML files from a directory into the registry."""
    (tmp_path / "workflow1.yaml").write_text(_VALID_WORKFLOW_YAML)
    (tmp_path / "workflow2.yaml").write_text(_SECOND_WORKFLOW_YAML)

    registry.discover(tmp_path)
    assert len(registry) == 2
    assert "test_workflow" in registry
    assert "second_workflow" in registry


def test_discover_validates_yaml(tmp_path: Path, registry: WorkflowRegistry) -> None:
    """discover() should raise ValidationError for invalid workflow YAML."""
    (tmp_path / "bad.yaml").write_text(_INVALID_WORKFLOW_YAML)

    with pytest.raises(ValidationError):
        registry.discover(tmp_path)


def test_register_workflow(registry: WorkflowRegistry) -> None:
    """register() should add a WorkflowDef to the registry."""
    wf = WorkflowDef(
        name="manual_workflow",
        description="Manually registered",
        agents=[
            {
                "name": "agent1",
                "type": "llm",
                "model": "gemini-2.5-flash",
                "instruction": "Do something",
            }
        ],
        orchestration={"type": "sequential", "agents": ["agent1"]},
    )
    registry.register(wf)
    assert "manual_workflow" in registry
    assert len(registry) == 1


def test_get_returns_hydrated_workflow(registry: WorkflowRegistry) -> None:
    """get() should return a HydratedWorkflow wrapping the WorkflowDef."""
    wf = WorkflowDef(
        name="my_workflow",
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
    registry.register(wf)
    hydrated = registry.get("my_workflow")
    assert isinstance(hydrated, HydratedWorkflow)
    assert hydrated.definition.name == "my_workflow"
    assert hydrated.agent is None  # Not yet hydrated


def test_get_unknown_raises_keyerror(registry: WorkflowRegistry) -> None:
    """get() should raise KeyError for an unknown workflow name."""
    with pytest.raises(KeyError, match="Unknown workflow: 'missing'"):
        registry.get("missing")


def test_list_workflows(tmp_path: Path, registry: WorkflowRegistry) -> None:
    """list_workflows() should return all WorkflowDef objects."""
    (tmp_path / "wf.yaml").write_text(_VALID_WORKFLOW_YAML)
    registry.discover(tmp_path)

    workflows = registry.list_workflows()
    assert len(workflows) == 1
    assert isinstance(workflows[0], WorkflowDef)
    assert workflows[0].name == "test_workflow"


def test_all_returns_hydrated_list(tmp_path: Path, registry: WorkflowRegistry) -> None:
    """all() should return list of HydratedWorkflow objects."""
    (tmp_path / "wf1.yaml").write_text(_VALID_WORKFLOW_YAML)
    (tmp_path / "wf2.yaml").write_text(_SECOND_WORKFLOW_YAML)
    registry.discover(tmp_path)

    hydrated_list = registry.all()
    assert len(hydrated_list) == 2
    assert all(isinstance(hw, HydratedWorkflow) for hw in hydrated_list)


def test_discover_agent_packages(tmp_path: Path, registry: WorkflowRegistry) -> None:
    """discover() scans agent packages (dirs with workflow.yaml) when path contains them."""
    pkg = tmp_path / "test_pkg"
    pkg.mkdir()
    (pkg / "workflow.yaml").write_text(_VALID_WORKFLOW_YAML)
    (pkg / "__init__.py").touch()

    registry.discover(tmp_path)
    assert len(registry) == 1
    assert "test_workflow" in registry


def test_hydrate_placeholder(registry: WorkflowRegistry) -> None:
    """hydrate() is a no-op placeholder for Phase 2B."""
    tool_registry = ToolRegistry()
    # Should not raise
    registry.hydrate(tool_registry)
