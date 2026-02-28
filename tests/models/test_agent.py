from __future__ import annotations

import pytest
from pydantic import ValidationError

from pyflow.models.agent import AgentConfig


class TestAgentConfigLlm:
    def test_llm_agent_valid(self):
        agent = AgentConfig(
            name="fetcher",
            type="llm",
            model="gemini-2.5-flash",
            instruction="Fetch exchange rates",
            tools=["http_request"],
            output_key="rate_data",
        )
        assert agent.name == "fetcher"
        assert agent.type == "llm"
        assert agent.model == "gemini-2.5-flash"
        assert agent.instruction == "Fetch exchange rates"
        assert agent.tools == ["http_request"]
        assert agent.output_key == "rate_data"

    def test_llm_agent_requires_model(self):
        with pytest.raises(ValidationError, match="model"):
            AgentConfig(
                name="bad",
                type="llm",
                instruction="do stuff",
            )

    def test_llm_agent_requires_instruction(self):
        with pytest.raises(ValidationError, match="instruction"):
            AgentConfig(
                name="bad",
                type="llm",
                model="gemini-2.5-flash",
            )

    def test_llm_agent_defaults(self):
        agent = AgentConfig(
            name="minimal",
            type="llm",
            model="gemini-2.5-flash",
            instruction="Do something",
        )
        assert agent.tools == []
        assert agent.output_key is None
        assert agent.sub_agents is None


class TestAgentConfigSequential:
    def test_sequential_agent_valid(self):
        agent = AgentConfig(
            name="pipeline",
            type="sequential",
            sub_agents=["fetcher", "analyzer"],
        )
        assert agent.type == "sequential"
        assert agent.sub_agents == ["fetcher", "analyzer"]
        assert agent.model is None
        assert agent.instruction is None

    def test_sequential_requires_sub_agents(self):
        with pytest.raises(ValidationError, match="sub_agents"):
            AgentConfig(name="bad", type="sequential")


class TestAgentConfigParallel:
    def test_parallel_agent_valid(self):
        agent = AgentConfig(
            name="fan_out",
            type="parallel",
            sub_agents=["a", "b", "c"],
        )
        assert agent.type == "parallel"
        assert agent.sub_agents == ["a", "b", "c"]

    def test_parallel_requires_sub_agents(self):
        with pytest.raises(ValidationError, match="sub_agents"):
            AgentConfig(name="bad", type="parallel")


class TestAgentConfigLoop:
    def test_loop_agent_valid(self):
        agent = AgentConfig(
            name="retry_loop",
            type="loop",
            sub_agents=["worker"],
        )
        assert agent.type == "loop"
        assert agent.sub_agents == ["worker"]

    def test_loop_requires_sub_agents(self):
        with pytest.raises(ValidationError, match="sub_agents"):
            AgentConfig(name="bad", type="loop")


class TestAgentConfigCallbacks:
    def test_llm_with_callbacks(self):
        config = AgentConfig(
            name="test",
            type="llm",
            model="gemini-2.5-flash",
            instruction="test",
            callbacks={"before_agent": "log_start", "after_agent": "log_output"},
        )
        assert config.callbacks == {"before_agent": "log_start", "after_agent": "log_output"}

    def test_callbacks_default_none(self):
        config = AgentConfig(
            name="test", type="llm", model="gemini-2.5-flash", instruction="test"
        )
        assert config.callbacks is None


class TestAgentConfigInvalidType:
    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            AgentConfig(
                name="bad",
                type="unknown",
                model="x",
                instruction="y",
            )
