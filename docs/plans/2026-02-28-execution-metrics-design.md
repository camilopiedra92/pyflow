# Execution Metrics & Observability

## Problem

PyFlow workflows execute through ADK but expose no execution metadata. `RunResult` has an opaque `usage_metadata: Any` field that goes unused. The streaming endpoint sends zero metadata per event. Debugging requires manually iterating events and extracting fields from ADK objects.

## Design Philosophy

ADK already provides comprehensive observability infrastructure:
- **OpenTelemetry spans** for `invoke_agent`, `generate_content`, `execute_tool` with tokens, model, latency
- **Plugin callback system** with `before/after` hooks for model calls, tool calls, agent runs, and events
- **SQLite span exporter** for local debugging
- **OTLP exporters** for production backends (Datadog, Grafana, Jaeger)

We should not reinvent any of this. Instead, we add a thin layer that:
1. **Collects aggregate metrics** via an ADK Plugin (always-on, cheap)
2. **Exposes them in `RunResult`** and API responses
3. **Delegates detailed tracing to OTEL** (ADK already instruments everything)

## Data Model

### UsageSummary

```python
class UsageSummary(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
    duration_ms: int = 0
    steps: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    model: str | None = None
```

### RunResult (updated)

```python
class RunResult(BaseModel):
    content: str = ""
    author: str = ""
    usage: UsageSummary | None = None   # replaces usage_metadata: Any
    session_id: str | None = None
```

## MetricsPlugin

An ADK `BasePlugin` subclass that accumulates metrics during execution:

| Callback | Action |
|----------|--------|
| `before_run_callback` | Record start time |
| `after_model_callback` | Accumulate tokens from `llm_response.usage_metadata`, record model name, increment `llm_calls` |
| `before_tool_callback` | Increment `tool_calls` |
| `on_event_callback` | Increment `steps` |
| `after_run_callback` | Calculate `duration_ms` from start time |

The plugin exposes a `summary() -> UsageSummary` method that the executor reads after the run completes.

**Important:** MetricsPlugin is always injected by the executor — not configured per workflow. It is invisible to workflow authors.

## Integration Points

### Executor (`executor.py`)
- Creates a fresh `MetricsPlugin` per `run()` call
- Injects it into the Runner's plugin list
- After run completes, calls `plugin.summary()` to build `UsageSummary`
- Attaches it to `RunResult.usage`

### Server (`server.py`)
- `WorkflowRunResponse` already includes `RunResult` — usage comes for free
- Streaming endpoint adds `tokens` and `step_type` to SSE events via `on_event_callback` data

### CLI (`cli.py`)
- `pyflow run` prints usage summary after the result

### OTEL Setup (optional, via env vars)
- If `OTEL_EXPORTER_OTLP_ENDPOINT` is set, ADK auto-configures OTLP exporters (no PyFlow code needed)
- For local dev, `SqliteSpanExporter` can be configured via `runtime.plugins: [trace_sqlite]`
- PyFlow just calls `maybe_set_otel_providers()` during boot if OTEL env vars are present

## What We Don't Do (YAGNI)

- **No trace list in RunResult** — detailed traces belong in OTEL, not API responses
- **No `include_trace` parameter** — clean separation: aggregates in responses, details in OTEL
- **No structlog per-step logging** — OTEL logs already cover this
- **No cost calculation** — depends on model pricing which changes; consumers calculate from tokens
- **No custom span creation** — ADK already creates spans for everything we care about

## Files Changed

| File | Change |
|------|--------|
| `pyflow/models/runner.py` | Add `UsageSummary`, replace `usage_metadata: Any` with `usage: UsageSummary \| None` |
| `pyflow/platform/metrics_plugin.py` | New: `MetricsPlugin(BasePlugin)` |
| `pyflow/platform/executor.py` | Inject `MetricsPlugin`, extract `UsageSummary` after run |
| `pyflow/server.py` | Add step metadata to SSE events |
| `pyflow/cli.py` | Print usage summary |
| `tests/` | Tests for MetricsPlugin, updated RunResult tests, executor integration |
