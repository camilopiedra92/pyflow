# PyFlow

Agent platform powered by Google ADK. Workflows defined in YAML, auto-hydrated into ADK agent trees with self-registering tools.

## Commands

- `source .venv/bin/activate` — activate virtual environment (required before running anything)
- `pip install -e ".[dev]"` — install with dev dependencies
- `pytest -v` — run all 476 tests
- `pyflow run <workflow_name>` — execute a workflow by name
- `pyflow validate <workflow.yaml>` — validate YAML syntax against WorkflowDef schema
- `pyflow list --tools` — list registered platform tools
- `pyflow list --workflows` — list discovered workflows
- `pyflow init <name>` — scaffold a new agent package under `agents/`
- `pyflow serve` — start FastAPI server on port 8000

## Environment

- Python 3.12 (requires >=3.11), macOS/Linux/Windows
- Virtual environment at `.venv/` — always activate before running commands
- `asyncio_mode = "auto"` in pytest config — async tests need no decorator
- `.env` for local secrets (gitignored) — copy from `.env.example`

## Git Strategy (GitHub Flow)

- Main branch: `main` — always stable, all tests pass
- All work happens in feature branches: `feat/`, `fix/`, `test/`, `docs/`, `chore/`
- Branch naming matches conventional commits: `feat/add-cache-tool`, `fix/hydrator-edge-case`
- Every feature branch merges to `main` via PR — no direct pushes to `main`
- Delete feature branches after merge
- Never work directly on `main` — always create a branch first

## Code Style

- ruff for linting/formatting (line-length 100, target py311)
- Pydantic v2 models for data validation (`pyflow/models/`)
- `from __future__ import annotations` in all modules
- async/await throughout the platform — tools and runner are async
- structlog for structured logging with ISO timestamps
- Conventional commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:`

## Architecture

- `pyflow/platform/app.py` — PyFlowPlatform orchestrator (boot, shutdown, run_workflow lifecycle)
- `pyflow/platform/registry/tool_registry.py` — ToolRegistry: auto-discover + register tools
- `pyflow/platform/registry/workflow_registry.py` — WorkflowRegistry: discover + hydrate YAML workflows
- `pyflow/platform/registry/discovery.py` — Filesystem scanner for tools and agent packages
- `pyflow/platform/hydration/hydrator.py` — WorkflowHydrator: YAML -> Pydantic -> ADK Agent tree
- `pyflow/platform/hydration/schema.py` — json_schema_to_pydantic: JSON Schema -> dynamic Pydantic models
- `pyflow/platform/executor.py` — WorkflowExecutor: builds ADK Runner, injects datetime state into sessions
- `pyflow/platform/a2a/cards.py` — AgentCardGenerator: load static agent-card.json from agent packages
- `pyflow/tools/base.py` — BasePlatformTool ABC + auto-registration via `__init_subclass__`
- `pyflow/tools/http.py` — HttpTool (httpx, SSRF protection)
- `pyflow/tools/transform.py` — TransformTool (jsonpath-ng)
- `pyflow/tools/condition.py` — ConditionTool (AST-validated safe eval)
- `pyflow/tools/alert.py` — AlertTool (webhook notifications)
- `pyflow/tools/storage.py` — StorageTool (JSON file read/write/append)
- `pyflow/tools/ynab.py` — YnabTool (YNAB budget API: budgets, accounts, categories, payees, transactions)
- `pyflow/models/workflow.py` — WorkflowDef, OrchestrationConfig, A2AConfig, RuntimeConfig
- `pyflow/platform/agents/expr_agent.py` — ExprAgent: inline safe Python expressions (AST-validated sandbox)
- `pyflow/models/agent.py` — AgentConfig (model, instruction, tools, description, schemas, generation config, agent_tools)
- `pyflow/models/tool.py` — ToolMetadata
- `pyflow/models/platform.py` — PlatformConfig (pydantic-settings BaseSettings, timezone)
- `pyflow/cli.py` — Typer CLI (run, validate, list, init, serve)
- `pyflow/server.py` — FastAPI server with REST + A2A endpoints
- `pyflow/config.py` — structlog configuration
- `agents/` — ADK-compatible agent packages (each with `__init__.py`, `agent.py`, `agent-card.json`, `workflow.yaml`)
- `tests/` — mirrors source structure, pytest + pytest-asyncio

## Key Patterns

- Tools inherit from `BasePlatformTool` and auto-register via `__init_subclass__` — no manual registration needed
- Each tool defines `name`, `description` class vars + async `execute()` with typed parameters
- `as_function_tool()` converts any platform tool to an ADK `FunctionTool`
- Workflows are YAML with `agents` (each with `name`, `type`, `model`, `instruction`, `tools`, `output_key`, plus optional `description`, `include_contents`, `output_schema`, `input_schema`, `temperature`, `max_output_tokens`, `top_p`, `top_k`, `agent_tools`), `orchestration`, and optional `a2a`. Agent types: `llm`, `sequential`, `parallel`, `loop`, `code`, `tool`, `expr`
- `expr` agents evaluate safe Python expressions inline (AST-validated, restricted builtins, no imports/IO) — reuses sandbox from ConditionTool
- WorkflowHydrator resolves tool name references against ToolRegistry and creates ADK agent trees
- Non-Gemini models (anthropic/, openai/) auto-wrapped with LiteLlm (lazy-loaded via `@lru_cache`)
- `output_schema`/`input_schema` in YAML are JSON Schema dicts, converted to Pydantic models at hydration time via `json_schema_to_pydantic()`
- `temperature`, `max_output_tokens`, `top_p`, `top_k` build a `GenerateContentConfig` passed to LlmAgent
- `description` on LLM agents is used by `llm_routed` orchestration for agent routing
- `include_contents: "none"` hides conversation history from an agent (isolated sub-tasks)
- `agent_tools` wraps referenced agents as ADK `AgentTool` for agent-as-tool composition
- Built-in tool catalog: `exit_loop`, `google_search`, `load_memory` (lazy-imported from ADK)
- OrchestrationConfig supports `planner: builtin` with `planner_config: {thinking_budget: N}` for Gemini BuiltInPlanner
- A2A agent cards are static JSON files (`agent-card.json`) in each agent package, loaded at boot
- Each agent package exports `root_agent` via `__init__.py` for ADK compatibility (`adk web`, `adk deploy`)
- `WorkflowDef.from_yaml(path)` loads and validates YAML into Pydantic models
- Agent packages support standalone A2A deployment or monolith mode via `pyflow serve`
- `get_secret(name)` reads `PYFLOW_{NAME}` env var first, falls back to `_PLATFORM_SECRETS` dict. Tools use this for API tokens.
- PlatformConfig uses `pydantic-settings BaseSettings` — reads env vars with `PYFLOW_` prefix and `.env` files automatically
- Hydrator prepends `NOW: {current_datetime} ({timezone}).` to every LLM agent instruction automatically — all agents are datetime-aware
- Executor injects `{current_date}`, `{current_datetime}`, `{timezone}` into every session state
- `PYFLOW_TIMEZONE` env var configures timezone (defaults to system timezone detection via `/etc/localtime`)

## Agent Packages

- `agents/example/` — simple sequential workflow (condition + transform tools, description + temperature)
- `agents/exchange_tracker/` — 7-step pipeline: LLM (output_schema) → code → expr → tool → expr → expr → LLM (temperature)
- `agents/budget_analyst/` — ReAct agent with PlanReAct planner, YNAB tool (description, temperature, max_output_tokens)

Each package contains: `__init__.py`, `agent.py` (exports `root_agent`), `agent-card.json` (A2A metadata), `workflow.yaml` (definition). Use `pyflow init <name>` to scaffold new packages.

## Testing

- 476 tests across 35 test files
- TDD: tests written before implementation for every module
- HTTP tests use `pytest-httpx` mocks (no real network calls)
- CLI tests use `typer.testing.CliRunner`
- Server tests use `httpx.ASGITransport` for in-process FastAPI testing
- Integration tests validate full platform boot + workflow hydration (no real LLM calls)

## Dependencies

- `google-adk>=1.25` — ADK runtime (Runner, Session, Agents, FunctionTool)
- `pydantic>=2.0` — data validation and models
- `pyyaml>=6.0` — YAML workflow parsing
- `httpx>=0.27` — HTTP client for tools and tests
- `fastapi>=0.115` — REST + A2A API server
- `uvicorn>=0.30` — ASGI server
- `typer>=0.12` — CLI framework
- `structlog>=24.0` — structured logging
- `jsonpath-ng>=1.6` — JSONPath transforms
- `litellm>=1.0` (optional) — multi-provider LLM support (Anthropic, OpenAI)
- `pydantic-settings>=2.0` — env var and .env config loading (BaseSettings)
- `python-dotenv` — .env file loading for CLI (transitive via pydantic-settings)
