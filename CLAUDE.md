# PyFlow

Config-driven workflow automation engine. Workflows defined in YAML, executed as async DAGs.

## Commands

- `pip install -e ".[dev]"` — install with dev dependencies
- `pytest -v` — run tests
- `pyflow run <workflow.yaml>` — execute a workflow
- `pyflow validate <workflow.yaml>` — validate YAML syntax
- `pyflow list [dir]` — list workflows in directory
- `pyflow serve [dir]` — start API server

## Environment

- Python 3.11+, Windows 11, bash shell
- Path contains spaces — always quote file paths in shell commands
- asyncio_mode = "auto" in pytest config

## Code Style

- ruff for linting/formatting (line-length 100, target py311)
- Pydantic v2 models for validation
- async/await throughout the engine
- structlog for logging

## Architecture

- `pyflow/core/` — engine, models, context, loader, templates
- `pyflow/nodes/` — built-in node types (http, transform, condition)
- `pyflow/triggers/` — schedule and webhook triggers
- `pyflow/cli.py` — typer CLI
- `pyflow/server.py` — FastAPI server
- `tests/` — mirrors source structure, pytest + pytest-asyncio
