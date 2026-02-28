from __future__ import annotations

import json

import pytest

from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.plugin_manager import PluginManager
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.sessions.session import Session

from pyflow.platform.agents.code_agent import CodeAgent, _import_function


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
# Test functions used by CodeAgent tests
# ---------------------------------------------------------------------------

def _sync_add(a=0, b=0):
    return a + b


async def _async_multiply(x=1, y=1):
    return x * y


def _no_args():
    return {"status": "ok"}


def _raises():
    raise RuntimeError("boom")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCodeAgentSync:
    async def test_sync_function_reads_state_and_writes_output(self):
        agent = CodeAgent(
            name="adder",
            function_path="tests.platform.agents.test_code_agent._sync_add",
            input_keys=["a", "b"],
            output_key="sum",
        )
        ctx = _make_ctx(agent, state={"a": 3, "b": 7})
        events = [e async for e in agent._run_async_impl(ctx)]

        assert len(events) == 1
        event = events[0]
        assert event.author == "adder"
        assert event.actions.state_delta == {"sum": 10}
        assert event.content.parts[0].text == "10"

    async def test_missing_input_key_defaults_to_none(self):
        """Missing state keys resolve to None, which may cause the function to error."""
        agent = CodeAgent(
            name="adder",
            function_path="tests.platform.agents.test_code_agent._sync_add",
            input_keys=["a", "b"],
            output_key="sum",
        )
        ctx = _make_ctx(agent, state={"a": 5})
        events = [e async for e in agent._run_async_impl(ctx)]

        assert len(events) == 1
        # _sync_add(a=5, b=None) raises TypeError -> error event
        assert "CodeAgent error" in events[0].content.parts[0].text
        assert events[0].actions.state_delta == {}


class TestCodeAgentAsync:
    async def test_async_function_called_correctly(self):
        agent = CodeAgent(
            name="multiplier",
            function_path="tests.platform.agents.test_code_agent._async_multiply",
            input_keys=["x", "y"],
            output_key="product",
        )
        ctx = _make_ctx(agent, state={"x": 4, "y": 5})
        events = [e async for e in agent._run_async_impl(ctx)]

        assert len(events) == 1
        assert events[0].actions.state_delta == {"product": 20}


class TestCodeAgentNoArgs:
    async def test_empty_input_keys(self):
        agent = CodeAgent(
            name="checker",
            function_path="tests.platform.agents.test_code_agent._no_args",
            input_keys=[],
            output_key="status",
        )
        ctx = _make_ctx(agent)
        events = [e async for e in agent._run_async_impl(ctx)]

        assert len(events) == 1
        result = events[0].actions.state_delta["status"]
        assert result == {"status": "ok"}
        # Dict result should be JSON-serialized in content
        assert events[0].content.parts[0].text == json.dumps({"status": "ok"})


class TestCodeAgentStringResult:
    async def test_string_result_not_double_serialized(self):
        """String results should appear as-is, not JSON-quoted."""
        agent = CodeAgent(
            name="greeter",
            function_path="builtins.str",
            input_keys=[],
            output_key="greeting",
        )
        ctx = _make_ctx(agent)
        events = [e async for e in agent._run_async_impl(ctx)]

        assert len(events) == 1
        # str() with no args returns ""
        assert events[0].content.parts[0].text == ""


class TestCodeAgentErrorHandling:
    async def test_exception_yields_error_event(self):
        agent = CodeAgent(
            name="bad",
            function_path="tests.platform.agents.test_code_agent._raises",
            input_keys=[],
            output_key="result",
        )
        ctx = _make_ctx(agent)
        events = [e async for e in agent._run_async_impl(ctx)]

        assert len(events) == 1
        event = events[0]
        assert "CodeAgent error" in event.content.parts[0].text
        assert "boom" in event.content.parts[0].text
        assert event.actions.state_delta == {}

    async def test_bad_function_path_yields_error(self):
        agent = CodeAgent(
            name="bad",
            function_path="nonexistent.module.func",
            input_keys=[],
            output_key="result",
        )
        ctx = _make_ctx(agent)
        events = [e async for e in agent._run_async_impl(ctx)]

        assert len(events) == 1
        assert "CodeAgent error" in events[0].content.parts[0].text


class TestImportFunction:
    def test_valid_import(self):
        func = _import_function("json.dumps")
        assert callable(func)
        assert func is json.dumps

    def test_no_module_component(self):
        with pytest.raises(ImportError, match="no module component"):
            _import_function("nodots")

    def test_missing_function(self):
        with pytest.raises(ImportError, match="not found"):
            _import_function("json.nonexistent_func")

    def test_not_callable(self):
        with pytest.raises(ImportError, match="not callable"):
            _import_function("os.path.sep")
