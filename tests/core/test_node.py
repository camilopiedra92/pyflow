import pytest
from pyflow.core.node import BaseNode, NodeRegistry
from pyflow.core.context import ExecutionContext
from pyflow.core.models import NodeDef


class FakeNode(BaseNode):
    node_type = "fake"

    async def execute(self, config: dict, context: ExecutionContext) -> object:
        return {"fake": True}


class TestNodeRegistry:
    def setup_method(self):
        self.registry = NodeRegistry()

    def test_register_and_get(self):
        self.registry.register(FakeNode)
        cls = self.registry.get("fake")
        assert cls is FakeNode

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown node type"):
            self.registry.get("nonexistent")

    def test_register_duplicate_raises(self):
        self.registry.register(FakeNode)
        with pytest.raises(ValueError, match="already registered"):
            self.registry.register(FakeNode)

    def test_list_types(self):
        self.registry.register(FakeNode)
        assert "fake" in self.registry.list_types()


class TestBaseNode:
    async def test_execute(self):
        node = FakeNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute({"key": "value"}, ctx)
        assert result == {"fake": True}
