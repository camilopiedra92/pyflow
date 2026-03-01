---
name: create-workflow
description: >
  Create a new PyFlow YAML workflow that orchestrates agents into a pipeline.
  Use this skill whenever the user wants to create a workflow, build a pipeline,
  compose agents, set up an automation, define agent orchestration, or asks how
  to wire agents together. Also use this when the user mentions "workflow YAML",
  "orchestration", "agent pipeline", "sequential/parallel/loop/dag agents",
  or wants to make agents work together in a defined sequence.
---

# Create PyFlow Workflow

This skill guides the creation of YAML workflow definitions that PyFlow auto-discovers, validates, hydrates into ADK agent trees, and executes.

## Before You Start

1. **Understand the goal** — what is the workflow supposed to accomplish end-to-end?
2. **Identify the steps** — what are the individual operations? Which need an LLM, which are deterministic?
3. **Map the data flow** — what does each step produce, and what does the next step consume?
4. **Choose orchestration** — do steps run in sequence, parallel, or with complex dependencies?

## Workflow Lifecycle

When PyFlow boots, this happens automatically:

1. **Discover** — scans `agents/` for agent packages (subdirs with `workflow.yaml`)
2. **Parse** — validates YAML against `WorkflowDef` Pydantic model
3. **Hydrate** — resolves tool references and builds ADK agent tree
4. **Ready** — workflow is executable via CLI, API, or programmatically

No registration code needed. Run `pyflow init <name>` to scaffold a new agent package.

## Implementation Checklist

1. Ensure `.env` has required API keys (`GOOGLE_API_KEY`, etc.) — auto-loaded by `platform.boot()`
2. Design agents and data flow
3. Choose orchestration type
4. Scaffold the agent package and edit its files:
   - `pyflow init <name>` to scaffold the package
   - Edit `agents/<name>/workflow.yaml`
   - Add `a2a:` section to `workflow.yaml` if A2A discovery is needed (cards are generated at boot)
5. Validate: `source .venv/bin/activate && pyflow validate agents/<name>/workflow.yaml`
6. If using custom code/tools, ensure they exist
7. Test: `pyflow run <name> -i '{"message": "test input"}'`

## YAML Structure

Every workflow has three required sections and two optional ones:

```yaml
name: my_workflow                    # unique identifier
description: "What this workflow does"

agents: [...]                        # list of agent configs
orchestration: { ... }               # how agents are coordinated

runtime: { ... }                     # optional: service configuration
a2a: { ... }                         # optional: A2A protocol exposure
```

## Agent Types Reference

### LLM Agent — call a language model

The workhorse agent. Sends an instruction to an LLM, optionally with tools the LLM can invoke.

```yaml
- name: analyzer
  type: llm
  model: gemini-2.5-flash
  description: "Analyzes input data and produces structured summaries"
  instruction: "Analyze the data in {input_data} and provide a summary"
  tools: [http_request, condition]
  output_key: analysis
  temperature: 0.3
```

**Required fields:** `model`, `instruction`
**Optional fields:** `tools`, `output_key`, `callbacks`, `description`, `include_contents`, `output_schema`, `input_schema`, `temperature`, `max_output_tokens`, `top_p`, `top_k`, `agent_tools`

**Callbacks** use Python FQN (fully-qualified names) resolved via `importlib`:
```yaml
callbacks:
  before_agent: "mypackage.callbacks.log_before"
  after_agent: "mypackage.callbacks.log_after"
```

**New LLM fields (post ADK alignment):**
- `description` — used by `llm_routed` orchestration for agent routing (what does this agent do?)
- `include_contents: "none"` — hides conversation history (isolated sub-tasks)
- `output_schema` — JSON Schema dict, enforces structured JSON output via Pydantic model (see below)
- `input_schema` — JSON Schema dict, enforces structured JSON input (same schema format)
- `temperature`, `max_output_tokens`, `top_p`, `top_k` — generation config (controls LLM behavior)
- `agent_tools: [agent_name]` — wraps other agents as callable tools (agent-as-tool composition)

**Model strings:**
- Gemini (native): `gemini-2.5-flash`, `gemini-2.5-pro`
- Anthropic (via LiteLLM): `anthropic/claude-sonnet-4-20250514`
- OpenAI (via LiteLLM): `openai/gpt-4o`

**Instructions can reference state** with `{variable_name}` — resolved from session state at runtime.

**Automatic date awareness:** The `GlobalInstructionPlugin` injects `NOW: {current_datetime} ({timezone}).` into every LLM agent instruction at runtime. No manual setup needed — all LLM agents know the current date and time.

**Platform-injected state:** Every session also has `{current_date}`, `{current_datetime}`, and `{timezone}` available as template variables if you need to reference them explicitly in instructions or tool_config.

**Available tools:** `http_request`, `transform`, `condition`, `alert`, `storage`, plus ADK built-ins (see below), plus workflow-level OpenAPI tools (see below), plus any custom tools in `pyflow/tools/`, plus any Python callable via FQN (e.g. `mypackage.tools.custom_search`).

**ADK built-in tools** (available by name in `tools:` list):

| Tool | Category | Description |
|------|----------|-------------|
| `exit_loop` | Control | Signal loop completion from within a LoopAgent |
| `google_search` | Grounding | Google Search — Gemini invokes automatically |
| `google_maps_grounding` | Grounding | Google Maps — location-aware grounding |
| `url_context` | Grounding | Extract content from URLs in the conversation |
| `enterprise_web_search` | Grounding | Enterprise-compliant web search |
| `load_memory` | Memory | Load relevant memories for the current user |
| `preload_memory` | Memory | Preload all memories at session start |
| `load_artifacts` | Artifacts | Load artifacts into the session |
| `get_user_choice` | Interactive | Async user interaction (long-running) |
| `transfer_to_agent` | Control | Transfer control to another agent (useful for llm_routed) |

**`output_schema` reference** — enforces structured JSON output at the API level. The LLM can only produce JSON matching this schema:

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

Supported JSON Schema types: `string`, `integer`, `number`, `boolean`, nested `object`, `array` (with `items`). Fields in `required` are mandatory; others default to `None`. Converted to Pydantic models at hydration time via `json_schema_to_pydantic()`. Use this instead of the "LLM → Code → Expr" pattern whenever possible — it eliminates JSON parsing errors entirely.

### Expr Agent — inline safe expression

For lightweight calculations without creating a Python file. Evaluated in a sandboxed environment (AST-validated, restricted builtins only).

```yaml
- name: calculate_margin
  type: expr
  expression: "round((price - cost) / price * 100, 2)"
  input_keys: [price, cost]
  output_key: margin_pct
```

**Required fields:** `expression`, `output_key`
**Optional fields:** `input_keys`

**Available builtins:** `abs`, `all`, `any`, `bool`, `float`, `int`, `len`, `max`, `min`, `round`, `sorted`, `str`, `sum`, `tuple`, `list`.

**Blocked:** imports, IO, dunder access, `getattr`/`setattr`/`delattr`, `globals`/`locals`.

Use for: price calculations, threshold checks, simple transforms, aggregations. If you need imports or control flow, use a Code Agent instead.

### Code Agent — run a Python function

For complex logic that needs full Python. Points to a function by dotted module path.

```yaml
- name: enrich
  type: code
  function: myapp.transforms.enrich_payload
  input_keys: [raw_data, config]
  output_key: enriched
```

**Required fields:** `function`, `output_key`
**Optional fields:** `input_keys`

The function receives `input_keys` as keyword arguments (values from session state). It can be sync or async — CodeAgent detects and handles both.

### Tool Agent — deterministic tool execution

Executes a platform tool with fixed parameters. Unlike LLM agents that let the LLM decide when/how to call tools, ToolAgent always executes exactly once with the configured params.

```yaml
- name: fetch_rates
  type: tool
  tool: http_request
  tool_config:
    url: "https://api.example.com/rates/{currency}"
    method: GET
  output_key: rate_data
```

**Required fields:** `tool`, `output_key`
**Optional fields:** `tool_config`

**Template resolution:** `{variable}` placeholders in `tool_config` values are resolved from session state. A value that is exactly `"{key}"` preserves the original type (dict, list, etc.); partial matches like `"prefix_{key}"` produce strings.

### Workflow Agents — compose other agents

Nest agents for complex pipelines. These reference other agents by name via `sub_agents`.

```yaml
# Sequential: runs sub-agents one after another
- name: pipeline
  type: sequential
  sub_agents: [step_a, step_b, step_c]

# Parallel: runs sub-agents concurrently
- name: fan_out
  type: parallel
  sub_agents: [worker_a, worker_b]

# Loop: repeats sub-agents until completion
- name: retry_loop
  type: loop
  sub_agents: [checker, worker]
```

**Required fields:** `sub_agents`

Workflow agents are defined AFTER their sub-agents in the YAML. The hydrator builds leaf agents first, then resolves sub_agent references in the second pass.

## Orchestration Types

Orchestration wraps all agents at the top level. Choose based on how your agents relate to each other.

### Sequential — pipeline

```yaml
orchestration:
  type: sequential
  agents: [fetch, process, report]
```

Each agent runs after the previous one finishes. Data flows through state.

### Parallel — fan-out

```yaml
orchestration:
  type: parallel
  agents: [analyzer_a, analyzer_b, analyzer_c]
```

All agents run concurrently. Best when agents are independent.

### Loop — iteration

```yaml
orchestration:
  type: loop
  agents: [check, work]
  max_iterations: 10        # safety limit, optional
```

Repeats until an agent signals completion or `max_iterations` is reached.

### DAG — dependency graph

```yaml
orchestration:
  type: dag
  nodes:
    - agent: fetch_prices
      depends_on: []
    - agent: fetch_inventory
      depends_on: []
    - agent: calculate
      depends_on: [fetch_prices, fetch_inventory]
    - agent: report
      depends_on: [calculate]
```

Agents with satisfied deps run in parallel. Validated at parse time for unknown references and cycles (Kahn's algorithm).

### ReAct — reasoning + acting

```yaml
orchestration:
  type: react
  agent: reasoner
  planner: plan_react       # optional: plan_react | builtin
  planner_config:           # optional: for builtin planner
    thinking_budget: 2048
```

Wraps a single LLM agent with a planner for multi-step reasoning with tools. Supported planners:
- `plan_react` — PlanReAct: plans before acting, good for data-heavy APIs
- `builtin` — Gemini BuiltInPlanner with native thinking (accepts `planner_config.thinking_budget`)

### LLM-Routed — dynamic delegation

```yaml
orchestration:
  type: llm_routed
  router: dispatcher
  agents: [billing, support, sales]
```

An LLM router classifies the input and delegates to the appropriate sub-agent.

## Data Flow Patterns

Agents communicate through **session state** — a shared key-value store that persists across the workflow execution.

### Automatic date awareness

The `GlobalInstructionPlugin` injects `NOW: {current_datetime} ({timezone}).` into every LLM agent instruction at runtime. No manual setup needed — this is handled by the executor's App model, not by the hydrator.

### Platform-injected state

The executor injects these variables into every session at creation time:

| Variable | Example | Description |
|----------|---------|-------------|
| `{current_date}` | `2026-02-28` | ISO date in configured timezone |
| `{current_datetime}` | `2026-02-28T15:30:00-05:00` | Full ISO datetime with offset |
| `{timezone}` | `America/Bogota` | IANA timezone name |

Configure via `PYFLOW_TIMEZONE` env var (defaults to system timezone auto-detection). These are also available for explicit use in `tool_config` values or expr/code agents via `input_keys`.

### Writing to state

Every agent with `output_key` writes its result to `state[output_key]`:
```yaml
output_key: rate_data    # result -> state["rate_data"]
```

### Reading from state

Depends on agent type:

| Agent type | How it reads state |
|-----------|-------------------|
| `llm` | `{variable}` in `instruction` string |
| `expr` | `input_keys` list — each key read from state |
| `code` | `input_keys` list — each key passed as kwarg to function |
| `tool` | `{variable}` in `tool_config` values |

### Common pattern: pipeline with state handoff

```yaml
agents:
  - name: fetch
    type: tool
    tool: http_request
    tool_config: { url: "https://api.example.com/data" }
    output_key: raw_data              # writes state["raw_data"]

  - name: calculate
    type: expr
    expression: "sum(item['value'] for item in items)"
    input_keys: [items]               # reads state["items"]
    output_key: total                 # writes state["total"]

  - name: report
    type: llm
    model: gemini-2.5-flash
    instruction: "Summarize: total is {total}"   # reads state["total"]
    output_key: summary
```

## Choosing the Right Agent Type

| What you need | Agent type | Why |
|---------------|-----------|-----|
| LLM reasoning, natural language, tool calling | `llm` | Only type that calls LLMs |
| `price * qty * 1.21` | `expr` | Single expression, sandboxed |
| Parse CSV, call libraries, complex logic | `code` | Full Python, any import |
| Fixed HTTP call, deterministic tool use | `tool` | No LLM, exact params every time |
| Run steps A then B then C | `sequential` | Composes other agents |
| Run A, B, C at the same time | `parallel` | Independent work |
| Retry until done | `loop` | Iterative refinement |

## Runtime Configuration

Optional — defaults are sensible for development.

```yaml
runtime:
  session_service: in_memory     # in_memory | sqlite | database
  session_db_url: null           # required for "database"
  memory_service: none           # in_memory | none
  artifact_service: none         # in_memory | file | none
  artifact_dir: null             # for "file" artifact service
  credential_service: none       # in_memory | none (for OAuth; use get_secret() for static API keys)
  plugins: []                    # logging | debug_logging | reflect_and_retry | context_filter | save_files_as_artifacts | multimodal_tool_results
  # Context caching (Gemini 2.0+)
  context_cache_intervals: null  # cache every N turns
  context_cache_ttl: null        # cache TTL in seconds
  context_cache_min_tokens: null # minimum tokens to trigger caching
  # Event compaction (long conversations)
  compaction_interval: null      # compact every N events
  compaction_overlap: null       # overlap window size
  # Resumability
  resumable: false               # enable session resumability
```

For production persistence:
```yaml
runtime:
  session_service: sqlite        # auto-creates pyflow_sessions.db
  plugins: [logging]
  resumable: true                # enable session resumability
```

For long-running Gemini conversations:
```yaml
runtime:
  context_cache_intervals: 5     # cache every 5 turns
  context_cache_ttl: 1800        # 30 min TTL
  compaction_interval: 20        # compact every 20 events
  compaction_overlap: 5          # keep 5 events of overlap
```

## Tool Authentication

Tools that need API keys use `get_secret(name)` from `pyflow.tools.base`. It checks `PYFLOW_{NAME}` env var first, then the platform secrets dict:

```bash
# .env (gitignored, auto-loaded by platform.boot())
PYFLOW_YNAB_API_TOKEN=your-token
GOOGLE_API_KEY=your-gemini-key
```

This is the standard approach for all current tools. For OAuth flows (user login, token refresh), use `credential_service: in_memory` in the runtime config instead — ADK's credential service manages per-session tokens via the `ToolContext`.

## A2A Protocol (Optional)

Expose the workflow as an A2A-compatible agent with discoverable skills:

```yaml
a2a:
  version: "1.0.0"
  skills:
    - id: rate_tracking
      name: "Exchange Rate Tracking"
      description: "Monitor exchange rates between any currency pair"
      tags: [finance, monitoring]
```

Agent cards are generated at boot from the `a2a:` section in `workflow.yaml` (opt-in — only workflows with explicit `a2a:` get cards). Cards are served at `/.well-known/agent-card.json`. No static JSON files needed.

## Validation

Pydantic validates at multiple levels:

1. **AgentConfig** — type-specific field requirements (e.g. `llm` needs `model` + `instruction`)
2. **OrchestrationConfig** — type-specific fields + DAG cycle detection
3. **WorkflowDef** — all orchestration agent/node references exist in the agents list
4. **Hydration** — tool names resolve in registry, ExprAgent expressions pass AST validation

Use the CLI to catch errors early:
```bash
source .venv/bin/activate
pyflow validate agents/my_workflow/workflow.yaml
```

## Complete Examples

### Simple Pipeline

Fetch data, calculate, and report — the most common pattern.

```yaml
name: price_calculator
description: "Calculate total price with tax"

agents:
  - name: get_prices
    type: tool
    tool: http_request
    tool_config:
      url: "https://api.example.com/prices"
      method: GET
    output_key: prices

  - name: calculate_total
    type: expr
    expression: "sum(p['amount'] for p in items) * (1 + tax_rate)"
    input_keys: [items, tax_rate]
    output_key: total

  - name: format_report
    type: llm
    model: gemini-2.5-flash
    instruction: >
      Format a price report. The total is {total}.
      List each item and the final total with tax.
    output_key: report

orchestration:
  type: sequential
  agents: [get_prices, calculate_total, format_report]
```

### DAG with Parallel Fetch

Independent data sources fetched in parallel, then combined.

```yaml
name: market_report
description: "Aggregate data from multiple sources into a market report"

agents:
  - name: fetch_stocks
    type: tool
    tool: http_request
    tool_config: { url: "https://api.example.com/stocks" }
    output_key: stocks

  - name: fetch_forex
    type: tool
    tool: http_request
    tool_config: { url: "https://api.example.com/forex" }
    output_key: forex

  - name: fetch_commodities
    type: tool
    tool: http_request
    tool_config: { url: "https://api.example.com/commodities" }
    output_key: commodities

  - name: synthesize
    type: llm
    model: gemini-2.5-flash
    instruction: >
      Create a market report combining:
      - Stock data: {stocks}
      - Forex data: {forex}
      - Commodities data: {commodities}
    output_key: report

orchestration:
  type: dag
  nodes:
    - agent: fetch_stocks
      depends_on: []
    - agent: fetch_forex
      depends_on: []
    - agent: fetch_commodities
      depends_on: []
    - agent: synthesize
      depends_on: [fetch_stocks, fetch_forex, fetch_commodities]
```

### LLM-Routed Support System

Router delegates to specialist agents based on user input.

```yaml
name: support_router
description: "Route support requests to specialist agents"

agents:
  - name: dispatcher
    type: llm
    model: gemini-2.5-flash
    instruction: >
      You are a support request router. Analyze the user's message and
      delegate to the appropriate specialist agent.

  - name: billing
    type: llm
    model: gemini-2.5-flash
    instruction: "Handle billing questions. Check account status if needed."
    tools: [http_request]
    output_key: response

  - name: technical
    type: llm
    model: gemini-2.5-flash
    instruction: "Handle technical support. Diagnose issues step by step."
    tools: [http_request, condition]
    output_key: response

orchestration:
  type: llm_routed
  router: dispatcher
  agents: [billing, technical]
```

### ReAct Agent with Tools

A single LLM agent that autonomously decides which tool calls to make. Uses PlanReAct for structured multi-step reasoning.

OpenAPI tools are defined in `pyflow.yaml` at the project root (infrastructure: spec + auth), not in the workflow YAML. Agents reference them by name, with optional per-agent glob filtering.

```yaml
# pyflow.yaml (project root) — defines the tool (infrastructure only)
openapi_tools:
  ynab:
    spec: specs/ynab-v1-openapi.yaml
    name_prefix: ynab           # optional: prefixes all generated tool names
    tool_filter: ["get*"]       # optional: project-level whitelist (list) or FQN predicate (string)
    auth:
      type: bearer
      token_env: PYFLOW_YNAB_API_TOKEN
```

**OpenAPI tool config fields:**
- `spec` — path to OpenAPI spec file (relative to project root)
- `name_prefix` — optional prefix for generated tool names (→ ADK `tool_name_prefix`)
- `tool_filter` — optional project-level filter: a list of operation names (whitelist) or a Python FQN string resolving to a predicate callable (→ ADK `tool_filter`)
- `auth` — authentication config (see auth types below)

**Auth types:** `none` (default), `bearer` (token via env var), `apikey` (header/query), `oauth2` (authorization code flow), `service_account` (GCP SA JSON key via env var + scopes)

```yaml
# service_account auth example (GCP APIs)
openapi_tools:
  sheets:
    spec: specs/sheets-v4.yaml
    auth:
      type: service_account
      service_account_env: PYFLOW_SA_KEY          # env var with SA JSON
      service_account_scopes:
        - https://www.googleapis.com/auth/spreadsheets
```

```yaml
# agents/budget_analyst/workflow.yaml — uses the tool with per-agent filtering
name: budget_analyst
description: "Answer questions about your YNAB budget"

agents:
  - name: analyst
    type: llm
    model: gemini-2.5-flash
    instruction: >
      You are a budget analyst.
      Start by calling list_budgets, then query as needed.
      NEVER call list_transactions without since_date.
    tools:
      - ynab: ["get*"]        # only GET operations (glob filter)
    output_key: analysis

orchestration:
  type: react
  agent: analyst
  planner: plan_react

a2a:
  version: "1.0.0"
  skills:
    - id: budget_analysis
      name: "Budget Analysis"
      description: "Analyze YNAB budget data"
      tags: [finance, budget]
```

**Tool filtering syntax:** `tools: [ynab]` gives all operations; `tools: [{ynab: ["get*"]}]` filters with `fnmatch` glob patterns. Different agents can use different subsets of the same API — filtering is per-agent, not per-spec. Note: per-agent `FilteredToolset` filtering (in workflow YAML) is separate from project-level `tool_filter` (in `pyflow.yaml`).

**Key lesson:** For APIs that return large responses, always instruct the agent to filter (e.g. `since_date`). PlanReAct plans filters before executing, saving tokens vs vanilla ReAct which fetches first.

## Common Mistakes

- **Referencing an agent name in orchestration that doesn't exist in agents list** — the `WorkflowDef` validator catches this at parse time
- **Forgetting `output_key`** on agents that need to pass data downstream — without it, the result doesn't enter session state
- **Using `{variable}` in expr/code agents** — those use `input_keys`, not template strings. Templates are for `llm` instructions and `tool_config` values only
- **Expecting LLM output to be a dict** — LLM agents write text to state. To enforce structured JSON, use `output_schema` (enforces schema via Pydantic at the API level). Without `output_schema`, add a Code agent to parse JSON output (see "Pattern: LLM → Code → Expr" in Data Flow)
- **Using `isinstance()` in ExprAgent** — `isinstance`, `type`, `dict`, `set`, `range`, `print` are NOT in the sandbox. Use `.get()` chains instead of `isinstance` checks. ExprAgent fails silently (error event) and downstream agents won't see the output_key
- **Defining workflow agents before their sub-agents** — the hydrator builds leaf agents first, then resolves sub_agent references. Order in the YAML doesn't strictly matter (the hydrator does two passes), but defining leaves first is clearer
- **Using `expr` when you need imports** — ExprAgent is sandboxed with no imports. Use `code` for anything that needs `import`
- **Circular DAG dependencies** — validated at parse time with Kahn's algorithm. If you get a cycle error, check `depends_on` references
