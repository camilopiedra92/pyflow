from __future__ import annotations

from typing import TYPE_CHECKING, Union

from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.sequential_agent import SequentialAgent

from pyflow.models.agent import AgentConfig
from pyflow.models.workflow import WorkflowDef

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
    appropriate orchestration agent (Sequential, Parallel, or Loop).
    """

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry

    def hydrate(self, workflow: WorkflowDef) -> BaseAgent:
        """Convert WorkflowDef into an ADK agent tree. Returns root ADK BaseAgent."""
        # Build individual agents from AgentConfig list
        agents_by_name: dict[str, BaseAgent] = {}
        for agent_config in workflow.agents:
            agents_by_name[agent_config.name] = self._build_agent(agent_config)

        # Build orchestration wrapper with agents in declared order
        orchestration = workflow.orchestration
        ordered_agents = [agents_by_name[name] for name in orchestration.agents]

        if orchestration.type == "sequential":
            return SequentialAgent(name=workflow.name, sub_agents=ordered_agents)
        elif orchestration.type == "parallel":
            return ParallelAgent(name=workflow.name, sub_agents=ordered_agents)
        elif orchestration.type == "loop":
            return LoopAgent(name=workflow.name, sub_agents=ordered_agents)

        raise ValueError(f"Unsupported orchestration type: {orchestration.type}")

    def _build_agent(self, config: AgentConfig) -> BaseAgent:
        """Build a single ADK agent from AgentConfig."""
        if config.type == "llm":
            return self._build_llm_agent(config)
        raise ValueError(f"Unsupported agent type for direct build: {config.type}")

    def _build_llm_agent(self, config: AgentConfig) -> LlmAgent:
        """Build an LlmAgent with resolved tools and optional LiteLLM model."""
        model: Union[str, BaseLlm] = self._resolve_model(config.model)
        tools = self._tool_registry.resolve_tools(config.tools) if config.tools else []

        kwargs: dict = {
            "name": config.name,
            "model": model,
            "instruction": config.instruction or "",
            "tools": tools,
        }
        if config.output_key:
            kwargs["output_key"] = config.output_key

        return LlmAgent(**kwargs)

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
