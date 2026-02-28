# PyFlow Concepts

PyFlow is an agent platform powered by Google ADK. Workflows are defined in YAML, auto-hydrated into ADK agent trees, and executed with tools that self-register at boot time.

This document covers the core building blocks: **agent types**, **orchestration patterns**, **computation levels**, and **platform tools**.

---

## Agent Types

Every agent in a workflow has a `type` that determines its behavior. There are two categories: **leaf agents** (do actual work) and **workflow agents** (compose other agents).

### Leaf Agents

| Type | Purpose | Key Fields |
|------|---------|------------|
| `llm` | Calls an LLM with an instruction and optional tools | `model`, `instruction`, `tools`, `output_key`, `description`, `temperature`, `output_schema`, `agent_tools` |
| `code` | Imports and runs a Python function | `function`, `input_keys`, `output_key` |
| `tool` | Executes a platform tool with fixed config | `tool`, `tool_config`, `output_key` |
| `expr` | Evaluates a safe Python expression inline | `expression`, `input_keys`, `output_key` |

### Workflow Agents

| Type | Purpose | Key Fields |
|------|---------|------------|
| `sequential` | Runs sub-agents one after another | `sub_agents` |
| `parallel` | Runs sub-agents concurrently | `sub_agents` |
| `loop` | Repeats sub-agents until stopped | `sub_agents` |

Workflow agents can be nested — a `sequential` agent can contain a `parallel` agent as one of its sub-agents, enabling complex multi-level pipelines.

---

## Computation Levels

PyFlow offers three levels of inline computation, from lightest to most powerful:

### 1. ExprAgent (`type: expr`) — One-liner expressions

For simple calculations that don't need imports or control flow. Evaluated in a sandbox with restricted builtins (`abs`, `min`, `max`, `round`, `sum`, `len`, `sorted`, `int`, `float`, `str`, `bool`, `list`, `tuple`, `all`, `any`). No imports, no IO, no `__dunder__` access.

```yaml
- name: calculate_margin
  type: expr
  expression: "round((price - cost) / price * 100, 2)"
  input_keys: [price, cost]
  output_key: margin_pct
```

Good for: price calculations, threshold checks that return a value, simple data transforms, aggregations.

### 2. CodeAgent (`type: code`) — Full Python functions

For logic that needs imports, loops, error handling, or any Python feature. Points to a function by its dotted module path. The function can be sync or async.

```yaml
- name: enrich_data
  type: code
  function: myapp.transforms.enrich_payload
  input_keys: [raw_data, config]
  output_key: enriched_data
```

```python
# myapp/transforms.py
import json
from datetime import datetime, timezone

def enrich_payload(raw_data=None, config=None):
    return {
        **raw_data,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "version": config.get("version", "1.0"),
    }
```

Good for: complex transformations, external library calls, multi-step logic, anything that's too complex for an expression.

### 3. Platform Tools (`BasePlatformTool`) — Reusable cross-workflow tools

For operations you'll use across multiple workflows. Tools self-register via `__init_subclass__` and become available by name in any workflow.

```python
# pyflow/tools/my_tool.py
from pyflow.tools.base import BasePlatformTool

class MyTool(BasePlatformTool):
    name = "my_tool"
    description = "Does something useful"

    async def execute(self, tool_context, param1: str, param2: int = 0) -> dict:
        # ... implementation
        return {"result": "done"}
```

Tools can be used in two ways:
- **By LLM agents** via the `tools` list — the LLM decides when and how to call them
- **By ToolAgents** via `tool` + `tool_config` — executed deterministically with fixed parameters

### When to use what

| Need | Use | Why |
|------|-----|-----|
| `price * quantity * 1.21` | `expr` | Single expression, no imports needed |
| Parse CSV, call external API, complex logic | `code` | Full Python, any library available |
| HTTP requests, JSONPath transforms, conditions | Platform Tool | Reusable, typed, auto-registered |
| Let the LLM decide what to do | `llm` with `tools` | LLM picks tools based on context |

---

## Orchestration Types

Orchestration defines how the top-level agents in a workflow are coordinated. Set in the `orchestration` section of the YAML.

### Sequential

Runs agents one after another. Each agent can read state written by previous agents.

```yaml
orchestration:
  type: sequential
  agents: [fetcher, analyzer, reporter]
```

### Parallel

Runs all agents concurrently. Useful when agents are independent or read from shared state without conflicts.

```yaml
orchestration:
  type: parallel
  agents: [sentiment_analyzer, entity_extractor, summarizer]
```

### Loop

Repeats agents until an agent signals completion. Optional `max_iterations` as a safety limit.

```yaml
orchestration:
  type: loop
  agents: [checker, worker]
  max_iterations: 10
```

### DAG (Directed Acyclic Graph)

Agents declare dependencies. Independent agents run in parallel; dependent agents wait for their predecessors. Validated at parse time for unknown references and cycles.

```yaml
orchestration:
  type: dag
  nodes:
    - agent: fetch_prices
      depends_on: []
    - agent: fetch_inventory
      depends_on: []
    - agent: calculate_orders
      depends_on: [fetch_prices, fetch_inventory]
    - agent: send_report
      depends_on: [calculate_orders]
```

In this example, `fetch_prices` and `fetch_inventory` run in parallel (no dependencies), then `calculate_orders` runs once both complete, and finally `send_report` runs.

### ReAct

Wraps a single LLM agent with a planner for multi-step reasoning. The agent iteratively reasons, acts (calls tools), and observes results.

```yaml
orchestration:
  type: react
  agent: reasoner
  planner: plan_react       # plan_react | builtin
  planner_config:           # for builtin planner only
    thinking_budget: 2048
```

Supported planners:
- `plan_react` — PlanReAct: plans filters/steps before executing, good for data-heavy APIs
- `builtin` — Gemini BuiltInPlanner with native thinking (accepts `planner_config.thinking_budget`)

### LLM-Routed

An LLM router agent dynamically delegates to specialized sub-agents based on the input.

```yaml
orchestration:
  type: llm_routed
  router: dispatcher
  agents: [billing_agent, support_agent, sales_agent]
```

### Choosing an orchestration type

| Pattern | Use when |
|---------|----------|
| `sequential` | Steps depend on previous output (pipeline) |
| `parallel` | Steps are independent (fan-out) |
| `loop` | Iterative refinement or polling |
| `dag` | Complex dependencies, some parallel, some sequential |
| `react` | LLM needs to reason step-by-step with tools |
| `llm_routed` | LLM should classify and delegate to specialists |

---

## Data Flow

Agents communicate through **session state** — a shared key-value store.

1. The hydrator prepends `NOW: {current_datetime} ({timezone}).` to every LLM agent instruction
2. The executor injects `current_date`, `current_datetime`, and `timezone` into session state
3. An agent writes results to `state[output_key]`
3. The next agent reads from `state` via `input_keys` (for `code`/`expr`) or `{variable}` templates in instructions (for `llm`)
4. ToolAgent resolves `{variable}` placeholders in `tool_config` from state

### Platform-Injected State

Every session starts with these variables pre-populated:

| Variable | Example | Description |
|----------|---------|-------------|
| `{current_date}` | `2026-02-28` | ISO date in configured timezone |
| `{current_datetime}` | `2026-02-28T15:30:00-05:00` | Full ISO datetime with timezone offset |
| `{timezone}` | `America/Bogota` | IANA timezone name |

Configure timezone via `PYFLOW_TIMEZONE` env var (defaults to system timezone).

All LLM agents automatically receive `NOW: {current_datetime} ({timezone}).` as the first line of their instruction — no manual setup needed. The variables above are also available for explicit use in `tool_config` or `input_keys`.

```yaml
agents:
  - name: fetch
    type: llm
    model: gemini-2.5-flash
    instruction: "Fetch the exchange rate for USD to EUR"
    tools: [http_request]
    output_key: rate_data          # writes to state["rate_data"]

  - name: calculate
    type: expr
    expression: "rate * amount"
    input_keys: [rate, amount]     # reads from state["rate"], state["amount"]
    output_key: total              # writes to state["total"]

  - name: report
    type: llm
    model: gemini-2.5-flash
    instruction: "Summarize the conversion: {total}"  # reads from state["total"]
    output_key: summary
```

### Pattern: Structured Output with `output_schema`

The preferred way to enforce structured LLM output is `output_schema`. The LLM is constrained at the API level to produce JSON matching the schema:

```yaml
- name: parser
  type: llm
  model: gemini-2.5-flash
  instruction: "Extract the currency pair from the user's message"
  output_key: parsed_input
  temperature: 0
  output_schema:
    type: object
    properties:
      base: { type: string }
      target: { type: string }
      threshold: { type: number }
    required: [base, target]
```

JSON Schema dicts are converted to Pydantic models at hydration time via `json_schema_to_pydantic()`. Supported types: `string`, `integer`, `number`, `boolean`, nested `object`, `array` with typed items, required vs optional fields.

### Pattern: LLM → Code → Expr (Legacy Structured Output)

Without `output_schema`, LLM agents write text to state even if the text is JSON. When you need to use individual fields from an LLM's JSON output in downstream agents, use this pattern:

1. **LLM agent** outputs structured JSON → `state["parsed_input"]` (a string)
2. **Code agent** parses the JSON string → `state["params"]` (a dict)
3. **Expr agents** extract individual fields → `state["base"]`, `state["target"]`, etc.

```yaml
# LLM outputs JSON string
- name: parser
  type: llm
  model: gemini-2.5-flash
  instruction: "Extract currencies. Return ONLY JSON: {\"base\": \"USD\", \"target\": \"EUR\"}"
  output_key: parsed_input

# Code agent parses JSON string into a dict
- name: parse_params
  type: code
  function: agents.exchange_tracker.helpers.parse_currency_request
  input_keys: [parsed_input]
  output_key: params

# Expr agents extract individual fields from the dict
- name: build_url
  type: expr
  expression: "'https://api.example.com/' + params['base']"
  input_keys: [params]
  output_key: fetch_url
```

This is necessary because each agent writes a single `output_key`. There is no way for one agent to write multiple top-level keys to state. The Code agent acts as a bridge between unstructured LLM output and structured state that downstream agents can consume.

---

## Platform Tools

Built-in tools available to any workflow. Each tool can be used in two ways:

- **By LLM agents** — listed in `tools:`, the LLM decides when and how to call them
- **By ToolAgents** — deterministic execution with fixed `tool_config` parameters

### `http_request` — HTTP Client

Make HTTP requests to external APIs. Includes SSRF protection that blocks requests to private/internal network addresses by default.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | *(required)* | The URL to request |
| `method` | `str` | `"GET"` | HTTP method: GET, POST, PUT, DELETE, PATCH |
| `headers` | `str` | `"{}"` | JSON string of request headers |
| `body` | `str` | `""` | JSON string of request body |
| `timeout` | `int` | `30` | Request timeout in seconds (1-300) |
| `allow_private` | `bool` | `False` | Allow requests to private network addresses |

**Returns:** `{"status": int, "headers": dict, "body": str|dict}` or `{"status": 0, "error": str}` on failure.

**LLM agent example:**
```yaml
- name: fetcher
  type: llm
  model: gemini-2.5-flash
  instruction: "Fetch the exchange rate from https://open.er-api.com/v6/latest/USD"
  tools: [http_request]
  output_key: rate_data
```

**ToolAgent example:**
```yaml
- name: fetcher
  type: tool
  tool: http_request
  tool_config:
    url: "https://open.er-api.com/v6/latest/{base_currency}"
    method: GET
  output_key: rate_data
```

---

### `transform` — JSONPath Extraction

Apply a JSONPath expression to extract or transform data from JSON input. Powered by `jsonpath-ng`.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input_data` | `str` | *(required)* | JSON string to transform |
| `expression` | `str` | *(required)* | JSONPath expression (e.g. `$.name`, `$.items[*].id`) |

**Returns:** `{"result": value}` for single match, `{"result": [values]}` for multiple matches, `{"result": null}` for no matches, or `{"result": null, "error": str}` on failure.

**LLM agent example:**
```yaml
- name: extractor
  type: llm
  model: gemini-2.5-flash
  instruction: "Extract the 'rates.EUR' field from the API response: {rate_data}"
  tools: [transform]
  output_key: eur_rate
```

**ToolAgent example:**
```yaml
- name: extractor
  type: tool
  tool: transform
  tool_config:
    input_data: "{rate_data}"
    expression: "$.rates.EUR"
  output_key: eur_rate
```

---

### `condition` — Boolean Expression Evaluator

Evaluate a boolean expression safely within an AST-validated sandbox. Returns `true` or `false`. Uses the same sandbox as ExprAgent — restricted builtins only, no imports, no IO, no dunder access.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `expression` | `str` | *(required)* | A Python boolean expression (e.g. `1 + 1 == 2`, `x > 5 and y < 10`) |

**Returns:** `{"result": bool}` or `{"result": false, "error": str}` on failure.

**Available builtins:** `abs`, `all`, `any`, `bool`, `float`, `int`, `len`, `max`, `min`, `round`, `sorted`, `str`, `sum`, `tuple`, `list`, `True`, `False`, `None`.

**LLM agent example:**
```yaml
- name: checker
  type: llm
  model: gemini-2.5-flash
  instruction: "Check if the exchange rate exceeds the threshold"
  tools: [condition]
  output_key: check_result
```

---

### `alert` — Webhook Notifications

Send alert messages to a webhook URL via HTTP POST. Includes SSRF protection.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `webhook_url` | `str` | *(required)* | The webhook URL to POST the alert to |
| `message` | `str` | *(required)* | The alert message to send |

**Returns:** `{"status": int, "sent": bool, "error": str|null}`.

The alert is sent as `{"message": "your message"}` in the POST body.

**LLM agent example:**
```yaml
- name: notifier
  type: llm
  model: gemini-2.5-flash
  instruction: "If the rate exceeds the threshold, send an alert to the webhook"
  tools: [alert]
  output_key: alert_result
```

**ToolAgent example:**
```yaml
- name: notifier
  type: tool
  tool: alert
  tool_config:
    webhook_url: "https://hooks.slack.com/services/xxx/yyy/zzz"
    message: "Rate alert: {analysis}"
  output_key: alert_result
```

---

### `storage` — Local File Storage

Read, write, or append data to local JSON/text files. Creates parent directories automatically on write/append.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | *(required)* | File path to read/write/append |
| `action` | `str` | `"read"` | One of `read`, `write`, `append` |
| `data` | `str` | `""` | Data to write/append (JSON string for structured data, plain text otherwise) |

**Returns:** `{"content": str|null, "success": bool}` or `{"content": null, "success": false, "error": str}` on failure.

**LLM agent example:**
```yaml
- name: logger
  type: llm
  model: gemini-2.5-flash
  instruction: "Save the analysis results to a log file"
  tools: [storage]
  output_key: save_result
```

**ToolAgent example:**
```yaml
- name: logger
  type: tool
  tool: storage
  tool_config:
    path: "output/results.json"
    action: write
    data: "{analysis}"
  output_key: save_result
```

---

### `ynab` — YNAB Budget API

Interact with the YNAB (You Need A Budget) API. Manage budgets, accounts, categories, payees, transactions, scheduled transactions, and budget months. Requires `PYFLOW_YNAB_API_TOKEN` environment variable or `ynab_api_token` in platform secrets.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `action` | `str` | *(required)* | The operation to perform (see actions table below) |
| `budget_id` | `str` | `""` | YNAB budget ID (required for most actions) |
| `account_id` | `str` | `""` | YNAB account ID |
| `category_id` | `str` | `""` | YNAB category ID |
| `payee_id` | `str` | `""` | YNAB payee ID |
| `transaction_id` | `str` | `""` | YNAB transaction ID |
| `scheduled_transaction_id` | `str` | `""` | YNAB scheduled transaction ID |
| `month` | `str` | `""` | Budget month in YYYY-MM-DD format (first day of month) |
| `data` | `str` | `"{}"` | JSON string for create/update payloads |
| `since_date` | `str` | `""` | Filter transactions since this date (YYYY-MM-DD) |
| `type_filter` | `str` | `""` | Filter transaction type (`uncategorized`, `unapproved`) |

**Actions:**

| Action | HTTP | Description |
|--------|------|-------------|
| `list_budgets` | GET | List all budgets |
| `get_budget` | GET | Get budget details |
| `list_accounts` | GET | List accounts in a budget |
| `get_account` | GET | Get account details |
| `list_categories` | GET | List categories |
| `get_category` | GET | Get category details |
| `update_category` | PATCH | Update category (budgeted amount, etc.) |
| `list_payees` | GET | List payees |
| `update_payee` | PATCH | Update payee name |
| `list_transactions` | GET | List transactions (supports `since_date`, `type_filter`) |
| `get_transaction` | GET | Get transaction details |
| `create_transaction` | POST | Create transaction(s) |
| `update_transaction` | PATCH | Update transaction(s) |
| `list_scheduled_transactions` | GET | List scheduled transactions |
| `create_scheduled_transaction` | POST | Create scheduled transaction |
| `update_scheduled_transaction` | PUT | Update scheduled transaction |
| `delete_scheduled_transaction` | DELETE | Delete scheduled transaction |
| `list_months` | GET | List budget months |
| `get_month_category` | GET | Get category details for a specific month |

**Returns:** `{"success": true, "data": {...}}` on success, `{"success": false, "error": "message"}` on failure.

**Setup:**
```bash
# Set your YNAB API token (get one at https://app.ynab.com/settings/developer)
echo 'PYFLOW_YNAB_API_TOKEN=your-token-here' >> .env
```

**ToolAgent example:**
```yaml
- name: list_budgets
  type: tool
  tool: ynab
  tool_config:
    action: list_budgets
  output_key: budgets

- name: get_transactions
  type: tool
  tool: ynab
  tool_config:
    action: list_transactions
    budget_id: "{budget_id}"
    since_date: "2024-01-01"
  output_key: transactions
```

**LLM agent example:**
```yaml
- name: budget_assistant
  type: llm
  model: gemini-2.5-flash
  instruction: "Help the user check their YNAB budget. List their budgets first, then get transactions for the requested budget."
  tools: [ynab]
  output_key: budget_info
```

---

### ADK Built-in Tools

These tools are provided by Google ADK and available by name in any workflow. They are lazy-imported and don't require extra installation.

**Grounding tools** — Gemini 2 models invoke these automatically when listed in `tools:`:

| Tool | Purpose |
|------|---------|
| `google_search` | Google Search — gives the LLM access to web search results |
| `google_maps_grounding` | Google Maps — location-aware grounding for geographic queries |
| `url_context` | URL content extraction — retrieves and uses content from URLs in the conversation |
| `enterprise_web_search` | Enterprise-compliant web search grounding |

**Memory & artifact tools:**

| Tool | Purpose |
|------|---------|
| `load_memory` | Load relevant memories for the current user (semantic search) |
| `preload_memory` | Preload all memories at session start |
| `load_artifacts` | Load artifacts (files, images) into the session |

**Control & interactive tools:**

| Tool | Purpose |
|------|---------|
| `exit_loop` | Signal loop completion from within a LoopAgent |
| `get_user_choice` | Async user interaction — pauses for user input (long-running) |

### Creating Custom Tools

Tools self-register via `__init_subclass__`. To add a new tool:

1. Create a file in `pyflow/tools/`
2. Inherit from `BasePlatformTool`
3. Set `name` and `description` class vars
4. Implement `async execute(self, tool_context, ...)` with typed parameters

```python
# pyflow/tools/my_tool.py
from __future__ import annotations

from google.adk.tools.tool_context import ToolContext

from pyflow.tools.base import BasePlatformTool


class MyTool(BasePlatformTool):
    name = "my_tool"
    description = "Short description of what this tool does."

    async def execute(
        self,
        tool_context: ToolContext,
        param1: str,
        param2: int = 0,
    ) -> dict:
        """Detailed description for the LLM.

        Args:
            param1: Description of param1.
            param2: Description of param2.
        """
        # ... implementation
        return {"result": "done"}
```

The tool is immediately available as `my_tool` in any workflow — no registration code needed. ADK's `FunctionTool` inspects the `execute()` signature to generate the tool schema for the LLM.

**Accessing secrets:** Tools that need API tokens use `get_secret(name)` from `pyflow.tools.base`. This checks the `PYFLOW_{NAME}` environment variable first (uppercased), then falls back to the platform secrets dict. Set secrets via environment variables or `.env` file:

```bash
# .env (gitignored)
PYFLOW_MY_API_TOKEN=your-token-here
```

```python
from pyflow.tools.base import get_secret

class MyApiTool(BasePlatformTool):
    name = "my_api"
    description = "Call my API"

    async def execute(self, tool_context: ToolContext, query: str) -> dict:
        token = get_secret("my_api_token")  # reads PYFLOW_MY_API_TOKEN
        if not token:
            return {"success": False, "error": "API token not configured"}
        # ... use token
```

---

## Callbacks

LLM agents support lifecycle callbacks that run before and/or after the agent runs. Callbacks are registered by name in Python and referenced by name in YAML.

### Registering a Callback

```python
from pyflow.platform.callbacks import register_callback

async def log_start(callback_context):
    print(f"Agent starting: {callback_context.agent_name}")

async def log_output(callback_context):
    print(f"Agent finished: {callback_context.agent_name}")

register_callback("log_start", log_start)
register_callback("log_output", log_output)
```

### Using Callbacks in YAML

```yaml
- name: analyzer
  type: llm
  model: gemini-2.5-flash
  instruction: "Analyze the data"
  callbacks:
    before_agent: log_start
    after_agent: log_output
  output_key: analysis
```

**How it works:**
- The YAML key (e.g. `before_agent`) is auto-normalized to the ADK parameter name (`before_agent_callback`)
- If a callback name isn't found in the registry, it's silently ignored — this allows referencing optional callbacks
- Callbacks are resolved at hydration time, not at runtime

### Available Hooks

| Hook | When it runs |
|------|-------------|
| `before_agent` | Before the agent processes input |
| `after_agent` | After the agent produces output |

---

## Runtime Config

The `runtime` section configures the ADK services that back the workflow. All fields are optional with sensible defaults.

```yaml
runtime:
  session_service: in_memory
  session_db_url: null
  memory_service: none
  artifact_service: none
  artifact_dir: null
  plugins: []
```

### Session Service

Controls how conversation sessions (state, events, history) are persisted.

| Value | Backend | Use when |
|-------|---------|----------|
| `in_memory` *(default)* | In-process dict | Development, testing, stateless workflows |
| `sqlite` | SQLite via aiosqlite | Single-server persistence, local deployments |
| `database` | Any SQLAlchemy-compatible DB | Production, multi-server deployments |

For `sqlite`, defaults to `sqlite+aiosqlite:///pyflow_sessions.db` if no `session_db_url` is provided. For `database`, `session_db_url` is required.

```yaml
# Local persistence
runtime:
  session_service: sqlite

# PostgreSQL
runtime:
  session_service: database
  session_db_url: "postgresql+asyncpg://user:pass@host/db"
```

### Memory Service

Long-term memory across sessions (semantic search over past interactions).

| Value | Backend | Use when |
|-------|---------|----------|
| `none` *(default)* | Disabled | Most workflows |
| `in_memory` | In-process store | Testing memory-enabled agents |

### Artifact Service

File/blob storage for agents (images, documents, generated files).

| Value | Backend | Use when |
|-------|---------|----------|
| `none` *(default)* | Disabled | Most workflows |
| `in_memory` | In-process store | Testing artifact handling |
| `file` | Local filesystem | Persisting generated files |

For `file`, defaults to `./artifacts` if no `artifact_dir` is provided.

```yaml
runtime:
  artifact_service: file
  artifact_dir: "./output/artifacts"
```

### Plugins

ADK plugins that hook into the agent lifecycle.

| Plugin | Purpose |
|--------|---------|
| `logging` | Structured logging of agent events |
| `reflect_and_retry` | Auto-retry failed tool calls with reflection (experimental) |

```yaml
runtime:
  plugins: [logging, reflect_and_retry]
```

Unknown plugin names are silently skipped.

---

## Security Model

PyFlow enforces security at multiple layers to prevent code injection, SSRF, and sandbox escapes.

### Expression Sandbox (ConditionTool + ExprAgent)

Both `ConditionTool` and `ExprAgent` evaluate Python expressions within a strict sandbox. The expression is **AST-validated** before evaluation — the entire parse tree is walked and checked against deny lists.

**What's blocked:**

| Category | Examples | Reason |
|----------|----------|--------|
| Imports | `__import__('os')`, `import os` | No module access |
| Dangerous calls | `open()`, `compile()`, `breakpoint()` | No code generation or IO |
| Introspection | `getattr()`, `setattr()`, `delattr()`, `globals()`, `locals()`, `vars()` | No runtime inspection |
| Dunder access | `x.__class__`, `x.__dict__`, `x.__subclasses__()` | No object model escape |
| Forbidden names | `__builtins__`, `__loader__`, `__spec__`, `type`, `memoryview` | No interpreter internals |

**What's allowed:**

Only a restricted set of builtins: `abs`, `all`, `any`, `bool`, `float`, `int`, `len`, `max`, `min`, `round`, `sorted`, `str`, `sum`, `tuple`, `list`, `True`, `False`, `None`.

**Notable exclusions**: `isinstance`, `type`, `dict`, `set`, `range`, `map`, `filter`, `zip`, `enumerate`, `print` are NOT available. Use dict methods like `.get()` instead of `isinstance()` checks, and list comprehensions instead of `map()`/`filter()`.

**Validation timing:**
- `ExprAgent` validates at **construction time** (`model_post_init`) — unsafe expressions fail during workflow hydration, before any workflow runs
- `ConditionTool` validates at **call time** — since the expression comes from the LLM dynamically

### SSRF Protection

`HttpTool` and `AlertTool` block requests to private/internal network addresses by default. The `is_private_url()` check rejects:

| Target | Examples |
|--------|----------|
| Localhost | `localhost`, `127.0.0.1`, `::1` |
| Private networks | `10.x.x.x`, `172.16.x.x`, `192.168.x.x` |
| Link-local | `169.254.x.x`, `fe80::` |
| Reserved | Other IANA-reserved ranges |

`HttpTool` exposes an `allow_private: bool` parameter to explicitly opt in to private network access when needed (e.g. internal APIs in a trusted environment). `AlertTool` does not — private webhooks are always blocked.

### Security Boundaries Summary

| Layer | Mechanism | Protects against |
|-------|-----------|-----------------|
| Expression sandbox | AST validation + restricted builtins | Code injection, sandbox escape |
| SSRF protection | IP/hostname validation | Internal network access |
| Tool type system | Pydantic validation on AgentConfig | Malformed workflow definitions |
| Hydration-time validation | ExprAgent `model_post_init`, DAG cycle detection | Invalid expressions, circular dependencies |

---

## Multi-Model Support

PyFlow supports multiple LLM providers. Gemini models work natively with ADK; all other providers go through [LiteLLM](https://docs.litellm.ai/docs/providers), a translation layer that provides a unified interface to 100+ LLMs.

### How It Works

When the hydrator encounters a model string, it decides the path automatically:

```
"gemini-2.5-flash"                  → passed as string directly (native ADK)
"anthropic/claude-sonnet-4-20250514" → wrapped with LiteLlm(model=...)
"openai/gpt-4o"                     → wrapped with LiteLlm(model=...)
```

This happens at hydration time — the YAML author just writes a model string and PyFlow handles the rest. Any model string starting with `anthropic/` or `openai/` triggers the LiteLLM wrapper.

### Setup

**1. Install LiteLLM:**

```bash
pip install litellm
# or
pip install "google-adk[extensions]"
```

LiteLLM is lazy-imported — workflows using only Gemini models don't need it installed.

**2. Set API keys in `.env`:**

```bash
# .env (gitignored) — auto-loaded by PyFlowPlatform.boot()
GOOGLE_API_KEY=your-google-api-key

# Only if using anthropic/ models:
ANTHROPIC_API_KEY=your-anthropic-api-key

# Only if using openai/ models:
OPENAI_API_KEY=your-openai-api-key
```

PyFlow auto-loads `.env` during `platform.boot()` following the ADK pattern (walks from `workflows_dir` to root). All variables in `.env` are exported to `os.environ`, making them available to third-party SDKs. Disable with `PYFLOW_LOAD_DOTENV=false` or `ADK_DISABLE_LOAD_DOTENV=1`.

### Supported Models

| Provider | Prefix | Model examples | API key env var |
|----------|--------|---------------|-----------------|
| Google Gemini | *(none)* | `gemini-2.5-flash`, `gemini-2.5-pro` | `GOOGLE_API_KEY` |
| Anthropic | `anthropic/` | `anthropic/claude-sonnet-4-20250514`, `anthropic/claude-haiku-4-5-20251001` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai/` | `openai/gpt-4o`, `openai/gpt-4.1`, `openai/gpt-4.1-mini` | `OPENAI_API_KEY` |

For the full list of model strings per provider, see: [LiteLLM Providers Documentation](https://docs.litellm.ai/docs/providers).

### YAML Examples

**Gemini (native):**
```yaml
- name: analyzer
  type: llm
  model: gemini-2.5-flash
  instruction: "Analyze the data"
```

**Anthropic via LiteLLM:**
```yaml
- name: analyzer
  type: llm
  model: anthropic/claude-sonnet-4-20250514
  instruction: "Analyze the data"
```

**OpenAI via LiteLLM:**
```yaml
- name: analyzer
  type: llm
  model: openai/gpt-4o
  instruction: "Analyze the data"
```

### Mixed-Model Workflows

Different agents in the same workflow can use different providers. This is useful for cost optimization (expensive model for reasoning, cheap model for formatting) or capability matching:

```yaml
agents:
  - name: researcher
    type: llm
    model: anthropic/claude-sonnet-4-20250514
    instruction: "Research the topic thoroughly"
    tools: [http_request]
    output_key: research

  - name: formatter
    type: llm
    model: gemini-2.5-flash
    instruction: "Format the research into a report: {research}"
    output_key: report

orchestration:
  type: sequential
  agents: [researcher, formatter]
```

### Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `No module named 'google.adk.models.lite_llm'` | LiteLLM not installed | `pip install litellm` |
| `AuthenticationError` from LiteLLM | API key missing or invalid | Set the correct `*_API_KEY` env var |
| Model works in API but not in PyFlow | Model string format mismatch | Use `provider/model-name` format per LiteLLM docs |

---

## YAML Workflow Structure

Complete reference of a workflow YAML file:

```yaml
name: my_workflow                    # required
description: "What this workflow does"

agents:                              # required, list of agent configs
  - name: agent_name                 # required, unique within workflow
    type: llm | code | tool | expr | sequential | parallel | loop
    # LLM fields:
    model: gemini-2.5-flash
    instruction: "What the LLM should do"
    tools: [http_request, condition]
    description: "Agent purpose for routing"  # optional
    include_contents: default        # default | none
    output_schema:                   # optional, JSON Schema -> enforces structured output
      type: object
      properties: { ... }
      required: [...]
    input_schema: { ... }            # optional, JSON Schema -> enforces structured input
    temperature: 0.7                 # optional, generation config
    max_output_tokens: 4096          # optional
    top_p: 0.95                      # optional
    top_k: 40                        # optional
    agent_tools: [other_agent]       # optional, wraps agents as callable tools
    callbacks:
      before_agent: callback_name
      after_agent: callback_name
    # Code fields:
    function: module.path.to.function
    # Tool fields:
    tool: tool_name
    tool_config: { key: value }
    # Expr fields:
    expression: "safe_python_expression"
    # Shared fields:
    input_keys: [key1, key2]         # for code/expr
    output_key: result_key           # where to write output in state
    sub_agents: [agent1, agent2]     # for sequential/parallel/loop

orchestration:                       # required
  type: sequential | parallel | loop | react | dag | llm_routed
  agents: [agent1, agent2]           # for sequential/parallel/loop/llm_routed
  nodes:                             # for dag
    - agent: name
      depends_on: [dep1, dep2]
  agent: agent_name                  # for react
  router: agent_name                 # for llm_routed
  planner: plan_react                # for react: plan_react | builtin
  planner_config:                    # for builtin planner
    thinking_budget: 2048
  max_iterations: 10                 # for loop

runtime:                             # optional
  session_service: in_memory         # in_memory | sqlite | database
  memory_service: none               # in_memory | none
  artifact_service: none             # in_memory | file | none

a2a:                                 # optional, A2A protocol config
  version: "1.0.0"
  skills:
    - id: skill_id
      name: "Skill Name"
      description: "What this skill does"
      tags: [tag1, tag2]
```

---

## A2A Protocol

Workflows can expose skills via the Agent-to-Agent (A2A) protocol. Agent cards are generated at boot from the `a2a:` section in `workflow.yaml` (opt-in — only workflows with an explicit `a2a:` section get cards) and served at `/.well-known/agent-card.json`.

```yaml
a2a:
  version: "1.0.0"
  skills:
    - id: rate_tracking
      name: "Exchange Rate Tracking"
      description: "Monitor exchange rates between any currency pair"
      tags: [finance, monitoring]
```
