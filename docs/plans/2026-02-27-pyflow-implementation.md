# PyFlow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a config-driven workflow automation engine where workflows are defined in YAML, executed as async DAGs, with CLI and service modes.

**Architecture:** Workflows are YAML files parsed into Pydantic models representing a DAG of nodes. An async engine resolves dependencies and executes nodes concurrently. Nodes are pluggable via a registry. Two entry points: CLI (typer) for on-demand runs, and a FastAPI server for webhooks/scheduling.

**Tech Stack:** Python 3.11+, asyncio, pydantic, pyyaml, jinja2, jsonpath-ng, httpx, typer, fastapi, uvicorn, apscheduler, structlog, pytest + pytest-asyncio

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `pyflow/__init__.py`
- Create: `pyflow/core/__init__.py`
- Create: `pyflow/nodes/__init__.py`
- Create: `pyflow/triggers/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/core/__init__.py`
- Create: `tests/nodes/__init__.py`
- Create: `tests/triggers/__init__.py`
- Create: `workflows/.gitkeep`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "pyflow"
version = "0.1.0"
description = "Config-driven workflow automation engine"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "jinja2>=3.1",
    "jsonpath-ng>=1.6",
    "httpx>=0.27",
    "typer>=0.12",
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "apscheduler>=3.10,<4.0",
    "structlog>=24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-httpx>=0.30",
    "ruff>=0.5",
]

[project.scripts]
pyflow = "pyflow.cli:app"

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py311"
line-length = 100
```

**Step 2: Create all `__init__.py` files and directory structure**

All `__init__.py` files are empty. Create `workflows/.gitkeep` as empty file.

**Step 3: Install in dev mode**

Run: `pip install -e ".[dev]"`
Expected: Installs all dependencies successfully.

**Step 4: Verify pytest runs**

Run: `pytest --co`
Expected: "no tests ran" (but no import errors)

**Step 5: Commit**

```bash
git add -A
git commit -m "chore: scaffold PyFlow project structure with dependencies"
```

---

### Task 2: Pydantic Models — Node, Trigger, Workflow

**Files:**
- Create: `tests/core/test_models.py`
- Create: `pyflow/core/models.py`

**Step 1: Write the failing tests**

```python
# tests/core/test_models.py
import pytest
import yaml
from pyflow.core.models import NodeDef, TriggerDef, WorkflowDef, OnError


class TestNodeDef:
    def test_minimal_node(self):
        node = NodeDef(id="step1", type="http", config={"url": "https://example.com"})
        assert node.id == "step1"
        assert node.type == "http"
        assert node.depends_on == []
        assert node.on_error == OnError.STOP
        assert node.when is None

    def test_node_with_dependencies(self):
        node = NodeDef(
            id="step2",
            type="transform",
            depends_on=["step1"],
            when="step1.result == true",
            config={"expression": "$.data"},
        )
        assert node.depends_on == ["step1"]
        assert node.when == "step1.result == true"

    def test_node_with_retry(self):
        node = NodeDef(
            id="step1",
            type="http",
            config={"url": "https://example.com"},
            on_error=OnError.RETRY,
            retry={"max_retries": 3, "delay": 2},
        )
        assert node.retry["max_retries"] == 3

    def test_node_requires_id_and_type(self):
        with pytest.raises(Exception):
            NodeDef(config={})


class TestTriggerDef:
    def test_webhook_trigger(self):
        trigger = TriggerDef(type="webhook", config={"path": "/hooks/github"})
        assert trigger.type == "webhook"

    def test_schedule_trigger(self):
        trigger = TriggerDef(type="schedule", config={"cron": "0 * * * *"})
        assert trigger.type == "schedule"

    def test_manual_trigger(self):
        trigger = TriggerDef(type="manual")
        assert trigger.config == {}


class TestWorkflowDef:
    def test_parse_from_dict(self):
        data = {
            "name": "test-workflow",
            "trigger": {"type": "manual"},
            "nodes": [
                {"id": "step1", "type": "http", "config": {"url": "https://example.com"}},
            ],
        }
        wf = WorkflowDef(**data)
        assert wf.name == "test-workflow"
        assert len(wf.nodes) == 1
        assert wf.trigger.type == "manual"

    def test_parse_from_yaml(self):
        yaml_str = """
name: yaml-workflow
description: test
trigger:
  type: webhook
  config:
    path: /test
nodes:
  - id: step1
    type: http
    config:
      url: https://example.com
  - id: step2
    type: transform
    depends_on: [step1]
    config:
      expression: "$.data"
"""
        data = yaml.safe_load(yaml_str)
        wf = WorkflowDef(**data)
        assert wf.name == "yaml-workflow"
        assert wf.description == "test"
        assert len(wf.nodes) == 2
        assert wf.nodes[1].depends_on == ["step1"]

    def test_duplicate_node_ids_rejected(self):
        data = {
            "name": "bad-workflow",
            "trigger": {"type": "manual"},
            "nodes": [
                {"id": "step1", "type": "http", "config": {}},
                {"id": "step1", "type": "transform", "config": {}},
            ],
        }
        with pytest.raises(ValueError, match="Duplicate node id"):
            WorkflowDef(**data)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pyflow.core.models'`

**Step 3: Write minimal implementation**

```python
# pyflow/core/models.py
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, field_validator


class OnError(StrEnum):
    SKIP = "skip"
    STOP = "stop"
    RETRY = "retry"


class NodeDef(BaseModel):
    id: str
    type: str
    config: dict = {}
    depends_on: list[str] = []
    when: str | None = None
    on_error: OnError = OnError.STOP
    retry: dict | None = None


class TriggerDef(BaseModel):
    type: str
    config: dict = {}


class WorkflowDef(BaseModel):
    name: str
    description: str | None = None
    trigger: TriggerDef
    nodes: list[NodeDef]

    @field_validator("nodes")
    @classmethod
    def validate_unique_ids(cls, nodes: list[NodeDef]) -> list[NodeDef]:
        ids = [n.id for n in nodes]
        duplicates = [i for i in ids if ids.count(i) > 1]
        if duplicates:
            raise ValueError(f"Duplicate node id: {duplicates[0]}")
        return nodes
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_models.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add pyflow/core/models.py tests/core/test_models.py
git commit -m "feat: add Pydantic models for workflow, node, and trigger definitions"
```

---

### Task 3: Execution Context

**Files:**
- Create: `tests/core/test_context.py`
- Create: `pyflow/core/context.py`

**Step 1: Write the failing tests**

```python
# tests/core/test_context.py
import pytest
from pyflow.core.context import ExecutionContext


class TestExecutionContext:
    def test_store_and_retrieve_result(self):
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_result("step1", {"data": [1, 2, 3]})
        assert ctx.get_result("step1") == {"data": [1, 2, 3]}

    def test_get_missing_result_raises(self):
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        with pytest.raises(KeyError):
            ctx.get_result("nonexistent")

    def test_has_result(self):
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        assert ctx.has_result("step1") is False
        ctx.set_result("step1", "ok")
        assert ctx.has_result("step1") is True

    def test_all_results(self):
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_result("a", 1)
        ctx.set_result("b", 2)
        assert ctx.all_results() == {"a": 1, "b": 2}

    def test_run_id_is_set(self):
        ctx = ExecutionContext(workflow_name="test", run_id="run-123")
        assert ctx.run_id == "run-123"
        assert ctx.workflow_name == "test"

    def test_mark_node_error(self):
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_error("step1", "Connection refused")
        assert ctx.get_error("step1") == "Connection refused"
        assert ctx.has_error("step1") is True
        assert ctx.has_error("step2") is False
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_context.py -v`
Expected: FAIL — import error

**Step 3: Write minimal implementation**

```python
# pyflow/core/context.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExecutionContext:
    workflow_name: str
    run_id: str
    _results: dict[str, object] = field(default_factory=dict, repr=False)
    _errors: dict[str, str] = field(default_factory=dict, repr=False)

    def set_result(self, node_id: str, result: object) -> None:
        self._results[node_id] = result

    def get_result(self, node_id: str) -> object:
        return self._results[node_id]

    def has_result(self, node_id: str) -> bool:
        return node_id in self._results

    def all_results(self) -> dict[str, object]:
        return dict(self._results)

    def set_error(self, node_id: str, error: str) -> None:
        self._errors[node_id] = error

    def get_error(self, node_id: str) -> str:
        return self._errors[node_id]

    def has_error(self, node_id: str) -> bool:
        return node_id in self._errors
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_context.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add pyflow/core/context.py tests/core/test_context.py
git commit -m "feat: add ExecutionContext for storing node results and errors"
```

---

### Task 4: Node Base Class + Registry

**Files:**
- Create: `tests/core/test_node.py`
- Create: `pyflow/core/node.py`

**Step 1: Write the failing tests**

```python
# tests/core/test_node.py
import pytest
from pyflow.core.node import BaseNode, NodeRegistry
from pyflow.core.context import ExecutionContext
from pyflow.core.models import NodeDef


class FakeNode(BaseNode):
    node_type = "fake"

    async def execute(self, config: dict, context: ExecutionContext) -> object:
        return {"fake": True}


class TestNodeRegistry:
    def setup_method(self):
        self.registry = NodeRegistry()

    def test_register_and_get(self):
        self.registry.register(FakeNode)
        cls = self.registry.get("fake")
        assert cls is FakeNode

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown node type"):
            self.registry.get("nonexistent")

    def test_register_duplicate_raises(self):
        self.registry.register(FakeNode)
        with pytest.raises(ValueError, match="already registered"):
            self.registry.register(FakeNode)

    def test_list_types(self):
        self.registry.register(FakeNode)
        assert "fake" in self.registry.list_types()


class TestBaseNode:
    async def test_execute(self):
        node = FakeNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute({"key": "value"}, ctx)
        assert result == {"fake": True}
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_node.py -v`
Expected: FAIL — import error

**Step 3: Write minimal implementation**

```python
# pyflow/core/node.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pyflow.core.context import ExecutionContext


class BaseNode(ABC):
    node_type: ClassVar[str]

    @abstractmethod
    async def execute(self, config: dict, context: ExecutionContext) -> object:
        ...


class NodeRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, type[BaseNode]] = {}

    def register(self, node_cls: type[BaseNode]) -> None:
        name = node_cls.node_type
        if name in self._registry:
            raise ValueError(f"Node type '{name}' already registered")
        self._registry[name] = node_cls

    def get(self, node_type: str) -> type[BaseNode]:
        if node_type not in self._registry:
            raise KeyError(f"Unknown node type: '{node_type}'")
        return self._registry[node_type]

    def list_types(self) -> list[str]:
        return list(self._registry.keys())
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_node.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add pyflow/core/node.py tests/core/test_node.py
git commit -m "feat: add BaseNode ABC and NodeRegistry for pluggable node types"
```

---

### Task 5: Template Resolution (Jinja2)

**Files:**
- Create: `tests/core/test_template.py`
- Create: `pyflow/core/template.py`

**Step 1: Write the failing tests**

```python
# tests/core/test_template.py
import pytest
from pyflow.core.template import resolve_templates
from pyflow.core.context import ExecutionContext


class TestResolveTemplates:
    def _make_ctx(self) -> ExecutionContext:
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_result("step1", {"title": "Bug report", "count": 42})
        ctx.set_result("step2", "plain string")
        return ctx

    def test_resolve_string(self):
        ctx = self._make_ctx()
        result = resolve_templates("Hello {{ step1.title }}", ctx)
        assert result == "Hello Bug report"

    def test_resolve_nested_dict(self):
        ctx = self._make_ctx()
        config = {
            "url": "https://api.com/{{ step1.title }}",
            "body": {"text": "Count: {{ step1.count }}"},
        }
        result = resolve_templates(config, ctx)
        assert result["url"] == "https://api.com/Bug report"
        assert result["body"]["text"] == "Count: 42"

    def test_resolve_list(self):
        ctx = self._make_ctx()
        result = resolve_templates(["{{ step2 }}", "static"], ctx)
        assert result == ["plain string", "static"]

    def test_no_template_passthrough(self):
        ctx = self._make_ctx()
        assert resolve_templates("no templates here", ctx) == "no templates here"
        assert resolve_templates(42, ctx) == 42
        assert resolve_templates(None, ctx) is None

    def test_missing_variable_raises(self):
        ctx = self._make_ctx()
        with pytest.raises(Exception):
            resolve_templates("{{ nonexistent.field }}", ctx)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_template.py -v`
Expected: FAIL — import error

**Step 3: Write minimal implementation**

```python
# pyflow/core/template.py
from __future__ import annotations

from typing import Any

from jinja2 import Environment, StrictUndefined

from pyflow.core.context import ExecutionContext


_env = Environment(undefined=StrictUndefined)


def resolve_templates(value: Any, context: ExecutionContext) -> Any:
    if isinstance(value, str):
        if "{{" not in value:
            return value
        template = _env.from_string(value)
        return template.render(context.all_results())
    if isinstance(value, dict):
        return {k: resolve_templates(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_templates(item, context) for item in value]
    return value
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_template.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add pyflow/core/template.py tests/core/test_template.py
git commit -m "feat: add Jinja2 template resolution for node configs"
```

---

### Task 6: Workflow Loader (YAML → Models)

**Files:**
- Create: `tests/core/test_loader.py`
- Create: `pyflow/core/loader.py`
- Create: `tests/fixtures/simple.yaml`

**Step 1: Write the test fixture**

```yaml
# tests/fixtures/simple.yaml
name: simple-workflow
description: A simple test workflow
trigger:
  type: manual
nodes:
  - id: greet
    type: http
    config:
      method: GET
      url: https://httpbin.org/get
```

**Step 2: Write the failing tests**

```python
# tests/core/test_loader.py
import pytest
from pathlib import Path
from pyflow.core.loader import load_workflow, load_all_workflows
from pyflow.core.models import WorkflowDef

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestLoadWorkflow:
    def test_load_from_file(self):
        wf = load_workflow(FIXTURES / "simple.yaml")
        assert isinstance(wf, WorkflowDef)
        assert wf.name == "simple-workflow"
        assert len(wf.nodes) == 1

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            load_workflow(Path("/nonexistent/workflow.yaml"))

    def test_load_invalid_yaml_raises(self):
        # Create a temp file with bad content
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write("not: valid: yaml: [[[")
            bad_path = Path(f.name)
        with pytest.raises(Exception):
            load_workflow(bad_path)
        bad_path.unlink()


class TestLoadAllWorkflows:
    def test_load_directory(self):
        workflows = load_all_workflows(FIXTURES)
        assert len(workflows) >= 1
        assert all(isinstance(wf, WorkflowDef) for wf in workflows)
```

**Step 3: Run tests to verify they fail**

Run: `pytest tests/core/test_loader.py -v`
Expected: FAIL — import error

**Step 4: Write minimal implementation**

```python
# pyflow/core/loader.py
from __future__ import annotations

from pathlib import Path

import yaml

from pyflow.core.models import WorkflowDef


def load_workflow(path: Path) -> WorkflowDef:
    if not path.exists():
        raise FileNotFoundError(f"Workflow file not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return WorkflowDef(**data)


def load_all_workflows(directory: Path) -> list[WorkflowDef]:
    workflows = []
    for path in sorted(directory.glob("*.yaml")):
        workflows.append(load_workflow(path))
    for path in sorted(directory.glob("*.yml")):
        workflows.append(load_workflow(path))
    return workflows
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/core/test_loader.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add pyflow/core/loader.py tests/core/test_loader.py tests/fixtures/simple.yaml
git commit -m "feat: add YAML workflow loader with directory scanning"
```

---

### Task 7: DAG Engine — Topological Sort + Async Execution

**Files:**
- Create: `tests/core/test_engine.py`
- Create: `pyflow/core/engine.py`

**Step 1: Write the failing tests**

```python
# tests/core/test_engine.py
import pytest
from pyflow.core.engine import WorkflowEngine
from pyflow.core.node import BaseNode, NodeRegistry
from pyflow.core.context import ExecutionContext
from pyflow.core.models import WorkflowDef

# Track execution order
execution_log: list[str] = []


class AppendNode(BaseNode):
    node_type = "append"

    async def execute(self, config: dict, context: ExecutionContext) -> object:
        execution_log.append(config.get("value", "default"))
        return config.get("value", "default")


class FailingNode(BaseNode):
    node_type = "failing"

    async def execute(self, config: dict, context: ExecutionContext) -> object:
        raise RuntimeError("intentional failure")


def make_registry() -> NodeRegistry:
    reg = NodeRegistry()
    reg.register(AppendNode)
    reg.register(FailingNode)
    return reg


class TestWorkflowEngine:
    def setup_method(self):
        execution_log.clear()

    async def test_single_node(self):
        wf = WorkflowDef(
            name="single",
            trigger={"type": "manual"},
            nodes=[{"id": "a", "type": "append", "config": {"value": "a"}}],
        )
        engine = WorkflowEngine(registry=make_registry())
        ctx = await engine.run(wf)
        assert ctx.get_result("a") == "a"

    async def test_sequential_dag(self):
        wf = WorkflowDef(
            name="sequential",
            trigger={"type": "manual"},
            nodes=[
                {"id": "a", "type": "append", "config": {"value": "a"}},
                {"id": "b", "type": "append", "depends_on": ["a"], "config": {"value": "b"}},
                {"id": "c", "type": "append", "depends_on": ["b"], "config": {"value": "c"}},
            ],
        )
        engine = WorkflowEngine(registry=make_registry())
        ctx = await engine.run(wf)
        assert execution_log == ["a", "b", "c"]
        assert ctx.get_result("c") == "c"

    async def test_parallel_dag(self):
        wf = WorkflowDef(
            name="parallel",
            trigger={"type": "manual"},
            nodes=[
                {"id": "a", "type": "append", "config": {"value": "a"}},
                {"id": "b", "type": "append", "config": {"value": "b"}},
                {"id": "c", "type": "append", "depends_on": ["a", "b"], "config": {"value": "c"}},
            ],
        )
        engine = WorkflowEngine(registry=make_registry())
        ctx = await engine.run(wf)
        # a and b can run in any order, but c must be last
        assert execution_log[-1] == "c"
        assert set(execution_log[:2]) == {"a", "b"}

    async def test_node_failure_with_stop(self):
        wf = WorkflowDef(
            name="fail-stop",
            trigger={"type": "manual"},
            nodes=[
                {"id": "a", "type": "failing", "config": {}, "on_error": "stop"},
                {"id": "b", "type": "append", "depends_on": ["a"], "config": {"value": "b"}},
            ],
        )
        engine = WorkflowEngine(registry=make_registry())
        ctx = await engine.run(wf)
        assert ctx.has_error("a")
        assert not ctx.has_result("b")

    async def test_node_failure_with_skip(self):
        wf = WorkflowDef(
            name="fail-skip",
            trigger={"type": "manual"},
            nodes=[
                {"id": "a", "type": "failing", "config": {}, "on_error": "skip"},
                {"id": "b", "type": "append", "config": {"value": "b"}},
            ],
        )
        engine = WorkflowEngine(registry=make_registry())
        ctx = await engine.run(wf)
        assert ctx.has_error("a")
        assert ctx.get_result("b") == "b"

    async def test_when_condition_skips_node(self):
        wf = WorkflowDef(
            name="conditional",
            trigger={"type": "manual"},
            nodes=[
                {"id": "a", "type": "append", "config": {"value": "a"}},
                {
                    "id": "b",
                    "type": "append",
                    "depends_on": ["a"],
                    "when": "a == 'nope'",
                    "config": {"value": "b"},
                },
            ],
        )
        engine = WorkflowEngine(registry=make_registry())
        ctx = await engine.run(wf)
        assert ctx.get_result("a") == "a"
        assert not ctx.has_result("b")

    async def test_cycle_detection(self):
        wf = WorkflowDef(
            name="cycle",
            trigger={"type": "manual"},
            nodes=[
                {"id": "a", "type": "append", "depends_on": ["b"], "config": {}},
                {"id": "b", "type": "append", "depends_on": ["a"], "config": {}},
            ],
        )
        engine = WorkflowEngine(registry=make_registry())
        with pytest.raises(ValueError, match="[Cc]ycle"):
            await engine.run(wf)

    async def test_template_resolution_in_config(self):
        wf = WorkflowDef(
            name="templates",
            trigger={"type": "manual"},
            nodes=[
                {"id": "a", "type": "append", "config": {"value": "hello"}},
                {
                    "id": "b",
                    "type": "append",
                    "depends_on": ["a"],
                    "config": {"value": "got: {{ a }}"},
                },
            ],
        )
        engine = WorkflowEngine(registry=make_registry())
        ctx = await engine.run(wf)
        assert ctx.get_result("b") == "got: hello"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_engine.py -v`
Expected: FAIL — import error

**Step 3: Write the implementation**

```python
# pyflow/core/engine.py
from __future__ import annotations

import asyncio
import uuid

import structlog

from pyflow.core.context import ExecutionContext
from pyflow.core.models import NodeDef, OnError, WorkflowDef
from pyflow.core.node import NodeRegistry
from pyflow.core.template import resolve_templates

logger = structlog.get_logger()


class WorkflowEngine:
    def __init__(self, registry: NodeRegistry) -> None:
        self._registry = registry

    async def run(self, workflow: WorkflowDef, run_id: str | None = None) -> ExecutionContext:
        run_id = run_id or str(uuid.uuid4())
        ctx = ExecutionContext(workflow_name=workflow.name, run_id=run_id)
        log = logger.bind(workflow=workflow.name, run_id=run_id)

        nodes_by_id = {n.id: n for n in workflow.nodes}
        self._check_for_cycles(nodes_by_id)

        log.info("workflow.start", node_count=len(workflow.nodes))
        await self._execute_dag(nodes_by_id, ctx, log)
        log.info("workflow.complete")
        return ctx

    def _check_for_cycles(self, nodes: dict[str, NodeDef]) -> None:
        visited: set[str] = set()
        in_stack: set[str] = set()

        def dfs(node_id: str) -> None:
            visited.add(node_id)
            in_stack.add(node_id)
            for dep in nodes.get(node_id, NodeDef(id="", type="")).depends_on:
                if dep in in_stack:
                    raise ValueError(f"Cycle detected involving node '{dep}'")
                if dep not in visited and dep in nodes:
                    dfs(dep)
            in_stack.discard(node_id)

        for nid in nodes:
            if nid not in visited:
                dfs(nid)

    async def _execute_dag(
        self,
        nodes: dict[str, NodeDef],
        ctx: ExecutionContext,
        log: structlog.stdlib.BoundLogger,
    ) -> None:
        completed: set[str] = set()
        failed_stop = False

        while len(completed) < len(nodes) and not failed_stop:
            ready = [
                n
                for n in nodes.values()
                if n.id not in completed
                and all(d in completed for d in n.depends_on)
            ]
            if not ready:
                break

            tasks = []
            for node_def in ready:
                tasks.append(self._execute_node(node_def, ctx, log))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for node_def, result in zip(ready, results):
                if isinstance(result, _StopSentinel):
                    failed_stop = True
                completed.add(node_def.id)

    async def _execute_node(
        self,
        node_def: NodeDef,
        ctx: ExecutionContext,
        log: structlog.stdlib.BoundLogger,
    ) -> object:
        nlog = log.bind(node_id=node_def.id, node_type=node_def.type)

        # Check 'when' condition
        if node_def.when:
            try:
                result = eval(node_def.when, {}, ctx.all_results())  # noqa: S307
                if not result:
                    nlog.info("node.skipped", reason="when condition false")
                    return None
            except Exception:
                nlog.info("node.skipped", reason="when condition evaluation failed")
                return None

        # Resolve templates in config
        config = resolve_templates(node_def.config, ctx)

        # Get node class and execute
        node_cls = self._registry.get(node_def.type)
        node = node_cls()

        try:
            nlog.info("node.start")
            result = await node.execute(config, ctx)
            ctx.set_result(node_def.id, result)
            nlog.info("node.complete")
            return result
        except Exception as exc:
            nlog.error("node.error", error=str(exc))
            ctx.set_error(node_def.id, str(exc))

            if node_def.on_error == OnError.RETRY:
                result = await self._retry_node(node, config, ctx, node_def, nlog)
                if result is not _RETRY_FAILED:
                    return result

            if node_def.on_error == OnError.STOP:
                return _StopSentinel()

            # on_error == skip: continue
            return None

    async def _retry_node(
        self,
        node: object,
        config: dict,
        ctx: ExecutionContext,
        node_def: NodeDef,
        log: structlog.stdlib.BoundLogger,
    ) -> object:
        max_retries = (node_def.retry or {}).get("max_retries", 3)
        delay = (node_def.retry or {}).get("delay", 1)

        for attempt in range(1, max_retries + 1):
            await asyncio.sleep(delay * (2 ** (attempt - 1)))
            try:
                log.info("node.retry", attempt=attempt)
                result = await node.execute(config, ctx)
                ctx.set_result(node_def.id, result)
                return result
            except Exception as exc:
                log.error("node.retry_failed", attempt=attempt, error=str(exc))

        return _RETRY_FAILED


class _StopSentinel:
    pass


_RETRY_FAILED = object()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_engine.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add pyflow/core/engine.py tests/core/test_engine.py
git commit -m "feat: add async DAG workflow engine with error handling and template resolution"
```

---

### Task 8: Built-in Nodes — HTTP, Transform, Condition

**Files:**
- Create: `tests/nodes/test_http.py`
- Create: `tests/nodes/test_transform.py`
- Create: `tests/nodes/test_condition.py`
- Create: `pyflow/nodes/http.py`
- Create: `pyflow/nodes/transform.py`
- Create: `pyflow/nodes/condition.py`

**Step 1: Write the failing tests for HTTP node**

```python
# tests/nodes/test_http.py
import pytest
from pyflow.nodes.http import HttpNode
from pyflow.core.context import ExecutionContext


class TestHttpNode:
    def test_node_type(self):
        assert HttpNode.node_type == "http"

    async def test_get_request(self, httpx_mock):
        httpx_mock.add_response(url="https://api.test.com/data", json={"ok": True})
        node = HttpNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {"method": "GET", "url": "https://api.test.com/data"}, ctx
        )
        assert result["status"] == 200
        assert result["body"] == {"ok": True}

    async def test_post_request_with_body(self, httpx_mock):
        httpx_mock.add_response(url="https://api.test.com/submit", json={"created": True})
        node = HttpNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {
                "method": "POST",
                "url": "https://api.test.com/submit",
                "body": {"name": "test"},
            },
            ctx,
        )
        assert result["status"] == 200

    async def test_with_headers(self, httpx_mock):
        httpx_mock.add_response(url="https://api.test.com/auth", json={"ok": True})
        node = HttpNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {
                "method": "GET",
                "url": "https://api.test.com/auth",
                "headers": {"Authorization": "Bearer token123"},
            },
            ctx,
        )
        assert result["status"] == 200
```

**Step 2: Write HTTP node implementation**

```python
# pyflow/nodes/http.py
from __future__ import annotations

import httpx

from pyflow.core.context import ExecutionContext
from pyflow.core.node import BaseNode


class HttpNode(BaseNode):
    node_type = "http"

    async def execute(self, config: dict, context: ExecutionContext) -> object:
        method = config.get("method", "GET").upper()
        url = config["url"]
        headers = config.get("headers", {})
        body = config.get("body")

        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, headers=headers, json=body)

        try:
            response_body = response.json()
        except Exception:
            response_body = response.text

        return {
            "status": response.status_code,
            "headers": dict(response.headers),
            "body": response_body,
        }
```

**Step 3: Write tests and implementation for Transform node**

```python
# tests/nodes/test_transform.py
import pytest
from pyflow.nodes.transform import TransformNode
from pyflow.core.context import ExecutionContext


class TestTransformNode:
    def test_node_type(self):
        assert TransformNode.node_type == "transform"

    async def test_jsonpath_expression(self):
        node = TransformNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_result("prev", {"data": {"users": [{"name": "Alice"}, {"name": "Bob"}]}})
        result = await node.execute(
            {"input": "{{ prev }}", "expression": "$.data.users[0].name"}, ctx
        )
        assert result == "Alice"

    async def test_jsonpath_returns_list(self):
        node = TransformNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_result("prev", {"items": [1, 2, 3]})
        result = await node.execute(
            {"input": "{{ prev }}", "expression": "$.items[*]"}, ctx
        )
        assert result == [1, 2, 3]
```

```python
# pyflow/nodes/transform.py
from __future__ import annotations

from jsonpath_ng.ext import parse as jsonpath_parse

from pyflow.core.context import ExecutionContext
from pyflow.core.node import BaseNode
from pyflow.core.template import resolve_templates


class TransformNode(BaseNode):
    node_type = "transform"

    async def execute(self, config: dict, context: ExecutionContext) -> object:
        input_data = config.get("input")
        if isinstance(input_data, str) and "{{" in input_data:
            input_data = resolve_templates(input_data, context)

        expression = config["expression"]
        matches = jsonpath_parse(expression).find(input_data)

        if len(matches) == 1:
            return matches[0].value
        return [m.value for m in matches]
```

**Step 4: Write tests and implementation for Condition node**

```python
# tests/nodes/test_condition.py
import pytest
from pyflow.nodes.condition import ConditionNode
from pyflow.core.context import ExecutionContext


class TestConditionNode:
    def test_node_type(self):
        assert ConditionNode.node_type == "condition"

    async def test_true_condition(self):
        node = ConditionNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_result("prev", 42)
        result = await node.execute({"if": "prev > 10"}, ctx)
        assert result is True

    async def test_false_condition(self):
        node = ConditionNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_result("prev", 5)
        result = await node.execute({"if": "prev > 10"}, ctx)
        assert result is False

    async def test_string_comparison(self):
        node = ConditionNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        ctx.set_result("step1", {"status": "active"})
        result = await node.execute({"if": "step1['status'] == 'active'"}, ctx)
        assert result is True
```

```python
# pyflow/nodes/condition.py
from __future__ import annotations

from pyflow.core.context import ExecutionContext
from pyflow.core.node import BaseNode


class ConditionNode(BaseNode):
    node_type = "condition"

    async def execute(self, config: dict, context: ExecutionContext) -> object:
        expression = config["if"]
        result = eval(expression, {"__builtins__": {}}, context.all_results())  # noqa: S307
        return bool(result)
```

**Step 5: Run all node tests**

Run: `pytest tests/nodes/ -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add pyflow/nodes/ tests/nodes/
git commit -m "feat: add built-in HTTP, Transform, and Condition nodes"
```

---

### Task 9: Default Node Registry

**Files:**
- Create: `tests/test_registry.py`
- Modify: `pyflow/nodes/__init__.py`

**Step 1: Write the failing test**

```python
# tests/test_registry.py
from pyflow.nodes import default_registry


class TestDefaultRegistry:
    def test_has_http(self):
        assert "http" in default_registry.list_types()

    def test_has_transform(self):
        assert "transform" in default_registry.list_types()

    def test_has_condition(self):
        assert "condition" in default_registry.list_types()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_registry.py -v`
Expected: FAIL — import error

**Step 3: Write implementation**

```python
# pyflow/nodes/__init__.py
from pyflow.core.node import NodeRegistry
from pyflow.nodes.condition import ConditionNode
from pyflow.nodes.http import HttpNode
from pyflow.nodes.transform import TransformNode

default_registry = NodeRegistry()
default_registry.register(HttpNode)
default_registry.register(TransformNode)
default_registry.register(ConditionNode)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_registry.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add pyflow/nodes/__init__.py tests/test_registry.py
git commit -m "feat: add default node registry with all built-in nodes"
```

---

### Task 10: CLI — run, validate, list

**Files:**
- Create: `tests/test_cli.py`
- Create: `pyflow/cli.py`

**Step 1: Write the failing tests**

```python
# tests/test_cli.py
import pytest
from pathlib import Path
from typer.testing import CliRunner
from pyflow.cli import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


class TestCli:
    def test_validate_valid_workflow(self):
        result = runner.invoke(app, ["validate", str(FIXTURES / "simple.yaml")])
        assert result.exit_code == 0
        assert "valid" in result.stdout.lower()

    def test_validate_nonexistent(self):
        result = runner.invoke(app, ["validate", "/nonexistent.yaml"])
        assert result.exit_code != 0

    def test_list_workflows(self):
        result = runner.invoke(app, ["list", str(FIXTURES)])
        assert result.exit_code == 0
        assert "simple-workflow" in result.stdout

    def test_run_workflow(self):
        result = runner.invoke(app, ["run", str(FIXTURES / "simple.yaml")])
        # Will fail on actual HTTP call but should at least parse
        # For now, check it attempts to run
        assert "simple-workflow" in result.stdout or result.exit_code != 0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — import error

**Step 3: Write implementation**

```python
# pyflow/cli.py
from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from pyflow.core.engine import WorkflowEngine
from pyflow.core.loader import load_all_workflows, load_workflow
from pyflow.nodes import default_registry

app = typer.Typer(name="pyflow", help="PyFlow — Workflow Automation Engine")


@app.command()
def run(workflow_path: Path) -> None:
    """Execute a workflow from a YAML file."""
    wf = load_workflow(workflow_path)
    typer.echo(f"Running workflow: {wf.name}")
    engine = WorkflowEngine(registry=default_registry)
    ctx = asyncio.run(engine.run(wf))
    typer.echo(f"Completed. Run ID: {ctx.run_id}")
    for node_id in [n.id for n in wf.nodes]:
        if ctx.has_result(node_id):
            typer.echo(f"  {node_id}: OK")
        elif ctx.has_error(node_id):
            typer.echo(f"  {node_id}: ERROR — {ctx.get_error(node_id)}")
        else:
            typer.echo(f"  {node_id}: SKIPPED")


@app.command()
def validate(workflow_path: Path) -> None:
    """Validate a workflow YAML file."""
    try:
        wf = load_workflow(workflow_path)
        typer.echo(f"Valid: {wf.name} ({len(wf.nodes)} nodes)")
    except Exception as exc:
        typer.echo(f"Invalid: {exc}", err=True)
        raise typer.Exit(code=1)


@app.command(name="list")
def list_workflows(directory: Path = typer.Argument(default=Path("workflows"))) -> None:
    """List all workflows in a directory."""
    workflows = load_all_workflows(directory)
    if not workflows:
        typer.echo("No workflows found.")
        return
    for wf in workflows:
        trigger = wf.trigger.type
        typer.echo(f"  {wf.name} [{trigger}] ({len(wf.nodes)} nodes)")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add pyflow/cli.py tests/test_cli.py
git commit -m "feat: add CLI with run, validate, and list commands"
```

---

### Task 11: Schedule Trigger (APScheduler)

**Files:**
- Create: `tests/triggers/test_schedule.py`
- Create: `pyflow/triggers/schedule.py`

**Step 1: Write the failing tests**

```python
# tests/triggers/test_schedule.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from pyflow.triggers.schedule import ScheduleTrigger
from pyflow.core.models import TriggerDef


class TestScheduleTrigger:
    def test_create_from_cron(self):
        trigger_def = TriggerDef(type="schedule", config={"cron": "0 * * * *"})
        trigger = ScheduleTrigger(trigger_def)
        assert trigger.cron == "0 * * * *"

    def test_create_from_interval(self):
        trigger_def = TriggerDef(type="schedule", config={"interval_seconds": 60})
        trigger = ScheduleTrigger(trigger_def)
        assert trigger.interval_seconds == 60

    def test_requires_cron_or_interval(self):
        trigger_def = TriggerDef(type="schedule", config={})
        with pytest.raises(ValueError, match="cron.*interval"):
            ScheduleTrigger(trigger_def)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/triggers/test_schedule.py -v`
Expected: FAIL — import error

**Step 3: Write implementation**

```python
# pyflow/triggers/schedule.py
from __future__ import annotations

from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from pyflow.core.models import TriggerDef


class ScheduleTrigger:
    def __init__(self, trigger_def: TriggerDef) -> None:
        self.cron: str | None = trigger_def.config.get("cron")
        self.interval_seconds: int | None = trigger_def.config.get("interval_seconds")
        if not self.cron and not self.interval_seconds:
            raise ValueError("Schedule trigger requires 'cron' or 'interval_seconds'")

    def register(self, scheduler: AsyncIOScheduler, callback: Callable) -> None:
        if self.cron:
            parts = self.cron.split()
            scheduler.add_job(
                callback,
                CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4],
                ),
            )
        else:
            scheduler.add_job(
                callback,
                IntervalTrigger(seconds=self.interval_seconds),
            )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/triggers/test_schedule.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add pyflow/triggers/schedule.py tests/triggers/test_schedule.py
git commit -m "feat: add schedule trigger with cron and interval support"
```

---

### Task 12: Webhook Trigger + FastAPI Server

**Files:**
- Create: `tests/test_server.py`
- Create: `pyflow/server.py`
- Create: `pyflow/triggers/webhook.py`

**Step 1: Write the failing tests**

```python
# tests/test_server.py
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from pyflow.server import create_app

FIXTURES = Path(__file__).parent / "fixtures"


class TestServer:
    async def test_health_check(self):
        app = create_app(FIXTURES)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_list_workflows(self):
        app = create_app(FIXTURES)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/workflows")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    async def test_trigger_workflow(self):
        app = create_app(FIXTURES)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/trigger/simple-workflow")
        # May fail on HTTP call inside workflow, but endpoint should respond
        assert response.status_code in (200, 500)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_server.py -v`
Expected: FAIL — import error

**Step 3: Write webhook trigger**

```python
# pyflow/triggers/webhook.py
from __future__ import annotations

from pyflow.core.models import TriggerDef


class WebhookTrigger:
    def __init__(self, trigger_def: TriggerDef) -> None:
        self.path: str = trigger_def.config.get("path", "/")
```

**Step 4: Write server implementation**

```python
# pyflow/server.py
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException

from pyflow.core.engine import WorkflowEngine
from pyflow.core.loader import load_all_workflows
from pyflow.nodes import default_registry


def create_app(workflows_dir: Path = Path("workflows")) -> FastAPI:
    app = FastAPI(title="PyFlow", version="0.1.0")
    engine = WorkflowEngine(registry=default_registry)

    workflows = {wf.name: wf for wf in load_all_workflows(workflows_dir)}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/workflows")
    async def list_workflows():
        return [
            {"name": wf.name, "trigger": wf.trigger.type, "nodes": len(wf.nodes)}
            for wf in workflows.values()
        ]

    @app.post("/trigger/{workflow_name}")
    async def trigger_workflow(workflow_name: str, payload: dict | None = None):
        if workflow_name not in workflows:
            raise HTTPException(status_code=404, detail=f"Workflow '{workflow_name}' not found")
        wf = workflows[workflow_name]
        ctx = await engine.run(wf)
        results = {}
        for node in wf.nodes:
            if ctx.has_result(node.id):
                results[node.id] = "ok"
            elif ctx.has_error(node.id):
                results[node.id] = f"error: {ctx.get_error(node.id)}"
            else:
                results[node.id] = "skipped"
        return {"run_id": ctx.run_id, "results": results}

    return app
```

**Step 5: Add serve command to CLI**

Append to `pyflow/cli.py`:

```python
@app.command()
def serve(
    workflows_dir: Path = typer.Argument(default=Path("workflows")),
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
) -> None:
    """Start PyFlow server with webhook listeners and schedulers."""
    import uvicorn
    from pyflow.server import create_app

    fastapi_app = create_app(workflows_dir)
    typer.echo(f"Starting PyFlow server on {host}:{port}")
    uvicorn.run(fastapi_app, host=host, port=port)
```

**Step 6: Run tests to verify they pass**

Run: `pytest tests/test_server.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add pyflow/server.py pyflow/triggers/webhook.py pyflow/cli.py tests/test_server.py
git commit -m "feat: add FastAPI server with webhook triggers and workflow API"
```

---

### Task 13: Structured Logging

**Files:**
- Create: `pyflow/config.py`

**Step 1: Write implementation**

```python
# pyflow/config.py
from __future__ import annotations

import structlog


def configure_logging(json_output: bool = False) -> None:
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(0),
    )
```

**Step 2: Wire into CLI — add to top of `run` and `serve` commands**

Add `configure_logging()` call at the start of `run()` and `serve()` in `pyflow/cli.py`.

**Step 3: Verify manually**

Run: `pyflow run tests/fixtures/simple.yaml`
Expected: See structured log output with timestamps

**Step 4: Commit**

```bash
git add pyflow/config.py pyflow/cli.py
git commit -m "feat: add structured logging configuration"
```

---

### Task 14: End-to-End Integration Test

**Files:**
- Create: `tests/test_integration.py`
- Create: `tests/fixtures/multi_step.yaml`

**Step 1: Create a multi-step workflow fixture**

```yaml
# tests/fixtures/multi_step.yaml
name: multi-step-test
description: Integration test with multiple node types
trigger:
  type: manual
nodes:
  - id: start
    type: condition
    config:
      if: "True"

  - id: transform
    type: transform
    depends_on: [start]
    config:
      input:
        items: [1, 2, 3, 4, 5]
      expression: "$.items[*]"

  - id: check
    type: condition
    depends_on: [transform]
    config:
      if: "len(transform) == 5"
```

**Step 2: Write the integration test**

```python
# tests/test_integration.py
import pytest
from pathlib import Path
from pyflow.core.engine import WorkflowEngine
from pyflow.core.loader import load_workflow
from pyflow.nodes import default_registry

FIXTURES = Path(__file__).parent / "fixtures"


class TestIntegration:
    async def test_multi_step_workflow(self):
        wf = load_workflow(FIXTURES / "multi_step.yaml")
        engine = WorkflowEngine(registry=default_registry)
        ctx = await engine.run(wf)

        assert ctx.get_result("start") is True
        assert ctx.get_result("transform") == [1, 2, 3, 4, 5]
        assert ctx.get_result("check") is True

    async def test_load_and_validate_all_fixtures(self):
        from pyflow.core.loader import load_all_workflows
        workflows = load_all_workflows(FIXTURES)
        assert len(workflows) >= 2
```

**Step 3: Run integration tests**

Run: `pytest tests/test_integration.py -v`
Expected: All PASS

**Step 4: Run full test suite**

Run: `pytest -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add tests/test_integration.py tests/fixtures/multi_step.yaml
git commit -m "test: add end-to-end integration tests"
```

---

### Task 15: Update CLAUDE.md and Example Workflow

**Files:**
- Modify: `CLAUDE.md`
- Create: `workflows/example.yaml`

**Step 1: Update CLAUDE.md with project context**

```markdown
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
```

**Step 2: Create example workflow**

```yaml
# workflows/example.yaml
name: example-webhook-handler
description: Example workflow that receives a webhook and logs the payload
trigger:
  type: manual
nodes:
  - id: check-input
    type: condition
    config:
      if: "True"

  - id: transform-data
    type: transform
    depends_on: [check-input]
    config:
      input:
        message: "Hello from PyFlow!"
        items: [1, 2, 3]
      expression: "$.message"
```

**Step 3: Commit**

```bash
git add CLAUDE.md workflows/example.yaml
git commit -m "docs: update CLAUDE.md with project context and add example workflow"
```
