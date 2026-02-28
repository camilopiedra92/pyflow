from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import AsyncGenerator

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event
from pydantic import model_validator


@dataclass
class DagNode:
    """Runtime DAG node pairing an agent with its dependency names."""

    name: str
    agent: BaseAgent
    depends_on: set[str] = field(default_factory=set)


class DagAgent(BaseAgent):
    """DAG orchestrator: executes sub-agents respecting dependency edges.

    Agents with satisfied dependencies run in parallel (wave execution).
    Data flows between agents via session.state using output_key.
    """

    dag_nodes: list  # list of DagNode dataclass instances

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def _validate_dag(self):
        """Validate no cycles exist using Kahn's algorithm."""
        node_names = {n.name for n in self.dag_nodes}
        in_degree = {n.name: len(n.depends_on) for n in self.dag_nodes}
        dependents = defaultdict(list)

        for node in self.dag_nodes:
            for dep in node.depends_on:
                if dep not in node_names:
                    raise ValueError(f"Unknown dependency '{dep}' in node '{node.name}'")
                dependents[dep].append(node.name)

        queue = [name for name, deg in in_degree.items() if deg == 0]
        visited = 0
        while queue:
            current = queue.pop(0)
            visited += 1
            for child in dependents[current]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if visited != len(self.dag_nodes):
            raise ValueError("DAG contains a cycle")
        return self

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Execute DAG with wave-based parallel scheduling."""
        nodes_by_name = {n.name: n for n in self.dag_nodes}
        remaining_deps = {n.name: set(n.depends_on) for n in self.dag_nodes}
        completed: set[str] = set()
        started: set[str] = set()

        while len(completed) < len(self.dag_nodes):
            # Find ready nodes: all deps satisfied, not started
            ready = [
                name
                for name, deps in remaining_deps.items()
                if deps.issubset(completed) and name not in started
            ]

            if not ready:
                raise RuntimeError("DAG deadlock: no ready nodes but not all completed")

            # Launch ready nodes in parallel
            async def run_node(node_name: str):
                node = nodes_by_name[node_name]
                events = []
                async for event in node.agent.run_async(ctx):
                    events.append(event)
                return node_name, events

            tasks = [run_node(name) for name in ready]
            for name in ready:
                started.add(name)

            # Run in parallel with gather
            finished = await asyncio.gather(*tasks)

            for node_name, events in finished:
                completed.add(node_name)
                # Yield all events from this node
                for event in events:
                    yield event
