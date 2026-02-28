---
name: create-agent-type
description: >
  Create a new PyFlow agent type that integrates into the hydration pipeline.
  Use this skill whenever the user wants to add a new agent type, create a
  custom agent, extend the agent system, or build a new kind of workflow step.
  Also use this when the user mentions "new agent type", "BaseAgent", "custom
  agent", "hydrator", or wants to add a new value to the agent type Literal.
  This is distinct from creating a workflow (which composes existing agent
  types) — this skill creates entirely new agent types.
---

# Create PyFlow Agent Type

This skill guides the creation of a new agent type — a new kind of building block that can be used in any workflow YAML. This is the pattern used to build ExprAgent, CodeAgent, ToolAgent, and DagAgent.

Adding a new agent type touches exactly 7 files, always in the same pattern. This skill encodes that pattern to avoid missed steps.

## Before You Start

1. **Is a new agent type necessary?** Most workflow needs are covered by existing types:
   - Need LLM reasoning? → `llm`
   - Need a one-liner calculation? → `expr`
   - Need full Python logic? → `code`
   - Need deterministic tool execution? → `tool`
   - Need to compose agents? → `sequential` / `parallel` / `loop`

   A new agent type is warranted when you need a fundamentally different *execution pattern* — a new way agents interact with the runtime, not just new logic (which `code` already handles).

2. **Design the interface** — what fields does the user configure in YAML? What does the agent do at runtime? What does it write to state?

## The 7-File Pattern

Every new agent type requires changes to exactly these files:

| # | File | Change |
|---|------|--------|
| 1 | `pyflow/models/agent.py` | Add type to Literal, add config fields, add validation |
| 2 | `pyflow/platform/agents/<type>_agent.py` | **NEW** — agent class extending BaseAgent |
| 3 | `pyflow/platform/agents/__init__.py` | Add export |
| 4 | `pyflow/platform/hydration/hydrator.py` | Add import, add case to first pass, add build method |
| 5 | `tests/models/test_agent.py` | Config validation tests |
| 6 | `tests/platform/agents/test_<type>_agent.py` | **NEW** — agent execution tests |
| 7 | `tests/platform/hydration/test_hydrator.py` | Hydration tests |

Follow this order. Write tests before or alongside implementation (TDD).

## Step 1: AgentConfig Model (`pyflow/models/agent.py`)

### Add the type to the Literal

```python
type: Literal["llm", "sequential", "parallel", "loop", "code", "tool", "expr", "NEW_TYPE"]
```

### Add config fields

Add fields specific to the new agent type, grouped with a comment. All new fields should be optional (`| None = None`) since they're only relevant for this type.

```python
# NewTypeAgent fields
new_field: str | None = None
another_field: list[str] | None = None
```

### Add validation

Add an `elif` case in `_validate_by_type`. Validate that required fields are present.

```python
elif self.type == "new_type":
    if not self.new_field:
        raise ValueError("new_type agent requires 'new_field'")
    if not self.output_key:
        raise ValueError("new_type agent requires 'output_key'")
```

The pattern for leaf agents is: require the type-specific field(s) + `output_key` (so the agent writes to state). Workflow agents (sequential/parallel/loop) require `sub_agents` instead.

## Step 2: Agent Class (`pyflow/platform/agents/<type>_agent.py`)

Create a new file. Follow the established pattern from CodeAgent/ExprAgent/ToolAgent:

```python
from __future__ import annotations

import json
from typing import AsyncGenerator

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event, EventActions
from google.genai import types


class NewTypeAgent(BaseAgent):
    """One-line description of what this agent does.

    More detail about behavior, inputs, outputs, and any security
    considerations.
    """

    # Pydantic fields — these become the agent's configuration
    new_field: str
    input_keys: list[str]
    output_key: str

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        try:
            # 1. Read inputs from session state
            variables = {key: ctx.session.state.get(key) for key in self.input_keys}

            # 2. Do the work
            result = self._do_work(variables)

        except Exception as exc:
            # Error path: yield error event with empty state_delta
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(
                    parts=[types.Part(text=f"NewTypeAgent error: {exc}")],
                    role="model",
                ),
                actions=EventActions(state_delta={}),
            )
            return

        # Success path: write to session state AND emit state_delta
        ctx.session.state[self.output_key] = result
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
```

### Key patterns to follow

**Event structure**: Every agent yields exactly one Event per execution — either success or error. The Event must include:
- `author=self.name` — identifies which agent produced the event
- `invocation_id=ctx.invocation_id` — ties event to the invocation
- `content` — with a `types.Content(parts=[types.Part(text=...)], role="model")`
- `actions` — with `EventActions(state_delta={...})`

**State propagation (critical)**: Always write to `ctx.session.state` directly AND include in `state_delta`. ADK's SequentialAgent does not apply `state_delta` from events between sub-agents — subsequent agents in a sequence won't see the state unless it's written directly to the session.

```python
# BOTH are needed:
ctx.session.state[self.output_key] = result          # immediate visibility for next agent
actions=EventActions(state_delta={self.output_key: result})  # for ADK Runner event processing
```

**State delta**: On success, `state_delta={self.output_key: result}`. On error, `state_delta={}` (empty — don't pollute state with error data).

**Result text**: Use `json.dumps(result)` for non-string results, raw string for string results. This prevents double-serialization.

**Error handling**: Catch exceptions broadly, yield an error event, and `return`. Never let exceptions propagate — they'd crash the ADK runner.

**Construction-time validation**: If the agent has inputs that can be validated without runtime context (like ExprAgent validating its expression AST), override `model_post_init` for fail-fast behavior:

```python
def model_post_init(self, __context) -> None:
    super().model_post_init(__context)
    # Validate here — raises on invalid config
```

This catches bad configuration at hydration time instead of at runtime, which is much better for debugging.

### Reading session state

Always read from `ctx.session.state`:
```python
value = ctx.session.state.get("key")           # single key
variables = {k: ctx.session.state.get(k) for k in self.input_keys}  # multiple keys
```

### Reusing platform infrastructure

Import from existing modules instead of reimplementing:
- AST sandbox: `from pyflow.tools.condition import _validate_ast, _SAFE_BUILTINS`
- JSON parsing: `from pyflow.tools.parsing import safe_json_parse`
- SSRF checks: `from pyflow.tools.security import is_private_url`

## Step 3: Exports (`pyflow/platform/agents/__init__.py`)

Add the import and update `__all__`:

```python
from pyflow.platform.agents.new_type_agent import NewTypeAgent

__all__ = ["CodeAgent", "DagAgent", "ExprAgent", "NewTypeAgent", "ToolAgent"]
```

Keep `__all__` sorted alphabetically.

## Step 4: Hydrator (`pyflow/platform/hydration/hydrator.py`)

Three changes needed:

### Add import

```python
from pyflow.platform.agents.new_type_agent import NewTypeAgent
```

### Add case to first pass (leaf agents)

In `_build_all_agents`, add the case in the first-pass match statement (for leaf agents that don't depend on other agents):

```python
case "new_type":
    agents[config.name] = self._build_new_type_agent(config)
```

If the new type is a workflow agent (has sub_agents), add it to the second pass instead, alongside sequential/parallel/loop.

### Add build method

```python
def _build_new_type_agent(self, config: AgentConfig) -> NewTypeAgent:
    """Build a NewTypeAgent from AgentConfig."""
    return NewTypeAgent(
        name=config.name,
        new_field=config.new_field,
        input_keys=config.input_keys or [],
        output_key=config.output_key,
    )
```

Note: `config.input_keys or []` — always default `None` to empty list for the agent class.

## Step 5: Tests

### Model tests (`tests/models/test_agent.py`)

Add a new test class following the existing pattern:

```python
class TestAgentConfigNewType:
    def test_new_type_agent_valid(self):
        agent = AgentConfig(
            name="example",
            type="new_type",
            new_field="value",
            input_keys=["x", "y"],
            output_key="result",
        )
        assert agent.type == "new_type"
        assert agent.new_field == "value"
        assert agent.input_keys == ["x", "y"]
        assert agent.output_key == "result"

    def test_new_type_requires_new_field(self):
        with pytest.raises(ValidationError, match="new_field"):
            AgentConfig(name="bad", type="new_type", output_key="result")

    def test_new_type_requires_output_key(self):
        with pytest.raises(ValidationError, match="output_key"):
            AgentConfig(name="bad", type="new_type", new_field="value")

    def test_new_type_defaults(self):
        agent = AgentConfig(
            name="minimal",
            type="new_type",
            new_field="value",
            output_key="out",
        )
        assert agent.input_keys is None
        assert agent.model is None
        assert agent.sub_agents is None
```

### Agent execution tests (`tests/platform/agents/test_<type>_agent.py`)

Create a new test file. Use the standard `_make_ctx` helper:

```python
from __future__ import annotations

import pytest

from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.plugin_manager import PluginManager
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.sessions.session import Session

from pyflow.platform.agents.new_type_agent import NewTypeAgent


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
```

Test categories to cover:
- **Success path** — normal execution, verify state_delta and content text
- **Error path** — bad input, verify error event with empty state_delta
- **Edge cases** — empty input_keys, missing state keys, boundary values
- **Event metadata** — verify `author` and `invocation_id` are set correctly
- **Construction validation** — if using `model_post_init`, test that invalid config raises

Pattern for async tests (no decorator needed — `asyncio_mode = "auto"`):
```python
class TestNewTypeAgentExecution:
    async def test_success(self):
        agent = NewTypeAgent(
            name="test",
            new_field="value",
            input_keys=["x"],
            output_key="result",
        )
        ctx = _make_ctx(agent, state={"x": 42})
        events = [e async for e in agent._run_async_impl(ctx)]

        assert len(events) == 1
        assert events[0].actions.state_delta == {"result": expected}
        assert events[0].author == "test"

    async def test_error_yields_error_event(self):
        agent = NewTypeAgent(...)
        ctx = _make_ctx(agent, state={"x": "bad_value"})
        events = [e async for e in agent._run_async_impl(ctx)]

        assert len(events) == 1
        assert "NewTypeAgent error" in events[0].content.parts[0].text
        assert events[0].actions.state_delta == {}
```

### Hydrator tests (`tests/platform/hydration/test_hydrator.py`)

Add a test class following the existing pattern:

```python
class TestHydrateNewTypeAgent:
    def test_new_type_agent_hydrated(self, mock_tool_registry):
        """AgentConfig type=new_type -> NewTypeAgent."""
        from pyflow.platform.agents.new_type_agent import NewTypeAgent

        agents = [
            AgentConfig(
                name="example",
                type="new_type",
                new_field="value",
                input_keys=["x"],
                output_key="result",
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        agent = root.sub_agents[0]
        assert isinstance(agent, NewTypeAgent)
        assert agent.name == "example"
        assert agent.new_field == "value"
        assert agent.input_keys == ["x"]
        assert agent.output_key == "result"

    def test_new_type_defaults_input_keys_to_empty(self, mock_tool_registry):
        """New type agent with no input_keys -> defaults to empty list."""
        from pyflow.platform.agents.new_type_agent import NewTypeAgent

        agents = [
            AgentConfig(
                name="minimal",
                type="new_type",
                new_field="value",
                output_key="out",
            ),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        agent = root.sub_agents[0]
        assert isinstance(agent, NewTypeAgent)
        assert agent.input_keys == []

    def test_new_type_alongside_llm(self, mock_tool_registry):
        """New type agent alongside LLM agent in sequential orchestration."""
        from pyflow.platform.agents.new_type_agent import NewTypeAgent

        agents = [
            AgentConfig(
                name="step1",
                type="new_type",
                new_field="value",
                input_keys=["x"],
                output_key="intermediate",
            ),
            _make_llm_agent_config(name="step2", instruction="Process"),
        ]
        workflow = _make_workflow(agents=agents)
        hydrator = WorkflowHydrator(mock_tool_registry)
        root = hydrator.hydrate(workflow)

        assert len(root.sub_agents) == 2
        assert isinstance(root.sub_agents[0], NewTypeAgent)
        assert root.sub_agents[1].name == "step2"
```

## Step 6: Verify

```bash
source .venv/bin/activate
pytest tests/models/test_agent.py -v                        # model validation
pytest tests/platform/agents/test_<type>_agent.py -v        # agent execution
pytest tests/platform/hydration/test_hydrator.py -v         # hydration
pytest -v                                                     # full suite
ruff check                                                    # lint
```

All 5 commands must pass before the agent type is complete.

## What NOT To Do

- **Don't forget any of the 7 files** — the most common mistake is missing the `__init__.py` export or the hydrator case
- **Don't let exceptions propagate from `_run_async_impl`** — always catch and yield error events
- **Don't write to state on error** — use `state_delta={}`, not `state_delta={self.output_key: None}`
- **Don't skip construction-time validation** — if you can detect bad config without runtime context, do it in `model_post_init`
- **Don't add the type to the second pass unless it has `sub_agents`** — leaf agents go in the first pass
- **Don't forget `from __future__ import annotations`** — required in all modules
