from __future__ import annotations

import time
from typing import Any, Optional, TYPE_CHECKING

import structlog

logger = structlog.get_logger()

from google.adk.plugins.base_plugin import BasePlugin

from pyflow.models.runner import UsageSummary

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.agents.invocation_context import InvocationContext
    from google.adk.events.event import Event
    from google.adk.models.llm_response import LlmResponse
    from google.adk.tools.base_tool import BaseTool
    from google.adk.tools.tool_context import ToolContext


class MetricsPlugin(BasePlugin):
    """Collects aggregate execution metrics during an ADK run."""

    def __init__(self) -> None:
        super().__init__(name="pyflow_metrics")
        self._start_time: float = 0.0
        self._end_time: float = 0.0
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._cached_tokens: int = 0
        self._total_tokens: int = 0
        self._steps: int = 0
        self._llm_calls: int = 0
        self._tool_calls: int = 0
        self._model: str | None = None

    async def before_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> None:
        self._start_time = time.monotonic()

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> Optional[LlmResponse]:
        self._llm_calls += 1
        usage = getattr(llm_response, "usage_metadata", None)
        if usage:
            self._input_tokens += getattr(usage, "prompt_token_count", 0) or 0
            self._output_tokens += getattr(usage, "candidates_token_count", 0) or 0
            self._cached_tokens += getattr(usage, "cached_content_token_count", 0) or 0
            self._total_tokens += getattr(usage, "total_token_count", 0) or 0
        model_ver = getattr(llm_response, "model_version", None)
        if model_ver:
            self._model = model_ver
        logger.info(
            "workflow.llm_call",
            tokens_in=getattr(usage, "prompt_token_count", 0) or 0 if usage else 0,
            tokens_out=getattr(usage, "candidates_token_count", 0) or 0 if usage else 0,
            model=model_ver or self._model,
            llm_call=self._llm_calls,
        )
        return None

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[dict]:
        self._tool_calls += 1
        logger.info(
            "workflow.tool_call",
            tool=tool.name,
            tool_call=self._tool_calls,
        )
        return None

    async def on_event_callback(
        self, *, invocation_context: InvocationContext, event: Event
    ) -> Optional[Event]:
        self._steps += 1
        return None

    async def after_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> None:
        self._end_time = time.monotonic()
        duration = int((self._end_time - self._start_time) * 1000) if self._start_time else 0
        logger.info(
            "workflow.complete",
            duration_ms=duration,
            tokens_in=self._input_tokens,
            tokens_out=self._output_tokens,
            total_tokens=self._total_tokens,
            steps=self._steps,
            llm_calls=self._llm_calls,
            tool_calls=self._tool_calls,
            model=self._model,
        )

    def summary(self) -> UsageSummary:
        duration = 0
        if self._start_time and self._end_time:
            duration = max(1, int((self._end_time - self._start_time) * 1000))
        return UsageSummary(
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            cached_tokens=self._cached_tokens,
            total_tokens=self._total_tokens,
            duration_ms=duration,
            steps=self._steps,
            llm_calls=self._llm_calls,
            tool_calls=self._tool_calls,
            model=self._model,
        )
