# PyFlow

Agent platform powered by Google ADK. Workflows defined in YAML, auto-hydrated into ADK agent trees with self-registering tools.

## Commands

- `source .venv/bin/activate` — activate virtual environment (required before running anything)
- `pip install -e ".[dev]"` — install with dev dependencies
- `pytest -v` — run all 539 tests
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

- `pyflow/platform/app.py` — PyFlowPlatform orchestrator (boot with .env loading, shutdown, run_workflow lifecycle)
- `pyflow/platform/registry/tool_registry.py` — ToolRegistry: auto-discover + register tools (custom + OpenAPI)
- `pyflow/platform/registry/workflow_registry.py` — WorkflowRegistry: discover + hydrate YAML workflows
- `pyflow/platform/registry/discovery.py` — Filesystem scanner for agent packages
- `pyflow/platform/hydration/hydrator.py` — WorkflowHydrator: YAML -> Pydantic -> ADK Agent tree; `build_root_agent()` factory for agent packages
- `pyflow/platform/hydration/schema.py` — json_schema_to_pydantic: JSON Schema -> dynamic Pydantic models
- `pyflow/platform/executor.py` — WorkflowExecutor: builds Runner-per-run with ADK App, MetricsPlugin, datetime state via GlobalInstructionPlugin
- `pyflow/platform/a2a/cards.py` — AgentCardGenerator: generate A2A cards from workflow definitions (opt-in via `a2a:` section)
- `pyflow/tools/base.py` — BasePlatformTool ABC + auto-registration via `__init_subclass__`
- `pyflow/tools/http.py` — HttpTool (httpx, SSRF protection)
- `pyflow/tools/transform.py` — TransformTool (jsonpath-ng)
- `pyflow/tools/condition.py` — ConditionTool (AST-validated safe eval)
- `pyflow/tools/alert.py` — AlertTool (webhook notifications)
- `pyflow/tools/storage.py` — StorageTool (JSON file read/write/append)
- `pyflow/platform/openapi_auth.py` — resolve_openapi_auth: OpenAPI auth config to ADK auth scheme/credential
- `pyflow/models/workflow.py` — WorkflowDef (with openapi_tools), OrchestrationConfig, A2AConfig, RuntimeConfig, McpServerConfig
- `pyflow/platform/agents/expr_agent.py` — ExprAgent: inline safe Python expressions (AST-validated sandbox)
- `pyflow/models/agent.py` — AgentConfig (model, instruction, tools, description, schemas, generation config, agent_tools), OpenApiAuthConfig, OpenApiToolConfig
- `pyflow/models/tool.py` — ToolMetadata
- `pyflow/platform/callbacks.py` — FQN-based callback resolution via `importlib` (Python dotted paths like `mypackage.callbacks.log_request`)
- `pyflow/models/platform.py` — PlatformConfig (pydantic-settings BaseSettings, timezone, cors_origins, telemetry)
- `pyflow/cli.py` — Typer CLI (run, validate, list, init, serve)
- `pyflow/server.py` — FastAPI server with REST + A2A endpoints + optional CORS middleware
- `pyflow/config.py` — structlog configuration
- `agents/` — ADK-compatible agent packages (each with `__init__.py`, `agent.py`, `workflow.yaml`)
- `tests/` — mirrors source structure, pytest + pytest-asyncio

## Key Patterns

- Tools inherit from `BasePlatformTool` and auto-register via `__init_subclass__` — no manual registration needed
- Each tool defines `name`, `description` class vars + async `execute()` with typed parameters
- `as_function_tool()` converts any platform tool to an ADK `FunctionTool`
- Workflows are YAML with `agents` (each with `name`, `type`, `model`, `instruction`, `tools`, `output_key`, plus optional `description`, `include_contents`, `output_schema`, `input_schema`, `temperature`, `max_output_tokens`, `top_p`, `top_k`, `agent_tools`), `orchestration`, optional `openapi_tools` (workflow-level dict of named OpenAPI specs), and optional `a2a`. Agent types: `llm`, `sequential`, `parallel`, `loop`, `code`, `tool`, `expr`
- `expr` agents evaluate safe Python expressions inline (AST-validated, restricted builtins, no imports/IO) — reuses sandbox from ConditionTool
- WorkflowHydrator resolves tool name references against ToolRegistry and creates ADK agent trees
- Non-Gemini models (anthropic/, openai/) auto-wrapped with LiteLlm (lazy-loaded via `@lru_cache`)
- `output_schema`/`input_schema` in YAML are JSON Schema dicts, converted to Pydantic models at hydration time via `json_schema_to_pydantic()`
- `temperature`, `max_output_tokens`, `top_p`, `top_k` build a `GenerateContentConfig` passed to LlmAgent
- `description` on LLM agents is used by `llm_routed` orchestration for agent routing
- `include_contents: "none"` hides conversation history from an agent (isolated sub-tasks)
- `agent_tools` wraps referenced agents as ADK `AgentTool` for agent-as-tool composition
- Built-in tool catalog (lazy-imported from ADK): `exit_loop`, `google_search`, `google_maps_grounding`, `enterprise_web_search`, `url_context`, `load_memory`, `preload_memory`, `load_artifacts`, `get_user_choice`, `transfer_to_agent`
- FQN tool resolution: ToolRegistry falls back to `importlib` import for dotted names (e.g. `tools: ["http_request", "mypackage.tools.custom_search"]`)
- OrchestrationConfig supports `planner: builtin` with `planner_config: {thinking_budget: N}` for Gemini BuiltInPlanner
- A2A agent cards are generated at boot from `workflow.yaml` `a2a:` section (opt-in: only workflows with explicit `a2a:` get cards)
- Each agent package exports `root_agent` via `__init__.py` for ADK compatibility (`adk web`, `adk deploy`); `agent.py` uses `build_root_agent(__file__)` factory
- `WorkflowDef.from_yaml(path)` loads and validates YAML into Pydantic models
- Agent packages support standalone A2A deployment or monolith mode via `pyflow serve`
- `get_secret(name)` reads `PYFLOW_{NAME}` env var first, falls back to `_PLATFORM_SECRETS` dict. Tools use this for API tokens.
- PlatformConfig uses `pydantic-settings BaseSettings` — reads env vars with `PYFLOW_` prefix and `.env` files automatically
- `GlobalInstructionPlugin` injects `NOW: {current_datetime} ({timezone}).` into every LLM agent instruction at runtime — all agents are datetime-aware (moved from hydrator build-time to executor runtime via ADK plugin)
- Executor injects `{current_date}`, `{current_datetime}`, `{timezone}` into every session state
- Executor wraps agent in ADK `App` model (`Runner(app=app)` instead of `Runner(agent=agent)`) — unlocks context caching, event compaction, resumability, app-level plugins
- RuntimeConfig supports `context_cache_intervals/ttl/min_tokens` (Gemini 2.0+ context caching), `compaction_interval/overlap` (long conversation compaction), `resumable` (session resumability), `credential_service` (`in_memory` or `none`), `session_db_path` (SQLite path), `mcp_servers` (MCP server connections)
- `openapi_tools` on WorkflowDef: workflow-level dict of named OpenAPI specs with auth; ToolRegistry pre-builds `OpenAPIToolset` instances at boot, agents reference by name via `tools: [ynab]`
- Callbacks resolved via Python FQN (fully-qualified names) through `importlib` — e.g. `before_agent: "mypackage.callbacks.log_request"`. No manual registry needed
- Plugin registry includes 7 ADK plugins: `logging`, `debug_logging`, `reflect_and_retry`, `context_filter`, `save_files_as_artifacts`, `multimodal_tool_results`, `bigquery_analytics` (requires `PYFLOW_BQ_PROJECT_ID`/`PYFLOW_BQ_DATASET_ID` env vars)
- CORS middleware opt-in via `PlatformConfig.cors_origins` (env: `PYFLOW_CORS_ORIGINS`)
- `PYFLOW_TIMEZONE` env var configures timezone (defaults to system timezone detection via `/etc/localtime`)
- Platform auto-loads `.env` during `boot()` (ADK-aligned: walks from `workflows_dir` to root, preserves explicit env vars, respects `ADK_DISABLE_LOAD_DOTENV`). Disable via `PYFLOW_LOAD_DOTENV=false`

## Agent Packages

- `agents/example/` — simple sequential workflow (condition + transform tools, description + temperature)
- `agents/exchange_tracker/` — 7-step pipeline: LLM (output_schema) → code → expr → tool → expr → expr → LLM (temperature)
- `agents/budget_analyst/` — ReAct agent with PlanReAct planner, YNAB OpenAPI tools via `tools: [ynab]` (description, temperature, max_output_tokens)

Each package contains: `__init__.py`, `agent.py` (exports `root_agent` via `build_root_agent()` factory), `workflow.yaml` (definition + optional `a2a:` section for A2A discovery). Use `pyflow init <name>` to scaffold new packages.

## Testing

- 539 tests across 45 test files
- TDD: tests written before implementation for every module
- HTTP tests use `pytest-httpx` mocks (no real network calls)
- CLI tests use `typer.testing.CliRunner`
- Server tests use `httpx.ASGITransport` for in-process FastAPI testing
- Integration tests validate full platform boot + workflow hydration (no real LLM calls)

## Dependencies

- `google-adk>=1.26` — ADK runtime (App, Runner, Session, Agents, FunctionTool, Plugins)
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
- `PYFLOW_TELEMETRY_ENABLED` / `PYFLOW_TELEMETRY_EXPORT` — opt-in OpenTelemetry distributed tracing (`console`, `otlp`, `gcp`)
