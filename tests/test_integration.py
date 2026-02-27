from __future__ import annotations

import json

import pytest
from pathlib import Path
from pyflow.core.engine import WorkflowEngine
from pyflow.core.loader import load_workflow
from pyflow.core.models import WorkflowDef, TriggerDef, NodeDef
from pyflow.nodes import default_registry

FIXTURES = Path(__file__).parent / "fixtures"
WORKFLOWS = Path(__file__).parent.parent / "workflows"


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

    async def test_exchange_rate_workflow_loads(self):
        wf_path = WORKFLOWS / "exchange_rate_tracker.yaml"
        if not wf_path.exists():
            pytest.skip("exchange_rate_tracker.yaml not yet created")
        wf = load_workflow(wf_path)
        assert wf.name == "exchange-rate-tracker"
        assert len(wf.nodes) >= 1

    async def test_storage_roundtrip_in_workflow(self, tmp_path):
        file_path = str(tmp_path / "data.json")
        wf = WorkflowDef(
            name="storage-roundtrip",
            trigger=TriggerDef(type="manual"),
            nodes=[
                NodeDef(
                    id="write_data",
                    type="storage",
                    config={
                        "path": file_path,
                        "action": "write",
                        "data": [{"rate": 1.05}],
                    },
                ),
                NodeDef(
                    id="append_data",
                    type="storage",
                    depends_on=["write_data"],
                    config={
                        "path": file_path,
                        "action": "append",
                        "data": {"rate": 1.10},
                    },
                ),
                NodeDef(
                    id="read_data",
                    type="storage",
                    depends_on=["append_data"],
                    config={
                        "path": file_path,
                        "action": "read",
                    },
                ),
            ],
        )
        engine = WorkflowEngine(registry=default_registry)
        ctx = await engine.run(wf)

        assert ctx.get_result("write_data") == [{"rate": 1.05}]
        assert ctx.get_result("append_data") == [{"rate": 1.05}, {"rate": 1.10}]
        assert ctx.get_result("read_data") == [{"rate": 1.05}, {"rate": 1.10}]
        # Verify file on disk
        assert json.loads(Path(file_path).read_text(encoding="utf-8")) == [
            {"rate": 1.05},
            {"rate": 1.10},
        ]
