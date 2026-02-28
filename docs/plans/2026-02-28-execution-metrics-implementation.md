# Execution Metrics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expose per-execution aggregate metrics (tokens, duration, step/tool counts) through RunResult, API responses, CLI, and structured logs — leveraging ADK's plugin system instead of custom event parsing.

**Architecture:** A `MetricsPlugin(BasePlugin)` accumulates counters during execution via ADK callbacks. The executor injects it per-run, extracts a `UsageSummary` after completion, and attaches it to `RunResult`. No custom tracing — ADK's OTEL handles detailed spans.

**Tech Stack:** google-adk BasePlugin, Pydantic models, structlog, pytest + pytest-asyncio

---

### Task 1: UsageSummary Model

**Files:**
- Modify: `pyflow/models/runner.py:1-15`
- Test: `tests/models/test_runner.py`

**Step 1: Write the failing tests**

In `tests/models/test_runner.py`, add tests for `UsageSummary` and the updated `RunResult`:

```python
from pyflow.models.runner import RunResult, UsageSummary


class TestUsageSummary:
    def test_defaults(self):
        usage = UsageSummary()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cached_tokens == 0
        assert usage.total_tokens == 0
        assert usage.duration_ms == 0
        assert usage.steps == 0
        assert usage.llm_calls == 0
        assert usage.tool_calls == 0
        assert usage.model is None

    def test_with_values(self):
        usage = UsageSummary(
            input_tokens=1000,
            output_tokens=200,
            cached_tokens=500,
            total_tokens=1700,
            duration_ms=3200,
            steps=5,
            llm_calls=3,
            tool_calls=2,
            model="gemini-2.5-flash",
        )
        assert usage.input_tokens == 1000
        assert usage.model == "gemini-2.5-flash"

    def test_serialization(self):
        usage = UsageSummary(input_tokens=10, output_tokens=5, total_tokens=15)
        data = usage.model_dump()
        assert data["input_tokens"] == 10
        assert data["model"] is None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/models/test_runner.py::TestUsageSummary -v`
Expected: FAIL with `ImportError: cannot import name 'UsageSummary'`

**Step 3: Write UsageSummary and update RunResult**

Replace the full content of `pyflow/models/runner.py`:

```python
from __future__ import annotations

from pydantic import BaseModel


class UsageSummary(BaseModel):
    """Aggregate execution metrics collected by MetricsPlugin."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
    duration_ms: int = 0
    steps: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    model: str | None = None


class RunResult(BaseModel):
    """Result from executing a workflow via WorkflowExecutor."""

    content: str = ""
    author: str = ""
    usage: UsageSummary | None = None
    session_id: str | None = None
```

**Step 4: Update existing RunResult tests**

The existing tests reference `usage_metadata` which is now `usage`. Update `tests/models/test_runner.py` — replace the entire `TestRunResult` class:

```python
class TestRunResult:
    def test_creation_with_all_fields(self):
        usage = UsageSummary(input_tokens=10, output_tokens=20, total_tokens=30)
        result = RunResult(
            content="Hello, world!",
            author="agent_1",
            usage=usage,
        )
        assert result.content == "Hello, world!"
        assert result.author == "agent_1"
        assert result.usage.input_tokens == 10

    def test_defaults(self):
        result = RunResult()
        assert result.content == ""
        assert result.author == ""
        assert result.usage is None

    def test_run_result_with_session_id(self):
        result = RunResult(content="hello", session_id="sess-123")
        assert result.session_id == "sess-123"

    def test_run_result_session_id_default(self):
        result = RunResult()
        assert result.session_id is None

    def test_serialization(self):
        usage = UsageSummary(input_tokens=42, output_tokens=10, total_tokens=52)
        result = RunResult(content="hi", author="bot", usage=usage)
        data = result.model_dump()
        assert data["content"] == "hi"
        assert data["author"] == "bot"
        assert data["usage"]["input_tokens"] == 42
        assert data["session_id"] is None

    def test_serialization_no_usage(self):
        result = RunResult(content="hi", author="bot")
        data = result.model_dump()
        assert data["usage"] is None
```

**Step 5: Run all runner model tests**

Run: `pytest tests/models/test_runner.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add pyflow/models/runner.py tests/models/test_runner.py
git commit -m "feat: add UsageSummary model, replace usage_metadata with typed usage field"
```

---

### Task 2: MetricsPlugin

**Files:**
- Create: `pyflow/platform/metrics_plugin.py`
- Test: `tests/platform/test_metrics_plugin.py`

**Step 1: Write the failing tests**

Create `tests/platform/test_metrics_plugin.py`:

```python
from __future__ import annotations

import time
from unittest.mock import MagicMock

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
        assert result is None  # must not short-circuit
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
        assert result is None  # must not short-circuit
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

        # Simulate run lifecycle
        await plugin.before_run_callback(invocation_context=ctx)

        # Simulate model call
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

        # Simulate tool call
        await plugin.before_tool_callback(
            tool=MagicMock(), tool_args={}, tool_context=MagicMock()
        )

        # Simulate events
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
        """Summary works even if before_run was never called (duration=0)."""
        plugin = MetricsPlugin()
        summary = plugin.summary()
        assert summary.duration_ms == 0
        assert summary.steps == 0

    def test_plugin_name(self):
        plugin = MetricsPlugin()
        assert plugin.name == "pyflow_metrics"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/platform/test_metrics_plugin.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pyflow.platform.metrics_plugin'`

**Step 3: Implement MetricsPlugin**

Create `pyflow/platform/metrics_plugin.py`:

```python
from __future__ import annotations

import time
from typing import Any, Optional, TYPE_CHECKING

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
        return None

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[dict]:
        self._tool_calls += 1
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

    def summary(self) -> UsageSummary:
        duration = 0
        if self._start_time and self._end_time:
            duration = int((self._end_time - self._start_time) * 1000)
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
```

**Step 4: Run tests**

Run: `pytest tests/platform/test_metrics_plugin.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add pyflow/platform/metrics_plugin.py tests/platform/test_metrics_plugin.py
git commit -m "feat: add MetricsPlugin to collect aggregate execution metrics via ADK callbacks"
```

---

### Task 3: Integrate MetricsPlugin into Executor

**Files:**
- Modify: `pyflow/platform/executor.py:78-144`
- Test: `tests/platform/test_executor.py`

**Step 1: Write the failing tests**

Add to `tests/platform/test_executor.py`:

```python
from pyflow.models.runner import UsageSummary


class TestRunMetrics:
    async def test_run_returns_usage_summary(self):
        executor = WorkflowExecutor()
        mock_event = MagicMock()
        mock_event.is_final_response.return_value = True
        mock_event.content.parts = [MagicMock(text="Hello")]
        mock_event.author = "agent"

        mock_runner = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            yield mock_event

        mock_runner.run_async = fake_run

        result = await executor.run(mock_runner, message="hi")
        assert result.usage is not None
        assert isinstance(result.usage, UsageSummary)

    async def test_run_injects_metrics_plugin(self):
        """Executor should inject MetricsPlugin into runner's plugins list."""
        executor = WorkflowExecutor()
        mock_event = MagicMock()
        mock_event.is_final_response.return_value = False

        mock_runner = MagicMock()
        mock_runner.plugins = []
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run(**kwargs):
            return
            yield

        mock_runner.run_async = fake_run

        await executor.run(mock_runner, message="hi")
        # MetricsPlugin should have been added and then removed
        # Check that usage is still populated
        # (The plugin is injected, run completes, summary extracted)

    async def test_run_empty_response_still_has_usage(self):
        executor = WorkflowExecutor()
        mock_runner = MagicMock()
        mock_runner.plugins = None
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
```

Also update the existing import at the top of the file to include `UsageSummary`:

```python
from pyflow.models.runner import RunResult, UsageSummary
```

**Step 2: Run new tests to verify they fail**

Run: `pytest tests/platform/test_executor.py::TestRunMetrics -v`
Expected: FAIL — `RunResult` no longer has `usage_metadata` field, and no `UsageSummary` returned yet.

**Step 3: Update existing executor tests**

The existing `TestRun.test_returns_run_result` references `usage_metadata`. Update it to match the new field:

In `tests/platform/test_executor.py`, update `TestRun.test_returns_run_result` (line ~56-78):

Change the assertion line `assert result.session_id == "sess-1"` to also check:
```python
assert result.usage is not None
```

Remove `mock_event.usage_metadata = {"tokens": 100}` line — the executor no longer reads `usage_metadata` from events.

**Step 4: Implement executor changes**

In `pyflow/platform/executor.py`, modify `build_runner` and `run`:

1. Add import at top:
```python
from pyflow.platform.metrics_plugin import MetricsPlugin
```

2. Modify `run()` to inject MetricsPlugin, extract summary:

```python
async def run(
    self,
    runner: Runner,
    user_id: str = "default",
    message: str = "",
    session_id: str | None = None,
) -> RunResult:
    """Execute a workflow and collect results."""
    metrics = MetricsPlugin()
    if runner.plugins is None:
        runner.plugins = []
    runner.plugins.append(metrics)

    try:
        state = self._datetime_state()
        if session_id:
            session = await runner.session_service.get_session(
                app_name=self._app_name,
                user_id=user_id,
                session_id=session_id,
            )
            if session is None:
                session = await runner.session_service.create_session(
                    app_name=self._app_name,
                    user_id=user_id,
                    state=state,
                )
        else:
            session = await runner.session_service.create_session(
                app_name=self._app_name,
                user_id=user_id,
                state=state,
            )

        content = types.Content(
            role="user",
            parts=[types.Part(text=message)],
        )

        final_event = None
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.is_final_response() and event.content:
                final_event = event

        if final_event and final_event.content and final_event.content.parts:
            text = "".join(p.text for p in final_event.content.parts if p.text)
        else:
            text = ""

        author = getattr(final_event, "author", "") or "" if final_event else ""

        return RunResult(
            content=text,
            author=author,
            usage=metrics.summary(),
            session_id=session.id,
        )
    finally:
        runner.plugins.remove(metrics)
```

**Step 5: Run all executor tests**

Run: `pytest tests/platform/test_executor.py -v`
Expected: ALL PASS

**Step 6: Run full test suite to catch cascading breakage**

Run: `pytest -v`
Expected: Check for failures in tests that reference `usage_metadata` (server tests, CLI tests). Note which need updating — those are tasks 4 and 5.

**Step 7: Commit**

```bash
git add pyflow/platform/executor.py tests/platform/test_executor.py
git commit -m "feat: inject MetricsPlugin in executor, return UsageSummary in RunResult"
```

---

### Task 4: Update Server to Expose Usage

**Files:**
- Modify: `pyflow/server.py:105-121` (streaming endpoint SSE payload)
- Test: `tests/test_server.py`

**Step 1: Write the failing tests**

Add to `tests/test_server.py`:

```python
class TestWorkflowUsage:
    async def test_run_workflow_includes_usage(self, client: AsyncClient):
        """RunResult with usage should be included in response."""
        usage = UsageSummary(
            input_tokens=100, output_tokens=50, total_tokens=150,
            duration_ms=1200, steps=3, llm_calls=2, tool_calls=1,
            model="gemini-2.5-flash",
        )
        run_result = RunResult(content="done", author="agent", usage=usage)
        client._mock_platform.run_workflow.return_value = run_result

        response = await client.post(
            "/api/workflows/test/run",
            json={"message": "hello"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["usage"]["input_tokens"] == 100
        assert data["result"]["usage"]["duration_ms"] == 1200
        assert data["result"]["usage"]["model"] == "gemini-2.5-flash"

    async def test_run_workflow_usage_null_when_absent(self, client: AsyncClient):
        run_result = RunResult(content="done", author="agent")
        client._mock_platform.run_workflow.return_value = run_result

        response = await client.post(
            "/api/workflows/test/run",
            json={"message": "hello"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["usage"] is None
```

Add import at top of test file:
```python
from pyflow.models.runner import RunResult, UsageSummary
```

**Step 2: Run new tests**

Run: `pytest tests/test_server.py::TestWorkflowUsage -v`
Expected: Likely FAIL because existing tests reference `usage_metadata` field which no longer exists.

**Step 3: Fix existing server tests**

The existing `test_run_workflow_success` test creates `RunResult(content="done", author="test-agent")` which should still work since `usage` defaults to `None`. But any test asserting `usage_metadata` in response JSON needs updating.

Check server response — `WorkflowRunResponse` wraps `RunResult` via Pydantic serialization. The field rename from `usage_metadata` to `usage` will automatically appear in JSON responses. Update any assertion that checks for `usage_metadata` in response data.

**Step 4: Run all server tests**

Run: `pytest tests/test_server.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add pyflow/server.py tests/test_server.py
git commit -m "feat: expose UsageSummary in workflow API responses"
```

---

### Task 5: Update CLI to Show Usage

**Files:**
- Modify: `pyflow/cli.py:62-71`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
from pyflow.models.runner import RunResult, UsageSummary


class TestRunUsageOutput:
    def test_run_shows_usage_summary(self):
        usage = UsageSummary(
            input_tokens=500, output_tokens=100, total_tokens=600,
            duration_ms=2500, steps=4, llm_calls=2, tool_calls=1,
            model="gemini-2.5-flash",
        )
        result = RunResult(content="answer", author="agent", usage=usage)
        mock_platform = _make_mock_platform(run_result=result)
        with patch("pyflow.cli.PyFlowPlatform", return_value=mock_platform):
            res = runner.invoke(app, ["run", "my_workflow"])
        assert res.exit_code == 0
        assert "500" in res.stdout  # input_tokens visible
        assert "100" in res.stdout  # output_tokens visible
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::TestRunUsageOutput -v`
Expected: FAIL — CLI currently dumps raw JSON; usage is serialized as nested dict but not formatted.

**Step 3: Implement CLI usage display**

In `pyflow/cli.py`, update the `_run` inner function to format the usage summary after the result JSON:

```python
async def _run():
    await platform.boot()
    try:
        result = await platform.run_workflow(workflow_name, input_data, user_id=user_id)
        data = result.model_dump() if hasattr(result, "model_dump") else result
        typer.echo(json.dumps(data, indent=2))
    finally:
        await platform.shutdown()
```

The `model_dump()` call already includes `usage` in the JSON output. The test just needs to check the serialized JSON contains the usage data. No code change needed in CLI unless we want a formatted human-readable summary.

Actually, the `_make_mock_platform` returns `run_result` directly via `mock.run_workflow = AsyncMock(return_value=run_result)`, and the CLI does `result.model_dump()` — this will serialize the `RunResult` including `usage`. The test should pass as-is once the model change is in place.

If the test still fails, it means the existing `_make_mock_platform` doesn't return a proper `RunResult` object. Update it to accept `RunResult` directly.

**Step 4: Fix existing CLI tests**

Check if `_make_mock_platform` passes `run_result` through correctly. Currently it does: `mock.run_workflow = AsyncMock(return_value=run_result or {"status": "ok"})`. When a `RunResult` is passed, `.model_dump()` is called on it. When a `dict` is passed (default), `model_dump` won't exist — but `hasattr(result, "model_dump")` handles that.

**Step 5: Run all CLI tests**

Run: `pytest tests/test_cli.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add pyflow/cli.py tests/test_cli.py
git commit -m "feat: include usage metrics in CLI output"
```

---

### Task 6: Add structlog Emission in MetricsPlugin

**Files:**
- Modify: `pyflow/platform/metrics_plugin.py`
- Test: `tests/platform/test_metrics_plugin.py`

**Step 1: Write the failing tests**

Add to `tests/platform/test_metrics_plugin.py`:

```python
from unittest.mock import patch


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
        tool.name = "ynab"
        tool_ctx = MagicMock()

        with patch("pyflow.platform.metrics_plugin.logger") as mock_logger:
            await plugin.before_tool_callback(
                tool=tool, tool_args={"action": "list"}, tool_context=tool_ctx
            )
            mock_logger.info.assert_called_once()
            call_kwargs = mock_logger.info.call_args
            assert call_kwargs[0][0] == "workflow.tool_call"
            assert call_kwargs[1]["tool"] == "ynab"

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
```

**Step 2: Run to verify failure**

Run: `pytest tests/platform/test_metrics_plugin.py::TestMetricsPluginLogging -v`
Expected: FAIL — no structlog calls in MetricsPlugin yet.

**Step 3: Add structlog to MetricsPlugin**

In `pyflow/platform/metrics_plugin.py`, add at top:

```python
import structlog

logger = structlog.get_logger()
```

Add logging to callbacks:

In `after_model_callback`, after accumulating tokens:
```python
logger.info(
    "workflow.llm_call",
    tokens_in=getattr(usage, "prompt_token_count", 0) or 0,
    tokens_out=getattr(usage, "candidates_token_count", 0) or 0,
    model=model_ver or self._model,
    llm_call=self._llm_calls,
)
```

In `before_tool_callback`, after incrementing:
```python
logger.info(
    "workflow.tool_call",
    tool=tool.name,
    tool_call=self._tool_calls,
)
```

In `after_run_callback`, after setting end time:
```python
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
```

**Step 4: Run all MetricsPlugin tests**

Run: `pytest tests/platform/test_metrics_plugin.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add pyflow/platform/metrics_plugin.py tests/platform/test_metrics_plugin.py
git commit -m "feat: emit structured logs per LLM call, tool call, and run completion"
```

---

### Task 7: Full Suite Verification and Cleanup

**Files:**
- Possibly fix: any files with `usage_metadata` references

**Step 1: Search for remaining `usage_metadata` references**

Run: `grep -r "usage_metadata" pyflow/ tests/ --include="*.py"`

Fix any remaining references to use `usage` instead.

**Step 2: Run full test suite**

Run: `pytest -v`
Expected: ALL 482+ tests pass (original + new tests)

**Step 3: Verify with a live smoke test (optional)**

Run the same budget_analyst query we used earlier to confirm usage metrics appear in the RunResult:

```python
source .venv/bin/activate && python -c "
import asyncio
from pyflow.platform.app import PyFlowPlatform

async def main():
    p = PyFlowPlatform()
    await p.boot()
    r = await p.run_workflow('budget_analyst', {'message': 'Cuantos budgets tengo?'})
    print(f'Content: {r.content[:100]}...')
    print(f'Usage: {r.usage}')

asyncio.run(main())
"
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: clean up usage_metadata references, all tests green"
```
