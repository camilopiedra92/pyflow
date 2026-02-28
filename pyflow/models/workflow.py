from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator

from pyflow.models.agent import AgentConfig


class SkillDef(BaseModel):
    """A skill exposed via the A2A protocol."""

    id: str
    name: str
    description: str = ""
    tags: list[str] = []


class A2AConfig(BaseModel):
    """A2A protocol configuration for a workflow."""

    version: str = "1.0.0"
    skills: list[SkillDef] = []


class RuntimeConfig(BaseModel):
    """ADK runtime service configuration for a workflow."""

    session_service: Literal["in_memory", "sqlite", "database"] = "in_memory"
    session_db_url: str | None = None
    memory_service: Literal["in_memory", "none"] = "none"
    artifact_service: Literal["in_memory", "file", "none"] = "none"
    artifact_dir: str | None = None
    plugins: list[str] = []


class DagNode(BaseModel):
    """A node in a DAG orchestration with dependency edges."""

    agent: str
    depends_on: list[str] = []


class OrchestrationConfig(BaseModel):
    """Defines how agents are orchestrated within a workflow."""

    type: Literal["sequential", "parallel", "loop"]
    agents: list[str]


class WorkflowDef(BaseModel):
    """Top-level workflow definition parsed from YAML."""

    name: str
    description: str = ""
    agents: list[AgentConfig]
    orchestration: OrchestrationConfig
    a2a: A2AConfig | None = None

    @model_validator(mode="after")
    def _validate_orchestration_refs(self) -> WorkflowDef:
        agent_names = {a.name for a in self.agents}
        for ref in self.orchestration.agents:
            if ref not in agent_names:
                raise ValueError(
                    f"Orchestration references unknown agent '{ref}'. "
                    f"Known agents: {sorted(agent_names)}"
                )
        return self
