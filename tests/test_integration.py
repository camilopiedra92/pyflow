import pytest
from pathlib import Path
from pyflow.core.engine import WorkflowEngine
from pyflow.core.loader import load_workflow
from pyflow.nodes import default_registry

FIXTURES = Path(__file__).parent / "fixtures"


class TestIntegration:
    async def test_multi_step_workflow(self):
        wf = load_workflow(FIXTURES / "multi_step.yaml")
        engine = WorkflowEngine(registry=default_registry)
        ctx = await engine.run(wf)

        assert ctx.get_result("start") is True
        assert ctx.get_result("transform") == [1, 2, 3, 4, 5]
        assert ctx.get_result("check") is True

    async def test_load_and_validate_all_fixtures(self):
        from pyflow.core.loader import load_all_workflows
        workflows = load_all_workflows(FIXTURES)
        assert len(workflows) >= 2
