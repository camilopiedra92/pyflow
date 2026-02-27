# PyFlow

Config-driven workflow automation engine with AI-powered nodes. Define workflows in YAML, execute as async DAGs.

## Features

- **Async DAG Engine** — Topological sort, parallel execution, retry with exponential backoff
- **7 Built-in Nodes** — HTTP, Transform (JSONPath), Condition, Alert, Storage, LLM
- **Multi-Provider AI** — Google Gemini, Anthropic Claude, OpenAI GPT via unified `llm` node
- **Fully Typed** — Pydantic v2 models for all configs, responses, and workflow definitions
- **Secure** — AST-validated eval, Jinja2 sandbox, SSRF protection, API key auth
- **Headless API** — FastAPI server with REST endpoints and webhook triggers
- **164 Tests** — Comprehensive test suite with mocked providers

## Quickstart

```bash
# Install
pip install -e ".[dev]"

# Run a workflow
pyflow run workflows/example.yaml

# Start the server
pyflow serve

# Validate a workflow
pyflow validate workflows/exchange_rate_tracker.yaml
```

## Example Workflow

```yaml
name: exchange-rate-tracker
description: Monitors USDCOP and alerts on significant changes
trigger:
  type: schedule
  config:
    cron: "0 * * * *"

nodes:
  - id: fetch_rate
    type: http
    config:
      url: "https://open.er-api.com/v6/latest/USD"
      timeout: 15

  - id: extract_cop
    type: transform
    depends_on: [fetch_rate]
    config:
      input: "{{ fetch_rate }}"
      expression: "$.body.rates.COP"

  - id: check_change
    type: condition
    depends_on: [extract_cop]
    config:
      if: "extract_cop > 4000"

  - id: notify
    type: alert
    depends_on: [check_change]
    when: "check_change == True"
    config:
      webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK"
      message: "USDCOP is now {{ extract_cop }}"
```

## AI-Powered Workflows

```yaml
- id: classify
  type: llm
  config:
    provider: google          # google | anthropic | openai
    model: gemini-2.0-flash
    prompt: "Classify this ticket: {{ ticket.body }}"
    output_format: json
```

Install AI providers:
```bash
pip install -e ".[ai]"  # google-genai, anthropic, openai
```

## Node Types

| Node | Type | Description |
|------|------|-------------|
| HTTP | `http` | Make HTTP requests (GET, POST, etc.) with timeout and SSRF protection |
| Transform | `transform` | Extract/transform data using JSONPath expressions |
| Condition | `condition` | Evaluate boolean expressions with safe eval |
| Alert | `alert` | Send webhook notifications (Slack, Discord, Teams) |
| Storage | `storage` | Read/write/append JSON to local files |
| LLM | `llm` | Multi-provider AI (Google, Anthropic, OpenAI) |

## Architecture

```
pyflow/
  core/
    engine.py       — Async DAG executor (topological sort, parallel, retry)
    models.py       — Pydantic models: WorkflowDef, NodeDef, TriggerDef
    context.py      — ExecutionContext (node results/errors per run)
    template.py     — Jinja2 sandboxed template resolution
    safe_eval.py    — AST-validated expression evaluation
    loader.py       — YAML workflow loader
    node.py         — BaseNode[TConfig, TResponse] ABC + NodeRegistry
  nodes/
    schemas.py      — Pydantic config/response models for all nodes
    http.py         — HTTP requests (httpx, SSRF protection)
    transform.py    — JSONPath transforms (jsonpath-ng)
    condition.py    — Boolean conditions (safe eval)
    alert.py        — Webhook alerts
    storage.py      — JSON file storage
    llm.py          — Multi-provider LLM node
  ai/
    base.py         — LLMConfig, LLMResponse, BaseLLMProvider
    providers/      — Google, Anthropic, OpenAI implementations
  server.py         — FastAPI server with auth middleware
  cli.py            — Typer CLI (run, validate, list, serve)
```

## Security

- **Safe eval** — AST-validated expressions block `__import__`, `exec`, dunder access
- **Jinja2 sandbox** — `SandboxedEnvironment` prevents template injection
- **SSRF protection** — Blocks requests to private/internal IP ranges
- **API key auth** — Optional `PYFLOW_API_KEY` for server endpoints
- **No secret leaks** — Internal errors return generic messages to clients

## Development

```bash
# Setup
python -m venv .venv
source .venv/Scripts/activate  # Windows
pip install -e ".[dev]"

# Run tests
pytest -v

# Lint
ruff check .
ruff format .
```

## Tech Stack

Python 3.12 | FastAPI | Pydantic v2 | httpx | Jinja2 | jsonpath-ng | structlog | APScheduler | typer

## License

MIT
