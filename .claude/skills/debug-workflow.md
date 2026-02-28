---
name: debug-workflow
description: >
  Diagnose and fix PyFlow workflow failures. Use this skill whenever a workflow
  fails to validate, hydrate, or execute, or when the user reports unexpected
  behavior from a workflow. Also use this when the user mentions "workflow error",
  "hydration failed", "agent error", "workflow not working", "validation error",
  "KeyError" in workflow context, "tool not found", or when debugging any issue
  in the PyFlow pipeline (YAML parsing, Pydantic validation, hydration, or runtime).
---

# Debug PyFlow Workflow

Systematic approach to diagnosing workflow failures. Workflows can fail at four distinct stages — identifying *which* stage tells you *where* to look.

## Failure Stages

```
YAML file → [1. Parse] → WorkflowDef → [2. Validate] → Valid Def → [3. Hydrate] → Agent Tree → [4. Execute] → Result
```

| Stage | When | Error looks like |
|-------|------|-----------------|
| **Parse** | YAML syntax or schema mismatch | `yaml.scanner.ScannerError`, `ValidationError` from Pydantic |
| **Validate** | Config rules violated | `ValidationError` with field-specific messages |
| **Hydrate** | Tool/agent references can't be resolved | `KeyError`, `ValueError` during `WorkflowHydrator.hydrate()` |
| **Execute** | Runtime failure during agent execution | Agent error events, empty results, wrong state |

## Step 1: Reproduce the Error

Before diagnosing, reproduce the exact failure:

```bash
source .venv/bin/activate

# Validation only (stages 1-2):
pyflow validate pyflow/agents/<name>/workflow.yaml

# Full execution (stages 1-4):
pyflow run <name> -i '{"message": "test input"}'
```

Read the error message carefully. The stage tells you where to look.

## Stage 1: Parse Errors

**Symptoms:** `yaml.scanner.ScannerError`, `yaml.parser.ParserError`, or Pydantic `ValidationError` with "unexpected keyword argument".

### Common causes

**Bad YAML syntax:**
```yaml
# Wrong — YAML indentation error
agents:
- name: fetch    # missing space after dash
  type: llm

# Right
agents:
  - name: fetch
    type: llm
```

**Unknown fields:**
```yaml
# Wrong — "prompt" is not a valid field, it's "instruction"
- name: agent1
  type: llm
  model: gemini-2.5-flash
  prompt: "Do something"          # should be "instruction"

# Wrong — "agent_type" is not valid, it's "type"
- name: agent1
  agent_type: llm                  # should be "type"
```

**Invalid type value:**
```yaml
# Wrong — "llm_agent" is not a valid type
- name: agent1
  type: llm_agent                  # should be "llm"
```

### Diagnosis

Read the YAML file and check:
1. Indentation is consistent (2 spaces per level)
2. Lists use `- ` prefix with a space
3. All field names match `AgentConfig` or `WorkflowDef` schema
4. The `type` value is one of: `llm`, `sequential`, `parallel`, `loop`, `code`, `tool`, `expr`

Reference: `pyflow/models/agent.py` for AgentConfig fields, `pyflow/models/workflow.py` for WorkflowDef/OrchestrationConfig fields.

## Stage 2: Validation Errors

**Symptoms:** `ValidationError` with specific field messages like "llm agent requires 'model'" or "Orchestration references unknown agent".

### Agent validation errors

Each agent type has required fields. The validator in `AgentConfig._validate_by_type` checks these:

| Type | Required fields |
|------|----------------|
| `llm` | `model`, `instruction` |
| `code` | `function`, `output_key` |
| `tool` | `tool`, `output_key` |
| `expr` | `expression`, `output_key` |
| `sequential` / `parallel` / `loop` | `sub_agents` |

**Fix:** Add the missing required field to the agent config.

### Orchestration validation errors

| Error | Cause | Fix |
|-------|-------|-----|
| "requires a non-empty 'agents' list" | sequential/parallel/loop missing `agents` | Add `agents: [name1, name2]` |
| "requires the 'agent' field" | react missing `agent` | Add `agent: agent_name` |
| "requires a non-empty 'nodes' list" | dag missing `nodes` | Add `nodes` with agent/depends_on |
| "requires the 'router' field" | llm_routed missing `router` | Add `router: router_agent_name` |

### Cross-reference validation errors

**"Orchestration references unknown agent 'X'"** — An agent name in the orchestration section doesn't match any name in the agents list.

Diagnosis checklist:
1. Check for typos in agent names
2. Verify the `agents` list and `orchestration.agents` / `orchestration.nodes` reference the same names
3. Names are case-sensitive

```yaml
agents:
  - name: fetcher      # defined as "fetcher"
    type: llm
    ...

orchestration:
  type: sequential
  agents: [Fetcher]    # WRONG — capital F, should be "fetcher"
```

### DAG-specific validation errors

**"Unknown dependency 'X' in DAG node 'Y'"** — A `depends_on` references a node that doesn't exist.

**"DAG contains a cycle"** — Circular dependency detected. Check `depends_on` chains for loops:
```yaml
# This is a cycle: A -> B -> C -> A
nodes:
  - agent: A
    depends_on: [C]
  - agent: B
    depends_on: [A]
  - agent: C
    depends_on: [B]
```

## Stage 3: Hydration Errors

**Symptoms:** Errors during `WorkflowHydrator.hydrate()`, typically `KeyError` for tools or `ValueError` for expressions.

### "Unknown tool: 'X'"

A tool name in an agent's `tools` list or a ToolAgent's `tool` field doesn't match any registered platform tool.

Diagnosis:
```bash
# List all registered tools
pyflow list --tools
```

Check:
1. Is the tool name spelled correctly? Available: `http_request`, `transform`, `condition`, `alert`, `storage`, `ynab` (plus any custom tools)
2. If it's a custom tool, does the file exist in `pyflow/tools/`?
3. Does the custom tool class have `name = "exact_name"` as a class-level string?
4. Is the tool module importable? Try: `python -c "import pyflow.tools.<module_name>"`

### ExprAgent AST validation error

**"Access to 'X' is not allowed"** or **"Call to 'X' is not allowed"** — The expression uses forbidden constructs.

The sandbox blocks: imports, `getattr`/`setattr`/`delattr`, `globals`/`locals`/`vars`, dunder access (`__class__`, `__dict__`), `open`/`compile`/`breakpoint`.

Fix: Simplify the expression to use only safe builtins (`abs`, `all`, `any`, `bool`, `float`, `int`, `len`, `max`, `min`, `round`, `sorted`, `str`, `sum`, `tuple`, `list`). If you need more, use a `code` agent instead.

### LiteLLM import error

**"No module named 'google.adk.models.lite_llm'"** — Using an `anthropic/` or `openai/` model but `litellm` isn't installed.

Fix: `pip install litellm` or `pip install google-adk[extensions]`

### CodeAgent import error

**"Invalid function path"** or **"Function 'X' not found"** — The `function` field doesn't resolve.

Check:
1. Dotted path format: `module.submodule.function_name` (must have at least one dot)
2. Module is importable: `python -c "import module.submodule"`
3. Function exists in the module and is callable

## Stage 4: Runtime Errors

**Symptoms:** Workflow executes but produces wrong results, empty output, or agent error events.

### Agent error events

Error events contain `"XxxAgent error: ..."` in the content text and `state_delta={}`. Check the error message:

| Agent | Error prefix | Common causes |
|-------|-------------|---------------|
| CodeAgent | "CodeAgent error:" | Function raised exception, bad kwargs from state |
| ToolAgent | "ToolAgent error:" | Tool execution failed, template resolution failed |
| ExprAgent | "ExprAgent error:" | Division by zero, undefined variable, type mismatch, using builtins not in sandbox (e.g. `isinstance`) |

### ExprAgent silent failures

ExprAgent errors are easy to miss — the agent yields an error event with `state_delta={}`, so the `output_key` is never written to state. Downstream agents then fail with missing state keys.

**Common causes:**
- Using `isinstance()`, `type()`, `dict()`, `set()`, `range()`, `print()` — these are NOT in the safe builtins
- Fix: use `.get()` chains instead of `isinstance` checks, list comprehensions instead of `map()`/`filter()`

```yaml
# WRONG — isinstance not available
expression: "x if isinstance(data, dict) else None"

# RIGHT — use .get() to safely access dict keys
expression: "data.get('key', 'default')"
```

### LLM uses wrong date

The hydrator prepends `NOW: {current_datetime} ({timezone}).` to every LLM instruction automatically, and the executor injects the actual values into session state. If the agent still uses wrong dates:

1. Check `PYFLOW_TIMEZONE` in `.env` — wrong timezone = wrong "today"
2. The LLM may ignore the date prefix if the instruction is ambiguous — reinforce with explicit filtering guidance (e.g. "use since_date based on today's date")
3. Verify the session state injection by checking executor tests

### Rate limiting / ResourceExhausted

Large API responses (e.g. unfiltered YNAB transactions = 167KB) fill the LLM context. With multi-turn ReAct loops, token usage multiplies. Gemini's free tier has 1M tokens/min.

**Fix:** Instruct agents to ALWAYS filter data (e.g. `since_date` for transactions). Use PlanReAct instead of vanilla ReAct for data-heavy APIs — it plans filters before executing.

### Empty or missing output

**No final response text:**
1. Check that the last agent in the pipeline has `output_key` set
2. Check that the LLM agent actually produces output (instruction may be unclear)
3. For ReAct/PlanReAct agents, the final response may have multiple text parts — verify the executor joins all parts (not just `parts[0]`)

**State key missing between agents:**
1. Verify the producing agent has `output_key: key_name`
2. Verify the consuming agent references the same key:
   - LLM: `{key_name}` in `instruction`
   - expr/code: `key_name` in `input_keys`
   - tool: `{key_name}` in `tool_config` values

### Wrong data in state

Add a temporary `expr` agent to inspect state:
```yaml
- name: debug_state
  type: expr
  expression: "str(data)"      # converts state value to string for inspection
  input_keys: [data]           # the key you want to inspect
  output_key: debug_output
```

### Template resolution issues (ToolAgent)

`{variable}` in `tool_config` resolves from session state. If the variable doesn't exist in state, the literal string `{variable}` is passed through (not an error).

Check:
1. The producing agent actually wrote to state (has `output_key`)
2. The key name matches exactly (case-sensitive)
3. For type preservation: `"{key}"` (exact match) preserves the original type; `"prefix_{key}"` produces a string

## Diagnosis Flowchart

```
Error occurs
├── pyflow validate fails?
│   ├── YAML syntax error → Fix indentation, quoting, list format
│   ├── "requires 'field'" → Add missing required field for agent type
│   ├── "references unknown agent" → Fix agent name typo
│   └── "DAG contains a cycle" → Break circular depends_on
│
├── pyflow run fails at startup?
│   ├── "Unknown tool" → Check tool name, verify tool file exists
│   ├── "not allowed" in expr → Simplify expression or use code agent
│   ├── "Invalid function path" → Fix dotted path in code agent
│   └── LiteLLM import error → pip install litellm
│
├── Runs but wrong output?
│   ├── Empty result → Check output_key on final agent
│   ├── Wrong date → Check PYFLOW_TIMEZONE, reinforce date in instruction
│   ├── ResourceExhausted → Filter data (since_date), use PlanReAct
│   ├── Missing state between agents → Verify key names match
│   ├── Agent error event → Read error message, fix input data
│   └── Template not resolved → Check {variable} matches state key
│
└── Not sure which stage?
    └── Run: pyflow validate pyflow/agents/<name>/workflow.yaml
        ├── Passes → Problem is in hydration or runtime (stage 3-4)
        └── Fails → Problem is in parse or validation (stage 1-2)
```

## Quick Reference: Available Tools

```
http_request  — HTTP client with SSRF protection
transform     — JSONPath data extraction
condition     — Safe boolean expression evaluation
alert         — Webhook notifications
storage       — Local file read/write/append
ynab          — YNAB budget API (19 actions, requires PYFLOW_YNAB_API_TOKEN)
```

List custom tools: `pyflow list --tools`

## Quick Reference: Agent Types

```
llm         — LLM with instruction + tools (requires: model, instruction)
expr        — Safe Python expression       (requires: expression, output_key)
code        — Python function import       (requires: function, output_key)
tool        — Deterministic tool execution  (requires: tool, output_key)
sequential  — Run sub-agents in order      (requires: sub_agents)
parallel    — Run sub-agents concurrently  (requires: sub_agents)
loop        — Repeat sub-agents            (requires: sub_agents)
```

## Quick Reference: Orchestration Types

```
sequential  — Pipeline: A then B then C    (requires: agents)
parallel    — Fan-out: A, B, C at once     (requires: agents)
loop        — Repeat until done            (requires: agents; optional: max_iterations)
dag         — Dependency graph             (requires: nodes with depends_on)
react       — Reasoning + acting           (requires: agent; optional: planner)
llm_routed  — LLM delegates to specialists (requires: router, agents)
```
