from __future__ import annotations

from pathlib import Path

import yaml

from pyflow.core.models import WorkflowDef


def load_workflow(path: Path) -> WorkflowDef:
    if not path.exists():
        raise FileNotFoundError(f"Workflow file not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return WorkflowDef(**data)


def load_all_workflows(directory: Path) -> list[WorkflowDef]:
    workflows = []
    for path in sorted(directory.glob("*.yaml")):
        workflows.append(load_workflow(path))
    for path in sorted(directory.glob("*.yml")):
        workflows.append(load_workflow(path))
    return workflows
