import pytest
import yaml
from pyflow.core.models import NodeDef, TriggerDef, WorkflowDef, OnError


class TestNodeDef:
    def test_minimal_node(self):
        node = NodeDef(id="step1", type="http", config={"url": "https://example.com"})
        assert node.id == "step1"
        assert node.type == "http"
        assert node.depends_on == []
        assert node.on_error == OnError.STOP
        assert node.when is None

    def test_node_with_dependencies(self):
        node = NodeDef(
            id="step2",
            type="transform",
            depends_on=["step1"],
            when="step1.result == true",
            config={"expression": "$.data"},
        )
        assert node.depends_on == ["step1"]
        assert node.when == "step1.result == true"

    def test_node_with_retry(self):
        node = NodeDef(
            id="step1",
            type="http",
            config={"url": "https://example.com"},
            on_error=OnError.RETRY,
            retry={"max_retries": 3, "delay": 2},
        )
        assert node.retry["max_retries"] == 3

    def test_node_requires_id_and_type(self):
        with pytest.raises(Exception):
            NodeDef(config={})


class TestTriggerDef:
    def test_webhook_trigger(self):
        trigger = TriggerDef(type="webhook", config={"path": "/hooks/github"})
        assert trigger.type == "webhook"

    def test_schedule_trigger(self):
        trigger = TriggerDef(type="schedule", config={"cron": "0 * * * *"})
        assert trigger.type == "schedule"

    def test_manual_trigger(self):
        trigger = TriggerDef(type="manual")
        assert trigger.config == {}


class TestWorkflowDef:
    def test_parse_from_dict(self):
        data = {
            "name": "test-workflow",
            "trigger": {"type": "manual"},
            "nodes": [
                {"id": "step1", "type": "http", "config": {"url": "https://example.com"}},
            ],
        }
        wf = WorkflowDef(**data)
        assert wf.name == "test-workflow"
        assert len(wf.nodes) == 1
        assert wf.trigger.type == "manual"

    def test_parse_from_yaml(self):
        yaml_str = """
name: yaml-workflow
description: test
trigger:
  type: webhook
  config:
    path: /test
nodes:
  - id: step1
    type: http
    config:
      url: https://example.com
  - id: step2
    type: transform
    depends_on: [step1]
    config:
      expression: "$.data"
"""
        data = yaml.safe_load(yaml_str)
        wf = WorkflowDef(**data)
        assert wf.name == "yaml-workflow"
        assert wf.description == "test"
        assert len(wf.nodes) == 2
        assert wf.nodes[1].depends_on == ["step1"]

    def test_duplicate_node_ids_rejected(self):
        data = {
            "name": "bad-workflow",
            "trigger": {"type": "manual"},
            "nodes": [
                {"id": "step1", "type": "http", "config": {}},
                {"id": "step1", "type": "transform", "config": {}},
            ],
        }
        with pytest.raises(ValueError, match="Duplicate node id"):
            WorkflowDef(**data)
