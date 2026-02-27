import pytest
from pyflow.nodes.transform import TransformNode
from pyflow.core.context import ExecutionContext


class TestTransformNode:
    def test_node_type(self):
        assert TransformNode.node_type == "transform"

    async def test_jsonpath_expression(self):
        node = TransformNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_result("prev", {"data": {"users": [{"name": "Alice"}, {"name": "Bob"}]}})
        result = await node.execute(
            {"input": "{{ prev }}", "expression": "$.data.users[0].name"}, ctx
        )
        assert result == "Alice"

    async def test_jsonpath_returns_list(self):
        node = TransformNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_result("prev", {"items": [1, 2, 3]})
        result = await node.execute(
            {"input": "{{ prev }}", "expression": "$.items[*]"}, ctx
        )
        assert result == [1, 2, 3]
