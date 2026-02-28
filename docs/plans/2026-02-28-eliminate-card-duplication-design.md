# Eliminate Agent Card Duplication — Design

**Date:** 2026-02-28
**Status:** Approved

## Problem

Each agent package has duplicated metadata across multiple files:

1. **`agent-card.json` duplicates `workflow.yaml`**: name, description, and skills appear in both
2. **`agent.py` is identical boilerplate** across all 3 packages (23 lines each)
3. **`a2a:` section in YAML is parsed but never used** — the platform reads static JSON instead

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Card source of truth | `workflow.yaml` `a2a:` section | Single source, YAML is primary definition |
| Generation timing | Boot-time, cached in memory | One boot, always synced, zero JSON files |
| A2A opt-in | Explicit `a2a:` required | ADK pattern (`adk api_server` requires `agent.json`), least privilege |
| agent.py | Keep with factory function | ADK convention (`__init__.py` + `agent.py`), tooling compat |
| Well-known path | `/.well-known/agent-card.json` only | Current a2a-sdk v0.3+ standard |

## Design

### 1. Agent Card Generation from YAML

**Before:** `agent-card.json` → `load_card()` → `load_all()` → endpoint
**After:** `workflow.yaml` (a2a:) → `generate_card()` → cached in platform → endpoint

Changes to `AgentCardGenerator`:
- Remove `load_card()` and `load_all()` (no more JSON loading)
- Rename `generate_all()` → `generate_cards()` with opt-in filter
- `generate_cards()` only produces cards for workflows with `a2a:` present

```python
def generate_cards(self, workflows: list[WorkflowDef]) -> list[AgentCard]:
    """Generate cards for A2A-enabled workflows (those with a2a: section)."""
    return [self.generate_card(w) for w in workflows if w.a2a is not None]
```

Changes to `PyFlowPlatform`:
- In `boot()`, after hydration: `self._agent_cards = self._a2a.generate_cards(...)`
- `agent_cards()` returns cached list instead of reading JSON from disk

### 2. Factory Function for agent.py

New `build_root_agent()` in `pyflow/platform/hydration/hydrator.py`:

```python
def build_root_agent(caller_file: str) -> BaseAgent:
    """Build ADK root_agent from workflow.yaml next to caller_file."""
    workflow_path = Path(caller_file).parent / "workflow.yaml"
    tools = ToolRegistry()
    tools.discover()
    workflow = WorkflowDef.from_yaml(workflow_path)
    hydrator = WorkflowHydrator(tools)
    return hydrator.hydrate(workflow)
```

Each `agent.py` reduces from 23 lines to 3:

```python
"""package_name — ADK-compatible agent package."""
from pyflow.platform.hydration.hydrator import build_root_agent

root_agent = build_root_agent(__file__)
```

### 3. Scaffold Update (`pyflow init`)

- Update `_INIT_AGENT_PY` to use factory function
- Remove `_INIT_CARD_JSON` template entirely
- `init` command no longer generates `agent-card.json`

## Files Affected

| File | Action |
|------|--------|
| `agents/*/agent-card.json` (x3) | Delete |
| `agents/*/agent.py` (x3) | Simplify to 3 lines |
| `pyflow/platform/hydration/hydrator.py` | Add `build_root_agent()` |
| `pyflow/platform/a2a/cards.py` | Remove `load_card`/`load_all`, add filtered `generate_cards` |
| `pyflow/platform/app.py` | Cache cards in boot, simplify `agent_cards()` |
| `pyflow/cli.py` | Update scaffold templates, remove `_INIT_CARD_JSON` |
| `tests/platform/a2a/test_cards.py` | Remove load tests, add opt-in filter tests |

## Agent Package Structure (After)

```
agents/budget_analyst/
    __init__.py       # from .agent import root_agent
    agent.py          # root_agent = build_root_agent(__file__)
    workflow.yaml     # single source of truth (includes a2a: section)
```

## ADK Alignment

- Follows ADK's opt-in A2A pattern (only packages with explicit config get cards)
- Maintains ADK package convention (`__init__.py` + `agent.py` + `root_agent`)
- Aligned with `to_a2a()` pattern (generate at startup, serve from memory)
- Uses `/.well-known/agent-card.json` per a2a-sdk v0.3+ standard
