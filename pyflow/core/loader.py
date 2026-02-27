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
    paths = sorted([*directory.glob("*.yaml"), *directory.glob("*.yml")])
    return [load_workflow(path) for path in paths]
