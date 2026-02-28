from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.plugin_manager import PluginManager
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.sessions.session import Session
from google.adk.tools.tool_context import ToolContext

from pyflow.platform.agents.tool_agent import ToolAgent, _resolve_templates
from pyflow.tools.base import BasePlatformTool


class StubTool(BasePlatformTool):
    """Stub tool for testing. Not auto-registered (no class-level ``name``)."""

    name = None  # type: ignore[assignment]
    description = "stub"

    async def execute(self, tool_context: ToolContext, **kwargs: Any) -> dict:
        return {"echo": kwargs}


# Prevent StubTool from auto-registering in the global registry
StubTool.__init_subclass__ = lambda **kw: None  # noqa: ARG005


def _make_stub_tool(side_effect=None) -> BasePlatformTool:
    """Create a stub tool with an optional side_effect for its execute method."""
    tool = StubTool()
    if side_effect is not None:
        tool.execute = AsyncMock(side_effect=side_effect)
    return tool


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
# ToolAgent execution tests
# ---------------------------------------------------------------------------


class TestToolAgentExecution:
    async def test_executes_tool_and_writes_state(self):
        tool = _make_stub_tool()
        agent = ToolAgent(
            name="fetcher",
            tool_instance=tool,
            fixed_config={"url": "https://example.com", "method": "GET"},
            output_key="response",
        )
        ctx = _make_ctx(agent)
        events = [e async for e in agent._run_async_impl(ctx)]

        assert len(events) == 1
        event = events[0]
        assert event.author == "fetcher"
        result = event.actions.state_delta["response"]
        assert result == {"echo": {"url": "https://example.com", "method": "GET"}}

    async def test_template_resolution_from_state(self):
        tool = _make_stub_tool()
        agent = ToolAgent(
            name="fetcher",
            tool_instance=tool,
            fixed_config={"url": "https://api.com/{endpoint}", "method": "GET"},
            output_key="data",
        )
        ctx = _make_ctx(agent, state={"endpoint": "users"})
        events = [e async for e in agent._run_async_impl(ctx)]

        result = events[0].actions.state_delta["data"]
        assert result == {"echo": {"url": "https://api.com/users", "method": "GET"}}

    async def test_full_template_preserves_type(self):
        """A value that is exactly ``{key}`` should return the raw state value."""
        tool = _make_stub_tool()
        agent = ToolAgent(
            name="processor",
            tool_instance=tool,
            fixed_config={"data": "{input_data}"},
            output_key="result",
        )
        state_data = {"key": "value", "count": 42}
        ctx = _make_ctx(agent, state={"input_data": state_data})
        events = [e async for e in agent._run_async_impl(ctx)]

        result = events[0].actions.state_delta["result"]
        assert result["echo"]["data"] == state_data

    async def test_empty_config(self):
        tool = _make_stub_tool()
        agent = ToolAgent(
            name="simple",
            tool_instance=tool,
            fixed_config={},
            output_key="out",
        )
        ctx = _make_ctx(agent)
        events = [e async for e in agent._run_async_impl(ctx)]

        assert events[0].actions.state_delta["out"] == {"echo": {}}


class TestToolAgentErrorHandling:
    async def test_tool_exception_yields_error_event(self):
        tool = _make_stub_tool(side_effect=RuntimeError("connection failed"))
        agent = ToolAgent(
            name="broken",
            tool_instance=tool,
            fixed_config={"url": "https://example.com"},
            output_key="data",
        )
        ctx = _make_ctx(agent)
        events = [e async for e in agent._run_async_impl(ctx)]

        assert len(events) == 1
        event = events[0]
        assert "ToolAgent error" in event.content.parts[0].text
        assert "connection failed" in event.content.parts[0].text
        assert event.actions.state_delta == {}


# ---------------------------------------------------------------------------
# Template resolution tests
# ---------------------------------------------------------------------------


class TestResolveTemplates:
    def test_no_templates(self):
        config = {"url": "https://example.com", "count": 5}
        result = _resolve_templates(config, {})
        assert result == config

    def test_full_match_preserves_type(self):
        result = _resolve_templates({"data": "{payload}"}, {"payload": [1, 2, 3]})
        assert result["data"] == [1, 2, 3]

    def test_partial_match_string_interpolation(self):
        result = _resolve_templates(
            {"url": "https://api.com/{version}/users"},
            {"version": "v2"},
        )
        assert result["url"] == "https://api.com/v2/users"

    def test_multiple_templates_in_one_string(self):
        result = _resolve_templates(
            {"path": "{base}/{endpoint}"},
            {"base": "api", "endpoint": "users"},
        )
        assert result["path"] == "api/users"

    def test_nested_dict_resolution(self):
        config = {"headers": {"Authorization": "Bearer {token}"}}
        result = _resolve_templates(config, {"token": "abc123"})
        assert result["headers"]["Authorization"] == "Bearer abc123"

    def test_list_resolution(self):
        config = {"tags": ["{env}", "static"]}
        result = _resolve_templates(config, {"env": "prod"})
        assert result["tags"] == ["prod", "static"]

    def test_missing_template_keeps_placeholder(self):
        result = _resolve_templates({"url": "{missing}"}, {})
        assert result["url"] == "{missing}"

    def test_non_string_values_pass_through(self):
        config = {"count": 42, "enabled": True, "data": None}
        result = _resolve_templates(config, {})
        assert result == config

    def test_does_not_mutate_original(self):
        config = {"url": "{host}/api"}
        original = {"url": "{host}/api"}
        _resolve_templates(config, {"host": "localhost"})
        assert config == original
