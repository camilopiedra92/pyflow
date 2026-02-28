# Agent Packages Design — ADK-Compatible Workflow Structure

**Date:** 2026-02-28
**Status:** Proposed

## Problem

PyFlow workflows live in flat YAML files under `workflows/`. This doesn't align with Google ADK's recommended agent structure (`agent_name/__init__.py` + `agent.py` + `agent-card.json`), limiting:

- **A2A interoperability**: Can't use `to_a2a()` or `adk web` directly on a workflow
- **Independent deployment**: Workflows can't be deployed as standalone A2A services
- **Agent discovery**: Agent cards are auto-generated at runtime instead of being static, versionable artifacts
- **ADK tooling compatibility**: `adk web`, `adk deploy`, Agent Engine expect the package convention

## Decision

Restructure workflows from flat YAML files into **ADK-compatible agent packages**. Each workflow becomes a Python package with a `root_agent` export, an `agent-card.json`, and the YAML definition co-located.

## Architecture

### Directory Structure

```
pyflow/
├── agents/                              # ADK-compatible agent packages
│   ├── __init__.py                      # Package marker
│   ├── budget_analyst/
│   │   ├── __init__.py                  # from .agent import root_agent
│   │   ├── agent.py                     # Hydrates YAML, exports root_agent
│   │   ├── agent-card.json              # A2A discovery metadata (static, versioned)
│   │   └── workflow.yaml                # Workflow definition (moved from workflows/)
│   ├── exchange_tracker/
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── agent-card.json
│   │   └── workflow.yaml
│   └── example/
│       ├── __init__.py
│       ├── agent.py
│       ├── agent-card.json
│       └── workflow.yaml
├── platform/                            # Engine (minimal changes)
├── tools/                               # Shared tools (no changes)
└── models/                              # Pydantic models (no changes)
```

### Agent Package Contents

**`__init__.py`** — ADK entry point:
```python
from .agent import root_agent
```

**`agent.py`** — Hydrates YAML into ADK agent tree:
```python
from __future__ import annotations

from pathlib import Path

from pyflow.platform.hydration.hydrator import WorkflowHydrator
from pyflow.platform.registry.tool_registry import ToolRegistry
from pyflow.models.workflow import WorkflowDef

_WORKFLOW_PATH = Path(__file__).parent / "workflow.yaml"


def _build_agent():
    tools = ToolRegistry()
    tools.discover()
    workflow = WorkflowDef.from_yaml(_WORKFLOW_PATH)
    hydrator = WorkflowHydrator(tools)
    return hydrator.hydrate(workflow)


root_agent = _build_agent()
```

**`agent-card.json`** — Static A2A metadata (versioned in git):
```json
{
  "name": "budget_analyst",
  "description": "Personal budget analyst powered by YNAB",
  "url": "http://localhost:8000/a2a/budget_analyst",
  "version": "1.0.0",
  "protocolVersion": "0.2.6",
  "capabilities": {},
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["application/json"],
  "skills": [
    {
      "id": "budget_analysis",
      "name": "Budget Analysis",
      "description": "Analyze your YNAB budget — spending, balances, categories, and trends",
      "tags": ["finance", "budget", "ynab"]
    }
  ]
}
```

**`workflow.yaml`** — Existing YAML definition (moved from `workflows/`).

### Platform Changes

#### WorkflowDef — Add `from_yaml()` class method

```python
class WorkflowDef(BaseModel):
    @classmethod
    def from_yaml(cls, path: Path) -> WorkflowDef:
        data = yaml.safe_load(path.read_text())
        return cls(**data)
```

#### WorkflowRegistry — Discover agent packages

Change discovery from `workflows/*.yaml` to `agents/*/workflow.yaml`:

```python
def discover(self, directory: Path) -> None:
    for package_dir in sorted(directory.iterdir()):
        if package_dir.is_dir() and (package_dir / "workflow.yaml").exists():
            workflow_def = self._load_yaml(package_dir / "workflow.yaml")
            self._workflows[workflow_def.name] = HydratedWorkflow(definition=workflow_def)
```

#### AgentCardGenerator — Read static JSON instead of generating

```python
class AgentCardGenerator:
    def load_card(self, package_dir: Path) -> AgentCard:
        card_path = package_dir / "agent-card.json"
        return AgentCard.model_validate_json(card_path.read_text())

    def load_all(self, agents_dir: Path) -> list[AgentCard]:
        cards = []
        for package_dir in sorted(agents_dir.iterdir()):
            card_path = package_dir / "agent-card.json"
            if card_path.exists():
                cards.append(self.load_card(package_dir))
        return cards
```

#### PlatformConfig — Update default path

```python
class PlatformConfig(BaseSettings):
    workflows_dir: str = "agents"  # Changed from "workflows"
```

#### PyFlowPlatform.agent_cards() — Load from files

```python
def agent_cards(self) -> list[AgentCard]:
    agents_dir = Path(self.config.workflows_dir)
    return self._a2a.load_all(agents_dir)
```

#### CLI — New `pyflow init` command

```
pyflow init <name>    # Scaffold a new agent package
```

Creates:
```
agents/<name>/
├── __init__.py
├── agent.py
├── agent-card.json   # Skeleton with name filled in
└── workflow.yaml     # Minimal template
```

## Deployment Modes

### Monolith (current behavior preserved)

```bash
pyflow serve          # Discovers all packages in agents/, serves via single FastAPI
```

### Standalone A2A agent (new capability)

```bash
adk web pyflow/agents/budget_analyst    # Runs single agent via ADK dev server
adk deploy pyflow/agents/budget_analyst # Deploy to Agent Engine / Cloud Run
```

### Multi-agent A2A network (future)

```bash
# Agent 1: budget analyst on port 8001
adk web pyflow/agents/budget_analyst --port 8001

# Agent 2: exchange tracker on port 8002
adk web pyflow/agents/exchange_tracker --port 8002

# Root orchestrator discovers and delegates via A2A
adk web pyflow/agents/orchestrator --port 8000
```

## Migration

1. Create `pyflow/agents/` directory with `__init__.py`
2. For each existing workflow in `workflows/`:
   a. Create package directory under `agents/`
   b. Move `workflow.yaml` from `workflows/` to package
   c. Generate `__init__.py` and `agent.py` from template
   d. Generate `agent-card.json` from existing `a2a:` section in YAML (or skeleton if none)
3. Update `WorkflowRegistry.discover()` to scan `agents/*/workflow.yaml`
4. Add `WorkflowDef.from_yaml()` class method
5. Refactor `AgentCardGenerator` to load static JSON files
6. Update `PlatformConfig.workflows_dir` default to `"agents"`
7. Update `PyFlowPlatform.agent_cards()` to use file-based loading
8. Add `pyflow init` CLI command
9. Update all tests to use new paths
10. Remove old `workflows/` directory
11. Update CLAUDE.md with new architecture

## What Stays the Same

- YAML workflow definitions (structure and syntax unchanged)
- Hydrator logic (no changes)
- Executor logic (no changes)
- Tool system (no changes)
- All Pydantic models (only additions, no breaking changes)
- Session state threading between agents
- Internal agent types (llm, code, expr, tool, sequential, parallel, loop)

## Testing

- Existing 412 tests adapted to new discovery paths
- New tests for `WorkflowDef.from_yaml()`
- New tests for `AgentCardGenerator.load_card()` / `load_all()`
- New tests for `pyflow init` CLI command
- Integration test: verify `root_agent` is importable from each package
- Integration test: verify `adk web` compatibility (agent package loads correctly)
