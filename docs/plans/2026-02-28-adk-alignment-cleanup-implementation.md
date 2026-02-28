# ADK Alignment Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove dead code, fix bugs, and integrate stable ADK features into PyFlow.

**Architecture:** Four phases — dead code removal, bug fixes, ADK feature integration, documentation updates. Each phase is independently testable. All changes maintain the 528+ test baseline.

**Tech Stack:** Python 3.12, google-adk 1.26, pydantic 2.x, pytest, pytest-asyncio

---

### Task 1: Remove `jinja2` dependency

**Files:**
- Modify: `pyproject.toml:11`

**Step 1: Remove jinja2 from dependencies**

Edit `pyproject.toml` line 11 — remove `"jinja2>=3.1",` from the `dependencies` list.

```toml
dependencies = [
    "google-adk>=1.26",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "pyyaml>=6.0",
    "jsonpath-ng>=1.6",
    "httpx>=0.27",
    "typer>=0.12",
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "structlog>=24.0",
]
```

Also bump `google-adk>=1.25` to `google-adk>=1.26` (aligning pyproject.toml with CLAUDE.md).

**Step 2: Run tests to verify nothing depends on jinja2**

Run: `source .venv/bin/activate && pytest -v --tb=short 2>&1 | tail -20`
Expected: All 528 tests pass.

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: remove unused jinja2 dep, bump google-adk to >=1.26"
```

---

### Task 2: Remove `PlatformConfig.tools_dir`

**Files:**
- Modify: `pyflow/models/platform.py:23`
- Modify: `tests/models/test_platform.py:12,20-26`

**Step 1: Update tests to remove tools_dir references**

In `tests/models/test_platform.py`:

`test_defaults` (line 10-16): Remove `assert config.tools_dir == "pyflow/tools"`.

`test_overrides` (line 18-30): Remove `tools_dir="custom/tools"` from constructor and `assert config.tools_dir == "custom/tools"`.

```python
class TestPlatformConfig:
    def test_defaults(self):
        config = PlatformConfig()
        assert config.workflows_dir == "agents"
        assert config.log_level == "INFO"
        assert config.host == "0.0.0.0"
        assert config.port == 8000

    def test_overrides(self):
        config = PlatformConfig(
            workflows_dir="custom/workflows",
            log_level="DEBUG",
            host="127.0.0.1",
            port=9000,
        )
        assert config.workflows_dir == "custom/workflows"
        assert config.log_level == "DEBUG"
        assert config.host == "127.0.0.1"
        assert config.port == 9000
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/models/test_platform.py -v`
Expected: PASS (tests no longer reference removed field — they should pass even before removing the field).

**Step 3: Remove tools_dir from PlatformConfig**

In `pyflow/models/platform.py`, remove line 23: `tools_dir: str = "pyflow/tools"`.

**Step 4: Run full tests**

Run: `source .venv/bin/activate && pytest -v --tb=short 2>&1 | tail -20`
Expected: All tests pass.

**Step 5: Commit**

```bash
git add pyflow/models/platform.py tests/models/test_platform.py
git commit -m "chore: remove dead PlatformConfig.tools_dir field"
```

---

### Task 3: Remove `WorkflowInput.data` field

**Files:**
- Modify: `pyflow/server.py:79-82`
- Modify: `tests/test_server.py` (multiple lines referencing `"data": {}`)

**Step 1: Update server tests to remove data field**

In `tests/test_server.py`, update all `json={"message": ..., "data": {}}` payloads to `json={"message": ...}`. Also update the `assert_awaited_once_with` calls that expect `{"message": ..., "data": {}}` to expect `{"message": ...}`.

Affected tests and their assertion changes:

- `test_run_workflow_success` (line 117): `json={"message": "hello"}`, assert called with `{"message": "hello"}, user_id="default"`
- `test_run_workflow_with_user_id` (line 136): `json={"message": "hello", "user_id": "alice"}`, assert called with `{"message": "hello"}, user_id="alice"`
- `test_run_workflow_user_id_default` (line 155-158): Already only sends `{"message": "hi"}` — update the assert to expect `{"message": "hi"}` (no `"data": {}`)
- `test_run_workflow_not_found` (line 166): `json={"message": ""}`
- `test_run_workflow_internal_error` (line 176): `json={"message": ""}`
- `test_a2a_execute_success` (line 241): `json={"message": "run it"}`, assert with `{"message": "run it"}`
- `test_a2a_execute_with_user_id` (line 260): `json={"message": "run it", "user_id": "bob"}`, assert with `{"message": "run it"}`
- `test_a2a_execute_not_found` (line 272): `json={"message": ""}`
- `test_a2a_execute_internal_error` (line 282): `json={"message": ""}`

**Step 2: Remove data field from WorkflowInput**

In `pyflow/server.py`, change `WorkflowInput`:

```python
class WorkflowInput(BaseModel):
    message: str = ""
    user_id: str = "default"
```

**Step 3: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_server.py -v`
Expected: All server tests pass.

**Step 4: Commit**

```bash
git add pyflow/server.py tests/test_server.py
git commit -m "chore: remove dead WorkflowInput.data field"
```

---

### Task 4: Remove `scan_directory()` and flat YAML fallback

**Files:**
- Modify: `pyflow/platform/registry/discovery.py:20-28` — remove `scan_directory()`
- Modify: `pyflow/platform/registry/workflow_registry.py:10,38-46` — remove import and fallback branch
- Modify: `tests/platform/registry/test_discovery.py:5,8-49` — remove `scan_directory` import and 5 tests
- Modify: `pyflow/platform/registry/__init__.py` — remove `scan_directory` from exports if present

**Step 1: Remove scan_directory tests**

In `tests/platform/registry/test_discovery.py`, remove:
- Line 5: `scan_directory` from the import
- Lines 8-49: All 5 `test_scan_*` functions (those that test `scan_directory`)

Keep the `scan_agent_packages` tests (lines 56-86).

Result:
```python
from __future__ import annotations

from pathlib import Path

from pyflow.platform.registry.discovery import scan_agent_packages


def test_scan_agent_packages_finds_packages(tmp_path: Path) -> None:
    """scan_agent_packages() returns dirs containing workflow.yaml."""
    pkg1 = tmp_path / "agent_a"
    pkg1.mkdir()
    (pkg1 / "workflow.yaml").write_text("name: a\n")
    (pkg1 / "__init__.py").touch()

    pkg2 = tmp_path / "agent_b"
    pkg2.mkdir()
    (pkg2 / "workflow.yaml").write_text("name: b\n")
    (pkg2 / "__init__.py").touch()

    notpkg = tmp_path / "not_a_package"
    notpkg.mkdir()
    (notpkg / "__init__.py").touch()

    result = scan_agent_packages(tmp_path)
    names = [p.name for p in result]
    assert names == ["agent_a", "agent_b"]
    assert "not_a_package" not in names


def test_scan_agent_packages_empty_dir(tmp_path: Path) -> None:
    """Empty directory returns empty list."""
    assert scan_agent_packages(tmp_path) == []


def test_scan_agent_packages_nonexistent(tmp_path: Path) -> None:
    """Nonexistent directory returns empty list."""
    assert scan_agent_packages(tmp_path / "missing") == []
```

**Step 2: Run test to verify they pass**

Run: `source .venv/bin/activate && pytest tests/platform/registry/test_discovery.py -v`
Expected: 3 tests pass (the scan_agent_packages tests).

**Step 3: Remove scan_directory from discovery.py**

In `pyflow/platform/registry/discovery.py`, remove lines 20-28 (the `scan_directory` function).

**Step 4: Remove flat YAML fallback from workflow_registry.py**

In `pyflow/platform/registry/workflow_registry.py`:
- Remove `scan_directory` from import on line 10
- Simplify `discover()` to only use `scan_agent_packages`:

```python
from pyflow.platform.registry.discovery import scan_agent_packages
```

```python
    def discover(self, directory: Path) -> None:
        """Scan directory for agent packages (subdirs containing workflow.yaml)."""
        for pkg_dir in scan_agent_packages(directory):
            workflow_def = self._load_yaml(pkg_dir / "workflow.yaml")
            self._workflows[workflow_def.name] = HydratedWorkflow(definition=workflow_def)
```

**Step 5: Check __init__.py exports**

Read `pyflow/platform/registry/__init__.py` and remove `scan_directory` if exported.

**Step 6: Run full tests**

Run: `source .venv/bin/activate && pytest -v --tb=short 2>&1 | tail -20`
Expected: All tests pass (528 minus 5 removed = 523 expected).

**Step 7: Commit**

```bash
git add pyflow/platform/registry/discovery.py pyflow/platform/registry/workflow_registry.py tests/platform/registry/test_discovery.py pyflow/platform/registry/__init__.py
git commit -m "chore: remove scan_directory and flat YAML fallback"
```

---

### Task 5: Fix `serve` CLI parameter propagation

**Files:**
- Modify: `pyflow/cli.py:123-134`
- Create: `tests/test_cli_serve.py`

**Step 1: Write the failing test**

Create `tests/test_cli_serve.py`:

```python
from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from pyflow.cli import app

runner = CliRunner()


class TestServeCommand:
    def test_serve_sets_env_vars(self):
        """serve command propagates host/port/workflows-dir via env vars."""
        with patch("pyflow.cli.uvicorn") as mock_uvicorn:
            with patch.dict("os.environ", {}, clear=False) as mock_env:
                result = runner.invoke(
                    app,
                    ["serve", "--host", "127.0.0.1", "--port", "9000", "--workflows-dir", "custom"],
                )
                assert result.exit_code == 0
                mock_uvicorn.run.assert_called_once_with(
                    "pyflow.server:app", host="127.0.0.1", port=9000, reload=False
                )

    def test_serve_defaults(self):
        """serve command uses default host/port when no flags given."""
        with patch("pyflow.cli.uvicorn") as mock_uvicorn:
            result = runner.invoke(app, ["serve"])
            assert result.exit_code == 0
            mock_uvicorn.run.assert_called_once_with(
                "pyflow.server:app", host="0.0.0.0", port=8000, reload=False
            )

    def test_serve_propagates_workflows_dir(self, monkeypatch):
        """serve command sets PYFLOW_WORKFLOWS_DIR env var."""
        captured_env = {}

        def capture_run(*args, **kwargs):
            import os
            captured_env["PYFLOW_WORKFLOWS_DIR"] = os.environ.get("PYFLOW_WORKFLOWS_DIR")
            captured_env["PYFLOW_HOST"] = os.environ.get("PYFLOW_HOST")
            captured_env["PYFLOW_PORT"] = os.environ.get("PYFLOW_PORT")

        with patch("pyflow.cli.uvicorn") as mock_uvicorn:
            mock_uvicorn.run = capture_run
            result = runner.invoke(
                app,
                ["serve", "--host", "10.0.0.1", "--port", "3000", "--workflows-dir", "my_agents"],
            )
            assert result.exit_code == 0
            assert captured_env["PYFLOW_WORKFLOWS_DIR"] == "my_agents"
            assert captured_env["PYFLOW_HOST"] == "10.0.0.1"
            assert captured_env["PYFLOW_PORT"] == "3000"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_cli_serve.py -v`
Expected: `test_serve_propagates_workflows_dir` FAILS because env vars are not set.

**Step 3: Fix serve command**

In `pyflow/cli.py`, update the `serve` command (lines 123-134):

```python
@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Server host"),
    port: int = typer.Option(8000, "--port", "-p", help="Server port"),
    workflows_dir: str = typer.Option(
        "agents", "--workflows-dir", "-w", help="Workflows directory"
    ),
) -> None:
    """Start the FastAPI server."""
    import os

    import uvicorn

    os.environ["PYFLOW_HOST"] = host
    os.environ["PYFLOW_PORT"] = str(port)
    os.environ["PYFLOW_WORKFLOWS_DIR"] = workflows_dir
    uvicorn.run("pyflow.server:app", host=host, port=port, reload=False)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_cli_serve.py -v`
Expected: All 3 tests PASS.

**Step 5: Run full tests**

Run: `source .venv/bin/activate && pytest -v --tb=short 2>&1 | tail -20`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add pyflow/cli.py tests/test_cli_serve.py
git commit -m "fix: serve CLI now propagates host/port/workflows-dir via env vars"
```

---

### Task 6: Fix MetricsPlugin concurrency — runner-per-run

**Files:**
- Modify: `pyflow/platform/executor.py:77-129,154-196,198-217`
- Modify: `pyflow/platform/app.py:123-137`
- Modify: `pyflow/server.py:102-133`
- Modify: `tests/platform/test_app.py:146-164`
- Create: `tests/platform/test_executor_concurrency.py`

This is the largest task. It changes the executor API from `run(runner, ...)` to `run(agent, runtime, ...)`.

**Step 1: Write the concurrency test**

Create `tests/platform/test_executor_concurrency.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock, AsyncMock, patch

from pyflow.platform.executor import WorkflowExecutor
from pyflow.models.workflow import RuntimeConfig


class TestRunnerPerRun:
    async def test_build_runner_called_inside_run(self):
        """run() builds its own runner — no shared runner needed."""
        executor = WorkflowExecutor()
        agent = MagicMock()
        runtime = RuntimeConfig()

        with patch.object(executor, "build_runner") as mock_build:
            mock_runner = MagicMock()
            mock_runner.session_service = MagicMock()
            mock_runner.session_service.create_session = AsyncMock(
                return_value=MagicMock(id="session-1")
            )

            async def empty_gen(*args, **kwargs):
                return
                yield

            mock_runner.run_async = empty_gen
            mock_build.return_value = mock_runner

            await executor.run(agent=agent, runtime=runtime, message="hello")

            mock_build.assert_called_once_with(agent, runtime)

    async def test_metrics_plugin_not_mutated_after_build(self):
        """MetricsPlugin is part of the runner at build time, not injected later."""
        executor = WorkflowExecutor()
        agent = MagicMock()
        runtime = RuntimeConfig()

        runner = executor.build_runner(agent, runtime)

        plugin_names = [p.name for p in runner.plugin_manager.plugins]
        assert "pyflow_metrics" in plugin_names
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/platform/test_executor_concurrency.py -v`
Expected: FAIL — `run()` currently takes `runner`, not `agent`/`runtime`.

**Step 3: Refactor executor — runner-per-run**

In `pyflow/platform/executor.py`:

1. `build_runner()` now includes MetricsPlugin in the plugins list:

```python
    def build_runner(self, agent: BaseAgent, runtime: RuntimeConfig) -> Runner:
        from google.adk.apps import App, ResumabilityConfig
        from google.adk.apps.app import ContextCacheConfig
        from google.adk.apps.compaction import EventsCompactionConfig
        from google.adk.plugins.global_instruction_plugin import GlobalInstructionPlugin

        app_plugins = resolve_plugins(runtime.plugins) or []
        app_plugins.insert(
            0,
            GlobalInstructionPlugin(
                global_instruction="NOW: {current_datetime} ({timezone})."
            ),
        )
        # MetricsPlugin is part of the runner from construction — no mutation needed
        metrics = MetricsPlugin()
        app_plugins.append(metrics)

        app_kwargs: dict = {
            "name": self._app_name,
            "root_agent": agent,
            "plugins": app_plugins,
        }

        if runtime.context_cache_intervals is not None:
            cache_kwargs: dict = {"cache_intervals": runtime.context_cache_intervals}
            if runtime.context_cache_ttl is not None:
                cache_kwargs["ttl_seconds"] = runtime.context_cache_ttl
            if runtime.context_cache_min_tokens is not None:
                cache_kwargs["min_tokens"] = runtime.context_cache_min_tokens
            app_kwargs["context_cache_config"] = ContextCacheConfig(**cache_kwargs)

        if runtime.compaction_interval is not None and runtime.compaction_overlap is not None:
            app_kwargs["events_compaction_config"] = EventsCompactionConfig(
                compaction_interval=runtime.compaction_interval,
                overlap_size=runtime.compaction_overlap,
            )

        if runtime.resumable:
            app_kwargs["resumability_config"] = ResumabilityConfig(is_resumable=True)

        app = App(**app_kwargs)

        return Runner(
            app=app,
            session_service=self._build_session_service(runtime),
            memory_service=self._build_memory_service(runtime),
            artifact_service=self._build_artifact_service(runtime),
            credential_service=self._build_credential_service(runtime),
        )
```

2. `run()` now takes `agent` + `runtime` instead of `runner`:

```python
    def _get_metrics_plugin(self, runner: Runner) -> MetricsPlugin | None:
        """Find the MetricsPlugin from runner's plugin list."""
        for plugin in runner.plugin_manager.plugins:
            if isinstance(plugin, MetricsPlugin):
                return plugin
        return None

    async def run(
        self,
        agent: BaseAgent,
        runtime: RuntimeConfig,
        user_id: str = "default",
        message: str = "",
        session_id: str | None = None,
    ) -> RunResult:
        """Execute a workflow and collect results."""
        runner = self.build_runner(agent, runtime)
        metrics = self._get_metrics_plugin(runner)

        session = await self._get_or_create_session(runner, user_id, session_id)

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
            usage=metrics.summary() if metrics else UsageSummary(),
            session_id=session.id,
        )
```

3. `run_streaming()` same pattern:

```python
    async def run_streaming(
        self,
        agent: BaseAgent,
        runtime: RuntimeConfig,
        user_id: str = "default",
        message: str = "",
        session_id: str | None = None,
    ) -> AsyncGenerator:
        """Yield events as they arrive for streaming APIs."""
        runner = self.build_runner(agent, runtime)
        session = await self._get_or_create_session(runner, user_id, session_id)
        content = types.Content(
            role="user",
            parts=[types.Part(text=message)],
        )

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            yield event
```

**Step 4: Update app.py — pass agent+runtime directly**

In `pyflow/platform/app.py`, update `run_workflow()` (lines 123-137):

```python
    async def run_workflow(
        self,
        name: str,
        input_data: dict,
        user_id: str = "default",
    ) -> RunResult:
        """Execute a workflow by name."""
        self._ensure_booted()
        hw = self.workflows.get(name)
        if hw.agent is None:
            raise RuntimeError(f"Workflow '{name}' not hydrated.")
        message = input_data.get("message", "")
        return await self.executor.run(
            agent=hw.agent, runtime=hw.definition.runtime, user_id=user_id, message=message
        )
```

**Step 5: Update server.py streaming endpoint**

In `pyflow/server.py`, simplify the stream endpoint (lines 102-133):

```python
@app.post("/api/workflows/{name}/stream")
async def stream_workflow(name: str, input_data: WorkflowInput):
    """Stream workflow execution events as server-sent events."""
    platform = _get_platform()
    try:
        hw = platform.workflows.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found")

    if hw.agent is None:
        raise HTTPException(status_code=500, detail=f"Workflow '{name}' not hydrated")

    async def _event_stream():
        async for event in platform.executor.run_streaming(
            agent=hw.agent,
            runtime=hw.definition.runtime,
            user_id=input_data.user_id,
            message=input_data.message,
        ):
            payload = {
                "author": getattr(event, "author", ""),
                "is_final": event.is_final_response(),
            }
            if event.content and event.content.parts:
                payload["content"] = event.content.parts[0].text or ""
            else:
                payload["content"] = ""
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(_event_stream(), media_type="text/event-stream")
```

**Step 6: Update test_app.py delegation test**

In `tests/platform/test_app.py`, update `test_run_workflow_delegates_to_executor` (lines 146-165):

```python
@pytest.mark.asyncio
async def test_run_workflow_delegates_to_executor() -> None:
    p = _make_booted_platform()

    fake_agent = MagicMock()
    fake_hw = MagicMock()
    fake_hw.agent = fake_agent

    p.workflows.get = MagicMock(return_value=fake_hw)
    expected = RunResult(content="done")
    p.executor.run = AsyncMock(return_value=expected)

    result = await p.run_workflow("my_wf", {"message": "hello"})

    p.workflows.get.assert_called_once_with("my_wf")
    p.executor.run.assert_awaited_once_with(
        agent=fake_agent,
        runtime=fake_hw.definition.runtime,
        user_id="default",
        message="hello",
    )
    assert isinstance(result, RunResult)
    assert result.content == "done"
```

**Step 7: Run all tests**

Run: `source .venv/bin/activate && pytest -v --tb=short 2>&1 | tail -30`
Expected: All tests pass.

**Step 8: Commit**

```bash
git add pyflow/platform/executor.py pyflow/platform/app.py pyflow/server.py tests/platform/test_app.py tests/platform/test_executor_concurrency.py
git commit -m "fix: build runner per-run to eliminate MetricsPlugin concurrency issue"
```

---

### Task 7: Add `SqliteSessionService` mapping

**Files:**
- Modify: `pyflow/models/workflow.py:32`
- Modify: `pyflow/platform/executor.py` (in `_build_session_service`)
- Create: `tests/platform/test_executor_sqlite.py`

**Step 1: Write the failing test**

Create `tests/platform/test_executor_sqlite.py`:

```python
from __future__ import annotations

from pyflow.models.workflow import RuntimeConfig
from pyflow.platform.executor import WorkflowExecutor


class TestSqliteSessionService:
    def test_sqlite_uses_dedicated_service(self):
        """'sqlite' maps to SqliteSessionService, not DatabaseSessionService."""
        executor = WorkflowExecutor()
        runtime = RuntimeConfig(session_service="sqlite", session_db_path="test.db")
        service = executor._build_session_service(runtime)

        # Import the expected type
        from google.adk.sessions.sqlite_session_service import SqliteSessionService

        assert isinstance(service, SqliteSessionService)

    def test_sqlite_default_path(self):
        """'sqlite' without session_db_path uses default path."""
        executor = WorkflowExecutor()
        runtime = RuntimeConfig(session_service="sqlite")
        service = executor._build_session_service(runtime)

        from google.adk.sessions.sqlite_session_service import SqliteSessionService

        assert isinstance(service, SqliteSessionService)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/platform/test_executor_sqlite.py -v`
Expected: FAIL — `session_db_path` field doesn't exist on RuntimeConfig.

**Step 3: Add session_db_path to RuntimeConfig**

In `pyflow/models/workflow.py`, add after line 32:

```python
    session_db_path: str | None = None
```

**Step 4: Update _build_session_service in executor.py**

Replace the `case "sqlite"` block:

```python
    def _build_session_service(self, runtime: RuntimeConfig):
        match runtime.session_service:
            case "in_memory":
                return InMemorySessionService()
            case "sqlite":
                path = runtime.session_db_path or "pyflow_sessions.db"
                from google.adk.sessions.sqlite_session_service import SqliteSessionService

                return SqliteSessionService(db_path=path)
            case "database":
                if not runtime.session_db_url:
                    raise ValueError("database session_service requires session_db_url")
                from google.adk.sessions.database_session_service import DatabaseSessionService

                return DatabaseSessionService(db_url=runtime.session_db_url)
```

**Step 5: Run tests**

Run: `source .venv/bin/activate && pytest tests/platform/test_executor_sqlite.py -v`
Expected: All 2 tests PASS.

**Step 6: Run full tests**

Run: `source .venv/bin/activate && pytest -v --tb=short 2>&1 | tail -20`
Expected: All tests pass.

**Step 7: Commit**

```bash
git add pyflow/models/workflow.py pyflow/platform/executor.py tests/platform/test_executor_sqlite.py
git commit -m "feat: map 'sqlite' session_service to ADK SqliteSessionService"
```

---

### Task 8: Add `BigQueryAgentAnalyticsPlugin` to plugin registry

**Files:**
- Modify: `pyflow/platform/plugins.py:10-17`
- Create: `tests/platform/test_plugins_bigquery.py`

**Step 1: Write the failing test**

Create `tests/platform/test_plugins_bigquery.py`:

```python
from __future__ import annotations

from pyflow.platform.plugins import resolve_plugins


class TestBigQueryPlugin:
    def test_bigquery_analytics_resolves(self):
        """'bigquery_analytics' resolves to BigQueryAgentAnalyticsPlugin."""
        from google.adk.plugins.bigquery_agent_analytics_plugin import (
            BigQueryAgentAnalyticsPlugin,
        )

        plugins = resolve_plugins(["bigquery_analytics"])
        assert len(plugins) == 1
        assert isinstance(plugins[0], BigQueryAgentAnalyticsPlugin)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/platform/test_plugins_bigquery.py -v`
Expected: FAIL — `bigquery_analytics` not in `_PLUGIN_FACTORIES`.

Note: `BigQueryAgentAnalyticsPlugin.__init__` requires `project_id` and `dataset_id`. We need to handle this — it can't be a zero-arg lambda. Let's use a default factory that reads from env vars or config.

Update the test:

```python
from __future__ import annotations

import os
from unittest.mock import patch

from pyflow.platform.plugins import resolve_plugins


class TestBigQueryPlugin:
    def test_bigquery_analytics_in_registry(self):
        """'bigquery_analytics' is a known plugin name."""
        from pyflow.platform.plugins import _PLUGIN_FACTORIES

        assert "bigquery_analytics" in _PLUGIN_FACTORIES

    def test_bigquery_analytics_resolves_with_env(self, monkeypatch):
        """'bigquery_analytics' resolves when PYFLOW_BQ_* env vars are set."""
        monkeypatch.setenv("PYFLOW_BQ_PROJECT_ID", "test-project")
        monkeypatch.setenv("PYFLOW_BQ_DATASET_ID", "test-dataset")

        plugins = resolve_plugins(["bigquery_analytics"])
        assert len(plugins) == 1

    def test_bigquery_analytics_skipped_without_env(self):
        """'bigquery_analytics' is skipped when env vars are missing."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PYFLOW_BQ_PROJECT_ID", None)
            os.environ.pop("PYFLOW_BQ_DATASET_ID", None)
            plugins = resolve_plugins(["bigquery_analytics"])
            assert len(plugins) == 0
```

**Step 3: Add BigQuery plugin to registry**

In `pyflow/platform/plugins.py`, add the factory:

```python
import os

def _bigquery_analytics_factory():
    """Create BigQuery analytics plugin from env vars. Returns None if not configured."""
    project_id = os.environ.get("PYFLOW_BQ_PROJECT_ID")
    dataset_id = os.environ.get("PYFLOW_BQ_DATASET_ID")
    if not project_id or not dataset_id:
        return None
    from google.adk.plugins.bigquery_agent_analytics_plugin import (
        BigQueryAgentAnalyticsPlugin,
    )
    return BigQueryAgentAnalyticsPlugin(project_id=project_id, dataset_id=dataset_id)
```

Update `_PLUGIN_FACTORIES` to include it, and update `resolve_plugins` to filter `None` results:

```python
_PLUGIN_FACTORIES: dict[str, Callable] = {
    "logging": lambda: LoggingPlugin(),
    "debug_logging": lambda: DebugLoggingPlugin(),
    "reflect_and_retry": lambda: ReflectAndRetryToolPlugin(),
    "context_filter": lambda: ContextFilterPlugin(),
    "save_files_as_artifacts": lambda: SaveFilesAsArtifactsPlugin(),
    "multimodal_tool_results": lambda: MultimodalToolResultsPlugin(),
    "bigquery_analytics": _bigquery_analytics_factory,
}


def resolve_plugins(names: list[str]) -> list:
    """Resolve plugin names to ADK plugin instances. Unknown/unconfigured names are skipped."""
    plugins = []
    for name in names:
        if name in _PLUGIN_FACTORIES:
            plugin = _PLUGIN_FACTORIES[name]()
            if plugin is not None:
                plugins.append(plugin)
    return plugins
```

**Step 4: Run tests**

Run: `source .venv/bin/activate && pytest tests/platform/test_plugins_bigquery.py tests/platform/test_plugins.py -v`
Expected: All pass.

**Step 5: Commit**

```bash
git add pyflow/platform/plugins.py tests/platform/test_plugins_bigquery.py
git commit -m "feat: add BigQueryAgentAnalyticsPlugin to plugin registry"
```

---

### Task 9: Add MCP Tools support in YAML

**Files:**
- Modify: `pyflow/models/workflow.py` — add `McpServerConfig` model and `mcp_servers` field to `RuntimeConfig`
- Modify: `pyflow/platform/hydration/hydrator.py` — resolve MCP tools during hydration
- Modify: `pyflow/platform/app.py` — manage MCP lifecycle (connect/disconnect)
- Create: `tests/platform/test_mcp_tools.py`

**Step 1: Write tests for the config model**

Create `tests/platform/test_mcp_tools.py`:

```python
from __future__ import annotations

from pyflow.models.workflow import McpServerConfig, RuntimeConfig


class TestMcpServerConfig:
    def test_sse_config(self):
        config = McpServerConfig(uri="http://localhost:3000/sse", transport="sse")
        assert config.uri == "http://localhost:3000/sse"
        assert config.transport == "sse"

    def test_stdio_config(self):
        config = McpServerConfig(
            command="npx", args=["-y", "@mcp/server-filesystem", "/tmp"], transport="stdio"
        )
        assert config.command == "npx"
        assert config.transport == "stdio"

    def test_runtime_config_with_mcp(self):
        runtime = RuntimeConfig(
            mcp_servers=[
                McpServerConfig(uri="http://localhost:3000/sse", transport="sse"),
            ]
        )
        assert len(runtime.mcp_servers) == 1

    def test_runtime_config_default_empty(self):
        runtime = RuntimeConfig()
        assert runtime.mcp_servers == []
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/platform/test_mcp_tools.py::TestMcpServerConfig -v`
Expected: FAIL — `McpServerConfig` not defined.

**Step 3: Add McpServerConfig model**

In `pyflow/models/workflow.py`, before `RuntimeConfig`:

```python
class McpServerConfig(BaseModel):
    """Configuration for an MCP server connection."""

    transport: Literal["sse", "stdio"]
    # SSE transport
    uri: str | None = None
    headers: dict[str, str] | None = None
    # Stdio transport
    command: str | None = None
    args: list[str] = []
    env: dict[str, str] | None = None
```

Add `mcp_servers` field to `RuntimeConfig`:

```python
    mcp_servers: list[McpServerConfig] = []
```

**Step 4: Run config tests**

Run: `source .venv/bin/activate && pytest tests/platform/test_mcp_tools.py::TestMcpServerConfig -v`
Expected: All 4 tests PASS.

**Step 5: Write test for MCP tool resolution**

Add to `tests/platform/test_mcp_tools.py`:

```python
class TestMcpToolResolution:
    def test_mcp_server_config_to_connection_params_sse(self):
        """SSE config converts to SseConnectionParams."""
        from pyflow.platform.hydration.hydrator import _mcp_config_to_params

        config = McpServerConfig(uri="http://localhost:3000/sse", transport="sse")
        params = _mcp_config_to_params(config)

        from google.adk.tools.mcp_tool.mcp_toolset import SseConnectionParams

        assert isinstance(params, SseConnectionParams)

    def test_mcp_server_config_to_connection_params_stdio(self):
        """Stdio config converts to StdioServerParameters."""
        from pyflow.platform.hydration.hydrator import _mcp_config_to_params

        config = McpServerConfig(command="npx", args=["-y", "server"], transport="stdio")
        params = _mcp_config_to_params(config)

        from mcp import StdioServerParameters

        assert isinstance(params, StdioServerParameters)
```

**Step 6: Implement _mcp_config_to_params in hydrator.py**

Add to `pyflow/platform/hydration/hydrator.py`:

```python
def _mcp_config_to_params(config):
    """Convert McpServerConfig to ADK connection params."""
    from pyflow.models.workflow import McpServerConfig

    if config.transport == "sse":
        from google.adk.tools.mcp_tool.mcp_toolset import SseConnectionParams

        kwargs = {"url": config.uri}
        if config.headers:
            kwargs["headers"] = config.headers
        return SseConnectionParams(**kwargs)
    elif config.transport == "stdio":
        from mcp import StdioServerParameters

        kwargs = {"command": config.command, "args": config.args}
        if config.env:
            kwargs["env"] = config.env
        return StdioServerParameters(**kwargs)
    else:
        raise ValueError(f"Unknown MCP transport: {config.transport}")
```

**Step 7: Run tests**

Run: `source .venv/bin/activate && pytest tests/platform/test_mcp_tools.py -v`
Expected: All tests pass.

**Step 8: Commit**

```bash
git add pyflow/models/workflow.py pyflow/platform/hydration/hydrator.py tests/platform/test_mcp_tools.py
git commit -m "feat: add MCP tools support in workflow YAML (config + params conversion)"
```

Note: Full MCP lifecycle integration (connecting at boot, getting tools, closing on shutdown) should be a follow-up task once the config and conversion layer is tested. The McpToolset.get_tools() is async and requires running MCP servers — integration testing requires a separate strategy.

---

### Task 10: Add OpenAPI Tools support in YAML

**Files:**
- Modify: `pyflow/models/workflow.py` — add `OpenApiToolConfig` model and `openapi_tools` field to `RuntimeConfig`
- Create: `tests/platform/test_openapi_tools.py`

**Step 1: Write config model tests**

Create `tests/platform/test_openapi_tools.py`:

```python
from __future__ import annotations

from pyflow.models.workflow import OpenApiToolConfig, RuntimeConfig


class TestOpenApiToolConfig:
    def test_basic_config(self):
        config = OpenApiToolConfig(spec="specs/petstore.yaml")
        assert config.spec == "specs/petstore.yaml"
        assert config.name_prefix is None

    def test_config_with_prefix(self):
        config = OpenApiToolConfig(spec="specs/ynab.yaml", name_prefix="ynab")
        assert config.name_prefix == "ynab"

    def test_runtime_config_with_openapi(self):
        runtime = RuntimeConfig(
            openapi_tools=[
                OpenApiToolConfig(spec="specs/petstore.yaml", name_prefix="pet"),
            ]
        )
        assert len(runtime.openapi_tools) == 1

    def test_runtime_config_default_empty(self):
        runtime = RuntimeConfig()
        assert runtime.openapi_tools == []
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/platform/test_openapi_tools.py -v`
Expected: FAIL — `OpenApiToolConfig` not defined.

**Step 3: Add OpenApiToolConfig model**

In `pyflow/models/workflow.py`, before `RuntimeConfig`:

```python
class OpenApiToolConfig(BaseModel):
    """Configuration for auto-generating tools from an OpenAPI spec."""

    spec: str  # Path to OpenAPI spec file (YAML or JSON)
    name_prefix: str | None = None
```

Add `openapi_tools` field to `RuntimeConfig`:

```python
    openapi_tools: list[OpenApiToolConfig] = []
```

**Step 4: Run tests**

Run: `source .venv/bin/activate && pytest tests/platform/test_openapi_tools.py -v`
Expected: All 4 tests PASS.

**Step 5: Run full tests**

Run: `source .venv/bin/activate && pytest -v --tb=short 2>&1 | tail -20`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add pyflow/models/workflow.py tests/platform/test_openapi_tools.py
git commit -m "feat: add OpenAPI tools config model for workflow YAML"
```

Note: Like MCP, the actual OpenAPIToolset integration (loading spec files, generating RestApiTool instances) should be a follow-up task. The config model is the foundation.

---

### Task 11: Add OpenTelemetry config

**Files:**
- Modify: `pyflow/models/platform.py` — add telemetry fields
- Create: `tests/platform/test_telemetry_config.py`

**Step 1: Write the failing test**

Create `tests/platform/test_telemetry_config.py`:

```python
from __future__ import annotations

from pyflow.models.platform import PlatformConfig


class TestTelemetryConfig:
    def test_telemetry_disabled_by_default(self):
        config = PlatformConfig()
        assert config.telemetry_enabled is False

    def test_telemetry_export_default(self):
        config = PlatformConfig()
        assert config.telemetry_export == "console"

    def test_telemetry_enabled_via_constructor(self):
        config = PlatformConfig(telemetry_enabled=True, telemetry_export="otlp")
        assert config.telemetry_enabled is True
        assert config.telemetry_export == "otlp"

    def test_telemetry_enabled_via_env(self, monkeypatch):
        monkeypatch.setenv("PYFLOW_TELEMETRY_ENABLED", "true")
        monkeypatch.setenv("PYFLOW_TELEMETRY_EXPORT", "gcp")
        config = PlatformConfig()
        assert config.telemetry_enabled is True
        assert config.telemetry_export == "gcp"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/platform/test_telemetry_config.py -v`
Expected: FAIL — `telemetry_enabled` field doesn't exist.

**Step 3: Add telemetry fields to PlatformConfig**

In `pyflow/models/platform.py`, add:

```python
    telemetry_enabled: bool = False
    telemetry_export: Literal["console", "otlp", "gcp"] = "console"
```

Update the `Literal` import to include these values (already imported for `log_level`).

**Step 4: Run tests**

Run: `source .venv/bin/activate && pytest tests/platform/test_telemetry_config.py -v`
Expected: All 4 tests PASS.

**Step 5: Run full tests**

Run: `source .venv/bin/activate && pytest -v --tb=short 2>&1 | tail -20`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add pyflow/models/platform.py tests/platform/test_telemetry_config.py
git commit -m "feat: add OpenTelemetry config to PlatformConfig (opt-in)"
```

---

### Task 12: Add evaluation framework documentation

**Files:**
- Create: `docs/evaluation.md`

**Step 1: Write evaluation guide**

Create `docs/evaluation.md` documenting how to use `adk eval` with PyFlow agent packages:

```markdown
# Agent Evaluation

PyFlow agent packages are compatible with ADK's evaluation framework out of the box.

## Using `adk eval`

Each agent package exports `root_agent` via `__init__.py`, making it compatible with `adk eval`.

### Create test cases

Create a `.test.json` file in your agent package:

```json
[
  {
    "name": "basic_query",
    "input": "What is the exchange rate for USD to COP?",
    "expected_tool_use": ["http_request"],
    "expected_output_keywords": ["exchange", "rate"]
  }
]
```

### Run evaluation

```bash
adk eval agents/exchange_tracker/
```

### Evaluation types

- **Trajectory evaluation**: Verifies the agent uses the expected tools in the expected order
- **Response evaluation**: Checks final answer quality (keyword matching, LLM-as-judge)
- **Safety evaluation**: Runs safety checks on agent outputs

## Future: `pyflow eval`

A future `pyflow eval` command will wrap `adk eval` with PyFlow-specific features like workflow-level evaluation and multi-agent pipeline testing.
```

**Step 2: Commit**

```bash
git add docs/evaluation.md
git commit -m "docs: add evaluation framework guide for adk eval compatibility"
```

---

### Task 13: Update `docs/adk-alignment.md`

**Files:**
- Modify: `docs/adk-alignment.md`

**Step 1: Update the document**

Rewrite `docs/adk-alignment.md` to reflect:
- Plugins: 6 → 7 (add BigQuery analytics)
- New integrations: MCP tools, OpenAPI tools, OpenTelemetry config
- New session service: SqliteSessionService
- Add "ADK Features Intentionally Not Used" section:
  - `to_a2a()` — experimental, requires `a2a-sdk`, single-agent only
  - `get_fast_api_app()` — assumes filesystem AgentLoader, no pre-hydrated workflow support
  - `Agent Config YAML` — experimental, Gemini-only, LlmAgent-only
- Update the "ADK Features Used" table

**Step 2: Commit**

```bash
git add docs/adk-alignment.md
git commit -m "docs: update adk-alignment.md with new integrations and rationale"
```

---

### Task 14: Update `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update CLAUDE.md**

Changes to make:
- Remove `tools_dir` from PlatformConfig description
- Remove `jinja2` from dependencies list
- Bump `google-adk>=1.26` in dependencies
- Add `SqliteSessionService` to session service options
- Add `BigQueryAgentAnalyticsPlugin` to plugin list (7 plugins now)
- Add `mcp_servers` and `openapi_tools` to RuntimeConfig description
- Add `telemetry_enabled`/`telemetry_export` to PlatformConfig description
- Add `McpServerConfig`/`OpenApiToolConfig` to models
- Add `session_db_path` to RuntimeConfig fields
- Update test count
- Add `docs/evaluation.md` to docs list

**Step 2: Run full test suite to confirm final count**

Run: `source .venv/bin/activate && pytest -v --tb=short 2>&1 | tail -5`
Record actual test count for CLAUDE.md.

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md to reflect ADK alignment cleanup"
```

---

## Execution Order Summary

| Task | Type | Est. Complexity |
|------|------|----------------|
| 1. Remove jinja2 | Dead code | Trivial |
| 2. Remove tools_dir | Dead code | Trivial |
| 3. Remove WorkflowInput.data | Dead code | Small (test updates) |
| 4. Remove scan_directory | Dead code | Small (test updates) |
| 5. Fix serve CLI | Bug fix | Small |
| 6. Fix MetricsPlugin concurrency | Bug fix | Medium (API change) |
| 7. SqliteSessionService | ADK integration | Small |
| 8. BigQuery plugin | ADK integration | Small |
| 9. MCP tools config | ADK integration | Medium |
| 10. OpenAPI tools config | ADK integration | Small |
| 11. OpenTelemetry config | ADK integration | Small |
| 12. Evaluation docs | Documentation | Trivial |
| 13. Update adk-alignment.md | Documentation | Small |
| 14. Update CLAUDE.md | Documentation | Small |

Tasks 1-4 are independent. Tasks 5-6 are independent. Tasks 7-11 are independent. Tasks 12-14 depend on all prior tasks completing.
