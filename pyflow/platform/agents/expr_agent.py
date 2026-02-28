from __future__ import annotations

import json
from typing import AsyncGenerator

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event, EventActions
from google.genai import types

from pyflow.tools.condition import _SAFE_BUILTINS, _validate_ast

class ExprAgent(BaseAgent):
    """Non-LLM agent that evaluates a safe Python expression.

    Reads *input_keys* from ``session.state``, evaluates the *expression*
    within a sandboxed environment (AST-validated, restricted builtins),
    and writes the result to ``session.state[output_key]``.

    Uses the same AST validation as ``ConditionTool`` — no imports, no IO,
    no ``__dunder__`` access, restricted builtins only.
    """

    expression: str
    input_keys: list[str]
    output_key: str

    def model_post_init(self, __context) -> None:
        """Validate the expression AST at construction time for fast failure."""
        super().model_post_init(__context)
        _validate_ast(self.expression)

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        try:
            variables = {key: ctx.session.state.get(key) for key in self.input_keys}
            env = {"__builtins__": _SAFE_BUILTINS, **variables}
            result = eval(self.expression, env)  # noqa: S307 — AST-validated sandbox
        except Exception as exc:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(
                    parts=[types.Part(text=f"ExprAgent error: {exc}")],
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
