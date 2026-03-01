from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from pyflow.models.runner import UsageSummary
from pyflow.platform.metrics_plugin import MetricsPlugin


class TestMetricsPluginCallbacks:
    async def test_before_run_starts_timer(self):
        plugin = MetricsPlugin()
        ctx = MagicMock()
        await plugin.before_run_callback(invocation_context=ctx)
        assert plugin._start_time is not None
        assert plugin._start_time > 0

    async def test_after_model_accumulates_tokens(self):
        plugin = MetricsPlugin()
        callback_ctx = MagicMock()

        llm_response = MagicMock()
        llm_response.usage_metadata.prompt_token_count = 100
        llm_response.usage_metadata.candidates_token_count = 50
        llm_response.usage_metadata.cached_content_token_count = 20
        llm_response.usage_metadata.total_token_count = 170
        llm_response.model_version = "gemini-2.5-flash-preview-05-20"

        result = await plugin.after_model_callback(
            callback_context=callback_ctx, llm_response=llm_response
        )
        assert result is None
        assert plugin._input_tokens == 100
        assert plugin._output_tokens == 50
        assert plugin._cached_tokens == 20
        assert plugin._total_tokens == 170
        assert plugin._llm_calls == 1
        assert plugin._model == "gemini-2.5-flash-preview-05-20"

    async def test_after_model_accumulates_across_calls(self):
        plugin = MetricsPlugin()
        callback_ctx = MagicMock()

        for i in range(3):
            llm_response = MagicMock()
            llm_response.usage_metadata.prompt_token_count = 100
            llm_response.usage_metadata.candidates_token_count = 50
            llm_response.usage_metadata.cached_content_token_count = 0
            llm_response.usage_metadata.total_token_count = 150
            llm_response.model_version = "gemini-2.5-flash"
            await plugin.after_model_callback(
                callback_context=callback_ctx, llm_response=llm_response
            )

        assert plugin._input_tokens == 300
        assert plugin._output_tokens == 150
        assert plugin._llm_calls == 3

    async def test_after_model_handles_none_usage(self):
        plugin = MetricsPlugin()
        callback_ctx = MagicMock()
        llm_response = MagicMock()
        llm_response.usage_metadata = None
        llm_response.model_version = None

        result = await plugin.after_model_callback(
            callback_context=callback_ctx, llm_response=llm_response
        )
        assert result is None
        assert plugin._llm_calls == 1
        assert plugin._input_tokens == 0

    async def test_before_tool_increments_count(self):
        plugin = MetricsPlugin()
        tool = MagicMock()
        tool_ctx = MagicMock()

        result = await plugin.before_tool_callback(
            tool=tool, tool_args={"action": "list"}, tool_context=tool_ctx
        )
        assert result is None
        assert plugin._tool_calls == 1

    async def test_on_event_increments_steps(self):
        plugin = MetricsPlugin()
        ctx = MagicMock()
        event = MagicMock()

        result = await plugin.on_event_callback(invocation_context=ctx, event=event)
        assert result is None
        assert plugin._steps == 1

    async def test_on_event_accumulates(self):
        plugin = MetricsPlugin()
        ctx = MagicMock()
        for _ in range(5):
            await plugin.on_event_callback(invocation_context=ctx, event=MagicMock())
        assert plugin._steps == 5


class TestMetricsPluginSummary:
    async def test_summary_with_full_run(self):
        plugin = MetricsPlugin()
        ctx = MagicMock()

        await plugin.before_run_callback(invocation_context=ctx)

        llm_response = MagicMock()
        llm_response.usage_metadata.prompt_token_count = 500
        llm_response.usage_metadata.candidates_token_count = 100
        llm_response.usage_metadata.cached_content_token_count = 50
        llm_response.usage_metadata.total_token_count = 650
        llm_response.model_version = "gemini-2.5-flash"
        callback_ctx = MagicMock()
        await plugin.after_model_callback(
            callback_context=callback_ctx, llm_response=llm_response
        )

        await plugin.before_tool_callback(
            tool=MagicMock(), tool_args={}, tool_context=MagicMock()
        )

        for _ in range(3):
            await plugin.on_event_callback(invocation_context=ctx, event=MagicMock())

        await plugin.after_run_callback(invocation_context=ctx)

        summary = plugin.summary()
        assert isinstance(summary, UsageSummary)
        assert summary.input_tokens == 500
        assert summary.output_tokens == 100
        assert summary.cached_tokens == 50
        assert summary.total_tokens == 650
        assert summary.duration_ms > 0
        assert summary.steps == 3
        assert summary.llm_calls == 1
        assert summary.tool_calls == 1
        assert summary.model == "gemini-2.5-flash"

    def test_summary_without_run(self):
        plugin = MetricsPlugin()
        summary = plugin.summary()
        assert summary.duration_ms == 0
        assert summary.steps == 0

    def test_plugin_name(self):
        plugin = MetricsPlugin()
        assert plugin.name == "pyflow_metrics"


class TestMetricsPluginLogging:
    async def test_after_model_logs_step(self):
        plugin = MetricsPlugin()
        callback_ctx = MagicMock()
        llm_response = MagicMock()
        llm_response.usage_metadata.prompt_token_count = 100
        llm_response.usage_metadata.candidates_token_count = 50
        llm_response.usage_metadata.cached_content_token_count = 0
        llm_response.usage_metadata.total_token_count = 150
        llm_response.model_version = "gemini-2.5-flash"

        with patch("pyflow.platform.metrics_plugin.logger") as mock_logger:
            await plugin.after_model_callback(
                callback_context=callback_ctx, llm_response=llm_response
            )
            mock_logger.info.assert_called_once()
            call_kwargs = mock_logger.info.call_args
            assert call_kwargs[0][0] == "workflow.llm_call"
            assert call_kwargs[1]["tokens_in"] == 100
            assert call_kwargs[1]["tokens_out"] == 50

    async def test_before_tool_logs_call(self):
        plugin = MetricsPlugin()
        tool = MagicMock()
        tool.name = "http_request"
        tool_ctx = MagicMock()

        with patch("pyflow.platform.metrics_plugin.logger") as mock_logger:
            await plugin.before_tool_callback(
                tool=tool, tool_args={"action": "list"}, tool_context=tool_ctx
            )
            mock_logger.info.assert_called_once()
            call_kwargs = mock_logger.info.call_args
            assert call_kwargs[0][0] == "workflow.tool_call"
            assert call_kwargs[1]["tool"] == "http_request"

    async def test_after_run_logs_summary(self):
        plugin = MetricsPlugin()
        plugin._start_time = 1000.0
        plugin._input_tokens = 500
        plugin._output_tokens = 100
        ctx = MagicMock()

        with patch("pyflow.platform.metrics_plugin.logger") as mock_logger:
            with patch("time.monotonic", return_value=1003.0):
                await plugin.after_run_callback(invocation_context=ctx)
            mock_logger.info.assert_called_once()
            call_kwargs = mock_logger.info.call_args
            assert call_kwargs[0][0] == "workflow.complete"
            assert call_kwargs[1]["duration_ms"] == 3000
            assert call_kwargs[1]["tokens_in"] == 500
