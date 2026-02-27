import pytest
from pyflow.nodes.condition import ConditionNode
from pyflow.core.context import ExecutionContext


class TestConditionNode:
    def test_node_type(self):
        assert ConditionNode.node_type == "condition"

    async def test_true_condition(self):
        node = ConditionNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_result("prev", 42)
        result = await node.execute({"if": "prev > 10"}, ctx)
        assert result is True

    async def test_false_condition(self):
        node = ConditionNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_result("prev", 5)
        result = await node.execute({"if": "prev > 10"}, ctx)
        assert result is False

    async def test_string_comparison(self):
        node = ConditionNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_result("step1", {"status": "active"})
        result = await node.execute({"if": "step1['status'] == 'active'"}, ctx)
        assert result is True
