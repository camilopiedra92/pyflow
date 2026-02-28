from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, ConfigDict

from pyflow.models.workflow import WorkflowDef
from pyflow.platform.registry.discovery import scan_agent_packages

if TYPE_CHECKING:
    from pyflow.platform.registry.tool_registry import ToolRegistry


class HydratedWorkflow(BaseModel):
    """A workflow definition paired with its hydrated ADK agent (when available)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    definition: WorkflowDef
    agent: Any = None  # Filled by hydrator in Phase 2B
    package_dir: Path | None = None  # Directory containing workflow.yaml


class WorkflowRegistry:
    """Registry for workflow definitions with YAML auto-discovery."""

    def __init__(self) -> None:
        self._workflows: dict[str, HydratedWorkflow] = {}

    def discover(self, directory: Path) -> None:
        """Scan directory for agent packages (subdirs containing workflow.yaml)."""
        for pkg_dir in scan_agent_packages(directory):
            workflow_def = self._load_yaml(pkg_dir / "workflow.yaml")
            self._workflows[workflow_def.name] = HydratedWorkflow(
                definition=workflow_def, package_dir=pkg_dir
            )

    def _load_yaml(self, path: Path) -> WorkflowDef:
        """Load and validate a YAML file into a WorkflowDef."""
        data = yaml.safe_load(path.read_text())
        return WorkflowDef(**data)

    def register(self, workflow: WorkflowDef) -> None:
        """Manually register a workflow definition."""
        self._workflows[workflow.name] = HydratedWorkflow(definition=workflow)

    def get(self, name: str) -> HydratedWorkflow:
        """Get a hydrated workflow by name. Raises KeyError if not found."""
        if name not in self._workflows:
            raise KeyError(f"Unknown workflow: '{name}'. Available: {list(self._workflows.keys())}")
        return self._workflows[name]

    def list_workflows(self) -> list[WorkflowDef]:
        """Return all workflow definitions."""
        return [hw.definition for hw in self._workflows.values()]

    def all(self) -> list[HydratedWorkflow]:
        """Return all hydrated workflow entries."""
        return list(self._workflows.values())

    def hydrate(self, tool_registry: ToolRegistry) -> None:
        """Hydrate all workflows by converting WorkflowDefs into ADK agent trees."""
        from pyflow.platform.hydration.hydrator import WorkflowHydrator

        for hw in self._workflows.values():
            hydrator = WorkflowHydrator(tool_registry)
            hw.agent = hydrator.hydrate(hw.definition)

    def __len__(self) -> int:
        return len(self._workflows)

    def __contains__(self, name: str) -> bool:
        return name in self._workflows
