from __future__ import annotations

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event
from typing import AsyncGenerator

from pyflow.platform.agents.dag_agent import DagAgent, DagNodeRuntime


class StubAgent(BaseAgent):
    """Minimal BaseAgent subclass for testing."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        return
        yield  # make it an async generator


def _make_stub_agent(name: str) -> StubAgent:
    """Create a real BaseAgent stub for testing."""
    return StubAgent(name=name)


class TestDagValidation:
    def test_valid_linear_dag(self):
        a = _make_stub_agent("a")
        b = _make_stub_agent("b")
        nodes = [
            DagNodeRuntime(name="a", agent=a, depends_on=set()),
            DagNodeRuntime(name="b", agent=b, depends_on={"a"}),
        ]
        dag = DagAgent(name="test", dag_nodes=nodes, sub_agents=[a, b])
        assert len(dag.dag_nodes) == 2

    def test_valid_diamond_dag(self):
        agents = {n: _make_stub_agent(n) for n in "abcd"}
        nodes = [
            DagNodeRuntime(name="a", agent=agents["a"], depends_on=set()),
            DagNodeRuntime(name="b", agent=agents["b"], depends_on={"a"}),
            DagNodeRuntime(name="c", agent=agents["c"], depends_on={"a"}),
            DagNodeRuntime(name="d", agent=agents["d"], depends_on={"b", "c"}),
        ]
        dag = DagAgent(name="diamond", dag_nodes=nodes, sub_agents=list(agents.values()))
        assert len(dag.dag_nodes) == 4

    def test_single_node(self):
        a = _make_stub_agent("a")
        nodes = [DagNodeRuntime(name="a", agent=a, depends_on=set())]
        dag = DagAgent(name="test", dag_nodes=nodes, sub_agents=[a])
        assert len(dag.dag_nodes) == 1
