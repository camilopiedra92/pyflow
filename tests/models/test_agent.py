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
        config = AgentConfig(name="test", type="llm", model="gemini-2.5-flash", instruction="test")
        assert config.callbacks is None


class TestAgentConfigCode:
    def test_code_agent_valid(self):
        agent = AgentConfig(
            name="compute",
            type="code",
            function="myapp.utils.compute_score",
            input_keys=["raw_data"],
            output_key="score",
        )
        assert agent.type == "code"
        assert agent.function == "myapp.utils.compute_score"
        assert agent.input_keys == ["raw_data"]
        assert agent.output_key == "score"

    def test_code_agent_requires_function(self):
        with pytest.raises(ValidationError, match="function"):
            AgentConfig(name="bad", type="code", output_key="result")

    def test_code_agent_requires_output_key(self):
        with pytest.raises(ValidationError, match="output_key"):
            AgentConfig(name="bad", type="code", function="mod.func")

    def test_code_agent_defaults(self):
        agent = AgentConfig(
            name="minimal",
            type="code",
            function="mod.func",
            output_key="out",
        )
        assert agent.input_keys is None
        assert agent.model is None
        assert agent.sub_agents is None


class TestAgentConfigTool:
    def test_tool_agent_valid(self):
        agent = AgentConfig(
            name="fetcher",
            type="tool",
            tool="http_request",
            tool_config={"url": "https://api.example.com/data", "method": "GET"},
            output_key="api_data",
        )
        assert agent.type == "tool"
        assert agent.tool == "http_request"
        assert agent.tool_config == {"url": "https://api.example.com/data", "method": "GET"}
        assert agent.output_key == "api_data"

    def test_tool_agent_requires_tool(self):
        with pytest.raises(ValidationError, match="tool"):
            AgentConfig(name="bad", type="tool", output_key="result")

    def test_tool_agent_requires_output_key(self):
        with pytest.raises(ValidationError, match="output_key"):
            AgentConfig(name="bad", type="tool", tool="http_request")

    def test_tool_agent_defaults(self):
        agent = AgentConfig(
            name="minimal",
            type="tool",
            tool="http_request",
            output_key="out",
        )
        assert agent.tool_config is None
        assert agent.model is None
        assert agent.sub_agents is None


class TestAgentConfigExpr:
    def test_expr_agent_valid(self):
        agent = AgentConfig(
            name="calc",
            type="expr",
            expression="price * quantity",
            input_keys=["price", "quantity"],
            output_key="total",
        )
        assert agent.type == "expr"
        assert agent.expression == "price * quantity"
        assert agent.input_keys == ["price", "quantity"]
        assert agent.output_key == "total"

    def test_expr_agent_requires_expression(self):
        with pytest.raises(ValidationError, match="expression"):
            AgentConfig(name="bad", type="expr", output_key="result")

    def test_expr_agent_requires_output_key(self):
        with pytest.raises(ValidationError, match="output_key"):
            AgentConfig(name="bad", type="expr", expression="1 + 1")

    def test_expr_agent_defaults(self):
        agent = AgentConfig(
            name="minimal",
            type="expr",
            expression="42",
            output_key="answer",
        )
        assert agent.input_keys is None
        assert agent.model is None
        assert agent.sub_agents is None


class TestAgentConfigInvalidType:
    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            AgentConfig(
                name="bad",
                type="unknown",
                model="x",
                instruction="y",
            )
