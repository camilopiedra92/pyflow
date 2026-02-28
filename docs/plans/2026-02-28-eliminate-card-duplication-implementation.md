# Eliminate Agent Card Duplication — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate duplicated metadata across agent packages by generating A2A cards from YAML at boot and replacing boilerplate `agent.py` with a factory function.

**Architecture:** `workflow.yaml` becomes the single source of truth for A2A metadata. Cards are generated at boot time and cached in `PyFlowPlatform`. A `build_root_agent()` factory replaces identical boilerplate across all agent packages.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, Google ADK

---

### Task 1: Refactor AgentCardGenerator — remove JSON loading, add opt-in filtering

**Files:**
- Modify: `tests/platform/a2a/test_cards.py`
- Modify: `pyflow/platform/a2a/cards.py`

**Step 1: Write failing tests for `generate_cards()` with opt-in filtering**

Add these tests at the end of `tests/platform/a2a/test_cards.py`, after the existing `TestCardStructure` class (line 150):

```python
class TestGenerateCards:
    """generate_cards() filters workflows by a2a presence (opt-in)."""

    def test_only_workflows_with_a2a_generate_cards(self) -> None:
        """Workflows without a2a: section are excluded."""
        gen = AgentCardGenerator()
        wf_with_a2a = _minimal_workflow("with_a2a", a2a=A2AConfig(skills=[]))
        wf_without_a2a = _minimal_workflow("without_a2a")

        cards = gen.generate_cards([wf_with_a2a, wf_without_a2a])

        assert len(cards) == 1
        assert cards[0].name == "with_a2a"

    def test_empty_list_returns_empty(self) -> None:
        gen = AgentCardGenerator()
        assert gen.generate_cards([]) == []

    def test_all_without_a2a_returns_empty(self) -> None:
        gen = AgentCardGenerator()
        workflows = [_minimal_workflow(f"wf_{i}") for i in range(3)]
        assert gen.generate_cards(workflows) == []

    def test_all_with_a2a_returns_all(self) -> None:
        gen = AgentCardGenerator()
        workflows = [
            _minimal_workflow(f"wf_{i}", a2a=A2AConfig()) for i in range(3)
        ]
        cards = gen.generate_cards(workflows)
        assert len(cards) == 3
        assert [c.name for c in cards] == ["wf_0", "wf_1", "wf_2"]
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/platform/a2a/test_cards.py::TestGenerateCards -v`
Expected: FAIL — `AgentCardGenerator` has no `generate_cards` method

**Step 3: Implement `generate_cards()` and remove JSON loading methods**

Replace `pyflow/platform/a2a/cards.py` entirely with:

```python
from __future__ import annotations

from pyflow.models.a2a import AgentCard
from pyflow.models.workflow import SkillDef, WorkflowDef


class AgentCardGenerator:
    """Generates A2A agent cards from workflow definitions."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self._base_url = base_url.rstrip("/")

    def generate_card(self, workflow: WorkflowDef) -> AgentCard:
        """Build an AgentCard from a WorkflowDef."""
        skills: list[SkillDef] = []
        if workflow.a2a and workflow.a2a.skills:
            skills = list(workflow.a2a.skills)

        return AgentCard(
            name=workflow.name,
            description=workflow.description,
            url=f"{self._base_url}/a2a/{workflow.name}",
            version=workflow.a2a.version if workflow.a2a else "1.0.0",
            skills=skills,
        )

    def generate_cards(self, workflows: list[WorkflowDef]) -> list[AgentCard]:
        """Generate cards for A2A-enabled workflows (those with a2a: section)."""
        return [self.generate_card(w) for w in workflows if w.a2a is not None]
```

**Step 4: Remove obsolete load tests from test file**

Delete `TestLoadCard` class (lines 152-189) and `TestLoadAll` class (lines 192-231) and `TestGenerateAll` class (lines 97-110) from `tests/platform/a2a/test_cards.py`. Also remove the `import json` at line 3 (no longer needed).

**Step 5: Run all card tests to verify everything passes**

Run: `source .venv/bin/activate && pytest tests/platform/a2a/test_cards.py -v`
Expected: All tests PASS (existing generate tests + new generate_cards tests)

**Step 6: Commit**

```bash
git add pyflow/platform/a2a/cards.py tests/platform/a2a/test_cards.py
git commit -m "refactor: replace JSON card loading with opt-in generate_cards()

Remove load_card/load_all (static JSON), add generate_cards() that
filters workflows by a2a: presence. YAML is now single source of truth
for A2A agent cards."
```

---

### Task 2: Update PyFlowPlatform — cache cards at boot

**Files:**
- Modify: `tests/platform/test_app.py`
- Modify: `pyflow/platform/app.py`

**Step 1: Update existing test for `agent_cards()` delegation**

Replace `test_agent_cards_delegates_to_generator` (lines 187-199 in `tests/platform/test_app.py`) with:

```python
def test_agent_cards_returns_cached_cards() -> None:
    """agent_cards() returns cards cached during boot."""
    p = _make_booted_platform()
    fake_card = AgentCard(name="test", url="http://localhost:8000/a2a/test")
    p._agent_cards = [fake_card]

    result = p.agent_cards()

    assert len(result) == 1
    assert result[0].name == "test"
```

**Step 2: Add test that boot generates and caches cards**

Add after the `test_boot_sets_booted_flag` test (after line 89):

```python
@pytest.mark.asyncio
async def test_boot_generates_agent_cards() -> None:
    """boot() generates and caches A2A agent cards from workflows."""
    p = PyFlowPlatform(PlatformConfig(load_dotenv=False))

    p.tools.discover = MagicMock()
    p.workflows.discover = MagicMock()
    p.workflows.hydrate = MagicMock()
    p.workflows.list_workflows = MagicMock(return_value=[])

    await p.boot()

    assert p._agent_cards == []
```

**Step 3: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/platform/test_app.py::test_agent_cards_returns_cached_cards tests/platform/test_app.py::test_boot_generates_agent_cards -v`
Expected: FAIL — `_agent_cards` attribute doesn't exist

**Step 4: Update `PyFlowPlatform`**

In `pyflow/platform/app.py`:

1. Add `self._agent_cards: list[AgentCard] = []` in `__init__` (after line 83)

2. Add card generation step at end of `boot()` (after line 109, before `self._booted = True`):
```python
        # 4. Generate A2A agent cards from workflows with a2a: section
        self._agent_cards = self._a2a.generate_cards(self.workflows.list_workflows())
        log.info("a2a.cards_generated", count=len(self._agent_cards))
```

3. Replace `agent_cards()` method (lines 147-150):
```python
    def agent_cards(self) -> list[AgentCard]:
        """Return A2A agent cards generated at boot from workflow definitions."""
        self._ensure_booted()
        return self._agent_cards
```

4. Remove `json` and `Path` imports from `from pathlib import Path` (line 5) if no longer used by other code. Check first — `Path` is still used in `boot()` line 103, so keep it. Remove only the unused import if any.

**Step 5: Run all platform tests**

Run: `source .venv/bin/activate && pytest tests/platform/test_app.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add pyflow/platform/app.py tests/platform/test_app.py
git commit -m "refactor: cache A2A cards at boot instead of reading JSON

Platform generates cards from workflows during boot() and caches them.
agent_cards() now returns cached list instead of reading from disk."
```

---

### Task 3: Add `build_root_agent()` factory function

**Files:**
- Create: `tests/platform/hydration/test_build_root_agent.py`
- Modify: `pyflow/platform/hydration/hydrator.py`

**Step 1: Write failing test for `build_root_agent()`**

Create `tests/platform/hydration/test_build_root_agent.py`:

```python
"""Tests for the build_root_agent factory function."""
from __future__ import annotations

from pathlib import Path

from pyflow.platform.hydration.hydrator import build_root_agent


class TestBuildRootAgent:
    def test_builds_agent_from_workflow_yaml(self, tmp_path: Path) -> None:
        """build_root_agent() hydrates workflow.yaml next to the caller file."""
        yaml_content = """\
name: test_factory
description: "Factory test workflow"
agents:
  - name: main
    type: llm
    model: gemini-2.5-flash
    instruction: "You are helpful."
    output_key: result
orchestration:
  type: sequential
  agents: [main]
"""
        (tmp_path / "workflow.yaml").write_text(yaml_content)
        fake_caller = tmp_path / "agent.py"
        fake_caller.touch()

        agent = build_root_agent(str(fake_caller))

        assert agent.name == "test_factory"

    def test_raises_on_missing_yaml(self, tmp_path: Path) -> None:
        """build_root_agent() raises if workflow.yaml is missing."""
        import pytest

        fake_caller = tmp_path / "agent.py"
        fake_caller.touch()

        with pytest.raises(FileNotFoundError):
            build_root_agent(str(fake_caller))
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/platform/hydration/test_build_root_agent.py -v`
Expected: FAIL — `build_root_agent` not found in module

**Step 3: Add `build_root_agent()` to hydrator module**

Add at the end of `pyflow/platform/hydration/hydrator.py` (after line 294):

```python
def build_root_agent(caller_file: str) -> BaseAgent:
    """Build an ADK root_agent from the workflow.yaml next to caller_file.

    Convenience factory for agent packages — replaces identical boilerplate
    across all packages with a single function call.

    Usage in agent packages::

        from pyflow.platform.hydration.hydrator import build_root_agent
        root_agent = build_root_agent(__file__)
    """
    from pyflow.platform.registry.tool_registry import ToolRegistry

    workflow_path = Path(caller_file).parent / "workflow.yaml"
    tools = ToolRegistry()
    tools.discover()
    workflow = WorkflowDef.from_yaml(workflow_path)
    hydrator = WorkflowHydrator(tools)
    return hydrator.hydrate(workflow)
```

Note: `ToolRegistry` import is inside the function to avoid circular imports (hydrator.py is imported by tool_registry indirectly). `Path` is already imported at the top. `WorkflowDef` is already imported.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/platform/hydration/test_build_root_agent.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add pyflow/platform/hydration/hydrator.py tests/platform/hydration/test_build_root_agent.py
git commit -m "feat: add build_root_agent() factory for agent packages

Convenience function that replaces identical boilerplate across all
agent packages. Usage: root_agent = build_root_agent(__file__)"
```

---

### Task 4: Simplify agent.py files in all 3 packages

**Files:**
- Modify: `agents/example/agent.py`
- Modify: `agents/budget_analyst/agent.py`
- Modify: `agents/exchange_tracker/agent.py`

**Step 1: Replace all 3 agent.py files**

`agents/example/agent.py`:
```python
"""example — ADK-compatible agent package."""
from pyflow.platform.hydration.hydrator import build_root_agent

root_agent = build_root_agent(__file__)
```

`agents/budget_analyst/agent.py`:
```python
"""budget_analyst — ADK-compatible agent package."""
from pyflow.platform.hydration.hydrator import build_root_agent

root_agent = build_root_agent(__file__)
```

`agents/exchange_tracker/agent.py`:
```python
"""exchange_tracker — ADK-compatible agent package."""
from pyflow.platform.hydration.hydrator import build_root_agent

root_agent = build_root_agent(__file__)
```

**Step 2: Run full test suite to verify nothing broke**

Run: `source .venv/bin/activate && pytest -v`
Expected: All 482+ tests PASS

**Step 3: Commit**

```bash
git add agents/example/agent.py agents/budget_analyst/agent.py agents/exchange_tracker/agent.py
git commit -m "refactor: replace agent.py boilerplate with build_root_agent() factory

Each agent.py reduces from 23 lines to 3 lines using the shared factory."
```

---

### Task 5: Update CLI scaffold — remove agent-card.json template

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `pyflow/cli.py`

**Step 1: Update init tests**

In `tests/test_cli.py`, modify `TestInitCommand`:

1. In `test_init_creates_agent_package` (line 157), remove the assertion `assert (pkg / "agent-card.json").exists()` (line 166).

2. Delete `test_init_card_is_valid_json` test entirely (lines 187-194) — no card file generated.

3. Add a new test to verify agent.py uses factory:

```python
    def test_init_agent_uses_factory(self, tmp_path: Path) -> None:
        """init command creates agent.py that uses build_root_agent factory."""
        runner.invoke(app, ["init", "test_agent", "--agents-dir", str(tmp_path)])
        agent_py = (tmp_path / "test_agent" / "agent.py").read_text()
        assert "build_root_agent" in agent_py
        assert "root_agent = build_root_agent(__file__)" in agent_py
```

**Step 2: Run init tests to verify failures**

Run: `source .venv/bin/activate && pytest tests/test_cli.py::TestInitCommand -v`
Expected: FAIL — old template still generates agent-card.json

**Step 3: Update CLI templates**

In `pyflow/cli.py`:

1. Replace `_INIT_AGENT_PY` (lines 16-39) with:
```python
_INIT_AGENT_PY = '''\
"""{name} — ADK-compatible agent package."""
from pyflow.platform.hydration.hydrator import build_root_agent

root_agent = build_root_agent(__file__)
'''
```

2. Delete `_INIT_CARD_JSON` template entirely (lines 60-72).

3. In the `init` command (line 184), remove the line:
```python
    (pkg_dir / "agent-card.json").write_text(_INIT_CARD_JSON.format(name=name))
```

**Step 4: Run init tests**

Run: `source .venv/bin/activate && pytest tests/test_cli.py::TestInitCommand -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add pyflow/cli.py tests/test_cli.py
git commit -m "refactor: update scaffold to use factory, remove agent-card.json template

pyflow init no longer generates agent-card.json. agent.py uses
build_root_agent() factory instead of inline boilerplate."
```

---

### Task 6: Delete static agent-card.json files

**Files:**
- Delete: `agents/example/agent-card.json`
- Delete: `agents/budget_analyst/agent-card.json`
- Delete: `agents/exchange_tracker/agent-card.json`

**Step 1: Delete the files**

```bash
rm agents/example/agent-card.json
rm agents/budget_analyst/agent-card.json
rm agents/exchange_tracker/agent-card.json
```

**Step 2: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`
Expected: All tests PASS — no code references these files anymore

**Step 3: Commit**

```bash
git add -u agents/
git commit -m "chore: delete static agent-card.json files

Cards are now generated from workflow.yaml a2a: section at boot time."
```

---

### Task 7: Update server test and run final verification

**Files:**
- Review: `tests/test_server.py` (likely no changes needed — mocked)

**Step 1: Check server test still passes**

Run: `source .venv/bin/activate && pytest tests/test_server.py::TestA2A -v`
Expected: PASS — test mocks `platform.agent_cards()` return value

**Step 2: Run full test suite as final verification**

Run: `source .venv/bin/activate && pytest -v`
Expected: All tests PASS

**Step 3: Verify test count**

Confirm test count is reasonable:
- Removed: ~9 tests (6 load tests + 3 generate_all tests + 1 init card test)
- Added: ~6 tests (4 generate_cards + 2 build_root_agent)
- Net: ~3 fewer tests, but all remaining tests exercise the new architecture

**Step 4: Final commit if any cleanup needed**

Only if there were unexpected test adjustments.
