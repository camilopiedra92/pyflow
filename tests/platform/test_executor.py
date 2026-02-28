from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

from pyflow.models.runner import RunResult, UsageSummary
from pyflow.models.workflow import RuntimeConfig
from pyflow.platform.executor import WorkflowExecutor, _detect_system_timezone


class TestBuildRunner:
    def test_default_runtime(self):
        executor = WorkflowExecutor()
        agent = MagicMock()
        runtime = RuntimeConfig()
        with patch("pyflow.platform.executor.Runner") as mock_runner_cls:
            with patch("pyflow.platform.executor.InMemorySessionService"):
                executor.build_runner(agent, runtime)
                mock_runner_cls.assert_called_once()
                # session_service should be InMemorySessionService
                call_kwargs = mock_runner_cls.call_args[1]
                assert call_kwargs["session_service"] is not None

    def test_memory_service_in_memory(self):
        executor = WorkflowExecutor()
        agent = MagicMock()
        runtime = RuntimeConfig(memory_service="in_memory")
        with patch("pyflow.platform.executor.Runner") as mock_runner_cls:
            with patch("pyflow.platform.executor.InMemorySessionService"):
                executor.build_runner(agent, runtime)
                call_kwargs = mock_runner_cls.call_args[1]
                assert call_kwargs["memory_service"] is not None

    def test_memory_service_none(self):
        executor = WorkflowExecutor()
        agent = MagicMock()
        runtime = RuntimeConfig(memory_service="none")
        with patch("pyflow.platform.executor.Runner") as mock_runner_cls:
            with patch("pyflow.platform.executor.InMemorySessionService"):
                executor.build_runner(agent, runtime)
                call_kwargs = mock_runner_cls.call_args[1]
                assert call_kwargs["memory_service"] is None

    def test_plugins_resolved(self):
        executor = WorkflowExecutor()
        agent = MagicMock()
        runtime = RuntimeConfig(plugins=["logging"])
        with patch("pyflow.platform.executor.Runner") as mock_runner_cls:
            with patch("pyflow.platform.executor.InMemorySessionService"):
                executor.build_runner(agent, runtime)
                call_kwargs = mock_runner_cls.call_args[1]
                assert call_kwargs["plugins"] is not None


class TestRun:
    async def test_returns_run_result(self):
        executor = WorkflowExecutor()
        mock_event = MagicMock()
        mock_event.is_final_response.return_value = True
        mock_event.content.parts = [MagicMock(text="Hello")]
        mock_event.author = "agent"

        mock_runner = MagicMock()
        mock_runner.plugin_manager.plugins = []
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            yield mock_event

        mock_runner.run_async = fake_run

        result = await executor.run(mock_runner, user_id="user1", message="hi")
        assert isinstance(result, RunResult)
        assert result.content == "Hello"
        assert result.session_id == "sess-1"
        assert result.author == "agent"
        assert result.usage is not None

    async def test_empty_response(self):
        executor = WorkflowExecutor()
        mock_runner = MagicMock()
        mock_runner.plugin_manager.plugins = []
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            return
            yield

        mock_runner.run_async = fake_run

        result = await executor.run(mock_runner, user_id="user1", message="hi")
        assert result.content == ""
        assert result.session_id == "sess-1"

    async def test_default_user_id(self):
        executor = WorkflowExecutor()
        mock_runner = MagicMock()
        mock_runner.plugin_manager.plugins = []
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            return
            yield

        mock_runner.run_async = fake_run

        await executor.run(mock_runner, message="hi")
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
        mock_runner = MagicMock()
        mock_runner.plugin_manager.plugins = []
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            return
            yield

        mock_runner.run_async = fake_run

        await executor.run(mock_runner, message="hi")
        call_kwargs = mock_runner.session_service.create_session.call_args[1]
        assert "state" in call_kwargs
        assert "current_date" in call_kwargs["state"]
        assert "current_datetime" in call_kwargs["state"]
        assert call_kwargs["state"]["timezone"] == "UTC"


class TestRunStreaming:
    async def test_yields_events(self):
        executor = WorkflowExecutor(tz_name="UTC")
        mock_event = MagicMock()
        mock_runner = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            yield mock_event

        mock_runner.run_async = fake_run

        events = [e async for e in executor.run_streaming(mock_runner, message="hi")]
        assert len(events) == 1
        assert events[0] is mock_event

    async def test_creates_session_with_datetime_state(self):
        executor = WorkflowExecutor(tz_name="UTC")
        mock_runner = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            return
            yield

        mock_runner.run_async = fake_run

        async for _ in executor.run_streaming(mock_runner, message="hi"):
            pass

        call_kwargs = mock_runner.session_service.create_session.call_args[1]
        assert "state" in call_kwargs
        assert "current_date" in call_kwargs["state"]
        assert call_kwargs["state"]["timezone"] == "UTC"

    async def test_session_id_reuses_existing(self):
        executor = WorkflowExecutor(tz_name="UTC")
        mock_runner = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "existing-sess"
        mock_runner.session_service.get_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            return
            yield

        mock_runner.run_async = fake_run

        async for _ in executor.run_streaming(
            mock_runner, message="hi", session_id="existing-sess"
        ):
            pass

        mock_runner.session_service.get_session.assert_called_once()
        mock_runner.session_service.create_session.assert_not_called()

    async def test_session_id_creates_new_when_not_found(self):
        executor = WorkflowExecutor(tz_name="UTC")
        mock_runner = MagicMock()
        mock_runner.session_service.get_session = AsyncMock(return_value=None)
        mock_session = MagicMock()
        mock_session.id = "new-sess"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            return
            yield

        mock_runner.run_async = fake_run

        async for _ in executor.run_streaming(
            mock_runner, message="hi", session_id="missing-sess"
        ):
            pass

        mock_runner.session_service.get_session.assert_called_once()
        mock_runner.session_service.create_session.assert_called_once()


class TestRunMetrics:
    async def test_run_returns_usage_summary(self):
        executor = WorkflowExecutor()
        mock_event = MagicMock()
        mock_event.is_final_response.return_value = True
        mock_event.content.parts = [MagicMock(text="Hello")]
        mock_event.author = "agent"

        mock_runner = MagicMock()
        mock_runner.plugin_manager.plugins = []
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            yield mock_event

        mock_runner.run_async = fake_run

        result = await executor.run(mock_runner, message="hi")
        assert result.usage is not None
        assert isinstance(result.usage, UsageSummary)

    async def test_run_empty_response_still_has_usage(self):
        executor = WorkflowExecutor()
        mock_runner = MagicMock()
        mock_runner.plugin_manager.plugins = []
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            return
            yield

        mock_runner.run_async = fake_run

        result = await executor.run(mock_runner, message="hi")
        assert result.usage is not None
        assert result.usage.steps == 0
        assert result.usage.duration_ms >= 0
