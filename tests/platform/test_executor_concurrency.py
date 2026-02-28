from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pyflow.models.workflow import RuntimeConfig
from pyflow.platform.executor import WorkflowExecutor
from pyflow.platform.metrics_plugin import MetricsPlugin


def _mock_agent():
    """Create a MagicMock that passes App's BaseAgent validation."""
    from google.adk.agents import BaseAgent

    return MagicMock(spec=BaseAgent)


class TestRunnerPerRun:
    async def test_build_runner_includes_metrics_plugin(self):
        """build_runner() includes MetricsPlugin in the runner's plugin list."""
        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig()

        runner = executor.build_runner(agent, runtime)

        plugin_names = [p.name for p in runner.plugin_manager.plugins]
        assert "pyflow_metrics" in plugin_names

    async def test_run_builds_fresh_runner(self):
        """run() builds its own runner internally."""
        executor = WorkflowExecutor()
        agent = _mock_agent()
        runtime = RuntimeConfig()

        with patch.object(executor, "build_runner") as mock_build:
            mock_runner = MagicMock()
            mock_runner.session_service = MagicMock()
            mock_runner.session_service.create_session = AsyncMock(
                return_value=MagicMock(id="session-1")
            )
            mock_runner.plugin_manager.plugins = [MetricsPlugin()]

            async def empty_gen(*args, **kwargs):
                return
                yield

            mock_runner.run_async = empty_gen
            mock_build.return_value = mock_runner

            await executor.run(agent=agent, runtime=runtime, message="hello")

            mock_build.assert_called_once_with(agent, runtime)
