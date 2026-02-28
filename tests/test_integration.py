"""Integration tests — validate full platform boot and workflow hydration."""

from __future__ import annotations

from pathlib import Path

import yaml

from pyflow.models.platform import PlatformConfig
from pyflow.models.workflow import WorkflowDef
from pyflow.platform.app import PyFlowPlatform
from pyflow.platform.executor import WorkflowExecutor


class TestPlatformIntegration:
    async def test_boot_discovers_tools(self):
        """Platform boot discovers all built-in tools."""
        config = PlatformConfig(workflows_dir="agents")
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
        config = PlatformConfig(workflows_dir="agents")
        platform = PyFlowPlatform(config)
        await platform.boot()
        workflows = platform.list_workflows()
        names = [w.name for w in workflows]
        assert "exchange_tracker" in names
        assert "example" in names
        await platform.shutdown()

    async def test_workflow_hydration_creates_agents(self):
        """Hydrated workflow has an ADK agent tree."""
        config = PlatformConfig(workflows_dir="agents")
        platform = PyFlowPlatform(config)
        await platform.boot()
        hw = platform.workflows.get("exchange_tracker")
        assert hw.agent is not None
        assert hw.agent.name == "exchange_tracker"
        await platform.shutdown()

    async def test_agent_cards_generated(self):
        """A2A agent cards loaded from agent package directories."""
        config = PlatformConfig(workflows_dir="agents")
        platform = PyFlowPlatform(config)
        await platform.boot()
        cards = platform.agent_cards()
        assert len(cards) >= 1
        card = next(c for c in cards if c.name == "exchange_tracker")
        assert len(card.skills) == 1
        assert card.skills[0].id == "rate_tracking"
        await platform.shutdown()

    async def test_platform_uses_workflow_executor(self):
        """Platform uses WorkflowExecutor, not legacy PlatformRunner."""
        config = PlatformConfig(workflows_dir="agents")
        platform = PyFlowPlatform(config)
        assert isinstance(platform.executor, WorkflowExecutor)
        assert not hasattr(platform, "runner"), "PlatformRunner should not exist"

    async def test_run_workflow_accepts_user_id(self):
        """Platform.run_workflow accepts user_id parameter."""
        import inspect

        sig = inspect.signature(PyFlowPlatform.run_workflow)
        params = list(sig.parameters.keys())
        assert "user_id" in params
        # Verify the default value
        assert sig.parameters["user_id"].default == "default"


class TestWorkflowValidation:
    async def test_validate_exchange_tracker_workflow(self):
        """exchange_tracker.yaml is valid and uses mixed agent types."""
        path = Path("agents/exchange_tracker/workflow.yaml")
        assert path.exists()
        data = yaml.safe_load(path.read_text())
        workflow = WorkflowDef(**data)
        assert workflow.name == "exchange_tracker"
        assert len(workflow.agents) == 7
        assert workflow.orchestration.type == "sequential"
        agent_types = {a.name: a.type for a in workflow.agents}
        assert agent_types["parser"] == "llm"
        assert agent_types["parse_params"] == "code"
        assert agent_types["build_url"] == "expr"
        assert agent_types["fetcher"] == "tool"
        assert agent_types["extract_rate"] == "expr"
        assert agent_types["check_threshold"] == "expr"
        assert agent_types["reporter"] == "llm"

    async def test_validate_example_workflow(self):
        """example.yaml is valid and parses correctly."""
        path = Path("agents/example/workflow.yaml")
        assert path.exists()
        data = yaml.safe_load(path.read_text())
        workflow = WorkflowDef(**data)
        assert workflow.name == "example"
        assert len(workflow.agents) == 2
        assert workflow.orchestration.type == "sequential"


class TestRuntimeConfig:
    async def test_exchange_tracker_has_runtime_config(self):
        """exchange_tracker.yaml includes runtime configuration."""
        path = Path("agents/exchange_tracker/workflow.yaml")
        data = yaml.safe_load(path.read_text())
        workflow = WorkflowDef(**data)
        assert workflow.runtime.session_service == "in_memory"

    async def test_example_has_runtime_config(self):
        """example.yaml includes runtime configuration."""
        path = Path("agents/example/workflow.yaml")
        data = yaml.safe_load(path.read_text())
        workflow = WorkflowDef(**data)
        assert workflow.runtime.session_service == "in_memory"

    async def test_runtime_config_hydrates_correctly(self):
        """Workflows with runtime config hydrate through the platform."""
        config = PlatformConfig(workflows_dir="agents")
        platform = PyFlowPlatform(config)
        await platform.boot()

        hw = platform.workflows.get("exchange_tracker")
        assert hw.definition.runtime.session_service == "in_memory"

        hw_ex = platform.workflows.get("example")
        assert hw_ex.definition.runtime.session_service == "in_memory"

        await platform.shutdown()

    async def test_runtime_defaults_when_omitted(self):
        """RuntimeConfig defaults are applied when runtime section is absent."""
        workflow = WorkflowDef(
            name="no-runtime",
            description="Workflow without explicit runtime",
            agents=[
                {
                    "name": "a1",
                    "type": "llm",
                    "model": "gemini-2.5-flash",
                    "instruction": "test",
                }
            ],
            orchestration={"type": "sequential", "agents": ["a1"]},
        )
        assert workflow.runtime.session_service == "in_memory"
        assert workflow.runtime.memory_service == "none"
        assert workflow.runtime.artifact_service == "none"
