from __future__ import annotations

from unittest.mock import MagicMock, patch

from pyflow.models.agent import AgentConfig
from pyflow.models.workflow import OrchestrationConfig, WorkflowDef
from pyflow.platform.hydration.hydrator import WorkflowHydrator
from pyflow.platform.registry.tool_registry import ToolRegistry


class TestHydratorOpenApiToolsViaRegistry:
    """Verify hydrator resolves OpenAPI tools through the ToolRegistry (not inline)."""

    def test_tools_resolved_via_resolve_tools(self):
        """When agent has tools: [ynab], hydrator calls resolve_tools which returns toolset."""
        registry = MagicMock(spec=ToolRegistry)
        mock_toolset = MagicMock()
        registry.resolve_tools.return_value = [mock_toolset]

        workflow = WorkflowDef(
            name="test_openapi",
            agents=[
                AgentConfig(
                    name="agent1",
                    type="llm",
                    model="gemini-2.5-flash",
                    instruction="Use the API",
                    tools=["ynab"],
                )
            ],
            orchestration=OrchestrationConfig(type="react", agent="agent1"),
        )

        hydrator = WorkflowHydrator(registry)
        agent = hydrator.hydrate(workflow)
        registry.resolve_tools.assert_called_once_with(["ynab"])
        assert agent is not None

    def test_no_tools_unchanged(self):
        """Agent without tools works as before."""
        registry = MagicMock(spec=ToolRegistry)
        registry.resolve_tools.return_value = [MagicMock()]

        workflow = WorkflowDef(
            name="no_openapi",
            agents=[
                AgentConfig(
                    name="agent1",
                    type="llm",
                    model="gemini-2.5-flash",
                    instruction="No tools",
                    tools=["http_request"],
                )
            ],
            orchestration=OrchestrationConfig(type="react", agent="agent1"),
        )

        hydrator = WorkflowHydrator(registry)
        agent = hydrator.hydrate(workflow)
        assert agent is not None

    def test_hydrator_no_base_dir(self):
        """WorkflowHydrator no longer accepts base_dir parameter."""
        registry = MagicMock(spec=ToolRegistry)
        hydrator = WorkflowHydrator(registry)
        assert hydrator._tool_registry is registry


class TestBuildRootAgentOpenApi:
    def test_build_root_agent_creates_hydrator(self, tmp_path):
        """build_root_agent creates a WorkflowHydrator with the tool registry."""
        pkg_dir = tmp_path / "agents" / "my_agent"
        pkg_dir.mkdir(parents=True)
        workflow_yaml = pkg_dir / "workflow.yaml"
        workflow_yaml.write_text(
            "name: test\n"
            "agents:\n"
            "  - name: a1\n"
            "    type: llm\n"
            "    model: gemini-2.5-flash\n"
            "    instruction: hi\n"
            "orchestration:\n"
            "  type: react\n"
            "  agent: a1\n"
        )
        agent_py = pkg_dir / "agent.py"
        agent_py.write_text("")

        with patch(
            "pyflow.platform.hydration.hydrator.WorkflowHydrator"
        ) as MockHydrator:
            mock_instance = MagicMock()
            mock_instance.hydrate.return_value = MagicMock()
            MockHydrator.return_value = mock_instance

            from pyflow.platform.hydration.hydrator import build_root_agent

            build_root_agent(str(agent_py))

        MockHydrator.assert_called_once()
        # WorkflowHydrator should receive only tool_registry (no base_dir)
        call_args = MockHydrator.call_args
        assert len(call_args.args) == 1 or (
            len(call_args.args) == 0 and len(call_args.kwargs) == 1
        )

    def test_build_root_agent_registers_openapi_tools(self, tmp_path):
        """build_root_agent registers workflow-level openapi_tools before hydration."""
        pkg_dir = tmp_path / "agents" / "my_agent"
        pkg_dir.mkdir(parents=True)
        workflow_yaml = pkg_dir / "workflow.yaml"
        workflow_yaml.write_text(
            "name: test\n"
            "agents:\n"
            "  - name: a1\n"
            "    type: llm\n"
            "    model: gemini-2.5-flash\n"
            "    instruction: hi\n"
            "    tools: [ynab]\n"
            "openapi_tools:\n"
            "  ynab:\n"
            "    spec: specs/test.yaml\n"
            "orchestration:\n"
            "  type: react\n"
            "  agent: a1\n"
        )
        agent_py = pkg_dir / "agent.py"
        agent_py.write_text("")

        with (
            patch(
                "pyflow.platform.hydration.hydrator.WorkflowHydrator"
            ) as MockHydrator,
            patch(
                "pyflow.platform.registry.tool_registry.ToolRegistry.register_openapi_tools"
            ) as mock_register,
        ):
            mock_instance = MagicMock()
            mock_instance.hydrate.return_value = MagicMock()
            MockHydrator.return_value = mock_instance

            from pyflow.platform.hydration.hydrator import build_root_agent

            build_root_agent(str(agent_py))

        mock_register.assert_called_once()
        call_args = mock_register.call_args
        configs = call_args[0][0]
        assert "ynab" in configs

    def test_build_root_agent_skips_when_no_openapi(self, tmp_path):
        """build_root_agent does not call register_openapi_tools when none defined."""
        pkg_dir = tmp_path / "agents" / "my_agent"
        pkg_dir.mkdir(parents=True)
        workflow_yaml = pkg_dir / "workflow.yaml"
        workflow_yaml.write_text(
            "name: test\n"
            "agents:\n"
            "  - name: a1\n"
            "    type: llm\n"
            "    model: gemini-2.5-flash\n"
            "    instruction: hi\n"
            "orchestration:\n"
            "  type: react\n"
            "  agent: a1\n"
        )
        agent_py = pkg_dir / "agent.py"
        agent_py.write_text("")

        with (
            patch(
                "pyflow.platform.hydration.hydrator.WorkflowHydrator"
            ) as MockHydrator,
            patch(
                "pyflow.platform.registry.tool_registry.ToolRegistry.register_openapi_tools"
            ) as mock_register,
        ):
            mock_instance = MagicMock()
            mock_instance.hydrate.return_value = MagicMock()
            MockHydrator.return_value = mock_instance

            from pyflow.platform.hydration.hydrator import build_root_agent

            build_root_agent(str(agent_py))

        mock_register.assert_not_called()
