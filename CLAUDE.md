# PyFlow

Agent platform powered by Google ADK. Workflows defined in YAML, auto-hydrated into ADK agent trees with self-registering tools.

## Commands

- `source .venv/bin/activate` — activate virtual environment (required before running anything)
- `pip install -e ".[dev]"` — install with dev dependencies
- `pytest -v` — run all 221 tests
- `pyflow run <workflow_name>` — execute a workflow by name
- `pyflow validate <workflow.yaml>` — validate YAML syntax against WorkflowDef schema
- `pyflow list --tools` — list registered platform tools
- `pyflow list --workflows` — list discovered workflows
- `pyflow serve` — start FastAPI server on port 8000

## Environment

- Python 3.12 (requires >=3.11), macOS/Linux/Windows
- Virtual environment at `.venv/` — always activate before running commands
- `asyncio_mode = "auto"` in pytest config — async tests need no decorator

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
- `pyflow/platform/registry/discovery.py` — Filesystem scanner for tools/ and workflows/
- `pyflow/platform/hydration/hydrator.py` — WorkflowHydrator: YAML -> Pydantic -> ADK Agent tree
- `pyflow/platform/runner/engine.py` — PlatformRunner wrapping ADK Runner
- `pyflow/platform/session/service.py` — SessionManager wrapping ADK InMemorySessionService
- `pyflow/platform/a2a/cards.py` — AgentCardGenerator: auto-generate agent-card.json from registry
- `pyflow/tools/base.py` — BasePlatformTool ABC + auto-registration via `__init_subclass__`
- `pyflow/tools/http.py` — HttpTool (httpx, SSRF protection)
- `pyflow/tools/transform.py` — TransformTool (jsonpath-ng)
- `pyflow/tools/condition.py` — ConditionTool (AST-validated safe eval)
- `pyflow/tools/alert.py` — AlertTool (webhook notifications)
- `pyflow/tools/storage.py` — StorageTool (JSON file read/write/append)
- `pyflow/models/workflow.py` — WorkflowDef, AgentConfig, OrchestrationConfig, A2AConfig
- `pyflow/models/agent.py` — AgentConfig (model, instruction, tools ref)
- `pyflow/models/tool.py` — ToolMetadata, ToolConfig base, ToolResponse base
- `pyflow/models/platform.py` — PlatformConfig
- `pyflow/cli.py` — Typer CLI (run, validate, list, serve)
- `pyflow/server.py` — FastAPI server with REST + A2A endpoints
- `pyflow/config.py` — structlog configuration
- `workflows/` — YAML workflow definitions (auto-discovered on boot)
- `tests/` — mirrors source structure, pytest + pytest-asyncio

## Key Patterns

- Tools inherit from `BasePlatformTool` and auto-register via `__init_subclass__` — no manual registration needed
- Each tool defines `name`, `description`, `config_model`, `response_model` class vars + async `execute()`
- `as_function_tool()` converts any platform tool to an ADK `FunctionTool`
- Workflows are YAML with `agents` (each with `name`, `type`, `model`, `instruction`, `tools`, `output_key`), `orchestration`, and optional `a2a`
- WorkflowHydrator resolves tool name references against ToolRegistry and creates ADK agent trees
- Non-Gemini models (anthropic/, openai/) auto-wrapped with LiteLlm
- A2A agent cards auto-generated from workflow definitions with skills metadata

## Testing

- 221 tests across 20 test files
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
