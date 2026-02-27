# PyFlow — Workflow Automation Engine

Config-driven workflow automation platform in Python, inspired by N8N. Workflows are defined in YAML, executed as async DAGs, with both CLI and service modes.

## Architecture

```
pyflow/
├── core/
│   ├── engine.py        # Workflow executor (async DAG runner)
│   ├── workflow.py      # Workflow model (parsed from YAML)
│   ├── node.py          # Base node + registry
│   └── context.py       # Shared execution context between nodes
├── nodes/               # Built-in node types
│   ├── http.py          # HTTP request node
│   ├── transform.py     # Data transformation (jq-like)
│   ├── condition.py     # If/else branching
│   └── webhook.py       # Webhook trigger
├── triggers/
│   ├── schedule.py      # Cron/interval triggers (APScheduler)
│   └── webhook.py       # HTTP webhook listener
├── cli.py               # CLI entry point (typer)
├── server.py            # Service mode (FastAPI)
└── config.py            # App configuration
workflows/               # User-defined YAML workflows
```

Each workflow is a DAG of nodes. The engine resolves dependencies and runs nodes concurrently via asyncio.

## Workflow Definition (YAML)

```yaml
name: notify-on-new-issue
description: Watch GitHub and notify Slack

trigger:
  type: webhook
  path: /github/issues

nodes:
  - id: extract
    type: transform
    config:
      expression: "$.body.issue"

  - id: check-label
    type: condition
    depends_on: [extract]
    config:
      if: "$.labels[?(@.name == 'bug')]"

  - id: notify-slack
    type: http
    depends_on: [check-label]
    when: "check-label.result == true"
    config:
      method: POST
      url: "https://hooks.slack.com/..."
      body:
        text: "New bug: {{ extract.result.title }}"
```

Key concepts:
- `trigger` — what starts the workflow (webhook, cron, manual)
- `nodes` — list of steps, each with a `type` from the node registry
- `depends_on` — defines the DAG (which nodes must complete first)
- `when` — optional condition to execute a node
- `{{ }}` — Jinja2 template expressions referencing previous node outputs

## Data Flow

Each node receives a `context` with results from all completed predecessor nodes. Output is stored as `context[node_id]`. Template expressions `{{ node_id.result.field }}` are resolved before each node executes.

## Error Handling

Each node can define `on_error: skip | stop | retry`:
- `skip` — log error, continue workflow
- `stop` — halt the entire workflow
- `retry` — retry with exponential backoff

```yaml
  - id: call-api
    type: http
    config:
      url: "https://api.example.com/data"
    on_error: retry
    retry:
      max_retries: 3
      delay: 2  # seconds, doubles each retry
```

Structured logging via `structlog`. Each execution gets a unique `run_id`.

## CLI & Service Mode

**CLI** (typer):
- `pyflow run <workflow.yaml>` — execute a workflow manually
- `pyflow validate <workflow.yaml>` — validate syntax
- `pyflow list` — list available workflows

**Service mode** (FastAPI):
- `pyflow serve` — start server, activate schedulers and webhook listeners
- `POST /trigger/{workflow}` — trigger a workflow via API
- `GET /status/{run_id}` — check execution status

## Tech Stack

| Component | Library |
|-----------|---------|
| Async runtime | asyncio (stdlib) |
| Scheduling | apscheduler |
| HTTP server | fastapi + uvicorn |
| HTTP client | httpx |
| CLI | typer |
| YAML parsing | pyyaml |
| Template expressions | jinja2 |
| JSONPath | jsonpath-ng |
| Logging | structlog |
| Validation | pydantic |

## Decisions

- **Approach chosen:** Lightweight asyncio over Celery-based or Prefect-inspired
- **Rationale:** Full control, minimal dependencies, appropriate for MVP
- **Execution model:** Both CLI (on-demand) and service (long-running daemon)
- **Config format:** YAML over JSON for readability
