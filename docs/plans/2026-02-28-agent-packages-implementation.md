# Agent Packages Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure workflows from flat YAML files into ADK-compatible agent packages, enabling standalone A2A deployment and `adk web` / `adk deploy` compatibility.

**Architecture:** Each workflow becomes a Python package under `pyflow/agents/` with `__init__.py`, `agent.py`, `agent-card.json`, and `workflow.yaml`. The platform discovery changes from scanning `workflows/*.yaml` to scanning `pyflow/agents/*/workflow.yaml`. Agent cards become static JSON files instead of being auto-generated at runtime.

**Tech Stack:** Python 3.12, Pydantic v2, PyYAML, Google ADK, pytest, Typer CLI

**Prereqs:** Always run `source /Users/camilopiedra/Development/pyflow/.venv/bin/activate` before any command.

---

### Task 1: Add `WorkflowDef.from_yaml()` class method

**Files:**
- Modify: `pyflow/models/workflow.py:124-171`
- Test: `tests/models/test_workflow.py`

**Step 1: Write the failing test**

In `tests/models/test_workflow.py`, add at the bottom:

```python
class TestFromYaml:
    def test_from_yaml_loads_valid_workflow(self, tmp_path: Path) -> None:
        """from_yaml() parses a YAML file into a WorkflowDef."""
        yaml_content = textwrap.dedent("""\
            name: test_wf
            description: A test workflow
            agents:
              - name: a1
                type: llm
                model: gemini-2.5-flash
                instruction: Do something
            orchestration:
              type: sequential
              agents: [a1]
        """)
        path = tmp_path / "workflow.yaml"
        path.write_text(yaml_content)

        wf = WorkflowDef.from_yaml(path)

        assert wf.name == "test_wf"
        assert wf.description == "A test workflow"
        assert len(wf.agents) == 1
        assert wf.orchestration.type == "sequential"

    def test_from_yaml_file_not_found(self, tmp_path: Path) -> None:
        """from_yaml() raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            WorkflowDef.from_yaml(tmp_path / "nonexistent.yaml")

    def test_from_yaml_invalid_yaml(self, tmp_path: Path) -> None:
        """from_yaml() raises ValidationError for invalid workflow YAML."""
        path = tmp_path / "bad.yaml"
        path.write_text("name: bad\n")
        with pytest.raises(ValidationError):
            WorkflowDef.from_yaml(path)
```

You will need to add `import textwrap` and `from pathlib import Path` to the test file imports if not already present.

**Step 2: Run test to verify it fails**

Run: `pytest tests/models/test_workflow.py::TestFromYaml -v`
Expected: FAIL — `WorkflowDef` has no attribute `from_yaml`

**Step 3: Write minimal implementation**

In `pyflow/models/workflow.py`, add to the imports:

```python
from pathlib import Path
import yaml
```

Add this classmethod to the `WorkflowDef` class (after the `_validate_orchestration_refs` method):

```python
    @classmethod
    def from_yaml(cls, path: Path) -> WorkflowDef:
        """Load and validate a YAML file into a WorkflowDef."""
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")
        data = yaml.safe_load(path.read_text())
        return cls(**data)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/models/test_workflow.py::TestFromYaml -v`
Expected: 3 PASS

**Step 5: Commit**

```bash
git add pyflow/models/workflow.py tests/models/test_workflow.py
git commit -m "feat: add WorkflowDef.from_yaml() class method"
```

---

### Task 2: Create agent package directories and move YAML files

**Files:**
- Create: `pyflow/agents/__init__.py`
- Create: `pyflow/agents/budget_analyst/__init__.py`
- Create: `pyflow/agents/budget_analyst/agent.py`
- Create: `pyflow/agents/budget_analyst/agent-card.json`
- Move: `workflows/budget_analyst.yaml` → `pyflow/agents/budget_analyst/workflow.yaml`
- Create: `pyflow/agents/exchange_tracker/__init__.py`
- Create: `pyflow/agents/exchange_tracker/agent.py`
- Create: `pyflow/agents/exchange_tracker/agent-card.json`
- Move: `workflows/exchange_tracker.yaml` → `pyflow/agents/exchange_tracker/workflow.yaml`
- Create: `pyflow/agents/example/__init__.py`
- Create: `pyflow/agents/example/agent.py`
- Create: `pyflow/agents/example/agent-card.json`
- Move: `workflows/example.yaml` → `pyflow/agents/example/workflow.yaml`

**Step 1: Create the directory structure**

```bash
mkdir -p pyflow/agents/budget_analyst pyflow/agents/exchange_tracker pyflow/agents/example
touch pyflow/agents/__init__.py
```

**Step 2: Move YAML files**

```bash
cp workflows/budget_analyst.yaml pyflow/agents/budget_analyst/workflow.yaml
cp workflows/exchange_tracker.yaml pyflow/agents/exchange_tracker/workflow.yaml
cp workflows/example.yaml pyflow/agents/example/workflow.yaml
```

Note: We `cp` instead of `mv` for now — the old `workflows/` dir stays until all references are updated. We'll remove it in the final cleanup task.

**Step 3: Create `__init__.py` for each agent package**

Each `__init__.py` follows the ADK convention:

`pyflow/agents/budget_analyst/__init__.py`:
```python
from .agent import root_agent
```

`pyflow/agents/exchange_tracker/__init__.py`:
```python
from .agent import root_agent
```

`pyflow/agents/example/__init__.py`:
```python
from .agent import root_agent
```

**Step 4: Create `agent.py` for each agent package**

All three follow the same template. Example for `pyflow/agents/budget_analyst/agent.py`:

```python
"""Budget Analyst — ADK-compatible agent package."""
from __future__ import annotations

from pathlib import Path

from pyflow.models.workflow import WorkflowDef
from pyflow.platform.hydration.hydrator import WorkflowHydrator
from pyflow.platform.registry.tool_registry import ToolRegistry

_WORKFLOW_PATH = Path(__file__).parent / "workflow.yaml"


def _build_agent():
    """Hydrate YAML workflow into an ADK agent tree."""
    tools = ToolRegistry()
    tools.discover()
    workflow = WorkflowDef.from_yaml(_WORKFLOW_PATH)
    hydrator = WorkflowHydrator(tools)
    return hydrator.hydrate(workflow)


root_agent = _build_agent()
```

For `exchange_tracker/agent.py` and `example/agent.py`, same content with adjusted docstring (e.g., `"""Exchange Tracker — ADK-compatible agent package."""`).

**Step 5: Create `agent-card.json` for each agent package**

`pyflow/agents/budget_analyst/agent-card.json`:
```json
{
  "name": "budget_analyst",
  "description": "Personal budget analyst powered by YNAB — answers natural language questions about your finances",
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

`pyflow/agents/exchange_tracker/agent-card.json`:
```json
{
  "name": "exchange_tracker",
  "description": "Track exchange rates between any currency pair and alert on thresholds",
  "url": "http://localhost:8000/a2a/exchange_tracker",
  "version": "1.0.0",
  "protocolVersion": "0.2.6",
  "capabilities": {},
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["application/json"],
  "skills": [
    {
      "id": "rate_tracking",
      "name": "Exchange Rate Tracking",
      "description": "Monitor exchange rates between any currency pair",
      "tags": ["finance", "monitoring", "forex"]
    }
  ]
}
```

`pyflow/agents/example/agent-card.json`:
```json
{
  "name": "example",
  "description": "Example workflow that processes data with condition checks",
  "url": "http://localhost:8000/a2a/example",
  "version": "1.0.0",
  "protocolVersion": "0.2.6",
  "capabilities": {},
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["application/json"],
  "skills": []
}
```

**Step 6: Commit**

```bash
git add pyflow/agents/
git commit -m "feat: create ADK-compatible agent packages for all workflows"
```

---

### Task 3: Update WorkflowRegistry to discover agent packages

**Files:**
- Modify: `pyflow/platform/registry/workflow_registry.py`
- Modify: `pyflow/platform/registry/discovery.py`
- Test: `tests/platform/registry/test_workflow_registry.py`
- Test: `tests/platform/registry/test_discovery.py`

**Step 1: Add `scan_agent_packages()` to discovery module — write failing test**

In `tests/platform/registry/test_discovery.py`, add:

```python
from pyflow.platform.registry.discovery import scan_agent_packages


def test_scan_agent_packages_finds_packages(tmp_path: Path) -> None:
    """scan_agent_packages() returns dirs containing workflow.yaml."""
    pkg1 = tmp_path / "agent_a"
    pkg1.mkdir()
    (pkg1 / "workflow.yaml").write_text("name: a\n")
    (pkg1 / "__init__.py").touch()

    pkg2 = tmp_path / "agent_b"
    pkg2.mkdir()
    (pkg2 / "workflow.yaml").write_text("name: b\n")
    (pkg2 / "__init__.py").touch()

    # Not a package (no workflow.yaml)
    notpkg = tmp_path / "not_a_package"
    notpkg.mkdir()
    (notpkg / "__init__.py").touch()

    result = scan_agent_packages(tmp_path)
    names = [p.name for p in result]
    assert names == ["agent_a", "agent_b"]
    assert "not_a_package" not in names


def test_scan_agent_packages_empty_dir(tmp_path: Path) -> None:
    """Empty directory returns empty list."""
    assert scan_agent_packages(tmp_path) == []


def test_scan_agent_packages_nonexistent(tmp_path: Path) -> None:
    """Nonexistent directory returns empty list."""
    assert scan_agent_packages(tmp_path / "missing") == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/platform/registry/test_discovery.py::test_scan_agent_packages_finds_packages -v`
Expected: FAIL — `cannot import name 'scan_agent_packages'`

**Step 3: Implement `scan_agent_packages()`**

In `pyflow/platform/registry/discovery.py`, add:

```python
def scan_agent_packages(path: Path) -> list[Path]:
    """Scan a directory for agent packages (subdirs containing workflow.yaml).

    Returns a sorted list of package directory Paths. If the directory does
    not exist, returns an empty list.
    """
    if not path.exists():
        return []
    return sorted(
        d for d in path.iterdir()
        if d.is_dir() and (d / "workflow.yaml").exists()
    )
```

**Step 4: Run discovery tests**

Run: `pytest tests/platform/registry/test_discovery.py -v`
Expected: All PASS (old tests + 3 new)

**Step 5: Update WorkflowRegistry.discover() — write failing test**

In `tests/platform/registry/test_workflow_registry.py`, add a new test:

```python
def test_discover_agent_packages(tmp_path: Path, registry: WorkflowRegistry) -> None:
    """discover() scans agent packages (dirs with workflow.yaml) when path contains them."""
    pkg = tmp_path / "test_pkg"
    pkg.mkdir()
    (pkg / "workflow.yaml").write_text(_VALID_WORKFLOW_YAML)
    (pkg / "__init__.py").touch()

    registry.discover(tmp_path)
    assert len(registry) == 1
    assert "test_workflow" in registry
```

**Step 6: Run test to verify current behavior**

Run: `pytest tests/platform/registry/test_workflow_registry.py::test_discover_agent_packages -v`
Expected: FAIL — current `discover()` looks for `*.yaml` in the dir, not in subdirs

**Step 7: Update `WorkflowRegistry.discover()` to support both layouts**

In `pyflow/platform/registry/workflow_registry.py`, update the `discover` method:

```python
from pyflow.platform.registry.discovery import scan_agent_packages, scan_directory

def discover(self, directory: Path) -> None:
    """Scan directory for workflow definitions.

    Supports two layouts:
    - Agent packages: directory/*/workflow.yaml (preferred)
    - Flat YAML: directory/*.yaml (legacy)
    """
    packages = scan_agent_packages(directory)
    if packages:
        for pkg_dir in packages:
            workflow_def = self._load_yaml(pkg_dir / "workflow.yaml")
            self._workflows[workflow_def.name] = HydratedWorkflow(definition=workflow_def)
    else:
        for yaml_path in scan_directory(directory, ".yaml"):
            workflow_def = self._load_yaml(yaml_path)
            self._workflows[workflow_def.name] = HydratedWorkflow(definition=workflow_def)
```

**Step 8: Run all workflow registry tests**

Run: `pytest tests/platform/registry/test_workflow_registry.py -v`
Expected: All PASS (old tests still pass because they use flat YAML layout as fallback)

**Step 9: Commit**

```bash
git add pyflow/platform/registry/discovery.py pyflow/platform/registry/workflow_registry.py tests/platform/registry/test_discovery.py tests/platform/registry/test_workflow_registry.py
git commit -m "feat: WorkflowRegistry discovers agent packages (agents/*/workflow.yaml)"
```

---

### Task 4: Refactor AgentCardGenerator to load static JSON

**Files:**
- Modify: `pyflow/platform/a2a/cards.py`
- Modify: `tests/platform/a2a/test_cards.py`

**Step 1: Write failing tests for file-based card loading**

In `tests/platform/a2a/test_cards.py`, add:

```python
import json
from pathlib import Path


class TestLoadCard:
    def test_load_card_from_json(self, tmp_path: Path) -> None:
        """load_card() reads agent-card.json from a package directory."""
        card_data = {
            "name": "test_agent",
            "description": "Test agent",
            "url": "http://localhost:8000/a2a/test_agent",
            "version": "1.0.0",
            "skills": [],
        }
        (tmp_path / "agent-card.json").write_text(json.dumps(card_data))

        gen = AgentCardGenerator()
        card = gen.load_card(tmp_path)

        assert isinstance(card, AgentCard)
        assert card.name == "test_agent"
        assert card.url == "http://localhost:8000/a2a/test_agent"

    def test_load_card_with_skills(self, tmp_path: Path) -> None:
        """load_card() deserializes skills from JSON."""
        card_data = {
            "name": "skilled_agent",
            "description": "Has skills",
            "url": "http://localhost:8000/a2a/skilled_agent",
            "version": "2.0.0",
            "skills": [
                {"id": "s1", "name": "Skill One", "description": "First", "tags": ["a"]},
            ],
        }
        (tmp_path / "agent-card.json").write_text(json.dumps(card_data))

        gen = AgentCardGenerator()
        card = gen.load_card(tmp_path)

        assert card.version == "2.0.0"
        assert len(card.skills) == 1
        assert card.skills[0].id == "s1"


class TestLoadAll:
    def test_load_all_from_agent_packages(self, tmp_path: Path) -> None:
        """load_all() loads cards from all agent package subdirs."""
        for name in ["agent_a", "agent_b"]:
            pkg = tmp_path / name
            pkg.mkdir()
            card_data = {"name": name, "description": f"Desc {name}", "url": f"http://localhost/{name}", "skills": []}
            (pkg / "agent-card.json").write_text(json.dumps(card_data))

        gen = AgentCardGenerator()
        cards = gen.load_all(tmp_path)

        assert len(cards) == 2
        assert [c.name for c in cards] == ["agent_a", "agent_b"]

    def test_load_all_skips_dirs_without_card(self, tmp_path: Path) -> None:
        """load_all() ignores subdirectories without agent-card.json."""
        pkg = tmp_path / "has_card"
        pkg.mkdir()
        (pkg / "agent-card.json").write_text(json.dumps({"name": "has_card", "description": "", "url": "http://x", "skills": []}))

        no_card = tmp_path / "no_card"
        no_card.mkdir()

        gen = AgentCardGenerator()
        cards = gen.load_all(tmp_path)
        assert len(cards) == 1
        assert cards[0].name == "has_card"

    def test_load_all_empty_dir(self, tmp_path: Path) -> None:
        """Empty directory returns empty list."""
        gen = AgentCardGenerator()
        assert gen.load_all(tmp_path) == []
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/platform/a2a/test_cards.py::TestLoadCard -v`
Expected: FAIL — `AgentCardGenerator` has no `load_card` method

**Step 3: Add `load_card()` and `load_all()` to AgentCardGenerator**

Replace `pyflow/platform/a2a/cards.py` content with:

```python
from __future__ import annotations

import json
from pathlib import Path

from pyflow.models.a2a import AgentCard
from pyflow.models.workflow import SkillDef, WorkflowDef


class AgentCardGenerator:
    """Loads A2A agent cards from static JSON files or generates from workflow definitions."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self._base_url = base_url.rstrip("/")

    # -- File-based loading (agent packages) ----------------------------------

    def load_card(self, package_dir: Path) -> AgentCard:
        """Load an agent card from a package directory's agent-card.json."""
        card_path = package_dir / "agent-card.json"
        data = json.loads(card_path.read_text())
        return AgentCard.model_validate(data)

    def load_all(self, agents_dir: Path) -> list[AgentCard]:
        """Load agent cards from all agent package subdirectories."""
        cards = []
        for package_dir in sorted(agents_dir.iterdir()):
            card_path = package_dir / "agent-card.json"
            if package_dir.is_dir() and card_path.exists():
                cards.append(self.load_card(package_dir))
        return cards

    # -- Generation from WorkflowDef (legacy, kept for backward compat) -------

    def generate_card(self, workflow: WorkflowDef) -> AgentCard:
        """Generate an A2A agent card for a single workflow."""
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

    def generate_all(self, workflows: list[WorkflowDef]) -> list[AgentCard]:
        """Generate agent cards for all workflows."""
        return [self.generate_card(w) for w in workflows]
```

**Step 4: Run all card tests**

Run: `pytest tests/platform/a2a/test_cards.py -v`
Expected: All PASS (old generation tests + new loading tests)

**Step 5: Commit**

```bash
git add pyflow/platform/a2a/cards.py tests/platform/a2a/test_cards.py
git commit -m "feat: AgentCardGenerator loads static agent-card.json files"
```

---

### Task 5: Update AgentCard model for JSON field names

**Files:**
- Modify: `pyflow/models/a2a.py`
- Test: `tests/models/test_a2a_models.py`

The `agent-card.json` files use camelCase keys (`protocolVersion`, `defaultInputModes`) per A2A spec, but the Pydantic model uses snake_case. We need to ensure `model_validate()` can parse camelCase JSON.

**Step 1: Write failing test**

In `tests/models/test_a2a_models.py`, add:

```python
class TestAgentCardJsonParsing:
    def test_parse_camel_case_json(self) -> None:
        """AgentCard parses camelCase JSON keys from agent-card.json files."""
        data = {
            "name": "test",
            "description": "desc",
            "url": "http://localhost:8000/a2a/test",
            "version": "1.0.0",
            "protocolVersion": "0.2.6",
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["application/json"],
            "skills": [],
        }
        card = AgentCard.model_validate(data)
        assert card.protocol_version == "0.2.6"
        assert card.default_input_modes == ["text/plain"]
        assert card.default_output_modes == ["application/json"]
```

**Step 2: Run test**

Run: `pytest tests/models/test_a2a_models.py::TestAgentCardJsonParsing -v`
Expected: FAIL — `protocolVersion` not recognized (Pydantic expects `protocol_version`)

**Step 3: Add `populate_by_name=True` alias config to AgentCard**

In `pyflow/models/a2a.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from pyflow.models.workflow import SkillDef


class AgentCard(BaseModel):
    """A2A protocol agent card -- describes agent capabilities for discovery."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str = ""
    url: str
    version: str = "1.0.0"
    protocol_version: str = Field(default="0.2.6", alias="protocolVersion")
    capabilities: dict = {}
    default_input_modes: list[str] = Field(default=["text/plain"], alias="defaultInputModes")
    default_output_modes: list[str] = Field(default=["application/json"], alias="defaultOutputModes")
    supports_authenticated_extended_card: bool = Field(default=False, alias="supportsAuthenticatedExtendedCard")
    skills: list[SkillDef] = []
```

**Step 4: Run all a2a model tests**

Run: `pytest tests/models/test_a2a_models.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add pyflow/models/a2a.py tests/models/test_a2a_models.py
git commit -m "feat: AgentCard supports camelCase JSON aliases for A2A spec"
```

---

### Task 6: Update PyFlowPlatform to use agent packages

**Files:**
- Modify: `pyflow/platform/app.py`
- Modify: `pyflow/models/platform.py`
- Test: `tests/platform/test_app.py`

**Step 1: Update PlatformConfig default**

In `pyflow/models/platform.py`, change:
```python
workflows_dir: str = "pyflow/agents"  # was "workflows"
```

**Step 2: Write failing test for file-based agent_cards()**

In `tests/platform/test_app.py`, add:

```python
def test_agent_cards_loads_from_files() -> None:
    """agent_cards() delegates to load_all() for file-based cards."""
    p = _make_booted_platform()

    fake_card = AgentCard(name="test", url="http://localhost:8000/a2a/test")
    p._a2a.load_all = MagicMock(return_value=[fake_card])

    result = p.agent_cards()

    p._a2a.load_all.assert_called_once_with(Path(p.config.workflows_dir))
    assert len(result) == 1
    assert result[0].name == "test"
```

**Step 3: Run test to verify it fails**

Run: `pytest tests/platform/test_app.py::test_agent_cards_loads_from_files -v`
Expected: FAIL — `agent_cards()` still calls `generate_all()`, not `load_all()`

**Step 4: Update `PyFlowPlatform.agent_cards()`**

In `pyflow/platform/app.py`, change the `agent_cards` method:

```python
def agent_cards(self) -> list[AgentCard]:
    """Load A2A agent cards from agent package directories."""
    self._ensure_booted()
    return self._a2a.load_all(Path(self.config.workflows_dir))
```

**Step 5: Update the old delegation test**

The existing `test_agent_cards_delegates_to_generator` test calls `generate_all()` which is now legacy. Update it to test the new behavior, or remove it and keep only the new test. Replace it with:

```python
def test_agent_cards_delegates_to_generator() -> None:
    """agent_cards() loads from files via load_all()."""
    p = _make_booted_platform()

    fake_card = AgentCard(name="test", url="http://localhost:8000/a2a/test")
    p._a2a.load_all = MagicMock(return_value=[fake_card])

    result = p.agent_cards()

    p._a2a.load_all.assert_called_once_with(Path(p.config.workflows_dir))
    assert len(result) == 1
    assert isinstance(result[0], AgentCard)
    assert result[0].name == "test"
```

**Step 6: Run all app tests**

Run: `pytest tests/platform/test_app.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add pyflow/platform/app.py pyflow/models/platform.py tests/platform/test_app.py
git commit -m "feat: PyFlowPlatform uses agent packages and file-based agent cards"
```

---

### Task 7: Update CLI default paths

**Files:**
- Modify: `pyflow/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Update CLI default `--workflows-dir` values**

In `pyflow/cli.py`, change all `--workflows-dir` defaults from `"workflows"` to `"pyflow/agents"`:

- `run` command: line 24 `workflows_dir: str = typer.Option("pyflow/agents", ...)`
- `list_cmd` command: line 74 `workflows_dir: str = typer.Option("pyflow/agents", ...)`
- `serve` command: line 101 `workflows_dir: str = typer.Option("pyflow/agents", ...)`

**Step 2: Run CLI tests**

Run: `pytest tests/test_cli.py -v`
Expected: All PASS (tests use mocked platform, not real paths)

**Step 3: Commit**

```bash
git add pyflow/cli.py
git commit -m "chore: update CLI default workflows-dir to pyflow/agents"
```

---

### Task 8: Add `pyflow init` CLI command

**Files:**
- Modify: `pyflow/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write failing test**

In `tests/test_cli.py`, add:

```python
class TestInitCommand:
    def test_init_creates_agent_package(self, tmp_path: Path) -> None:
        """init command scaffolds a new agent package directory."""
        result = runner.invoke(app, ["init", "my_agent", "--agents-dir", str(tmp_path)])
        assert result.exit_code == 0

        pkg = tmp_path / "my_agent"
        assert pkg.is_dir()
        assert (pkg / "__init__.py").exists()
        assert (pkg / "agent.py").exists()
        assert (pkg / "agent-card.json").exists()
        assert (pkg / "workflow.yaml").exists()

    def test_init_existing_package_fails(self, tmp_path: Path) -> None:
        """init command fails if package directory already exists."""
        (tmp_path / "existing").mkdir()
        result = runner.invoke(app, ["init", "existing", "--agents-dir", str(tmp_path)])
        assert result.exit_code == 1
        assert "already exists" in result.output
```

You'll need to add `from pathlib import Path` to the test file imports.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::TestInitCommand -v`
Expected: FAIL — no `init` command

**Step 3: Implement `init` command**

In `pyflow/cli.py`, add:

```python
_INIT_AGENT_PY = '''\
"""{name} — ADK-compatible agent package."""
from __future__ import annotations

from pathlib import Path

from pyflow.models.workflow import WorkflowDef
from pyflow.platform.hydration.hydrator import WorkflowHydrator
from pyflow.platform.registry.tool_registry import ToolRegistry

_WORKFLOW_PATH = Path(__file__).parent / "workflow.yaml"


def _build_agent():
    """Hydrate YAML workflow into an ADK agent tree."""
    tools = ToolRegistry()
    tools.discover()
    workflow = WorkflowDef.from_yaml(_WORKFLOW_PATH)
    hydrator = WorkflowHydrator(tools)
    return hydrator.hydrate(workflow)


root_agent = _build_agent()
'''

_INIT_WORKFLOW_YAML = '''\
name: {name}
description: "{name} workflow"

agents:
  - name: main
    type: llm
    model: gemini-2.5-flash
    instruction: "You are a helpful assistant."
    output_key: result

orchestration:
  type: sequential
  agents: [main]

runtime:
  session_service: in_memory
'''

_INIT_CARD_JSON = '''\
{{
  "name": "{name}",
  "description": "{name} workflow",
  "url": "http://localhost:8000/a2a/{name}",
  "version": "1.0.0",
  "protocolVersion": "0.2.6",
  "capabilities": {{}},
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["application/json"],
  "skills": []
}}
'''


@app.command()
def init(
    name: str = typer.Argument(help="Name for the new agent package"),
    agents_dir: str = typer.Option("pyflow/agents", "--agents-dir", help="Agents directory"),
) -> None:
    """Scaffold a new agent package."""
    pkg_dir = Path(agents_dir) / name
    if pkg_dir.exists():
        typer.echo(f"Package already exists: {pkg_dir}", err=True)
        raise typer.Exit(code=1)

    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("from .agent import root_agent\n")
    (pkg_dir / "agent.py").write_text(_INIT_AGENT_PY.format(name=name))
    (pkg_dir / "workflow.yaml").write_text(_INIT_WORKFLOW_YAML.format(name=name))
    (pkg_dir / "agent-card.json").write_text(_INIT_CARD_JSON.format(name=name))
    typer.echo(f"Created agent package: {pkg_dir}")
```

**Step 4: Run init tests**

Run: `pytest tests/test_cli.py::TestInitCommand -v`
Expected: All PASS

**Step 5: Run all CLI tests**

Run: `pytest tests/test_cli.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add pyflow/cli.py tests/test_cli.py
git commit -m "feat: add 'pyflow init' command to scaffold agent packages"
```

---

### Task 9: Update integration tests for new paths

**Files:**
- Modify: `tests/test_integration.py`

**Step 1: Update all integration tests**

All references to `PlatformConfig(workflows_dir="workflows")` need to change to `PlatformConfig(workflows_dir="pyflow/agents")`.

All references to `Path("workflows/...")` need to change to `Path("pyflow/agents/.../workflow.yaml")`.

Specifically:

1. `test_boot_discovers_tools` — change `workflows_dir="workflows"` → `workflows_dir="pyflow/agents"`
2. `test_boot_discovers_workflows` — same change
3. `test_workflow_hydration_creates_agents` — same change
4. `test_agent_cards_generated` — same change; this test will now need an `agent-card.json` in the package dir. Since we created them in Task 2, the test should load from those files
5. `test_platform_uses_workflow_executor` — change `workflows_dir="workflows"` → `workflows_dir="pyflow/agents"`
6. `test_validate_exchange_tracker_workflow` — change path to `Path("pyflow/agents/exchange_tracker/workflow.yaml")`
7. `test_validate_example_workflow` — change path to `Path("pyflow/agents/example/workflow.yaml")`
8. `test_exchange_tracker_has_runtime_config` — change path
9. `test_example_has_runtime_config` — change path
10. `test_runtime_config_hydrates_correctly` — change `workflows_dir`

**Step 2: Run integration tests**

Run: `pytest tests/test_integration.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: update integration tests for agent package paths"
```

---

### Task 10: Move workflow helpers into exchange_tracker package

**Files:**
- Move: `workflows/helpers/__init__.py` → `pyflow/agents/exchange_tracker/helpers.py`
- Modify: `pyflow/agents/exchange_tracker/workflow.yaml` (update function path)
- Test: run existing tests

**Step 1: Copy helper to package**

```bash
cp workflows/helpers/__init__.py pyflow/agents/exchange_tracker/helpers.py
```

**Step 2: Update function path in workflow.yaml**

In `pyflow/agents/exchange_tracker/workflow.yaml`, change the `parse_params` agent:
```yaml
  - name: parse_params
    type: code
    function: pyflow.agents.exchange_tracker.helpers.parse_currency_request
    input_keys: [parsed_input]
    output_key: params
```

Was: `workflows.helpers.parse_currency_request`

**Step 3: Run integration tests**

Run: `pytest tests/test_integration.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add pyflow/agents/exchange_tracker/helpers.py pyflow/agents/exchange_tracker/workflow.yaml
git commit -m "refactor: move workflow helpers into exchange_tracker package"
```

---

### Task 11: Remove old workflows/ directory and update server

**Files:**
- Delete: `workflows/` directory
- Modify: `pyflow/server.py` (if any hardcoded paths)
- Test: run full test suite

**Step 1: Verify no remaining references to old paths**

Search for `workflows_dir="workflows"` and `Path("workflows` in the codebase. All should have been updated in previous tasks.

**Step 2: Remove old workflows directory**

```bash
rm -rf workflows/
```

**Step 3: Run full test suite**

Run: `pytest -v`
Expected: All tests PASS (should be ~415+ tests with new ones added)

**Step 4: Commit**

```bash
git rm -r workflows/
git commit -m "chore: remove legacy workflows/ directory (migrated to pyflow/agents/)"
```

---

### Task 12: Update CLAUDE.md documentation

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update architecture section**

Replace references to `workflows/` with `pyflow/agents/`. Update the Architecture section to describe agent packages. Add the new `pyflow init` command. Update the Workflows section with new paths.

Key changes:
- `workflows/` → `pyflow/agents/` everywhere
- Add `pyflow/agents/` to Architecture section explaining ADK packages
- Add `pyflow init <name>` to Commands section
- Update Key Patterns to mention agent packages
- Update Workflows section with new paths
- Update Testing section if test count changed

**Step 2: Run `pytest -v` for final count**

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for agent packages architecture"
```

---

### Task 13: Final verification

**Step 1: Run full test suite**

Run: `pytest -v`
Expected: All tests PASS

**Step 2: Verify ADK compatibility**

Verify each agent package can export `root_agent`:
```python
python -c "from pyflow.agents.example import root_agent; print(root_agent.name)"
```
Expected: `example`

**Step 3: Verify CLI commands work**

```bash
pyflow list --workflows
pyflow validate pyflow/agents/example/workflow.yaml
pyflow init test_agent --agents-dir /tmp/test_agents
```

**Step 4: Clean up test agent**

```bash
rm -rf /tmp/test_agents
```
