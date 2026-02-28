"""Integration tests — validate full platform boot and workflow hydration."""
from __future__ import annotations

import pytest
from pathlib import Path

import yaml

from pyflow.models.platform import PlatformConfig
from pyflow.models.workflow import WorkflowDef
from pyflow.platform.app import PyFlowPlatform


class TestPlatformIntegration:
    async def test_boot_discovers_tools(self):
        """Platform boot discovers all built-in tools."""
        config = PlatformConfig(workflows_dir="workflows")
        platform = PyFlowPlatform(config)
        await platform.boot()
        tools = platform.list_tools()
        tool_names = [t.name for t in tools]
        assert "http_request" in tool_names
        assert "transform" in tool_names
        assert "condition" in tool_names
        assert "alert" in tool_names
        assert "storage" in tool_names
        await platform.shutdown()

    async def test_boot_discovers_workflows(self):
        """Platform boot discovers YAML workflows."""
        config = PlatformConfig(workflows_dir="workflows")
        platform = PyFlowPlatform(config)
        await platform.boot()
        workflows = platform.list_workflows()
        names = [w.name for w in workflows]
        assert "exchange_tracker" in names
        await platform.shutdown()

    async def test_workflow_hydration_creates_agents(self):
        """Hydrated workflow has an ADK agent tree."""
        config = PlatformConfig(workflows_dir="workflows")
        platform = PyFlowPlatform(config)
        await platform.boot()
        hw = platform.workflows.get("exchange_tracker")
        assert hw.agent is not None
        assert hw.agent.name == "exchange_tracker"
        await platform.shutdown()

    async def test_agent_cards_generated(self):
        """A2A agent cards generated from workflow registry."""
        config = PlatformConfig(workflows_dir="workflows")
        platform = PyFlowPlatform(config)
        await platform.boot()
        cards = platform.agent_cards()
        assert len(cards) >= 1
        card = next(c for c in cards if c.name == "exchange_tracker")
        assert len(card.skills) == 1
        assert card.skills[0].id == "rate_tracking"
        await platform.shutdown()

    async def test_validate_example_workflow(self):
        """Example workflow YAML is valid."""
        path = Path("workflows/exchange_tracker.yaml")
        assert path.exists()
        data = yaml.safe_load(path.read_text())
        workflow = WorkflowDef(**data)
        assert workflow.name == "exchange_tracker"
        assert len(workflow.agents) == 2
        assert workflow.orchestration.type == "sequential"
