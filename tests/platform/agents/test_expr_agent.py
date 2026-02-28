from __future__ import annotations

import pytest

from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.plugin_manager import PluginManager
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.sessions.session import Session

from pyflow.platform.agents.expr_agent import ExprAgent


def _make_ctx(agent, state: dict | None = None) -> InvocationContext:
    """Create a minimal InvocationContext for testing."""
    session = Session(
        id="test-session",
        app_name="test",
        user_id="test-user",
        state=state or {},
        events=[],
    )
    return InvocationContext(
        invocation_id="test-inv",
        agent=agent,
        session=session,
        session_service=InMemorySessionService(),
        agent_states={},
        end_of_agents={},
        plugin_manager=PluginManager(),
    )


# ---------------------------------------------------------------------------
# Arithmetic expressions
# ---------------------------------------------------------------------------


class TestExprAgentArithmetic:
    async def test_simple_addition(self):
        agent = ExprAgent(
            name="calc",
            expression="a + b",
            input_keys=["a", "b"],
            output_key="result",
        )
        ctx = _make_ctx(agent, state={"a": 3, "b": 7})
        events = [e async for e in agent._run_async_impl(ctx)]

        assert len(events) == 1
        assert events[0].actions.state_delta == {"result": 10}
        assert events[0].content.parts[0].text == "10"

    async def test_margin_calculation(self):
        agent = ExprAgent(
            name="margin",
            expression="round((price - cost) / price * 100, 2)",
            input_keys=["price", "cost"],
            output_key="margin_pct",
        )
        ctx = _make_ctx(agent, state={"price": 100.0, "cost": 65.0})
        events = [e async for e in agent._run_async_impl(ctx)]

        assert events[0].actions.state_delta == {"margin_pct": 35.0}

    async def test_expression_with_builtins(self):
        agent = ExprAgent(
            name="aggregator",
            expression="sum(values)",
            input_keys=["values"],
            output_key="total",
        )
        ctx = _make_ctx(agent, state={"values": [10, 20, 30]})
        events = [e async for e in agent._run_async_impl(ctx)]

        assert events[0].actions.state_delta == {"total": 60}


# ---------------------------------------------------------------------------
# String results
# ---------------------------------------------------------------------------


class TestExprAgentStringResult:
    async def test_string_result_not_double_serialized(self):
        agent = ExprAgent(
            name="fmt",
            expression="str(count) + ' items'",
            input_keys=["count"],
            output_key="label",
        )
        ctx = _make_ctx(agent, state={"count": 5})
        events = [e async for e in agent._run_async_impl(ctx)]

        assert events[0].actions.state_delta == {"label": "5 items"}
        assert events[0].content.parts[0].text == "5 items"


# ---------------------------------------------------------------------------
# No input keys
# ---------------------------------------------------------------------------


class TestExprAgentNoInputKeys:
    async def test_constant_expression(self):
        agent = ExprAgent(
            name="const",
            expression="42",
            input_keys=[],
            output_key="answer",
        )
        ctx = _make_ctx(agent)
        events = [e async for e in agent._run_async_impl(ctx)]

        assert events[0].actions.state_delta == {"answer": 42}


# ---------------------------------------------------------------------------
# Boolean and comparison expressions
# ---------------------------------------------------------------------------


class TestExprAgentBoolean:
    async def test_comparison_returns_bool(self):
        agent = ExprAgent(
            name="check",
            expression="score > threshold",
            input_keys=["score", "threshold"],
            output_key="passed",
        )
        ctx = _make_ctx(agent, state={"score": 85, "threshold": 70})
        events = [e async for e in agent._run_async_impl(ctx)]

        assert events[0].actions.state_delta == {"passed": True}


# ---------------------------------------------------------------------------
# List/dict expressions
# ---------------------------------------------------------------------------


class TestExprAgentComplex:
    async def test_list_comprehension(self):
        agent = ExprAgent(
            name="doubler",
            expression="[x * 2 for x in items]",
            input_keys=["items"],
            output_key="doubled",
        )
        ctx = _make_ctx(agent, state={"items": [1, 2, 3]})
        events = [e async for e in agent._run_async_impl(ctx)]

        assert events[0].actions.state_delta == {"doubled": [2, 4, 6]}

    async def test_dict_expression(self):
        agent = ExprAgent(
            name="builder",
            expression="{'total': a + b, 'avg': (a + b) / 2}",
            input_keys=["a", "b"],
            output_key="stats",
        )
        ctx = _make_ctx(agent, state={"a": 10, "b": 20})
        events = [e async for e in agent._run_async_impl(ctx)]

        assert events[0].actions.state_delta == {"stats": {"total": 30, "avg": 15.0}}


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestExprAgentErrors:
    async def test_runtime_error_yields_error_event(self):
        agent = ExprAgent(
            name="bad",
            expression="a / b",
            input_keys=["a", "b"],
            output_key="result",
        )
        ctx = _make_ctx(agent, state={"a": 1, "b": 0})
        events = [e async for e in agent._run_async_impl(ctx)]

        assert len(events) == 1
        assert "ExprAgent error" in events[0].content.parts[0].text
        assert events[0].actions.state_delta == {}

    async def test_missing_variable_yields_error(self):
        agent = ExprAgent(
            name="bad",
            expression="x + y",
            input_keys=["x"],
            output_key="result",
        )
        ctx = _make_ctx(agent, state={"x": 5})
        events = [e async for e in agent._run_async_impl(ctx)]

        assert len(events) == 1
        assert "ExprAgent error" in events[0].content.parts[0].text
        assert events[0].actions.state_delta == {}

    async def test_event_metadata(self):
        """Verify author and invocation_id are set correctly."""
        agent = ExprAgent(
            name="meta_test",
            expression="1 + 1",
            input_keys=[],
            output_key="result",
        )
        ctx = _make_ctx(agent)
        events = [e async for e in agent._run_async_impl(ctx)]

        assert events[0].author == "meta_test"
        assert events[0].invocation_id == "test-inv"


# ---------------------------------------------------------------------------
# AST validation at construction time
# ---------------------------------------------------------------------------


class TestExprAgentASTValidation:
    def test_import_rejected_at_construction(self):
        with pytest.raises(ValueError, match="not allowed"):
            ExprAgent(
                name="bad",
                expression="__import__('os')",
                input_keys=[],
                output_key="result",
            )

    def test_dunder_access_rejected_at_construction(self):
        with pytest.raises(ValueError, match="not allowed"):
            ExprAgent(
                name="bad",
                expression="x.__class__",
                input_keys=["x"],
                output_key="result",
            )

    def test_syntax_error_rejected_at_construction(self):
        with pytest.raises(SyntaxError):
            ExprAgent(
                name="bad",
                expression="if True:",
                input_keys=[],
                output_key="result",
            )

    def test_valid_expression_passes_construction(self):
        agent = ExprAgent(
            name="ok",
            expression="max(a, b) + min(c, d)",
            input_keys=["a", "b", "c", "d"],
            output_key="result",
        )
        assert agent.expression == "max(a, b) + min(c, d)"
