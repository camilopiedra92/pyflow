from __future__ import annotations

import json

import pytest

from pyflow.core.context import ExecutionContext
from pyflow.nodes.storage import StorageNode


class TestStorageNode:
    def test_node_type(self):
        assert StorageNode.node_type == "storage"

    async def test_read_existing_file(self, tmp_path):
        data = [{"rate": 1.05, "date": "2026-02-27"}]
        file = tmp_path / "rates.json"
        file.write_text(json.dumps(data), encoding="utf-8")

        node = StorageNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {"path": str(file), "action": "read"}, ctx
        )
        assert result == data

    async def test_read_missing_file_returns_empty_list(self, tmp_path):
        node = StorageNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {"path": str(tmp_path / "nonexistent.json"), "action": "read"}, ctx
        )
        assert result == []

    async def test_write_creates_file(self, tmp_path):
        file = tmp_path / "output.json"
        data = [{"rate": 1.10}]

        node = StorageNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {"path": str(file), "action": "write", "data": data}, ctx
        )
        assert result == data
        assert file.exists()
        assert json.loads(file.read_text(encoding="utf-8")) == data

    async def test_write_creates_parent_dirs(self, tmp_path):
        file = tmp_path / "nested" / "deep" / "output.json"
        data = {"key": "value"}

        node = StorageNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {"path": str(file), "action": "write", "data": data}, ctx
        )
        assert result == data
        assert file.exists()
        assert file.parent.exists()

    async def test_append_to_existing(self, tmp_path):
        file = tmp_path / "rates.json"
        file.write_text(json.dumps([{"rate": 1.05}]), encoding="utf-8")

        node = StorageNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {"path": str(file), "action": "append", "data": {"rate": 1.10}}, ctx
        )
        assert result == [{"rate": 1.05}, {"rate": 1.10}]
        assert json.loads(file.read_text(encoding="utf-8")) == [{"rate": 1.05}, {"rate": 1.10}]

    async def test_append_to_missing_file(self, tmp_path):
        file = tmp_path / "new_rates.json"

        node = StorageNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {"path": str(file), "action": "append", "data": {"rate": 1.05}}, ctx
        )
        assert result == [{"rate": 1.05}]
        assert file.exists()
        assert json.loads(file.read_text(encoding="utf-8")) == [{"rate": 1.05}]

    async def test_unknown_action_raises(self, tmp_path):
        node = StorageNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        with pytest.raises(ValueError, match="Unknown storage action: 'delete'"):
            await node.execute(
                {"path": str(tmp_path / "data.json"), "action": "delete"}, ctx
            )

    async def test_default_action_is_read(self, tmp_path):
        file = tmp_path / "data.json"
        file.write_text(json.dumps([{"x": 1}]), encoding="utf-8")

        node = StorageNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute({"path": str(file)}, ctx)
        assert result == [{"x": 1}]
