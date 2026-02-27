import pytest
from pyflow.core.engine import WorkflowEngine
from pyflow.core.node import BaseNode, NodeRegistry
from pyflow.core.context import ExecutionContext
from pyflow.core.models import WorkflowDef

# Track execution order
execution_log: list[str] = []


class AppendNode(BaseNode):
    node_type = "append"

    async def execute(self, config: dict, context: ExecutionContext) -> object:
        execution_log.append(config.get("value", "default"))
        return config.get("value", "default")


class FailingNode(BaseNode):
    node_type = "failing"

    async def execute(self, config: dict, context: ExecutionContext) -> object:
        raise RuntimeError("intentional failure")


def make_registry() -> NodeRegistry:
    reg = NodeRegistry()
    reg.register(AppendNode)
    reg.register(FailingNode)
    return reg


class TestWorkflowEngine:
    def setup_method(self):
        execution_log.clear()

    async def test_single_node(self):
        wf = WorkflowDef(
            name="single",
            trigger={"type": "manual"},
            nodes=[{"id": "a", "type": "append", "config": {"value": "a"}}],
        )
        engine = WorkflowEngine(registry=make_registry())
        ctx = await engine.run(wf)
        assert ctx.get_result("a") == "a"

    async def test_sequential_dag(self):
        wf = WorkflowDef(
            name="sequential",
            trigger={"type": "manual"},
            nodes=[
                {"id": "a", "type": "append", "config": {"value": "a"}},
                {"id": "b", "type": "append", "depends_on": ["a"], "config": {"value": "b"}},
                {"id": "c", "type": "append", "depends_on": ["b"], "config": {"value": "c"}},
            ],
        )
        engine = WorkflowEngine(registry=make_registry())
        ctx = await engine.run(wf)
        assert execution_log == ["a", "b", "c"]
        assert ctx.get_result("c") == "c"

    async def test_parallel_dag(self):
        wf = WorkflowDef(
            name="parallel",
            trigger={"type": "manual"},
            nodes=[
                {"id": "a", "type": "append", "config": {"value": "a"}},
                {"id": "b", "type": "append", "config": {"value": "b"}},
                {"id": "c", "type": "append", "depends_on": ["a", "b"], "config": {"value": "c"}},
            ],
        )
        engine = WorkflowEngine(registry=make_registry())
        ctx = await engine.run(wf)
        assert execution_log[-1] == "c"
        assert set(execution_log[:2]) == {"a", "b"}

    async def test_node_failure_with_stop(self):
        wf = WorkflowDef(
            name="fail-stop",
            trigger={"type": "manual"},
            nodes=[
                {"id": "a", "type": "failing", "config": {}, "on_error": "stop"},
                {"id": "b", "type": "append", "depends_on": ["a"], "config": {"value": "b"}},
            ],
        )
        engine = WorkflowEngine(registry=make_registry())
        ctx = await engine.run(wf)
        assert ctx.has_error("a")
        assert not ctx.has_result("b")

    async def test_node_failure_with_skip(self):
        wf = WorkflowDef(
            name="fail-skip",
            trigger={"type": "manual"},
            nodes=[
                {"id": "a", "type": "failing", "config": {}, "on_error": "skip"},
                {"id": "b", "type": "append", "config": {"value": "b"}},
            ],
        )
        engine = WorkflowEngine(registry=make_registry())
        ctx = await engine.run(wf)
        assert ctx.has_error("a")
        assert ctx.get_result("b") == "b"

    async def test_when_condition_skips_node(self):
        wf = WorkflowDef(
            name="conditional",
            trigger={"type": "manual"},
            nodes=[
                {"id": "a", "type": "append", "config": {"value": "a"}},
                {
                    "id": "b",
                    "type": "append",
                    "depends_on": ["a"],
                    "when": "a == 'nope'",
                    "config": {"value": "b"},
                },
            ],
        )
        engine = WorkflowEngine(registry=make_registry())
        ctx = await engine.run(wf)
        assert ctx.get_result("a") == "a"
        assert not ctx.has_result("b")

    async def test_cycle_detection(self):
        wf = WorkflowDef(
            name="cycle",
            trigger={"type": "manual"},
            nodes=[
                {"id": "a", "type": "append", "depends_on": ["b"], "config": {}},
                {"id": "b", "type": "append", "depends_on": ["a"], "config": {}},
            ],
        )
        engine = WorkflowEngine(registry=make_registry())
        with pytest.raises(ValueError, match="[Cc]ycle"):
            await engine.run(wf)

    async def test_template_resolution_in_config(self):
        wf = WorkflowDef(
            name="templates",
            trigger={"type": "manual"},
            nodes=[
                {"id": "a", "type": "append", "config": {"value": "hello"}},
                {
                    "id": "b",
                    "type": "append",
                    "depends_on": ["a"],
                    "config": {"value": "got: {{ a }}"},
                },
            ],
        )
        engine = WorkflowEngine(registry=make_registry())
        ctx = await engine.run(wf)
        assert ctx.get_result("b") == "got: hello"
