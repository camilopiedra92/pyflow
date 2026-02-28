from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, AsyncGenerator

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event, EventActions
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from pydantic import ConfigDict

from pyflow.tools.base import BasePlatformTool

# Pattern matching ``{variable_name}`` placeholders in config values.
_TEMPLATE_RE = re.compile(r"\{(\w+)\}")


class ToolAgent(BaseAgent):
    """Non-LLM agent that executes a platform tool with fixed configuration.

    Template variables like ``{key}`` in *fixed_config* values are resolved
    from ``session.state`` before each execution.  A value that is exactly
    ``"{key}"`` is replaced by the raw state value (preserving type); partial
    matches like ``"prefix_{key}_suffix"`` produce a string.
    """

    tool_instance: BasePlatformTool
    fixed_config: dict[str, Any]
    output_key: str

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        try:
            resolved = _resolve_templates(self.fixed_config, dict(ctx.session.state))
            tc = ToolContext(ctx)
            result = await self.tool_instance.execute(tool_context=tc, **resolved)
        except Exception as exc:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(
                    parts=[types.Part(text=f"ToolAgent error: {exc}")],
                    role="model",
                ),
                actions=EventActions(state_delta={}),
            )
            return

        result_text = json.dumps(result) if not isinstance(result, str) else result
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(
                parts=[types.Part(text=result_text)],
                role="model",
            ),
            actions=EventActions(state_delta={self.output_key: result}),
        )


def _resolve_templates(config: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Recursively resolve ``{variable}`` templates in config values from state."""
    resolved = deepcopy(config)
    for key, value in resolved.items():
        resolved[key] = _resolve_value(value, state)
    return resolved


def _resolve_value(value: Any, state: dict[str, Any]) -> Any:
    """Resolve a single value, recursing into dicts and lists."""
    if isinstance(value, str):
        return _resolve_string(value, state)
    if isinstance(value, dict):
        return {k: _resolve_value(v, state) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_value(item, state) for item in value]
    return value


def _resolve_string(value: str, state: dict[str, Any]) -> Any:
    """Resolve a string template.

    Full match ``"{key}"`` → raw state value (preserves type).
    Partial match ``"prefix_{key}_suffix"`` → string interpolation.
    """
    match = _TEMPLATE_RE.fullmatch(value)
    if match:
        # Full match — return raw value to preserve type
        key = match.group(1)
        return state.get(key, value)
    # Partial match — string interpolation
    def _replacer(m: re.Match) -> str:
        return str(state.get(m.group(1), m.group(0)))

    return _TEMPLATE_RE.sub(_replacer, value)
