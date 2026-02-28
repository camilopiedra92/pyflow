from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyflow.models.agent import AgentConfig
from pyflow.models.workflow import OrchestrationConfig, WorkflowDef
from pyflow.platform.hydration.hydrator import WorkflowHydrator
from pyflow.platform.registry.tool_registry import ToolRegistry


def _make_llm_agent_config(
    name: str = "agent1",
    model: str = "gemini-2.0-flash",
    instruction: str = "Do something",
    tools: list[str] | None = None,
    output_key: str | None = None,
) -> AgentConfig:
    return AgentConfig(
        name=name,
        type="llm",
        model=model,
        instruction=instruction,
        tools=tools or [],
        output_key=output_key,
    )


def _make_workflow(
    name: str = "test_workflow",
    agents: list[AgentConfig] | None = None,
    orchestration_type: str = "sequential",
) -> WorkflowDef:
    agents = agents or [_make_llm_agent_config()]
    agent_names = [a.name for a in agents]
    return WorkflowDef(
        name=name,
        agents=agents,
        orchestration=OrchestrationConfig(type=orchestration_type, agents=agent_names),
    )


@pytest.fixture
def mock_tool_registry() -> ToolRegistry:
    registry = MagicMock(spec=ToolRegistry)
    registry.resolve_tools.return_value = [MagicMock(name="mock_function_tool")]
    return registry


class TestHydrateSingleLlmAgentSequential:
    def test_returns_sequential_agent_wrapping_llm_agent(self, mock_tool_registry):
        """Single LLM agent in sequential orchestration -> SequentialAgent wrapping LlmAgent."""
        from google.adk.agents.llm_agent import LlmAgent
        from google.adk.agents.sequential_agent import SequentialAgent

        workflow = _make_workflow()
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        assert isinstance(root, SequentialAgent)
        assert root.name == "test_workflow"
        assert len(root.sub_agents) == 1
        assert isinstance(root.sub_agents[0], LlmAgent)
        assert root.sub_agents[0].name == "agent1"


class TestHydrateMultiAgentSequential:
    def test_two_llm_agents_in_sequential(self, mock_tool_registry):
        """Two LLM agents in sequential -> SequentialAgent with 2 sub_agents."""
        from google.adk.agents.sequential_agent import SequentialAgent

        agents = [
            _make_llm_agent_config(name="fetcher", instruction="Fetch data"),
            _make_llm_agent_config(name="analyzer", instruction="Analyze data"),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        assert isinstance(root, SequentialAgent)
        assert len(root.sub_agents) == 2
        assert root.sub_agents[0].name == "fetcher"
        assert root.sub_agents[1].name == "analyzer"


class TestHydrateParallelOrchestration:
    def test_two_agents_in_parallel(self, mock_tool_registry):
        """Two agents in parallel -> ParallelAgent."""
        from google.adk.agents.parallel_agent import ParallelAgent

        agents = [
            _make_llm_agent_config(name="worker_a", instruction="Task A"),
            _make_llm_agent_config(name="worker_b", instruction="Task B"),
        ]
        workflow = _make_workflow(agents=agents, orchestration_type="parallel")
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        assert isinstance(root, ParallelAgent)
        assert root.name == "test_workflow"
        assert len(root.sub_agents) == 2


class TestHydrateLoopOrchestration:
    def test_agent_in_loop(self, mock_tool_registry):
        """Agent in loop -> LoopAgent."""
        from google.adk.agents.loop_agent import LoopAgent

        workflow = _make_workflow(orchestration_type="loop")
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        assert isinstance(root, LoopAgent)
        assert root.name == "test_workflow"
        assert len(root.sub_agents) == 1


class TestHydrateResolvesTools:
    def test_agent_with_tools_resolved_from_registry(self, mock_tool_registry):
        """Agent with tools: ["http_request"] -> tools resolved from ToolRegistry."""
        agents = [
            _make_llm_agent_config(name="fetcher", tools=["http_request"]),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        mock_tool_registry.resolve_tools.assert_called_once_with(["http_request"])
        llm_agent = root.sub_agents[0]
        assert len(llm_agent.tools) == 1


class TestHydrateLiteLlmForAnthropicModel:
    def test_anthropic_model_uses_litellm(self, mock_tool_registry):
        """Model 'anthropic/claude-sonnet-4-20250514' -> LiteLlm wrapper."""
        from google.adk.models.base_llm import BaseLlm

        agents = [
            _make_llm_agent_config(
                name="claude_agent", model="anthropic/claude-sonnet-4-20250514"
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)

        with patch(
            "pyflow.platform.hydration.hydrator._get_litellm"
        ) as mock_get_litellm:
            mock_litellm_cls = MagicMock()
            mock_model_instance = MagicMock(spec=BaseLlm)
            mock_litellm_cls.return_value = mock_model_instance
            mock_get_litellm.return_value = mock_litellm_cls

            root = hydrator.hydrate(workflow)

            mock_litellm_cls.assert_called_once_with(model="anthropic/claude-sonnet-4-20250514")
            llm_agent = root.sub_agents[0]
            assert llm_agent.model == mock_model_instance


class TestHydrateLiteLlmForOpenAIModel:
    def test_openai_model_uses_litellm(self, mock_tool_registry):
        """Model 'openai/gpt-4o' -> LiteLlm wrapper."""
        from google.adk.models.base_llm import BaseLlm

        agents = [
            _make_llm_agent_config(name="gpt_agent", model="openai/gpt-4o"),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)

        with patch(
            "pyflow.platform.hydration.hydrator._get_litellm"
        ) as mock_get_litellm:
            mock_litellm_cls = MagicMock()
            mock_model_instance = MagicMock(spec=BaseLlm)
            mock_litellm_cls.return_value = mock_model_instance
            mock_get_litellm.return_value = mock_litellm_cls

            root = hydrator.hydrate(workflow)

            mock_litellm_cls.assert_called_once_with(model="openai/gpt-4o")
            llm_agent = root.sub_agents[0]
            assert llm_agent.model == mock_model_instance


class TestHydrateGeminiModelDirect:
    def test_gemini_model_passed_as_string(self, mock_tool_registry):
        """Model 'gemini-2.0-flash' -> passed as string directly."""
        agents = [
            _make_llm_agent_config(name="gemini_agent", model="gemini-2.0-flash"),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        llm_agent = root.sub_agents[0]
        assert llm_agent.model == "gemini-2.0-flash"


class TestHydrateAgentWithOutputKey:
    def test_output_key_passed_to_llm_agent(self, mock_tool_registry):
        """Agent with output_key set -> LlmAgent gets output_key kwarg."""
        agents = [
            _make_llm_agent_config(name="keyed_agent", output_key="result_data"),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        llm_agent = root.sub_agents[0]
        assert llm_agent.output_key == "result_data"


class TestHydrateAgentWithoutTools:
    def test_agent_with_empty_tools(self, mock_tool_registry):
        """Agent with empty tools list -> LlmAgent with no tools."""
        agents = [
            _make_llm_agent_config(name="no_tools_agent", tools=[]),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        llm_agent = root.sub_agents[0]
        assert llm_agent.tools == []
        mock_tool_registry.resolve_tools.assert_not_called()
