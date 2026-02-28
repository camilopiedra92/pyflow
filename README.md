# PyFlow

**Define multi-agent workflows in YAML. Run them on Google ADK.**

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Tests: 539 passing](https://img.shields.io/badge/tests-539%20passing-brightgreen)
![Google ADK](https://img.shields.io/badge/powered%20by-Google%20ADK-4285F4)

PyFlow is an agent platform that turns YAML workflow definitions into [Google ADK](https://google.github.io/adk-docs/) agent trees. Tools self-register at boot, agents compose into pipelines (sequential, parallel, loop, DAG), and the [A2A protocol](https://google.github.io/A2A/) makes every workflow discoverable by other agents.

---

## Features

### Core

- **YAML → ADK agent trees** — define agents, tools, and orchestration in a single file; the platform hydrates it into a full ADK agent tree at boot
- **7 agent types** — `llm`, `code`, `tool`, `expr`, `sequential`, `parallel`, `loop`
- **Self-registering tools** — inherit `BasePlatformTool`, get auto-discovered; no decorators or manual registration
- **Agent-as-tool composition** — wrap any agent as an `AgentTool` for nested delegation via `agent_tools`

### Multi-Model

- **Gemini native** — first-class support through Google ADK
- **Anthropic & OpenAI** — prefix with `anthropic/` or `openai/` for automatic LiteLLM routing
- **Generation config** — `temperature`, `max_output_tokens`, `top_p`, `top_k` per agent

### Security

- **AST-validated eval** — `expr` agents and `condition` tool use a restricted Python sandbox (no imports, no IO, no `__dunder__` access)
- **SSRF protection** — HTTP tool blocks requests to private/internal networks

### Protocol & Integrations

- **A2A agent cards** — auto-generated from the `a2a:` section in workflow YAML; opt-in per workflow
- **REST + A2A server** — FastAPI server exposes both REST endpoints and A2A protocol
- **MCP tools** — connect to Model Context Protocol servers via `mcp_servers` in runtime config
- **OpenAPI tools** — auto-generate tools from OpenAPI specs via `openapi_tools` on agent config (ADK `OpenAPIToolset`)

### Developer Experience

- **CLI** — `pyflow run`, `validate`, `list`, `init`, `serve`
- **539 tests** across 45 test files — fully mocked, no real network or LLM calls
- **Fully typed** — Pydantic v2 models for all configs, responses, and workflow definitions
- **Structured logging** — structlog with ISO timestamps
- **OpenTelemetry** — opt-in tracing and metrics via platform telemetry config
- **7 ADK plugins** — `logging`, `debug_logging`, `reflect_and_retry`, `context_filter`, `save_files_as_artifacts`, `multimodal_tool_results`, `bigquery_analytics`
- **Datetime-aware** — platform injects `{current_date}`, `{current_datetime}`, `{timezone}` into every session

---

## Quickstart

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
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

---

## Example Workflow

The `exchange_tracker` workflow demonstrates four agent types working together in a 7-step sequential pipeline:

```yaml
name: exchange_tracker
description: "Track exchange rates between any currency pair and alert on thresholds"

agents:
  # Step 1: LLM parses user intent into structured JSON (output_schema enforces shape)
  - name: parser
    type: llm
    model: gemini-2.5-flash
    instruction: >
      Extract the currency pair from the user's message.
      - base: the source currency code (3-letter ISO, e.g. USD, EUR, GBP)
      - target: the target currency code
      - threshold: a numeric threshold if the user mentioned one, otherwise null
    output_key: parsed_input
    temperature: 0
    output_schema:
      type: object
      properties:
        base: { type: string }
        target: { type: string }
        threshold: { type: number }
      required: [base, target]

  # Step 2: CodeAgent parses the JSON string into a Python dict
  - name: parse_params
    type: code
    function: agents.exchange_tracker.helpers.parse_currency_request
    input_keys: [parsed_input]
    output_key: params

  # Step 3: ExprAgent builds the API URL (safe sandbox, no imports needed)
  - name: build_url
    type: expr
    expression: "'https://open.er-api.com/v6/latest/' + params['base']"
    input_keys: [params]
    output_key: fetch_url

  # Step 4: ToolAgent makes a deterministic HTTP call (no LLM involved)
  - name: fetcher
    type: tool
    tool: http_request
    tool_config:
      url: "{fetch_url}"
      method: GET
    output_key: api_response

  # Step 5: ExprAgent extracts the specific rate from the response
  - name: extract_rate
    type: expr
    expression: "api_response.get('body', {}).get('rates', {}).get(params['target'])"
    input_keys: [api_response, params]
    output_key: rate

  # Step 6: ExprAgent checks threshold if one was provided
  - name: check_threshold
    type: expr
    expression: >
      rate > params['threshold']
      if params.get('threshold') is not None and rate is not None
      else None
    input_keys: [rate, params]
    output_key: threshold_exceeded

  # Step 7: LLM generates a human-readable report from all collected state
  - name: reporter
    type: llm
    model: gemini-2.5-flash
    instruction: >
      Generate a concise exchange rate summary.
      Parameters: {params}
      Current rate: {rate}
      Threshold exceeded: {threshold_exceeded}
    output_key: analysis
    temperature: 0.3

orchestration:
  type: sequential
  agents: [parser, parse_params, build_url, fetcher, extract_rate, check_threshold, reporter]

a2a:
  version: "1.0.0"
  skills:
    - id: rate_tracking
      name: "Exchange Rate Tracking"
      description: "Monitor exchange rates between any currency pair"
      tags: [finance, monitoring, forex]
```

**What's happening**: An LLM extracts structured intent → a Python function parses it → an expression builds a URL → a tool fetches the data → two expressions extract and evaluate → an LLM writes the final report. Four agent types (`llm`, `code`, `expr`, `tool`), zero unnecessary LLM calls for deterministic steps.

---

## Agent Types

PyFlow agents fall into two categories: **leaf agents** that do work, and **workflow agents** that compose other agents.

### Leaf Agents

| Type | Purpose | Key Fields |
|------|---------|------------|
| `llm` | Call an LLM with an instruction and optional tools | `model`, `instruction`, `tools`, `output_key`, `output_schema`, `temperature` |
| `code` | Import and run a Python function (sync or async) | `function`, `input_keys`, `output_key` |
| `tool` | Execute a platform tool with fixed configuration | `tool`, `tool_config`, `output_key` |
| `expr` | Evaluate a safe Python expression inline | `expression`, `input_keys`, `output_key` |

### Workflow Agents

| Type | Purpose | Key Fields |
|------|---------|------------|
| `sequential` | Run sub-agents one after another | `sub_agents` |
| `parallel` | Run sub-agents concurrently | `sub_agents` |
| `loop` | Repeat sub-agents until an `exit_loop` tool is called | `sub_agents` |

Workflow agents nest — a `sequential` agent can contain a `parallel` agent as a sub-step, enabling multi-level pipelines.

### Orchestration Modes

The top-level `orchestration` block controls how root-level agents are composed:

| Mode | Behavior |
|------|----------|
| `sequential` | Agents run in order, each seeing the accumulated state |
| `parallel` | Agents run concurrently |
| `loop` | Agents repeat until exit condition |
| `dag` | Dependency graph — agents run in waves based on `depends_on` declarations |
| `llm_routed` | An LLM routes to sub-agents based on their `description` fields |
| `planner: builtin` | Gemini BuiltInPlanner dynamically orchestrates agents |

#### DAG Orchestration

Define explicit dependencies between agents. Nodes with satisfied dependencies run in parallel (wave-based scheduling via `asyncio.gather`). Cycles are detected at parse time using Kahn's algorithm.

```yaml
orchestration:
  type: dag
  nodes:
    - agent: fetch
      depends_on: []
    - agent: parse
      depends_on: [fetch]
    - agent: enrich
      depends_on: [fetch]
    - agent: store
      depends_on: [parse, enrich]   # waits for both before running
```

---

## Multi-Model Support

Use Gemini models natively, or prefix with `anthropic/` or `openai/` for LiteLLM routing:

```yaml
agents:
  - name: classifier
    type: llm
    model: gemini-2.5-flash                       # Google Gemini (native)
    instruction: "Classify this input"

  - name: writer
    type: llm
    model: anthropic/claude-sonnet-4-20250514      # Anthropic via LiteLLM
    instruction: "Write a report"

  - name: summarizer
    type: llm
    model: openai/gpt-4o                           # OpenAI via LiteLLM
    instruction: "Summarize the report"
```

Install LiteLLM for non-Gemini models:

```bash
pip install -e ".[litellm]"
```

---

## Platform Tools

### Custom Tools

| Name | Description |
|------|-------------|
| `http_request` | HTTP requests (GET/POST/PUT/DELETE) with SSRF protection |
| `transform` | Extract and transform data using JSONPath expressions |
| `condition` | Evaluate boolean expressions with AST-validated safe eval |
| `alert` | Send webhook notifications to Slack, Discord, or Teams |
| `storage` | Read, write, and append JSON to local files |

Custom tools inherit from `BasePlatformTool` and auto-register via `__init_subclass__`. To create a new tool:

```python
from pyflow.tools.base import BasePlatformTool

class MyTool(BasePlatformTool):
    name = "my_tool"
    description = "Does something useful"

    async def execute(self, action: str, data: dict | None = None) -> dict:
        return {"result": "done"}
```

### ADK Built-in Tools

These tools are available by name in any workflow — they're lazy-imported from Google ADK:

| Name | Description |
|------|-------------|
| `google_search` | Google Search grounding |
| `google_maps_grounding` | Google Maps grounding |
| `enterprise_web_search` | Enterprise web search |
| `url_context` | Fetch and process URL content |
| `load_memory` | Load agent memory |
| `preload_memory` | Preload memory into context |
| `load_artifacts` | Load stored artifacts |
| `get_user_choice` | Interactive user input |
| `exit_loop` | Signal loop termination |

---

## Architecture

```
pyflow/
  platform/
    app.py                    # PyFlowPlatform orchestrator (boot/shutdown lifecycle)
    executor.py               # WorkflowExecutor (ADK App model, builds Runner per-run, datetime state injection)
    registry/
      tool_registry.py        # Auto-discover + register tools
      workflow_registry.py    # Discover + hydrate YAML workflows
      discovery.py            # Filesystem scanner for agent packages
    hydration/
      hydrator.py             # YAML -> Pydantic -> ADK agent tree + build_root_agent() factory
      schema.py               # JSON Schema -> dynamic Pydantic models (output_schema/input_schema)
    agents/
      dag_agent.py            # DagAgent: wave-based parallel DAG execution with deadlock detection
      expr_agent.py           # ExprAgent: inline Python expressions (AST-validated sandbox)
    a2a/
      cards.py                # AgentCardGenerator: generate A2A cards from workflow definitions
  tools/
    base.py                   # BasePlatformTool ABC + auto-registration via __init_subclass__
    http.py                   # HttpTool (httpx, SSRF protection)
    transform.py              # TransformTool (jsonpath-ng)
    condition.py              # ConditionTool (AST-validated safe eval)
    alert.py                  # AlertTool (webhook notifications)
    storage.py                # StorageTool (JSON file read/write/append)
  models/
    workflow.py               # WorkflowDef, OrchestrationConfig, A2AConfig, RuntimeConfig, McpServerConfig
    agent.py                  # AgentConfig (model, instruction, tools, schemas, generation config, openapi_tools), OpenApiAuthConfig, OpenApiToolConfig
    tool.py                   # ToolMetadata
    platform.py               # PlatformConfig (pydantic-settings BaseSettings, telemetry config)
  server.py                   # FastAPI server with REST + A2A endpoints
  cli.py                      # Typer CLI (run, validate, list, init, serve)
  config.py                   # structlog configuration
agents/
  exchange_tracker/           # 7-step pipeline: LLM → code → expr → tool → expr → expr → LLM
  budget_analyst/             # ReAct agent with BuiltInPlanner and YNAB OpenAPI tools
  example/                    # Simple sequential workflow (condition + transform)
tests/                        # 539 tests across 45 files, mirrors source structure
```

### Platform Boot Sequence

```
boot()
  ├─ load .env              # ADK-aligned: walk from workflows_dir to root
  ├─ set_secrets()          # Inject config.secrets into tool secret store
  ├─ tools.discover()       # Scan tools/, auto-register via __init_subclass__
  ├─ workflows.discover()   # Scan agents/, discover packages
  └─ workflows.hydrate()    # Resolve tool refs → build ADK agent trees
      └─ ready

run(workflow, message)
  ├─ create_session(state)  # Inject {current_date}, {current_datetime}, {timezone}
  ├─ runner.run_async()     # Execute ADK agent tree
  └─ collect response       # Return final agent output
```

### Agent Package Structure

Each agent lives in its own package under `agents/`, compatible with `adk web` and `adk deploy`:

```
agents/my_agent/
  __init__.py       # Exports root_agent for ADK compatibility
  agent.py          # build_root_agent(__file__) factory
  workflow.yaml     # Workflow definition + optional a2a: section
```

Scaffold a new one with `pyflow init my_agent`.

---

## A2A Protocol

Workflows with an `a2a:` section in their YAML automatically get agent cards generated at boot. This enables agent-to-agent discovery following Google's [A2A protocol](https://google.github.io/A2A/).

```yaml
# Add to any workflow.yaml to enable A2A
a2a:
  version: "1.0.0"
  skills:
    - id: rate_tracking
      name: "Exchange Rate Tracking"
      description: "Monitor exchange rates between any currency pair"
      tags: [finance, monitoring, forex]
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/agent-card.json` | GET | A2A agent card discovery |
| `/a2a/{workflow_name}` | POST | Execute workflow via A2A protocol |
| `/api/workflows` | GET | List all registered workflows |
| `/api/workflows/{name}/run` | POST | Execute workflow via REST |
| `/api/tools` | GET | List all platform tools |
| `/health` | GET | Health check |

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `pyflow run <name>` | Execute a workflow by name |
| `pyflow validate <path>` | Validate a workflow YAML against the schema |
| `pyflow list --tools` | List all registered platform tools |
| `pyflow list --workflows` | List all discovered workflows |
| `pyflow init <name>` | Scaffold a new agent package under `agents/` |
| `pyflow serve` | Start the FastAPI server on port 8000 |

---

## Development

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest -v

# Lint and format
ruff check .
ruff format .
```

### Testing

- **539 tests** across 45 test files
- HTTP tests use `pytest-httpx` mocks (no real network calls)
- CLI tests use `typer.testing.CliRunner`
- Server tests use `httpx.ASGITransport` for in-process FastAPI testing
- Integration tests validate full platform boot + workflow hydration (no real LLM calls)
- `asyncio_mode = "auto"` — async tests need no decorator

---

## Tech Stack

Python 3.11+ | [Google ADK](https://google.github.io/adk-docs/) | [Pydantic v2](https://docs.pydantic.dev/) | [FastAPI](https://fastapi.tiangolo.com/) | [httpx](https://www.python-httpx.org/) | [jsonpath-ng](https://github.com/h2non/jsonpath-ng) | [structlog](https://www.structlog.org/) | [Typer](https://typer.tiangolo.com/) | [LiteLLM](https://docs.litellm.ai/)

## License

MIT
