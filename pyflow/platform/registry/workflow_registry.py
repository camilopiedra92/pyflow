from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from pyflow.models.workflow import WorkflowDef
from pyflow.platform.registry.discovery import scan_directory

if TYPE_CHECKING:
    from pyflow.platform.registry.tool_registry import ToolRegistry


@dataclass
class HydratedWorkflow:
    """A workflow definition paired with its hydrated ADK agent (when available)."""

    definition: WorkflowDef
    agent: Any | None = None  # Filled by hydrator in Phase 2B


class WorkflowRegistry:
    """Registry for workflow definitions with YAML auto-discovery."""

    def __init__(self) -> None:
        self._workflows: dict[str, HydratedWorkflow] = {}

    def discover(self, directory: Path) -> None:
        """Scan directory for YAML workflow files, parse into WorkflowDef, store."""
        for yaml_path in scan_directory(directory, ".yaml"):
            workflow_def = self._load_yaml(yaml_path)
            self._workflows[workflow_def.name] = HydratedWorkflow(definition=workflow_def)

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
            raise KeyError(
                f"Unknown workflow: '{name}'. Available: {list(self._workflows.keys())}"
            )
        return self._workflows[name]

    def list_workflows(self) -> list[WorkflowDef]:
        """Return all workflow definitions."""
        return [hw.definition for hw in self._workflows.values()]

    def all(self) -> list[HydratedWorkflow]:
        """Return all hydrated workflow entries."""
        return list(self._workflows.values())

    def hydrate(self, tool_registry: ToolRegistry) -> None:
        """Hydrate all workflows. Placeholder -- Phase 2B fills this."""
        pass

    def __len__(self) -> int:
        return len(self._workflows)

    def __contains__(self, name: str) -> bool:
        return name in self._workflows
