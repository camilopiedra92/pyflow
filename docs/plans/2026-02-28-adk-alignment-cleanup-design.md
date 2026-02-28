# ADK Alignment Cleanup — Design

**Date:** 2026-02-28
**Status:** Approved

## Problem

PyFlow assessment against Google ADK 1.26 revealed dead code, bugs, legacy patterns, and unused ADK features. This design addresses all findings while preserving PyFlow's genuine architectural value (multi-workflow server, custom agents, YAML workflow system, A2A routing).

### Validation Findings

Key findings from validating the assessment against actual code:

| Assessment claimed | Reality verified |
|---|---|
| "Replace A2A with `to_a2a()`" | `to_a2a()` is `@a2a_experimental`, requires uninstalled `a2a-sdk`, single-agent only — PyFlow's multi-workflow A2A is the correct choice |
| "Use `get_fast_api_app()` as server base" | Assumes filesystem `AgentLoader`, no support for pre-hydrated workflows — more work to adopt than maintain custom server |
| "`scan_directory()` is legacy" | Has tests but architecture committed to agent packages — backward-compat serves no purpose |

## Design

### Section 1: Dead Code Removal

| Item | File | Evidence | Action |
|---|---|---|---|
| `jinja2>=3.1` | `pyproject.toml:11` | Zero imports in entire source. Original plan used Jinja2 for templates but ToolAgent uses regex `{key}` pattern | Remove from dependencies |
| `PlatformConfig.tools_dir` | `models/platform.py:23` | `ToolRegistry.discover()` imports `pyflow.tools` directly via `__init_subclass__`. Field never read by any module | Remove field, update tests |
| `WorkflowInput.data` | `server.py:81` | Accepted in endpoint but `platform.run_workflow()` only reads `message` via `input_data.get("message", "")`. Silently discarded | Remove field from model |
| `scan_directory()` | `registry/discovery.py:20-28` | Architecture committed to agent packages. Flat YAML fallback in `WorkflowRegistry.discover()` never executes when packages exist | Remove function, remove fallback branch, remove import, remove tests |

### Section 2: Bug Fixes

#### 2.1 `serve` CLI ignores parameters

**Problem:** `cli.py:134` — `serve` accepts `--host`, `--port`, `--workflows-dir` but server creates its own `PlatformConfig()` from env vars, ignoring CLI args.

**Fix:** Set env vars `PYFLOW_HOST`, `PYFLOW_PORT`, `PYFLOW_WORKFLOWS_DIR` before `uvicorn.run()`. `PlatformConfig(BaseSettings)` reads them automatically via `env_prefix="PYFLOW_"`.

```python
@app.command()
def serve(host, port, workflows_dir):
    import os, uvicorn
    os.environ["PYFLOW_HOST"] = host
    os.environ["PYFLOW_PORT"] = str(port)
    os.environ["PYFLOW_WORKFLOWS_DIR"] = workflows_dir
    uvicorn.run("pyflow.server:app", host=host, port=port, reload=False)
```

#### 2.2 MetricsPlugin concurrency

**Problem:** `executor.py:163` — `MetricsPlugin` injected/removed from shared `runner.plugin_manager.plugins` list. Concurrent requests on same runner corrupt metrics.

**Fix:** Build a new Runner per `run()` call instead of sharing one. `build_runner()` is cheap (no I/O, just object construction). Caller passes `(agent, runtime)` instead of pre-built runner.

**Changes:**
- `executor.run(agent, runtime, ...)` instead of `executor.run(runner, ...)`
- `executor.run_streaming(agent, runtime, ...)` same pattern
- `MetricsPlugin` added at Runner construction in `build_runner()`, not mutated after
- `server.py` stream endpoint simplified (no longer builds its own runner)
- `app.py:run_workflow()` passes agent + runtime directly

### Section 3: ADK Feature Integration

#### 3.1 SqliteSessionService

**Current:** `"sqlite"` maps to `DatabaseSessionService(db_url="sqlite+aiosqlite:///...")` — requires SQLAlchemy URL format.

**Fix:** Map `"sqlite"` to `SqliteSessionService(db_path=...)`. Add `session_db_path: str | None` to `RuntimeConfig`. Keep `"database"` for PostgreSQL/MySQL.

#### 3.2 BigQueryAgentAnalyticsPlugin

**Current:** `plugins.py` registers 6 of 8 ADK plugins. Missing BigQuery analytics.

**Fix:** Add `"bigquery_analytics"` to `_PLUGIN_FACTORIES` dict. Lazy import like others.

#### 3.3 MCP Tools in YAML

**Current:** No way to use MCP server tools in workflows.

**Fix:** Add `mcp_servers` field to `RuntimeConfig`:

```yaml
runtime:
  mcp_servers:
    - uri: "http://localhost:3000/sse"
      transport: sse
    - command: "npx -y @modelcontextprotocol/server-filesystem /tmp"
      transport: stdio
```

`WorkflowHydrator` connects to MCP servers during hydration, discovers tools, and makes them available by name in `tools:` references. Connection lifecycle managed by `PyFlowPlatform.boot()/shutdown()`.

#### 3.4 OpenAPI Tools in YAML

**Current:** API tools implemented manually (e.g., YnabTool with 19 hardcoded routes).

**Fix:** Add support for OpenAPI spec references in tool config:

```yaml
runtime:
  openapi_tools:
    - spec: "specs/petstore.yaml"
      name_prefix: "petstore"
```

`OpenAPIToolset` generates `RestApiTool` instances registered by name. Does not replace existing manual tools (which have custom auth logic).

#### 3.5 OpenTelemetry

**Current:** structlog-based logging in MetricsPlugin. No distributed tracing.

**Fix:** Add opt-in telemetry config to `PlatformConfig`:

```python
telemetry_enabled: bool = False
telemetry_export: Literal["console", "otlp", "gcp"] = "console"
```

When enabled, configure OpenTelemetry exporters that ADK uses internally. Complements (does not replace) MetricsPlugin.

#### 3.6 Evaluation Framework

**Current:** 528 unit/integration tests but no agent quality evaluation.

**Fix Phase 1:** Document how to use `adk eval` directly with PyFlow agent packages (already compatible via `root_agent` convention).

**Fix Phase 2:** Add `pyflow eval` CLI command as wrapper with PyFlow-specific test case format.

### Section 4: Documentation Updates

| File | Changes |
|---|---|
| `docs/adk-alignment.md` | Add plugins count update, new integrations (MCP, OpenAPI, OTEL), add "ADK Features Intentionally Not Used" section with rationale for not using `to_a2a()` and `get_fast_api_app()` |
| `CLAUDE.md` | Remove `tools_dir` mention, add new features, update dependency list (remove jinja2), update test count |
| `pyproject.toml` | Remove `jinja2>=3.1`, bump to `google-adk>=1.26`, add optional deps for MCP/OpenAPI if needed |

## Files Affected

### Dead Code Removal
- `pyproject.toml` — remove jinja2
- `pyflow/models/platform.py` — remove tools_dir field
- `pyflow/server.py` — remove WorkflowInput.data field
- `pyflow/platform/registry/discovery.py` — remove scan_directory()
- `pyflow/platform/registry/workflow_registry.py` — remove flat YAML fallback + import
- `tests/models/test_platform.py` — update tools_dir tests
- `tests/platform/registry/test_discovery.py` — remove scan_directory tests

### Bug Fixes
- `pyflow/cli.py` — fix serve to propagate env vars
- `pyflow/platform/executor.py` — runner-per-run, remove plugin mutation
- `pyflow/platform/app.py` — pass agent+runtime instead of runner
- `pyflow/server.py` — simplify stream endpoint
- `tests/` — update executor/server test signatures

### ADK Integration
- `pyflow/platform/executor.py` — SqliteSessionService mapping
- `pyflow/models/workflow.py` — RuntimeConfig new fields (session_db_path, mcp_servers, openapi_tools)
- `pyflow/platform/plugins.py` — add BigQuery analytics
- `pyflow/platform/registry/tool_registry.py` — MCP + OpenAPI tool resolution
- `pyflow/platform/hydration/hydrator.py` — MCP + OpenAPI tool hydration
- `pyflow/platform/app.py` — MCP lifecycle (connect on boot, disconnect on shutdown)
- `pyflow/models/platform.py` — telemetry config fields
- `pyflow/cli.py` — eval command (phase 2)
- New tests for all new features

### Documentation
- `docs/adk-alignment.md` — full update
- `CLAUDE.md` — reflect changes
- `pyproject.toml` — deps update

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Keep custom A2A | Yes | ADK's `to_a2a()` is `@a2a_experimental`, requires `a2a-sdk`, single-agent only. PyFlow's multi-workflow routing has no ADK equivalent |
| Keep custom server | Yes | ADK's `get_fast_api_app()` assumes filesystem `AgentLoader`, doesn't support pre-hydrated workflows. PyFlow's server is simpler and more focused |
| Keep custom .env loading | Yes | PyFlow needs control over timing (before secrets injection). ADK's internal loading doesn't cover PyFlow's boot sequence |
| Remove flat YAML fallback | Yes | Architecture committed to agent packages. No backward-compat needed for a pattern no one uses |
| Runner-per-run | Yes | Eliminates shared mutable state. `build_runner()` is cheap (object construction only) |
| MCP as RuntimeConfig | Yes | Follows PyFlow's declarative YAML pattern. Connections managed by platform lifecycle |
| OpenTelemetry opt-in | Yes | Don't break existing structlog workflow. OTEL adds distributed tracing, doesn't replace per-run metrics |
