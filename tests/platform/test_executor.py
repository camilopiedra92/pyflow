from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.adk.agents import BaseAgent

from pyflow.models.runner import RunResult, UsageSummary
from pyflow.models.workflow import RuntimeConfig
from pyflow.platform.executor import WorkflowExecutor, _detect_system_timezone


def _mock_agent():
    """Create a MagicMock that passes App's BaseAgent validation."""
    return MagicMock(spec=BaseAgent)


class TestBuildRunner:
    def test_default_runtime_uses_app_model(self):
        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig()
        with patch("pyflow.platform.executor.Runner") as mock_runner_cls:
            with patch("pyflow.platform.executor.InMemorySessionService"):
                executor.build_runner(agent, runtime)
                mock_runner_cls.assert_called_once()
                call_kwargs = mock_runner_cls.call_args[1]
                # Runner should receive app= instead of agent=
                assert "app" in call_kwargs
                assert call_kwargs["session_service"] is not None

    def test_memory_service_in_memory(self):
        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig(memory_service="in_memory")
        with patch("pyflow.platform.executor.Runner") as mock_runner_cls:
            with patch("pyflow.platform.executor.InMemorySessionService"):
                executor.build_runner(agent, runtime)
                call_kwargs = mock_runner_cls.call_args[1]
                assert call_kwargs["memory_service"] is not None

    def test_memory_service_none(self):
        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig(memory_service="none")
        with patch("pyflow.platform.executor.Runner") as mock_runner_cls:
            with patch("pyflow.platform.executor.InMemorySessionService"):
                executor.build_runner(agent, runtime)
                call_kwargs = mock_runner_cls.call_args[1]
                assert call_kwargs["memory_service"] is None

    def test_plugins_included_in_app(self):
        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig(plugins=["logging"])
        with patch("pyflow.platform.executor.Runner") as mock_runner_cls:
            with patch("pyflow.platform.executor.InMemorySessionService"):
                executor.build_runner(agent, runtime)
                call_kwargs = mock_runner_cls.call_args[1]
                # Plugins are now in the App, not passed directly to Runner
                app = call_kwargs["app"]
                assert len(app.plugins) >= 3  # GlobalInstruction + logging + Metrics

    def test_global_instruction_plugin_always_present(self):
        """GlobalInstructionPlugin should be the first plugin in every App."""
        from google.adk.plugins.global_instruction_plugin import GlobalInstructionPlugin

        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig()
        with patch("pyflow.platform.executor.Runner") as mock_runner_cls:
            with patch("pyflow.platform.executor.InMemorySessionService"):
                executor.build_runner(agent, runtime)
                app = mock_runner_cls.call_args[1]["app"]
                assert isinstance(app.plugins[0], GlobalInstructionPlugin)

    def test_context_cache_config(self):
        """RuntimeConfig with context caching -> App gets ContextCacheConfig."""
        from google.adk.apps.app import ContextCacheConfig

        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig(
            context_cache_intervals=5,
            context_cache_ttl=600,
            context_cache_min_tokens=100,
        )
        with patch("pyflow.platform.executor.Runner") as mock_runner_cls:
            with patch("pyflow.platform.executor.InMemorySessionService"):
                executor.build_runner(agent, runtime)
                app = mock_runner_cls.call_args[1]["app"]
                assert isinstance(app.context_cache_config, ContextCacheConfig)
                assert app.context_cache_config.cache_intervals == 5
                assert app.context_cache_config.ttl_seconds == 600
                assert app.context_cache_config.min_tokens == 100

    def test_no_context_cache_by_default(self):
        """Default RuntimeConfig -> App has no context_cache_config."""
        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig()
        with patch("pyflow.platform.executor.Runner") as mock_runner_cls:
            with patch("pyflow.platform.executor.InMemorySessionService"):
                executor.build_runner(agent, runtime)
                app = mock_runner_cls.call_args[1]["app"]
                assert app.context_cache_config is None

    def test_events_compaction_config(self):
        """RuntimeConfig with compaction -> App gets EventsCompactionConfig."""
        from google.adk.apps.compaction import EventsCompactionConfig

        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig(compaction_interval=10, compaction_overlap=3)
        with patch("pyflow.platform.executor.Runner") as mock_runner_cls:
            with patch("pyflow.platform.executor.InMemorySessionService"):
                executor.build_runner(agent, runtime)
                app = mock_runner_cls.call_args[1]["app"]
                assert isinstance(app.events_compaction_config, EventsCompactionConfig)
                assert app.events_compaction_config.compaction_interval == 10
                assert app.events_compaction_config.overlap_size == 3

    def test_resumability_config(self):
        """RuntimeConfig with resumable=True -> App gets ResumabilityConfig."""
        from google.adk.apps import ResumabilityConfig

        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig(resumable=True)
        with patch("pyflow.platform.executor.Runner") as mock_runner_cls:
            with patch("pyflow.platform.executor.InMemorySessionService"):
                executor.build_runner(agent, runtime)
                app = mock_runner_cls.call_args[1]["app"]
                assert isinstance(app.resumability_config, ResumabilityConfig)
                assert app.resumability_config.is_resumable is True

    def test_credential_service_in_memory(self):
        """RuntimeConfig with credential_service='in_memory' -> Runner gets credential service."""
        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig(credential_service="in_memory")
        with patch("pyflow.platform.executor.Runner") as mock_runner_cls:
            with patch("pyflow.platform.executor.InMemorySessionService"):
                executor.build_runner(agent, runtime)
                call_kwargs = mock_runner_cls.call_args[1]
                assert call_kwargs["credential_service"] is not None

    def test_credential_service_none_by_default(self):
        """Default RuntimeConfig -> credential_service is None."""
        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig()
        with patch("pyflow.platform.executor.Runner") as mock_runner_cls:
            with patch("pyflow.platform.executor.InMemorySessionService"):
                executor.build_runner(agent, runtime)
                call_kwargs = mock_runner_cls.call_args[1]
                assert call_kwargs["credential_service"] is None


class TestRun:
    async def test_returns_run_result(self):
        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig()

        mock_event = MagicMock()
        mock_event.is_final_response.return_value = True
        mock_event.content.parts = [MagicMock(text="Hello")]
        mock_event.author = "agent"

        mock_runner = MagicMock()
        from pyflow.platform.metrics_plugin import MetricsPlugin

        mock_runner.plugin_manager.plugins = [MetricsPlugin()]
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            yield mock_event

        mock_runner.run_async = fake_run

        with patch.object(executor, "build_runner", return_value=mock_runner):
            result = await executor.run(agent=agent, runtime=runtime, user_id="user1", message="hi")
        assert isinstance(result, RunResult)
        assert result.content == "Hello"
        assert result.session_id == "sess-1"
        assert result.author == "agent"
        assert result.usage is not None

    async def test_empty_response(self):
        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig()

        mock_runner = MagicMock()
        from pyflow.platform.metrics_plugin import MetricsPlugin

        mock_runner.plugin_manager.plugins = [MetricsPlugin()]
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            return
            yield

        mock_runner.run_async = fake_run

        with patch.object(executor, "build_runner", return_value=mock_runner):
            result = await executor.run(agent=agent, runtime=runtime, user_id="user1", message="hi")
        assert result.content == ""
        assert result.session_id == "sess-1"

    async def test_default_user_id(self):
        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig()

        mock_runner = MagicMock()
        from pyflow.platform.metrics_plugin import MetricsPlugin

        mock_runner.plugin_manager.plugins = [MetricsPlugin()]
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            return
            yield

        mock_runner.run_async = fake_run

        with patch.object(executor, "build_runner", return_value=mock_runner):
            await executor.run(agent=agent, runtime=runtime, message="hi")
        # user_id defaults to "default"
        mock_runner.session_service.create_session.assert_called_once()
        call_kwargs = mock_runner.session_service.create_session.call_args[1]
        assert call_kwargs["user_id"] == "default"


class TestDatetimeState:
    def test_detect_system_timezone_returns_iana_name(self):
        tz = _detect_system_timezone()
        assert "/" in tz or tz == "UTC"

    def test_datetime_state_has_required_keys(self):
        executor = WorkflowExecutor(tz_name="America/Bogota")
        state = executor._datetime_state()
        assert "current_date" in state
        assert "current_datetime" in state
        assert "timezone" in state

    def test_datetime_state_date_format(self):
        executor = WorkflowExecutor(tz_name="UTC")
        state = executor._datetime_state()
        assert re.match(r"\d{4}-\d{2}-\d{2}$", state["current_date"])

    def test_datetime_state_iso_format(self):
        executor = WorkflowExecutor(tz_name="America/Bogota")
        state = executor._datetime_state()
        assert "T" in state["current_datetime"]
        assert "-05:00" in state["current_datetime"]

    def test_datetime_state_timezone_value(self):
        executor = WorkflowExecutor(tz_name="Europe/London")
        state = executor._datetime_state()
        assert state["timezone"] == "Europe/London"

    def test_custom_timezone_via_constructor(self):
        executor = WorkflowExecutor(tz_name="Asia/Tokyo")
        state = executor._datetime_state()
        assert state["timezone"] == "Asia/Tokyo"
        assert "+09:00" in state["current_datetime"]

    def test_empty_tz_falls_back_to_system(self):
        executor = WorkflowExecutor(tz_name="")
        state = executor._datetime_state()
        assert state["timezone"] != ""

    async def test_session_created_with_datetime_state(self):
        executor = WorkflowExecutor(tz_name="UTC")
        agent = _mock_agent()
        runtime = RuntimeConfig()

        mock_runner = MagicMock()
        from pyflow.platform.metrics_plugin import MetricsPlugin

        mock_runner.plugin_manager.plugins = [MetricsPlugin()]
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            return
            yield

        mock_runner.run_async = fake_run

        with patch.object(executor, "build_runner", return_value=mock_runner):
            await executor.run(agent=agent, runtime=runtime, message="hi")
        call_kwargs = mock_runner.session_service.create_session.call_args[1]
        assert "state" in call_kwargs
        assert "current_date" in call_kwargs["state"]
        assert "current_datetime" in call_kwargs["state"]
        assert call_kwargs["state"]["timezone"] == "UTC"


class TestRunStreaming:
    async def test_yields_events(self):
        executor = WorkflowExecutor(tz_name="UTC")
        agent = _mock_agent()
        runtime = RuntimeConfig()

        mock_event = MagicMock()
        mock_runner = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            yield mock_event

        mock_runner.run_async = fake_run

        with patch.object(executor, "build_runner", return_value=mock_runner):
            events = [
                e async for e in executor.run_streaming(agent=agent, runtime=runtime, message="hi")
            ]
        assert len(events) == 1
        assert events[0] is mock_event

    async def test_creates_session_with_datetime_state(self):
        executor = WorkflowExecutor(tz_name="UTC")
        agent = _mock_agent()
        runtime = RuntimeConfig()

        mock_runner = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            return
            yield

        mock_runner.run_async = fake_run

        with patch.object(executor, "build_runner", return_value=mock_runner):
            async for _ in executor.run_streaming(agent=agent, runtime=runtime, message="hi"):
                pass

        call_kwargs = mock_runner.session_service.create_session.call_args[1]
        assert "state" in call_kwargs
        assert "current_date" in call_kwargs["state"]
        assert call_kwargs["state"]["timezone"] == "UTC"

    async def test_session_id_reuses_existing(self):
        executor = WorkflowExecutor(tz_name="UTC")
        agent = _mock_agent()
        runtime = RuntimeConfig()

        mock_runner = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "existing-sess"
        mock_runner.session_service.get_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            return
            yield

        mock_runner.run_async = fake_run

        with patch.object(executor, "build_runner", return_value=mock_runner):
            async for _ in executor.run_streaming(
                agent=agent, runtime=runtime, message="hi", session_id="existing-sess"
            ):
                pass

        mock_runner.session_service.get_session.assert_called_once()
        mock_runner.session_service.create_session.assert_not_called()

    async def test_session_id_creates_new_when_not_found(self):
        executor = WorkflowExecutor(tz_name="UTC")
        agent = _mock_agent()
        runtime = RuntimeConfig()

        mock_runner = MagicMock()
        mock_runner.session_service.get_session = AsyncMock(return_value=None)
        mock_session = MagicMock()
        mock_session.id = "new-sess"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            return
            yield

        mock_runner.run_async = fake_run

        with patch.object(executor, "build_runner", return_value=mock_runner):
            async for _ in executor.run_streaming(
                agent=agent, runtime=runtime, message="hi", session_id="missing-sess"
            ):
                pass

        mock_runner.session_service.get_session.assert_called_once()
        mock_runner.session_service.create_session.assert_called_once()


class TestRunMetrics:
    async def test_run_returns_usage_summary(self):
        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig()

        mock_event = MagicMock()
        mock_event.is_final_response.return_value = True
        mock_event.content.parts = [MagicMock(text="Hello")]
        mock_event.author = "agent"

        mock_runner = MagicMock()
        from pyflow.platform.metrics_plugin import MetricsPlugin

        mock_runner.plugin_manager.plugins = [MetricsPlugin()]
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            yield mock_event

        mock_runner.run_async = fake_run

        with patch.object(executor, "build_runner", return_value=mock_runner):
            result = await executor.run(agent=agent, runtime=runtime, message="hi")
        assert result.usage is not None
        assert isinstance(result.usage, UsageSummary)

    async def test_run_empty_response_still_has_usage(self):
        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig()

        mock_runner = MagicMock()
        from pyflow.platform.metrics_plugin import MetricsPlugin

        mock_runner.plugin_manager.plugins = [MetricsPlugin()]
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            return
            yield

        mock_runner.run_async = fake_run

        with patch.object(executor, "build_runner", return_value=mock_runner):
            result = await executor.run(agent=agent, runtime=runtime, message="hi")
        assert result.usage is not None
        assert result.usage.steps == 0
        assert result.usage.duration_ms >= 0
