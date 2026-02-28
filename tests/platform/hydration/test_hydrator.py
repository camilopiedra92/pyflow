from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyflow.models.agent import AgentConfig
from pyflow.models.workflow import DagNode as DagNodeConfig
from pyflow.models.workflow import OrchestrationConfig, WorkflowDef
from pyflow.platform.hydration.hydrator import WorkflowHydrator
from pyflow.platform.registry.tool_registry import ToolRegistry


def _make_llm_agent_config(
    name: str = "agent1",
    model: str = "gemini-2.5-flash",
    instruction: str = "Do something",
    tools: list[str] | None = None,
    output_key: str | None = None,
    callbacks: dict[str, str] | None = None,
) -> AgentConfig:
    return AgentConfig(
        name=name,
        type="llm",
        model=model,
        instruction=instruction,
        tools=tools or [],
        output_key=output_key,
        callbacks=callbacks,
    )


def _make_workflow(
    name: str = "test_workflow",
    agents: list[AgentConfig] | None = None,
    orchestration_type: str = "sequential",
    orchestration: OrchestrationConfig | None = None,
) -> WorkflowDef:
    agents = agents or [_make_llm_agent_config()]
    if orchestration is None:
        agent_names = [a.name for a in agents]
        orchestration = OrchestrationConfig(type=orchestration_type, agents=agent_names)
    return WorkflowDef(
        name=name,
        agents=agents,
        orchestration=orchestration,
    )


@pytest.fixture
def mock_tool_registry() -> ToolRegistry:
    registry = MagicMock(spec=ToolRegistry)
    registry.resolve_tools.return_value = [MagicMock(name="mock_function_tool")]
    return registry


# ---------------------------------------------------------------------------
# Existing tests: sequential, parallel, loop, tools, litellm, output_key
# ---------------------------------------------------------------------------


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
            _make_llm_agent_config(name="claude_agent", model="anthropic/claude-sonnet-4-20250514"),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)

        with patch("pyflow.platform.hydration.hydrator._get_litellm") as mock_get_litellm:
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

        with patch("pyflow.platform.hydration.hydrator._get_litellm") as mock_get_litellm:
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
        """Model 'gemini-2.5-flash' -> passed as string directly."""
        agents = [
            _make_llm_agent_config(name="gemini_agent", model="gemini-2.5-flash"),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        llm_agent = root.sub_agents[0]
        assert llm_agent.model == "gemini-2.5-flash"


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


# ---------------------------------------------------------------------------
# New tests: react, dag, llm_routed, nested agents, callbacks, max_iterations
# ---------------------------------------------------------------------------


class TestHydrateReactOrchestration:
    def test_react_sets_planner(self, mock_tool_registry):
        """Orchestration type=react with planner=plan_react -> agent has PlanReActPlanner."""
        agents = [
            _make_llm_agent_config(name="reasoner", instruction="Reason step by step"),
        ]
        orch = OrchestrationConfig(type="react", agent="reasoner", planner="plan_react")
        workflow = _make_workflow(agents=agents, orchestration=orch)
        hydrator = WorkflowHydrator(mock_tool_registry)

        with patch("pyflow.platform.hydration.hydrator.PlanReActPlanner") as MockPlanner:
            mock_planner_instance = MagicMock()
            MockPlanner.return_value = mock_planner_instance

            root = hydrator.hydrate(workflow)

            from google.adk.agents.llm_agent import LlmAgent

            assert isinstance(root, LlmAgent)
            assert root.name == "reasoner"
            MockPlanner.assert_called_once()
            assert root.planner is mock_planner_instance

    def test_react_without_planner_returns_agent_no_planner(self, mock_tool_registry):
        """Orchestration type=react without planner -> agent returned without planner."""
        agents = [
            _make_llm_agent_config(name="reasoner", instruction="Reason step by step"),
        ]
        orch = OrchestrationConfig(type="react", agent="reasoner")
        workflow = _make_workflow(agents=agents, orchestration=orch)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        from google.adk.agents.llm_agent import LlmAgent

        assert isinstance(root, LlmAgent)
        assert root.name == "reasoner"

    def test_react_builtin_planner(self, mock_tool_registry):
        """Orchestration with planner=builtin -> agent has BuiltInPlanner."""
        agents = [
            _make_llm_agent_config(name="thinker", instruction="Think deeply"),
        ]
        orch = OrchestrationConfig(
            type="react",
            agent="thinker",
            planner="builtin",
            planner_config={"thinking_budget": 2048},
        )
        workflow = _make_workflow(agents=agents, orchestration=orch)
        hydrator = WorkflowHydrator(mock_tool_registry)

        with patch("pyflow.platform.hydration.hydrator.BuiltInPlanner") as MockPlanner:
            mock_planner_instance = MagicMock()
            MockPlanner.return_value = mock_planner_instance

            root = hydrator.hydrate(workflow)

            from google.adk.agents.llm_agent import LlmAgent

            assert isinstance(root, LlmAgent)
            MockPlanner.assert_called_once()
            assert root.planner is mock_planner_instance

    def test_react_builtin_planner_no_config(self, mock_tool_registry):
        """Orchestration with planner=builtin but no planner_config -> BuiltInPlanner()."""
        agents = [
            _make_llm_agent_config(name="thinker", instruction="Think"),
        ]
        orch = OrchestrationConfig(type="react", agent="thinker", planner="builtin")
        workflow = _make_workflow(agents=agents, orchestration=orch)
        hydrator = WorkflowHydrator(mock_tool_registry)

        with patch("pyflow.platform.hydration.hydrator.BuiltInPlanner") as MockPlanner:
            mock_planner_instance = MagicMock()
            MockPlanner.return_value = mock_planner_instance

            root = hydrator.hydrate(workflow)
            MockPlanner.assert_called_once_with()
            assert root.planner is mock_planner_instance


class TestHydrateDagOrchestration:
    def test_dag_creates_dag_agent(self, mock_tool_registry):
        """Orchestration type=dag with nodes -> DagAgent."""
        from pyflow.platform.agents.dag_agent import DagAgent

        agents = [
            _make_llm_agent_config(name="fetch", instruction="Fetch data"),
            _make_llm_agent_config(name="parse", instruction="Parse data"),
            _make_llm_agent_config(name="store", instruction="Store data"),
        ]
        orch = OrchestrationConfig(
            type="dag",
            nodes=[
                DagNodeConfig(agent="fetch", depends_on=[]),
                DagNodeConfig(agent="parse", depends_on=["fetch"]),
                DagNodeConfig(agent="store", depends_on=["parse"]),
            ],
        )
        workflow = _make_workflow(agents=agents, orchestration=orch)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        assert isinstance(root, DagAgent)
        assert root.name == "test_workflow"
        assert len(root.dag_nodes) == 3
        assert len(root.sub_agents) == 3

        # Verify dependency structure
        nodes_by_name = {n.name: n for n in root.dag_nodes}
        assert nodes_by_name["fetch"].depends_on == set()
        assert nodes_by_name["parse"].depends_on == {"fetch"}
        assert nodes_by_name["store"].depends_on == {"parse"}

    def test_dag_parallel_roots(self, mock_tool_registry):
        """DAG with two root nodes (no dependencies) -> both in dag_nodes."""
        from pyflow.platform.agents.dag_agent import DagAgent

        agents = [
            _make_llm_agent_config(name="a", instruction="A"),
            _make_llm_agent_config(name="b", instruction="B"),
            _make_llm_agent_config(name="c", instruction="C"),
        ]
        orch = OrchestrationConfig(
            type="dag",
            nodes=[
                DagNodeConfig(agent="a", depends_on=[]),
                DagNodeConfig(agent="b", depends_on=[]),
                DagNodeConfig(agent="c", depends_on=["a", "b"]),
            ],
        )
        workflow = _make_workflow(agents=agents, orchestration=orch)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        assert isinstance(root, DagAgent)
        nodes_by_name = {n.name: n for n in root.dag_nodes}
        assert nodes_by_name["a"].depends_on == set()
        assert nodes_by_name["b"].depends_on == set()
        assert nodes_by_name["c"].depends_on == {"a", "b"}


class TestHydrateLlmRoutedOrchestration:
    def test_llm_routed_sets_sub_agents_on_router(self, mock_tool_registry):
        """Orchestration type=llm_routed -> router LlmAgent gets sub_agents."""
        from google.adk.agents.llm_agent import LlmAgent

        agents = [
            _make_llm_agent_config(name="dispatcher", instruction="Route requests"),
            _make_llm_agent_config(name="worker_a", instruction="Handle task A"),
            _make_llm_agent_config(name="worker_b", instruction="Handle task B"),
        ]
        orch = OrchestrationConfig(
            type="llm_routed",
            router="dispatcher",
            agents=["worker_a", "worker_b"],
        )
        workflow = _make_workflow(agents=agents, orchestration=orch)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        assert isinstance(root, LlmAgent)
        assert root.name == "dispatcher"
        assert len(root.sub_agents) == 2
        sub_names = [a.name for a in root.sub_agents]
        assert "worker_a" in sub_names
        assert "worker_b" in sub_names


class TestHydrateNestedAgents:
    def test_sequential_workflow_agent(self, mock_tool_registry):
        """AgentConfig type=sequential with sub_agents -> SequentialAgent."""
        from google.adk.agents.sequential_agent import SequentialAgent

        agents = [
            _make_llm_agent_config(name="step_a", instruction="Step A"),
            _make_llm_agent_config(name="step_b", instruction="Step B"),
            AgentConfig(
                name="pipeline",
                type="sequential",
                sub_agents=["step_a", "step_b"],
            ),
        ]
        orch = OrchestrationConfig(type="sequential", agents=["pipeline"])
        workflow = _make_workflow(agents=agents, orchestration=orch)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        assert isinstance(root, SequentialAgent)
        assert root.name == "test_workflow"
        assert len(root.sub_agents) == 1

        pipeline = root.sub_agents[0]
        assert isinstance(pipeline, SequentialAgent)
        assert pipeline.name == "pipeline"
        assert len(pipeline.sub_agents) == 2
        assert pipeline.sub_agents[0].name == "step_a"
        assert pipeline.sub_agents[1].name == "step_b"

    def test_parallel_workflow_agent(self, mock_tool_registry):
        """AgentConfig type=parallel with sub_agents -> ParallelAgent."""
        from google.adk.agents.parallel_agent import ParallelAgent

        agents = [
            _make_llm_agent_config(name="task_a", instruction="Task A"),
            _make_llm_agent_config(name="task_b", instruction="Task B"),
            AgentConfig(
                name="fan_out",
                type="parallel",
                sub_agents=["task_a", "task_b"],
            ),
        ]
        orch = OrchestrationConfig(type="sequential", agents=["fan_out"])
        workflow = _make_workflow(agents=agents, orchestration=orch)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        fan_out = root.sub_agents[0]
        assert isinstance(fan_out, ParallelAgent)
        assert fan_out.name == "fan_out"
        assert len(fan_out.sub_agents) == 2

    def test_loop_workflow_agent(self, mock_tool_registry):
        """AgentConfig type=loop with sub_agents -> LoopAgent."""
        from google.adk.agents.loop_agent import LoopAgent

        agents = [
            _make_llm_agent_config(name="checker", instruction="Check condition"),
            AgentConfig(
                name="retry_loop",
                type="loop",
                sub_agents=["checker"],
            ),
        ]
        orch = OrchestrationConfig(type="sequential", agents=["retry_loop"])
        workflow = _make_workflow(agents=agents, orchestration=orch)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        loop_agent = root.sub_agents[0]
        assert isinstance(loop_agent, LoopAgent)
        assert loop_agent.name == "retry_loop"
        assert len(loop_agent.sub_agents) == 1
        assert loop_agent.sub_agents[0].name == "checker"


class TestHydrateCallbacks:
    def test_callbacks_resolved_via_fqn(self, mock_tool_registry):
        """AgentConfig with FQN callback -> resolved via importlib and passed to LlmAgent."""
        agents = [
            _make_llm_agent_config(
                name="cb_agent",
                instruction="Do something",
                callbacks={"before_agent": "json.dumps"},
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        import json

        llm_agent = root.sub_agents[0]
        assert llm_agent.before_agent_callback is json.dumps

    def test_bad_fqn_callback_raises(self, mock_tool_registry):
        """AgentConfig with invalid FQN callback -> raises at hydration time."""
        agents = [
            _make_llm_agent_config(
                name="cb_agent",
                instruction="Do something",
                callbacks={"before_agent": "nonexistent_module.func"},
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)

        with pytest.raises(ModuleNotFoundError):
            hydrator.hydrate(workflow)

    def test_no_callbacks_returns_empty(self, mock_tool_registry):
        """AgentConfig with no callbacks -> no callback kwargs passed."""
        agents = [_make_llm_agent_config(name="plain_agent")]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        llm_agent = root.sub_agents[0]
        assert llm_agent.name == "plain_agent"


class TestHydrateLoopMaxIterations:
    def test_max_iterations_passed(self, mock_tool_registry):
        """Orchestration type=loop with max_iterations=5 -> LoopAgent.max_iterations=5."""
        from google.adk.agents.loop_agent import LoopAgent

        agents = [_make_llm_agent_config(name="worker", instruction="Work")]
        orch = OrchestrationConfig(type="loop", agents=["worker"], max_iterations=5)
        workflow = _make_workflow(agents=agents, orchestration=orch)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        assert isinstance(root, LoopAgent)
        assert root.max_iterations == 5

    def test_loop_without_max_iterations(self, mock_tool_registry):
        """Orchestration type=loop without max_iterations -> LoopAgent with default."""
        from google.adk.agents.loop_agent import LoopAgent

        workflow = _make_workflow(orchestration_type="loop")
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        assert isinstance(root, LoopAgent)
        # max_iterations should be None or default when not specified


# ---------------------------------------------------------------------------
# CodeAgent and ToolAgent hydration tests
# ---------------------------------------------------------------------------


class TestHydrateCodeAgent:
    def test_code_agent_hydrated(self, mock_tool_registry):
        """AgentConfig type=code -> CodeAgent with function_path, input_keys, output_key."""
        from pyflow.platform.agents.code_agent import CodeAgent

        agents = [
            AgentConfig(
                name="compute",
                type="code",
                function="myapp.utils.compute_score",
                input_keys=["raw_data", "threshold"],
                output_key="score",
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        code_agent = root.sub_agents[0]
        assert isinstance(code_agent, CodeAgent)
        assert code_agent.name == "compute"
        assert code_agent.function_path == "myapp.utils.compute_score"
        assert code_agent.input_keys == ["raw_data", "threshold"]
        assert code_agent.output_key == "score"

    def test_code_agent_defaults_input_keys_to_empty(self, mock_tool_registry):
        """Code agent with no input_keys -> defaults to empty list."""
        from pyflow.platform.agents.code_agent import CodeAgent

        agents = [
            AgentConfig(
                name="noop",
                type="code",
                function="builtins.dict",
                output_key="result",
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        code_agent = root.sub_agents[0]
        assert isinstance(code_agent, CodeAgent)
        assert code_agent.input_keys == []

    def test_code_agent_in_sequential_with_llm(self, mock_tool_registry):
        """Code agent alongside LLM agent in sequential orchestration."""
        from pyflow.platform.agents.code_agent import CodeAgent

        agents = [
            AgentConfig(
                name="transform",
                type="code",
                function="json.dumps",
                input_keys=["data"],
                output_key="json_data",
            ),
            _make_llm_agent_config(name="analyzer", instruction="Analyze"),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        assert len(root.sub_agents) == 2
        assert isinstance(root.sub_agents[0], CodeAgent)
        assert root.sub_agents[1].name == "analyzer"


class TestHydrateToolAgent:
    def test_tool_agent_hydrated(self, mock_tool_registry):
        """AgentConfig type=tool -> ToolAgent with tool_instance, fixed_config, output_key."""
        from pyflow.platform.agents.tool_agent import ToolAgent
        from pyflow.tools.base import BasePlatformTool

        mock_tool_instance = MagicMock(spec=BasePlatformTool)
        mock_tool_registry.get.return_value = mock_tool_instance

        agents = [
            AgentConfig(
                name="fetcher",
                type="tool",
                tool="http_request",
                tool_config={"url": "https://api.example.com", "method": "GET"},
                output_key="api_data",
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        tool_agent = root.sub_agents[0]
        assert isinstance(tool_agent, ToolAgent)
        assert tool_agent.name == "fetcher"
        assert tool_agent.tool_instance is mock_tool_instance
        assert tool_agent.fixed_config == {"url": "https://api.example.com", "method": "GET"}
        assert tool_agent.output_key == "api_data"
        mock_tool_registry.get.assert_called_once_with("http_request")

    def test_tool_agent_defaults_config_to_empty(self, mock_tool_registry):
        """Tool agent with no tool_config -> defaults to empty dict."""
        from pyflow.platform.agents.tool_agent import ToolAgent
        from pyflow.tools.base import BasePlatformTool

        mock_tool_registry.get.return_value = MagicMock(spec=BasePlatformTool)

        agents = [
            AgentConfig(
                name="simple",
                type="tool",
                tool="http_request",
                output_key="out",
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        tool_agent = root.sub_agents[0]
        assert isinstance(tool_agent, ToolAgent)
        assert tool_agent.fixed_config == {}

    def test_unknown_tool_raises(self, mock_tool_registry):
        """Tool agent referencing unknown tool -> KeyError at hydration time."""
        mock_tool_registry.get.side_effect = KeyError("Unknown tool: 'bad_tool'")

        agents = [
            AgentConfig(
                name="bad",
                type="tool",
                tool="bad_tool",
                output_key="out",
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)

        with pytest.raises(KeyError, match="bad_tool"):
            hydrator.hydrate(workflow)


# ---------------------------------------------------------------------------
# ExprAgent hydration tests
# ---------------------------------------------------------------------------


class TestHydrateExprAgent:
    def test_expr_agent_hydrated(self, mock_tool_registry):
        """AgentConfig type=expr -> ExprAgent with expression, input_keys, output_key."""
        from pyflow.platform.agents.expr_agent import ExprAgent

        agents = [
            AgentConfig(
                name="calc",
                type="expr",
                expression="price * quantity",
                input_keys=["price", "quantity"],
                output_key="total",
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        expr_agent = root.sub_agents[0]
        assert isinstance(expr_agent, ExprAgent)
        assert expr_agent.name == "calc"
        assert expr_agent.expression == "price * quantity"
        assert expr_agent.input_keys == ["price", "quantity"]
        assert expr_agent.output_key == "total"

    def test_expr_agent_defaults_input_keys_to_empty(self, mock_tool_registry):
        """Expr agent with no input_keys -> defaults to empty list."""
        from pyflow.platform.agents.expr_agent import ExprAgent

        agents = [
            AgentConfig(
                name="const",
                type="expr",
                expression="42",
                output_key="answer",
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        expr_agent = root.sub_agents[0]
        assert isinstance(expr_agent, ExprAgent)
        assert expr_agent.input_keys == []

    def test_expr_agent_in_sequential_with_llm(self, mock_tool_registry):
        """Expr agent alongside LLM agent in sequential orchestration."""
        from pyflow.platform.agents.expr_agent import ExprAgent

        agents = [
            AgentConfig(
                name="margin",
                type="expr",
                expression="round((price - cost) / price * 100, 2)",
                input_keys=["price", "cost"],
                output_key="margin_pct",
            ),
            _make_llm_agent_config(name="reporter", instruction="Report margin"),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        assert len(root.sub_agents) == 2
        assert isinstance(root.sub_agents[0], ExprAgent)
        assert root.sub_agents[1].name == "reporter"

    def test_description_passed_to_llm_agent(self, mock_tool_registry):
        """AgentConfig with description -> LlmAgent gets description kwarg."""
        agents = [
            AgentConfig(
                name="desc_agent",
                type="llm",
                model="gemini-2.5-flash",
                instruction="Do stuff",
                description="Handles data fetching from APIs",
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        llm_agent = root.sub_agents[0]
        assert llm_agent.description == "Handles data fetching from APIs"

    def test_description_empty_not_passed(self, mock_tool_registry):
        """AgentConfig with empty description -> LlmAgent uses its default."""
        agents = [_make_llm_agent_config(name="no_desc")]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        llm_agent = root.sub_agents[0]
        # Default LlmAgent description is empty string
        assert llm_agent.name == "no_desc"

    def test_include_contents_none_passed(self, mock_tool_registry):
        """AgentConfig with include_contents='none' -> LlmAgent gets include_contents."""
        agents = [
            AgentConfig(
                name="isolated",
                type="llm",
                model="gemini-2.5-flash",
                instruction="Process independently",
                include_contents="none",
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        llm_agent = root.sub_agents[0]
        assert llm_agent.include_contents == "none"

    def test_include_contents_default_not_passed(self, mock_tool_registry):
        """AgentConfig with include_contents='default' -> not passed to LlmAgent."""
        agents = [_make_llm_agent_config(name="normal")]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        llm_agent = root.sub_agents[0]
        # LlmAgent default is "default"
        assert llm_agent.name == "normal"

    def test_output_schema_creates_pydantic_model(self, mock_tool_registry):
        """AgentConfig with output_schema -> LlmAgent gets Pydantic output_schema."""
        from pydantic import BaseModel

        agents = [
            AgentConfig(
                name="structured",
                type="llm",
                model="gemini-2.5-flash",
                instruction="Return structured data",
                output_schema={
                    "type": "object",
                    "properties": {"result": {"type": "string"}, "score": {"type": "number"}},
                    "required": ["result", "score"],
                },
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        llm_agent = root.sub_agents[0]
        assert llm_agent.output_schema is not None
        assert issubclass(llm_agent.output_schema, BaseModel)

    def test_input_schema_creates_pydantic_model(self, mock_tool_registry):
        """AgentConfig with input_schema -> LlmAgent gets Pydantic input_schema."""
        from pydantic import BaseModel

        agents = [
            AgentConfig(
                name="typed_input",
                type="llm",
                model="gemini-2.5-flash",
                instruction="Process typed input",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        llm_agent = root.sub_agents[0]
        assert llm_agent.input_schema is not None
        assert issubclass(llm_agent.input_schema, BaseModel)

    def test_generate_content_config_with_temperature(self, mock_tool_registry):
        """AgentConfig with temperature -> LlmAgent gets GenerateContentConfig."""
        agents = [
            AgentConfig(
                name="warm_agent",
                type="llm",
                model="gemini-2.5-flash",
                instruction="Be creative",
                temperature=0.9,
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        llm_agent = root.sub_agents[0]
        assert llm_agent.generate_content_config is not None
        assert llm_agent.generate_content_config.temperature == 0.9

    def test_generate_content_config_all_params(self, mock_tool_registry):
        """AgentConfig with all gen params -> GenerateContentConfig has all fields."""
        agents = [
            AgentConfig(
                name="full_config",
                type="llm",
                model="gemini-2.5-flash",
                instruction="Controlled output",
                temperature=0.5,
                max_output_tokens=2048,
                top_p=0.95,
                top_k=40,
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        llm_agent = root.sub_agents[0]
        gen = llm_agent.generate_content_config
        assert gen is not None
        assert gen.temperature == 0.5
        assert gen.max_output_tokens == 2048
        assert gen.top_p == 0.95
        assert gen.top_k == 40

    def test_no_gen_params_no_config(self, mock_tool_registry):
        """AgentConfig with no gen params -> no GenerateContentConfig set."""
        agents = [_make_llm_agent_config(name="default_gen")]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        llm_agent = root.sub_agents[0]
        assert llm_agent.generate_content_config is None

    def test_no_schema_defaults(self, mock_tool_registry):
        """AgentConfig without schemas -> LlmAgent schemas are None."""
        agents = [_make_llm_agent_config(name="no_schema")]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        llm_agent = root.sub_agents[0]
        assert llm_agent.output_schema is None
        assert llm_agent.input_schema is None

    def test_agent_tools_wraps_agents_as_agent_tool(self, mock_tool_registry):
        """AgentConfig with agent_tools -> referenced agents wrapped as AgentTool."""
        from google.adk.tools.agent_tool import AgentTool

        agents = [
            _make_llm_agent_config(name="summarizer", instruction="Summarize text"),
            AgentConfig(
                name="researcher",
                type="llm",
                model="gemini-2.5-flash",
                instruction="Research topics",
                agent_tools=["summarizer"],
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        # Find the researcher agent in the orchestration
        researcher = next(a for a in root.sub_agents if a.name == "researcher")
        agent_tool_instances = [t for t in researcher.tools if isinstance(t, AgentTool)]
        assert len(agent_tool_instances) == 1
        assert agent_tool_instances[0].agent.name == "summarizer"

    def test_no_agent_tools_unchanged(self, mock_tool_registry):
        """AgentConfig without agent_tools -> tools list unchanged."""
        agents = [_make_llm_agent_config(name="plain", tools=["http_request"])]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        llm_agent = root.sub_agents[0]
        # Only the mock tool from registry, no AgentTool
        from google.adk.tools.agent_tool import AgentTool

        agent_tool_instances = [t for t in llm_agent.tools if isinstance(t, AgentTool)]
        assert len(agent_tool_instances) == 0

    def test_unsafe_expression_fails_at_hydration(self, mock_tool_registry):
        """Expr agent with unsafe expression -> ValueError at hydration time."""
        agents = [
            AgentConfig(
                name="bad",
                type="expr",
                expression="__import__('os')",
                output_key="result",
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)

        with pytest.raises(ValueError, match="not allowed"):
            hydrator.hydrate(workflow)
