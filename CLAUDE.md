# PyFlow

Config-driven workflow automation engine inspired by N8N. Workflows defined in YAML, executed as async DAGs.

## Commands

- `source .venv/Scripts/activate` — activate virtual environment (required before running anything)
- `pip install -e ".[dev]"` — install with dev dependencies
- `pytest -v` — run all 64 tests
- `pyflow run <workflow.yaml>` — execute a workflow
- `pyflow validate <workflow.yaml>` — validate YAML syntax
- `pyflow list [dir]` — list workflows in directory (default: `workflows/`)
- `pyflow serve [dir]` — start FastAPI server on port 8000

## Environment

- Python 3.12 (requires >=3.11), Windows 11, bash shell
- Virtual environment at `.venv/` — always activate before running commands
- Path contains spaces — always quote file paths in shell commands
- `asyncio_mode = "auto"` in pytest config — async tests need no decorator

## Code Style

- ruff for linting/formatting (line-length 100, target py311)
- Pydantic v2 models for data validation (`pyflow/core/models.py`)
- `from __future__ import annotations` in all modules
- async/await throughout the engine — nodes are async
- structlog for structured logging with ISO timestamps
- Conventional commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:`

## Architecture

- `pyflow/core/engine.py` — async DAG executor (topological sort, parallel execution, retry/skip/stop)
- `pyflow/core/models.py` — Pydantic models: WorkflowDef, NodeDef, TriggerDef, OnError
- `pyflow/core/context.py` — ExecutionContext (stores node results/errors per run)
- `pyflow/core/template.py` — Jinja2 template resolution for `{{ node_id.field }}` in configs
- `pyflow/core/loader.py` — YAML workflow loader (single file + directory scan)
- `pyflow/core/node.py` — BaseNode ABC + NodeRegistry (pluggable node types)
- `pyflow/nodes/` — built-in nodes: `http` (httpx), `transform` (jsonpath-ng), `condition` (eval)
- `pyflow/nodes/__init__.py` — `default_registry` with all built-in nodes pre-registered
- `pyflow/triggers/schedule.py` — APScheduler cron/interval triggers
- `pyflow/triggers/webhook.py` — webhook path configuration
- `pyflow/cli.py` — typer CLI (run, validate, list, serve)
- `pyflow/server.py` — FastAPI server (`/health`, `/workflows`, `/trigger/{name}`)
- `pyflow/config.py` — structlog configuration
- `tests/` — mirrors source structure, pytest + pytest-asyncio + pytest-httpx

## Key Patterns

- Nodes inherit from `BaseNode` and define `node_type` class var + async `execute(config, context)`
- Register new nodes via `default_registry.register(MyNode)` in `pyflow/nodes/__init__.py`
- Workflows are YAML with `trigger`, `nodes` (each with `id`, `type`, `config`, optional `depends_on`, `when`, `on_error`)
- `eval()` in ConditionNode and engine's `when` uses restricted builtins — no `__import__`, `exec`, `open`
- Template expressions `{{ node_id }}` resolve via Jinja2 StrictUndefined (missing vars raise errors)

## Testing

- 64 tests across 14 test files
- TDD: tests written before implementation for every module
- HTTP tests use `pytest-httpx` mocks (no real network calls except integration)
- CLI tests use `typer.testing.CliRunner`
- Server tests use `httpx.ASGITransport` for in-process FastAPI testing
