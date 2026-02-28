from __future__ import annotations

from typing import TYPE_CHECKING, Union

from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.planners import PlanReActPlanner

from pyflow.models.agent import AgentConfig
from pyflow.models.workflow import WorkflowDef
from pyflow.platform.agents.code_agent import CodeAgent
from pyflow.platform.agents.dag_agent import DagAgent, DagNode
from pyflow.platform.agents.expr_agent import ExprAgent
from pyflow.platform.agents.tool_agent import ToolAgent
from pyflow.platform.callbacks import resolve_callback

if TYPE_CHECKING:
    from google.adk.agents.base_agent import BaseAgent
    from google.adk.models.base_llm import BaseLlm

    from pyflow.platform.registry.tool_registry import ToolRegistry

# Lazy import — LiteLlm requires google-adk[extensions] which may not be installed.
LiteLlm = None


def _get_litellm():
    """Lazy-load LiteLlm to avoid import errors when extensions are not installed."""
    global LiteLlm  # noqa: PLW0603
    if LiteLlm is None:
        from google.adk.models.lite_llm import LiteLlm as _LiteLlm

        LiteLlm = _LiteLlm
    return LiteLlm


class WorkflowHydrator:
    """Converts a WorkflowDef into an ADK agent tree.

    Resolves tool references via ToolRegistry and wraps agents in the
    appropriate orchestration agent. Supports all 6 orchestration types:
    sequential, parallel, loop, react, dag, and llm_routed.

    Also supports nested workflow agents (AgentConfig with type sequential,
    parallel, or loop), callbacks, and planners.
    """

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry

    def hydrate(self, workflow: WorkflowDef) -> BaseAgent:
        """Convert WorkflowDef into an ADK agent tree. Returns root ADK BaseAgent."""
        # 1. Build all agents (including nested workflow agents)
        agents = self._build_all_agents(workflow.agents)
        # 2. Build orchestration wrapper
        return self._build_orchestration(workflow, agents)

    def _build_all_agents(self, configs: list[AgentConfig]) -> dict[str, BaseAgent]:
        """Build all agents, resolving sub_agents references.

        First pass builds leaf agents (no sub_agent dependencies): llm, code, tool.
        Second pass builds workflow agents (may reference other agents as sub_agents).
        """
        agents: dict[str, BaseAgent] = {}

        # First pass: build leaf agents (no sub_agent dependencies)
        for config in configs:
            match config.type:
                case "llm":
                    agents[config.name] = self._build_llm_agent(config)
                case "code":
                    agents[config.name] = self._build_code_agent(config)
                case "tool":
                    agents[config.name] = self._build_tool_agent(config)
                case "expr":
                    agents[config.name] = self._build_expr_agent(config)

        # Second pass: build workflow agents (may reference other agents)
        for config in configs:
            if config.type in ("sequential", "parallel", "loop"):
                agents[config.name] = self._build_workflow_agent(config, agents)

        return agents

    def _build_llm_agent(self, config: AgentConfig) -> LlmAgent:
        """Build an LlmAgent with resolved tools, model, and optional callbacks."""
        model: Union[str, BaseLlm] = self._resolve_model(config.model)
        tools = self._tool_registry.resolve_tools(config.tools) if config.tools else []
        callbacks = self._resolve_callbacks(config.callbacks)

        kwargs: dict = {
            "name": config.name,
            "model": model,
            "instruction": config.instruction or "",
            "tools": tools,
            **callbacks,
        }
        if config.output_key:
            kwargs["output_key"] = config.output_key

        return LlmAgent(**kwargs)

    def _build_code_agent(self, config: AgentConfig) -> CodeAgent:
        """Build a CodeAgent from AgentConfig."""
        return CodeAgent(
            name=config.name,
            function_path=config.function,
            input_keys=config.input_keys or [],
            output_key=config.output_key,
        )

    def _build_tool_agent(self, config: AgentConfig) -> ToolAgent:
        """Build a ToolAgent from AgentConfig. Resolves tool by name at hydration time."""
        tool_instance = self._tool_registry.get(config.tool)
        return ToolAgent(
            name=config.name,
            tool_instance=tool_instance,
            fixed_config=config.tool_config or {},
            output_key=config.output_key,
        )

    def _build_expr_agent(self, config: AgentConfig) -> ExprAgent:
        """Build an ExprAgent from AgentConfig."""
        return ExprAgent(
            name=config.name,
            expression=config.expression,
            input_keys=config.input_keys or [],
            output_key=config.output_key,
        )

    def _build_workflow_agent(self, config: AgentConfig, agents: dict[str, BaseAgent]) -> BaseAgent:
        """Build a workflow agent (sequential/parallel/loop) from AgentConfig."""
        sub = [agents[name] for name in (config.sub_agents or [])]

        match config.type:
            case "sequential":
                return SequentialAgent(name=config.name, sub_agents=sub)
            case "parallel":
                return ParallelAgent(name=config.name, sub_agents=sub)
            case "loop":
                return LoopAgent(name=config.name, sub_agents=sub)
            case _:
                raise ValueError(f"Unsupported workflow agent type: {config.type}")

    def _build_orchestration(
        self, workflow: WorkflowDef, agents: dict[str, BaseAgent]
    ) -> BaseAgent:
        """Build the top-level orchestration wrapper from the workflow definition."""
        orch = workflow.orchestration

        match orch.type:
            case "sequential":
                return SequentialAgent(
                    name=workflow.name,
                    sub_agents=[agents[n] for n in (orch.agents or [])],
                )
            case "parallel":
                return ParallelAgent(
                    name=workflow.name,
                    sub_agents=[agents[n] for n in (orch.agents or [])],
                )
            case "loop":
                kwargs: dict = {
                    "name": workflow.name,
                    "sub_agents": [agents[n] for n in (orch.agents or [])],
                }
                if orch.max_iterations is not None:
                    kwargs["max_iterations"] = orch.max_iterations
                return LoopAgent(**kwargs)
            case "react":
                assert orch.agent is not None
                agent = agents[orch.agent]
                planner = self._resolve_planner(orch.planner)
                if planner is not None:
                    agent.planner = planner
                return agent
            case "dag":
                assert orch.nodes is not None
                dag_nodes = [
                    DagNode(
                        name=node.agent,
                        agent=agents[node.agent],
                        depends_on=set(node.depends_on),
                    )
                    for node in orch.nodes
                ]
                return DagAgent(
                    name=workflow.name,
                    dag_nodes=dag_nodes,
                    sub_agents=[agents[node.agent] for node in orch.nodes],
                )
            case "llm_routed":
                assert orch.router is not None
                assert orch.agents is not None
                router = agents[orch.router]
                available = [agents[n] for n in orch.agents]
                router.sub_agents = available
                return router
            case _:
                raise ValueError(f"Unsupported orchestration type: {orch.type}")

    def _resolve_model(self, model_string: str | None) -> Union[str, BaseLlm]:
        """Resolve model string to ADK model.

        If model starts with 'anthropic/' or 'openai/', wrap with LiteLlm.
        Otherwise pass as string directly (Gemini models).
        """
        if not model_string:
            return ""
        if model_string.startswith(("anthropic/", "openai/")):
            cls = _get_litellm()
            return cls(model=model_string)
        return model_string

    def _resolve_callbacks(self, callbacks: dict[str, str] | None) -> dict:
        """Resolve callback names to functions from the callback registry.

        Keys in the callbacks dict are short names like 'before_agent'.
        They are normalized to ADK callback parameter names like 'before_agent_callback'.
        """
        if not callbacks:
            return {}
        result = {}
        for key, name in callbacks.items():
            cb = resolve_callback(name)
            if cb is not None:
                param_key = f"{key}_callback" if not key.endswith("_callback") else key
                result[param_key] = cb
        return result

    def _resolve_planner(self, planner_name: str | None):
        """Resolve a planner name to an ADK planner instance."""
        if planner_name == "plan_react":
            return PlanReActPlanner()
        return None
