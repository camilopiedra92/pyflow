# PyFlow

Agent platform powered by Google ADK. Define multi-agent workflows in YAML, auto-hydrated into ADK agent trees with self-registering tools and A2A protocol support.

## Features

- **Google ADK Runtime** -- Workflows become ADK agent trees (Sequential, Parallel, Loop)
- **Self-Registering Tools** -- Inherit `BasePlatformTool` to auto-register; no decorators needed
- **6 Built-in Tools** -- HTTP requests, JSONPath transforms, conditions, alerts, file storage, YNAB budget API
- **Multi-Model Support** -- Gemini native, Anthropic/OpenAI via LiteLLM
- **A2A Protocol** -- Auto-generated agent cards with skills metadata for agent discovery
- **Fully Typed** -- Pydantic v2 models for all configs, responses, and workflow definitions
- **Secure** -- AST-validated eval, SSRF protection on HTTP tool
- **Datetime-Aware** -- Platform injects `{current_date}`, `{current_datetime}`, `{timezone}` into every session
- **430 Tests** -- Comprehensive suite with mocked ADK components

## Quickstart

```bash
# Install
pip install -e ".[dev]"

# Run a workflow
pyflow run exchange_tracker

# Start the API server
pyflow serve

# Validate a workflow
pyflow validate agents/exchange_tracker/workflow.yaml

# List tools and workflows
pyflow list --tools
pyflow list --workflows

# Scaffold a new agent package
pyflow init my_agent
```

## Example Workflow

```yaml
name: exchange_tracker
description: "Track USD/MXN exchange rate and alert on thresholds"

agents:
  - name: fetcher
    type: llm
    model: gemini-2.5-flash
    instruction: "Fetch the current USD/MXN rate using http_request"
    tools:
      - http_request
    output_key: rate_data

  - name: analyzer
    type: llm
    model: gemini-2.5-flash
    instruction: "Analyze the rate from {rate_data}. Alert if above 20."
    tools:
      - condition
      - alert
    output_key: analysis

orchestration:
  type: sequential
  agents:
    - fetcher
    - analyzer

a2a:
  version: "1.0.0"
  skills:
    - id: rate_tracking
      name: "Exchange Rate Tracking"
      description: "Monitor USD/MXN exchange rates"
      tags: [finance, monitoring, forex]
```

## Multi-Model Support

Use Gemini models natively, or prefix with `anthropic/` or `openai/` for LiteLLM routing:

```yaml
agents:
  - name: classifier
    type: llm
    model: gemini-2.5-flash          # Google Gemini (native)
    instruction: "Classify this input"

  - name: writer
    type: llm
    model: anthropic/claude-sonnet-4-20250514  # Anthropic via LiteLLM
    instruction: "Write a report"

  - name: summarizer
    type: llm
    model: openai/gpt-4o             # OpenAI via LiteLLM
    instruction: "Summarize the report"
```

Install LiteLLM for non-Gemini models:
```bash
pip install -e ".[litellm]"
```

## Platform Tools

| Tool | Name | Description |
|------|------|-------------|
| HTTP | `http_request` | Make HTTP requests with SSRF protection |
| Transform | `transform` | Extract/transform data using JSONPath expressions |
| Condition | `condition` | Evaluate boolean expressions with safe eval |
| Alert | `alert` | Send webhook notifications (Slack, Discord, Teams) |
| Storage | `storage` | Read/write/append JSON to local files |
| YNAB | `ynab` | Manage YNAB budgets, accounts, categories, payees, and transactions |

## Architecture

```
pyflow/
  platform/
    app.py            -- PyFlowPlatform orchestrator (boot/shutdown lifecycle)
    registry/
      tool_registry.py    -- Auto-discover + register tools
      workflow_registry.py -- Discover + hydrate YAML workflows
      discovery.py         -- Filesystem scanner
    hydration/
      hydrator.py       -- YAML -> Pydantic -> ADK Agent tree
    executor.py       -- WorkflowExecutor (ADK Runner + datetime state injection)
    a2a/
      cards.py          -- Load static agent-card.json from packages
  agents/
    exchange_tracker/
      __init__.py       -- Package marker
      agent.py          -- ADK agent entry point
      agent-card.json   -- A2A agent card
      workflow.yaml     -- Workflow definition
    budget_analyst/
      ...               -- Same structure per agent
  tools/
    base.py           -- BasePlatformTool ABC + auto-registration
    http.py           -- HTTP requests (httpx, SSRF protection)
    transform.py      -- JSONPath transforms (jsonpath-ng)
    condition.py      -- Boolean conditions (safe eval)
    alert.py          -- Webhook alerts
    storage.py        -- JSON file storage
    ynab.py           -- YNAB budget API (19 actions)
  models/
    workflow.py       -- WorkflowDef, OrchestrationConfig, A2AConfig
    agent.py          -- AgentConfig
    tool.py           -- ToolMetadata
    platform.py       -- PlatformConfig (BaseSettings, env vars)
  server.py           -- FastAPI server with REST + A2A endpoints
  cli.py              -- Typer CLI (run, validate, list, init, serve)
```

### Platform Boot Sequence

```
boot() -> set_secrets()          -- inject config.secrets into tool secret store
       -> tools.discover()       -- scan tools/, auto-register via __init_subclass__
       -> workflows.discover()   -- scan agents/, discover packages
       -> workflows.hydrate()    -- resolve tool refs -> build ADK agent trees
       -> ready

run()  -> create_session(state)  -- inject {current_date}, {current_datetime}, {timezone}
       -> runner.run_async()     -- execute ADK agent tree
       -> collect final response
```

## A2A Protocol

Workflows with `a2a` config automatically expose agent cards for discovery:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/agent-card.json` | GET | A2A agent discovery |
| `/a2a/{workflow_name}` | POST | A2A execution |
| `/api/workflows` | GET | List all workflows |
| `/api/workflows/{name}/run` | POST | REST execution |
| `/api/tools` | GET | List platform tools |
| `/health` | GET | Health check |

## Development

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest -v

# Lint
ruff check .
ruff format .
```

## Tech Stack

Python 3.12 | Google ADK | Pydantic v2 | pydantic-settings | FastAPI | httpx | jsonpath-ng | structlog | typer | LiteLLM

## License

MIT
