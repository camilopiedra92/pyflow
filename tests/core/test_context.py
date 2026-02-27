import pytest
from pyflow.core.context import ExecutionContext


class TestExecutionContext:
    def test_store_and_retrieve_result(self):
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_result("step1", {"data": [1, 2, 3]})
        assert ctx.get_result("step1") == {"data": [1, 2, 3]}

    def test_get_missing_result_raises(self):
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        with pytest.raises(KeyError):
            ctx.get_result("nonexistent")

    def test_has_result(self):
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        assert ctx.has_result("step1") is False
        ctx.set_result("step1", "ok")
        assert ctx.has_result("step1") is True

    def test_all_results(self):
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_result("a", 1)
        ctx.set_result("b", 2)
        assert ctx.all_results() == {"a": 1, "b": 2}

    def test_run_id_is_set(self):
        ctx = ExecutionContext(workflow_name="test", run_id="run-123")
        assert ctx.run_id == "run-123"
        assert ctx.workflow_name == "test"

    def test_mark_node_error(self):
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_error("step1", "Connection refused")
        assert ctx.get_error("step1") == "Connection refused"
        assert ctx.has_error("step1") is True
        assert ctx.has_error("step2") is False
