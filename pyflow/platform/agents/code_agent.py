from __future__ import annotations

import importlib
import inspect
import json
from typing import AsyncGenerator

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event, EventActions
from google.genai import types


class CodeAgent(BaseAgent):
    """Non-LLM agent that executes a Python function.

    Imports the function from a dotted path (e.g. ``mymodule.utils.compute``),
    reads *input_keys* from ``session.state``, calls the function, and writes
    the result to ``session.state[output_key]``.
    """

    function_path: str
    input_keys: list[str]
    output_key: str

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        try:
            func = _import_function(self.function_path)
            kwargs = {key: ctx.session.state.get(key) for key in self.input_keys}
            if inspect.iscoroutinefunction(func):
                result = await func(**kwargs)
            else:
                result = func(**kwargs)
        except Exception as exc:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(
                    parts=[types.Part(text=f"CodeAgent error: {exc}")],
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


def _import_function(dotted_path: str):
    """Import a function from a dotted module path like ``pkg.mod.func``."""
    module_path, _, func_name = dotted_path.rpartition(".")
    if not module_path:
        raise ImportError(f"Invalid function path: '{dotted_path}' (no module component)")
    module = importlib.import_module(module_path)
    func = getattr(module, func_name, None)
    if func is None:
        raise ImportError(f"Function '{func_name}' not found in module '{module_path}'")
    if not callable(func):
        raise ImportError(f"'{dotted_path}' is not callable")
    return func
