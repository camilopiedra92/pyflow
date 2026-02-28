from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


from pyflow.models.runner import RunResult
from pyflow.models.workflow import RuntimeConfig
from pyflow.platform.executor import WorkflowExecutor


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
        mock_event.usage_metadata = {"tokens": 100}

        mock_runner = MagicMock()
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

    async def test_empty_response(self):
        executor = WorkflowExecutor()
        mock_runner = MagicMock()
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
