from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from pyflow.models.agent import OpenApiToolConfig


class ProjectConfig(BaseModel):
    """Project-level configuration loaded from pyflow.yaml.

    Holds infrastructure config that applies across all workflows,
    such as OpenAPI tool definitions. Returns empty defaults when
    pyflow.yaml doesn't exist (backwards-compatible).
    """

    openapi_tools: dict[str, OpenApiToolConfig] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path) -> ProjectConfig:
        """Load project config from a YAML file.

        Returns empty config if the file doesn't exist.
        """
        if not path.exists():
            return cls()
        data = yaml.safe_load(path.read_text())
        return cls(**(data or {}))
