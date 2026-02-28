from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
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

    type: Literal["sequential", "parallel", "loop", "react", "dag", "llm_routed"]
    agents: list[str] | None = None  # for sequential/parallel/loop/llm_routed
    nodes: list[DagNode] | None = None  # for dag
    agent: str | None = None  # for react (single agent)
    router: str | None = None  # for llm_routed
    planner: str | None = None  # for react
    max_iterations: int | None = None  # for loop

    @model_validator(mode="after")
    def _validate_type_fields(self) -> OrchestrationConfig:
        """Validate that required fields are present for each orchestration type."""
        orch_type = self.type

        if orch_type in ("sequential", "parallel", "loop"):
            if not self.agents:
                raise ValueError(
                    f"Orchestration type '{orch_type}' requires a non-empty 'agents' list"
                )

        elif orch_type == "react":
            if not self.agent:
                raise ValueError("Orchestration type 'react' requires the 'agent' field")

        elif orch_type == "dag":
            if not self.nodes:
                raise ValueError("Orchestration type 'dag' requires a non-empty 'nodes' list")
            self._validate_dag()

        elif orch_type == "llm_routed":
            if not self.router:
                raise ValueError("Orchestration type 'llm_routed' requires the 'router' field")
            if not self.agents:
                raise ValueError(
                    "Orchestration type 'llm_routed' requires a non-empty 'agents' list"
                )

        return self

    def _validate_dag(self) -> None:
        """Validate DAG nodes: no unknown dependencies and no cycles (Kahn's algorithm)."""
        assert self.nodes is not None
        node_names = {n.agent for n in self.nodes}

        # Check for unknown dependencies
        for node in self.nodes:
            for dep in node.depends_on:
                if dep not in node_names:
                    raise ValueError(
                        f"Unknown dependency '{dep}' in DAG node '{node.agent}'. "
                        f"Known nodes: {sorted(node_names)}"
                    )

        # Kahn's algorithm for cycle detection
        in_degree: dict[str, int] = {name: 0 for name in node_names}
        adjacency: dict[str, list[str]] = {name: [] for name in node_names}

        for node in self.nodes:
            for dep in node.depends_on:
                adjacency[dep].append(node.agent)
                in_degree[node.agent] += 1

        # Start with nodes that have no dependencies
        queue = [name for name, degree in in_degree.items() if degree == 0]
        visited_count = 0

        while queue:
            current = queue.pop(0)
            visited_count += 1
            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count != len(node_names):
            raise ValueError("DAG contains a cycle. All nodes must form a directed acyclic graph.")


class WorkflowDef(BaseModel):
    """Top-level workflow definition parsed from YAML."""

    name: str
    description: str = ""
    agents: list[AgentConfig]
    orchestration: OrchestrationConfig
    a2a: A2AConfig | None = None
    runtime: RuntimeConfig = RuntimeConfig()

    @model_validator(mode="after")
    def _validate_orchestration_refs(self) -> WorkflowDef:
        agent_names = {a.name for a in self.agents}
        orch = self.orchestration

        # Validate `agents` list references (sequential, parallel, loop, llm_routed)
        if orch.agents:
            for ref in orch.agents:
                if ref not in agent_names:
                    raise ValueError(
                        f"Orchestration references unknown agent '{ref}'. "
                        f"Known agents: {sorted(agent_names)}"
                    )

        # Validate `nodes` agent references (dag)
        if orch.nodes:
            for node in orch.nodes:
                if node.agent not in agent_names:
                    raise ValueError(
                        f"Orchestration references unknown agent '{node.agent}'. "
                        f"Known agents: {sorted(agent_names)}"
                    )

        # Validate `agent` reference (react)
        if orch.agent and orch.agent not in agent_names:
            raise ValueError(
                f"Orchestration references unknown agent '{orch.agent}'. "
                f"Known agents: {sorted(agent_names)}"
            )

        # Validate `router` reference (llm_routed)
        if orch.router and orch.router not in agent_names:
            raise ValueError(
                f"Orchestration references unknown agent '{orch.router}'. "
                f"Known agents: {sorted(agent_names)}"
            )

        return self

    @classmethod
    def from_yaml(cls, path: Path) -> WorkflowDef:
        """Load and validate a YAML file into a WorkflowDef."""
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")
        data = yaml.safe_load(path.read_text())
        return cls(**data)
