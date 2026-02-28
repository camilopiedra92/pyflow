from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import AsyncGenerator

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event


@dataclass
class DagNodeRuntime:
    """Runtime DAG node pairing an agent with its dependency names."""

    name: str
    agent: BaseAgent
    depends_on: set[str] = field(default_factory=set)


class DagAgent(BaseAgent):
    """DAG orchestrator: executes sub-agents respecting dependency edges.

    Agents with satisfied dependencies run in parallel (wave execution).
    Data flows between agents via session.state using output_key.

    Cycle detection and dependency validation are handled at YAML parse time
    by OrchestrationConfig._validate_dag().
    """

    dag_nodes: list[DagNodeRuntime]

    model_config = {"arbitrary_types_allowed": True}

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
