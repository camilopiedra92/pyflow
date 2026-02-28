# ADK-First Platform Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor PyFlow to use Google ADK natively, eliminating wrapper layers, supporting 6 orchestration types, and leveraging ADK plugins/memory/artifacts/callbacks.

**Architecture:** PyFlow becomes a configuration layer over ADK. YAML workflows hydrate directly to ADK primitives. Custom code only where ADK has no solution (DagAgent). Tools expose pure Python functions inspected by ADK's FunctionTool.

**Tech Stack:** google-adk 1.26, Pydantic v2, Python 3.12, pytest + pytest-asyncio, FastAPI, structlog

**Key ADK API facts (verified from source):**
- `Runner(session_service=..., memory_service=..., artifact_service=..., plugins=...)` — session_service is REQUIRED
- `FunctionTool(func=my_async_fn)` — auto-inspects params, injects `tool_context` if param named `tool_context`
- `BaseAgent` is a **Pydantic BaseModel** — custom agents must be too
- `LlmAgent` accepts: `before_agent_callback`, `after_agent_callback`, `before_tool_callback`, `after_tool_callback`, `before_model_callback`, `after_model_callback`
- `LoopAgent` accepts `max_iterations: Optional[int]`
- `PlanReActPlanner()` — no args needed
- `DatabaseSessionService(db_url="sqlite+aiosqlite:///file.db")` — needs async driver
- `ExitLoopTool` is a plain function `exit_loop`, not a class
- `ToolContext` = `Context` alias with `.state`, `.actions`, `.save_artifact()`, `.load_artifact()`

**Virtual env:** Always `source /Users/camilopiedra/Development/pyflow/.venv/bin/activate` before any command.

---

## Phase 1: Foundation — New Models & Shared Utilities

### Task 1.1: Add RuntimeConfig and DagNode models

**Files:**
- Modify: `pyflow/models/workflow.py`
- Test: `tests/models/test_workflow.py`

**Step 1: Write failing tests for RuntimeConfig**

Add to `tests/models/test_workflow.py`:

```python
class TestRuntimeConfig:
    def test_defaults(self):
        config = RuntimeConfig()
        assert config.session_service == "in_memory"
        assert config.session_db_url is None
        assert config.memory_service == "none"
        assert config.artifact_service == "none"
        assert config.artifact_dir is None
        assert config.plugins == []

    def test_all_fields(self):
        config = RuntimeConfig(
            session_service="sqlite",
            session_db_url="sqlite+aiosqlite:///test.db",
            memory_service="in_memory",
            artifact_service="file",
            artifact_dir="./artifacts",
            plugins=["logging", "reflect_and_retry"],
        )
        assert config.session_service == "sqlite"
        assert config.memory_service == "in_memory"
        assert config.artifact_service == "file"
        assert config.plugins == ["logging", "reflect_and_retry"]

    def test_invalid_session_service(self):
        with pytest.raises(ValidationError):
            RuntimeConfig(session_service="redis")

    def test_invalid_memory_service(self):
        with pytest.raises(ValidationError):
            RuntimeConfig(memory_service="redis")

    def test_invalid_artifact_service(self):
        with pytest.raises(ValidationError):
            RuntimeConfig(artifact_service="s3")
```

**Step 2: Write failing tests for DagNode**

Add to `tests/models/test_workflow.py`:

```python
class TestDagNode:
    def test_minimal(self):
        node = DagNode(agent="fetcher")
        assert node.agent == "fetcher"
        assert node.depends_on == []

    def test_with_dependencies(self):
        node = DagNode(agent="merger", depends_on=["a", "b"])
        assert node.depends_on == ["a", "b"]
```

**Step 3: Run tests to verify they fail**

Run: `pytest tests/models/test_workflow.py::TestRuntimeConfig tests/models/test_workflow.py::TestDagNode -v`
Expected: FAIL with `ImportError` (RuntimeConfig and DagNode don't exist yet)

**Step 4: Implement RuntimeConfig and DagNode**

In `pyflow/models/workflow.py`, add before `OrchestrationConfig`:

```python
class RuntimeConfig(BaseModel):
    """ADK runtime service configuration for a workflow."""

    session_service: Literal["in_memory", "sqlite", "database"] = "in_memory"
    session_db_url: str | None = None
    memory_service: Literal["in_memory", "none"] = "none"
    artifact_service: Literal["in_memory", "file", "none"] = "none"
    artifact_dir: str | None = None
    plugins: list[str] = []


class DagNode(BaseModel):
    """A node in a DAG orchestration with dependency edges."""

    agent: str
    depends_on: list[str] = []
```

**Step 5: Export from `pyflow/models/__init__.py`**

Add `RuntimeConfig` and `DagNode` to the imports and `__all__`.

**Step 6: Run tests to verify they pass**

Run: `pytest tests/models/test_workflow.py::TestRuntimeConfig tests/models/test_workflow.py::TestDagNode -v`
Expected: PASS

**Step 7: Commit**

```bash
git add pyflow/models/workflow.py pyflow/models/__init__.py tests/models/test_workflow.py
git commit -m "feat: add RuntimeConfig and DagNode models"
```

---

### Task 1.2: Expand OrchestrationConfig to 6 types

**Files:**
- Modify: `pyflow/models/workflow.py`
- Test: `tests/models/test_workflow.py`

**Step 1: Write failing tests for new orchestration types**

Add to `tests/models/test_workflow.py`:

```python
class TestOrchestrationConfigExpanded:
    def test_react(self):
        config = OrchestrationConfig(type="react", agent="reasoner", planner="plan_react")
        assert config.type == "react"
        assert config.agent == "reasoner"

    def test_react_requires_agent(self):
        with pytest.raises(ValidationError):
            OrchestrationConfig(type="react")

    def test_dag(self):
        config = OrchestrationConfig(
            type="dag",
            nodes=[
                DagNode(agent="a"),
                DagNode(agent="b", depends_on=["a"]),
            ],
        )
        assert config.type == "dag"
        assert len(config.nodes) == 2

    def test_dag_requires_nodes(self):
        with pytest.raises(ValidationError):
            OrchestrationConfig(type="dag")

    def test_dag_detects_cycle(self):
        with pytest.raises(ValidationError, match="cycle"):
            OrchestrationConfig(
                type="dag",
                nodes=[
                    DagNode(agent="a", depends_on=["b"]),
                    DagNode(agent="b", depends_on=["a"]),
                ],
            )

    def test_dag_unknown_dependency(self):
        with pytest.raises(ValidationError, match="Unknown dependency"):
            OrchestrationConfig(
                type="dag",
                nodes=[DagNode(agent="a", depends_on=["nonexistent"])],
            )

    def test_llm_routed(self):
        config = OrchestrationConfig(
            type="llm_routed", router="dispatcher", agents=["a", "b"]
        )
        assert config.type == "llm_routed"
        assert config.router == "dispatcher"

    def test_llm_routed_requires_router_and_agents(self):
        with pytest.raises(ValidationError):
            OrchestrationConfig(type="llm_routed", router="dispatcher")
        with pytest.raises(ValidationError):
            OrchestrationConfig(type="llm_routed", agents=["a"])

    def test_loop_with_max_iterations(self):
        config = OrchestrationConfig(type="loop", agents=["a", "b"], max_iterations=5)
        assert config.max_iterations == 5

    def test_sequential_still_works(self):
        config = OrchestrationConfig(type="sequential", agents=["a", "b"])
        assert config.type == "sequential"

    def test_parallel_still_works(self):
        config = OrchestrationConfig(type="parallel", agents=["a", "b"])
        assert config.type == "parallel"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/models/test_workflow.py::TestOrchestrationConfigExpanded -v`
Expected: FAIL

**Step 3: Expand OrchestrationConfig**

Replace `OrchestrationConfig` in `pyflow/models/workflow.py`:

```python
class OrchestrationConfig(BaseModel):
    """Orchestration configuration supporting 6 workflow types."""

    type: Literal["sequential", "parallel", "loop", "react", "dag", "llm_routed"]
    agents: list[str] | None = None
    nodes: list[DagNode] | None = None
    agent: str | None = None
    router: str | None = None
    planner: str | None = None
    max_iterations: int | None = None

    @model_validator(mode="after")
    def validate_by_type(self) -> OrchestrationConfig:
        match self.type:
            case "sequential" | "parallel":
                if not self.agents:
                    raise ValueError(f"'{self.type}' requires 'agents' list")
            case "loop":
                if not self.agents:
                    raise ValueError("'loop' requires 'agents' list")
            case "react":
                if not self.agent:
                    raise ValueError("'react' requires 'agent'")
            case "dag":
                if not self.nodes:
                    raise ValueError("'dag' requires 'nodes' list")
                self._validate_dag_acyclic()
            case "llm_routed":
                if not self.router or not self.agents:
                    raise ValueError("'llm_routed' requires 'router' and 'agents'")
        return self

    def _validate_dag_acyclic(self) -> None:
        """Validate DAG has no cycles using Kahn's algorithm."""
        node_names = {n.agent for n in self.nodes}
        in_degree: dict[str, int] = {}
        dependents: dict[str, list[str]] = {}

        for node in self.nodes:
            in_degree[node.agent] = len(node.depends_on)
            for dep in node.depends_on:
                if dep not in node_names:
                    raise ValueError(
                        f"Unknown dependency '{dep}' in node '{node.agent}'"
                    )
                dependents.setdefault(dep, []).append(node.agent)

        queue = [name for name, deg in in_degree.items() if deg == 0]
        visited = 0
        while queue:
            current = queue.pop(0)
            visited += 1
            for child in dependents.get(current, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if visited != len(self.nodes):
            raise ValueError("DAG contains a cycle")
```

**Step 4: Update WorkflowDef validator**

The existing `_validate_orchestration_refs` validator needs updating to handle new orchestration types. It currently checks `self.orchestration.agents` — it must also handle `nodes`, `agent`, and `router`:

```python
@model_validator(mode="after")
def _validate_orchestration_refs(self) -> WorkflowDef:
    agent_names = {a.name for a in self.agents}
    orch = self.orchestration

    if orch.agents:
        for ref in orch.agents:
            if ref not in agent_names:
                raise ValueError(f"Orchestration references unknown agent '{ref}'")

    if orch.nodes:
        for node in orch.nodes:
            if node.agent not in agent_names:
                raise ValueError(
                    f"DAG node references unknown agent '{node.agent}'"
                )

    if orch.agent and orch.agent not in agent_names:
        raise ValueError(f"React references unknown agent '{orch.agent}'")

    if orch.router and orch.router not in agent_names:
        raise ValueError(f"Router references unknown agent '{orch.router}'")

    return self
```

**Step 5: Add `runtime` field to WorkflowDef**

```python
class WorkflowDef(BaseModel):
    name: str
    description: str = ""
    runtime: RuntimeConfig = RuntimeConfig()  # NEW
    agents: list[AgentConfig]
    orchestration: OrchestrationConfig
    a2a: A2AConfig | None = None
```

**Step 6: Run tests**

Run: `pytest tests/models/test_workflow.py -v`
Expected: ALL PASS (including existing tests — ensure backward compat)

**Step 7: Commit**

```bash
git add pyflow/models/workflow.py tests/models/test_workflow.py
git commit -m "feat: expand OrchestrationConfig to 6 types with DAG cycle validation"
```

---

### Task 1.3: Add callbacks field to AgentConfig

**Files:**
- Modify: `pyflow/models/agent.py`
- Test: `tests/models/test_agent.py`

**Step 1: Write failing test**

Add to `tests/models/test_agent.py`:

```python
class TestAgentConfigCallbacks:
    def test_llm_with_callbacks(self):
        config = AgentConfig(
            name="test",
            type="llm",
            model="gemini-2.5-flash",
            instruction="test",
            callbacks={"before_agent": "log_start", "after_agent": "log_output"},
        )
        assert config.callbacks == {"before_agent": "log_start", "after_agent": "log_output"}

    def test_callbacks_default_none(self):
        config = AgentConfig(
            name="test", type="llm", model="gemini-2.5-flash", instruction="test"
        )
        assert config.callbacks is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/models/test_agent.py::TestAgentConfigCallbacks -v`
Expected: FAIL

**Step 3: Add callbacks field to AgentConfig**

In `pyflow/models/agent.py`, add to `AgentConfig`:

```python
callbacks: dict[str, str] | None = None
```

**Step 4: Run all agent tests**

Run: `pytest tests/models/test_agent.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add pyflow/models/agent.py tests/models/test_agent.py
git commit -m "feat: add callbacks field to AgentConfig"
```

---

### Task 1.4: Unify SkillDef and AgentCardSkill

**Files:**
- Modify: `pyflow/models/workflow.py`, `pyflow/models/a2a.py`, `pyflow/platform/a2a/cards.py`
- Test: `tests/models/test_a2a_models.py`, `tests/platform/a2a/test_cards.py`

**Step 1: Remove AgentCardSkill, use SkillDef everywhere**

In `pyflow/models/a2a.py`, replace `AgentCardSkill` import with `SkillDef`:

```python
from pyflow.models.workflow import SkillDef

class AgentCard(BaseModel):
    # ...
    skills: list[SkillDef] = []  # was list[AgentCardSkill]
```

Remove the `AgentCardSkill` class definition entirely.

**Step 2: Update cards.py to use SkillDef**

In `pyflow/platform/a2a/cards.py`, replace any `AgentCardSkill` references with `SkillDef`.

**Step 3: Update test imports**

In `tests/models/test_a2a_models.py`, replace `AgentCardSkill` imports with `SkillDef` from `pyflow.models.workflow`. Rename test class from `TestAgentCardSkill` to `TestSkillDefInA2A` (or keep and update imports).

**Step 4: Update `__init__.py` exports**

Remove `AgentCardSkill` from `pyflow/models/__init__.py`.

**Step 5: Run all tests**

Run: `pytest tests/models/test_a2a_models.py tests/platform/a2a/test_cards.py tests/models/test_workflow.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add pyflow/models/a2a.py pyflow/models/workflow.py pyflow/models/__init__.py pyflow/platform/a2a/cards.py tests/models/test_a2a_models.py
git commit -m "refactor: unify SkillDef and AgentCardSkill into single model"
```

---

### Task 1.5: Add session_id to RunResult

**Files:**
- Modify: `pyflow/models/runner.py`
- Test: `tests/models/test_runner.py`

**Step 1: Write failing test**

Add to `tests/models/test_runner.py`:

```python
def test_run_result_with_session_id(self):
    result = RunResult(content="hello", session_id="sess-123")
    assert result.session_id == "sess-123"

def test_run_result_session_id_default(self):
    result = RunResult()
    assert result.session_id is None
```

**Step 2: Add field**

In `pyflow/models/runner.py`:

```python
class RunResult(BaseModel):
    content: str = ""
    author: str = ""
    usage_metadata: Any = None
    session_id: str | None = None  # NEW
```

**Step 3: Run tests**

Run: `pytest tests/models/test_runner.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add pyflow/models/runner.py tests/models/test_runner.py
git commit -m "feat: add session_id to RunResult"
```

---

### Task 1.6: Create shared tool utilities

**Files:**
- Create: `pyflow/tools/security.py`
- Create: `pyflow/tools/parsing.py`
- Test: `tests/tools/test_security.py`
- Test: `tests/tools/test_parsing.py`

**Step 1: Write failing tests for security.py**

Create `tests/tools/test_security.py`:

```python
from __future__ import annotations

import pytest

from pyflow.tools.security import is_private_url


class TestIsPrivateUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/api",
            "http://localhost/api",
            "http://10.0.0.1/api",
            "http://172.16.0.1/api",
            "http://192.168.1.1/api",
            "http://169.254.169.254/latest/meta-data",
            "http://[::1]/api",
            "http://0.0.0.0/api",
        ],
    )
    def test_blocks_private_urls(self, url: str):
        assert is_private_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://api.example.com/data",
            "https://8.8.8.8/dns",
            "https://httpbin.org/get",
        ],
    )
    def test_allows_public_urls(self, url: str):
        assert is_private_url(url) is False
```

**Step 2: Write failing tests for parsing.py**

Create `tests/tools/test_parsing.py`:

```python
from __future__ import annotations

from pyflow.tools.parsing import safe_json_parse


class TestSafeJsonParse:
    def test_valid_json_object(self):
        assert safe_json_parse('{"key": "value"}') == {"key": "value"}

    def test_valid_json_array(self):
        assert safe_json_parse("[1, 2, 3]") == [1, 2, 3]

    def test_empty_string(self):
        assert safe_json_parse("") is None

    def test_none_input(self):
        assert safe_json_parse(None) is None

    def test_invalid_json(self):
        assert safe_json_parse("not json") is None

    def test_custom_default(self):
        assert safe_json_parse("bad", default={}) == {}
```

**Step 3: Run tests to verify they fail**

Run: `pytest tests/tools/test_security.py tests/tools/test_parsing.py -v`
Expected: FAIL (modules don't exist)

**Step 4: Implement security.py**

Create `pyflow/tools/security.py`:

```python
from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


def is_private_url(url: str) -> bool:
    """Check if URL points to a private/internal network address."""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    if hostname in ("localhost", ""):
        return True

    # Strip IPv6 brackets
    clean = hostname.strip("[]")

    try:
        addr = ipaddress.ip_address(clean)
        return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved
    except ValueError:
        return False
```

**Step 5: Implement parsing.py**

Create `pyflow/tools/parsing.py`:

```python
from __future__ import annotations

import json
from typing import Any


def safe_json_parse(value: str | None, default: Any = None) -> Any:
    """Parse JSON string safely, return default on failure."""
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default
```

**Step 6: Run tests**

Run: `pytest tests/tools/test_security.py tests/tools/test_parsing.py -v`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add pyflow/tools/security.py pyflow/tools/parsing.py tests/tools/test_security.py tests/tools/test_parsing.py
git commit -m "feat: add shared security and parsing utilities for tools"
```

---

### Task 1.7: Clean up ToolConfig and ToolResponse base classes

**Files:**
- Modify: `pyflow/models/tool.py`
- Modify: `pyflow/models/__init__.py`
- Test: `tests/models/test_tool.py`

**Step 1: Remove ToolConfig and ToolResponse from tool.py**

Keep only `ToolMetadata` in `pyflow/models/tool.py`. Remove `ToolConfig` and `ToolResponse` classes.

**Step 2: Remove from __init__.py exports**

Remove `ToolConfig` and `ToolResponse` from `pyflow/models/__init__.py`.

**Step 3: Update test_tool.py**

Remove `TestToolConfig` and `TestToolResponse` test classes. Keep `TestToolMetadata`.

**Step 4: Check for remaining imports of ToolConfig/ToolResponse**

Search the codebase for any remaining imports of `ToolConfig` or `ToolResponse`. These will exist in:
- `pyflow/tools/base.py` — will be updated in Phase 2
- `pyflow/tools/http.py`, `transform.py`, `condition.py`, `alert.py`, `storage.py` — will be updated in Phase 2
- Their corresponding tests — will be updated in Phase 2

For now, keep backward-compatible aliases in `pyflow/models/tool.py` so Phase 1 doesn't break existing code:

```python
class ToolConfig(BaseModel):
    """Deprecated: will be removed in Phase 2."""
    pass

class ToolResponse(BaseModel):
    """Deprecated: will be removed in Phase 2."""
    pass
```

**Step 5: Run all tests**

Run: `pytest -v`
Expected: ALL 221 PASS

**Step 6: Commit**

```bash
git add pyflow/models/tool.py pyflow/models/__init__.py tests/models/test_tool.py
git commit -m "refactor: deprecate ToolConfig and ToolResponse base classes"
```

---

## Phase 2: Tool System Refactor

### Task 2.1: Refactor BasePlatformTool

**Files:**
- Modify: `pyflow/tools/base.py`
- Test: `tests/tools/test_base.py`

**Step 1: Write failing tests for new BasePlatformTool**

Replace test contents in `tests/tools/test_base.py`:

```python
from __future__ import annotations

import pytest
from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext

from pyflow.tools.base import BasePlatformTool, get_registered_tools, _TOOL_AUTO_REGISTRY


class _DummyTool(BasePlatformTool):
    name = "dummy"
    description = "A dummy tool for testing"

    async def execute(self, tool_context: ToolContext, value: str) -> dict:
        return {"result": value}


class TestAutoRegistration:
    def test_subclass_auto_registers(self):
        assert "dummy" in _TOOL_AUTO_REGISTRY

    def test_abstract_base_not_registered(self):
        assert "BasePlatformTool" not in _TOOL_AUTO_REGISTRY

    def test_tool_without_name_not_registered(self):
        class NoName(BasePlatformTool):
            description = "no name"
            async def execute(self, tool_context, **kwargs):
                return {}
        assert "NoName" not in _TOOL_AUTO_REGISTRY


class TestGetRegisteredTools:
    def test_returns_dict_copy(self):
        tools = get_registered_tools()
        assert isinstance(tools, dict)
        assert "dummy" in tools

    def test_includes_builtin_tools(self):
        import pyflow.tools  # noqa: F401 — trigger registration
        tools = get_registered_tools()
        assert "http_request" in tools
        assert "transform" in tools
        assert "condition" in tools
        assert "alert" in tools
        assert "storage" in tools


class TestAsFunctionTool:
    def test_returns_function_tool(self):
        tool = _DummyTool.as_function_tool()
        assert isinstance(tool, FunctionTool)


class TestMetadata:
    def test_returns_tool_metadata(self):
        meta = _DummyTool.metadata()
        assert meta.name == "dummy"
        assert meta.description == "A dummy tool for testing"
```

**Step 2: Rewrite BasePlatformTool**

Replace `pyflow/tools/base.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext

from pyflow.models.tool import ToolMetadata

_TOOL_AUTO_REGISTRY: dict[str, type[BasePlatformTool]] = {}


class BasePlatformTool(ABC):
    """Base class for auto-registering platform tools.

    Subclasses define `name`, `description`, and implement `execute()` with
    typed parameters. ADK's FunctionTool inspects the function signature directly.
    """

    name: ClassVar[str]
    description: ClassVar[str]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "name") and isinstance(cls.__dict__.get("name"), str):
            _TOOL_AUTO_REGISTRY[cls.name] = cls

    @abstractmethod
    async def execute(self, tool_context: ToolContext, **kwargs: Any) -> dict:
        """Execute the tool. Subclasses define their own typed parameters."""
        ...

    @classmethod
    def as_function_tool(cls) -> FunctionTool:
        """Convert to ADK FunctionTool via native function inspection."""
        instance = cls()
        return FunctionTool(func=instance.execute)

    @classmethod
    def metadata(cls) -> ToolMetadata:
        """Return tool metadata for registry listing."""
        return ToolMetadata(name=cls.name, description=cls.description)


def get_registered_tools() -> dict[str, type[BasePlatformTool]]:
    """Return a copy of the auto-registration registry."""
    return dict(_TOOL_AUTO_REGISTRY)
```

**Step 3: Run tests**

Run: `pytest tests/tools/test_base.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add pyflow/tools/base.py tests/tools/test_base.py
git commit -m "refactor: simplify BasePlatformTool to delegate to ADK FunctionTool"
```

---

### Task 2.2: Migrate HttpTool

**Files:**
- Modify: `pyflow/tools/http.py`
- Test: `tests/tools/test_http.py`

**Step 1: Write tests for new HttpTool signature**

Rewrite `tests/tools/test_http.py` with the new function-parameter approach. Key changes:
- `execute()` takes `url: str, method: str, headers: str, body: str, timeout: int, allow_private: bool` directly
- `headers` and `body` are JSON strings
- Import `is_private_url` from `pyflow.tools.security`
- Returns `dict` not `HttpToolResponse`

```python
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from pyflow.tools.http import HttpTool


class TestHttpToolExecute:
    async def test_get_request(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"data": "test"}

        with patch("pyflow.tools.http.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            tool = HttpTool()
            result = await tool.execute(
                tool_context=MagicMock(),
                url="https://api.example.com/data",
            )
            assert result["status"] == 200

    async def test_post_with_json_body(self):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.json.return_value = {"created": True}

        with patch("pyflow.tools.http.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            tool = HttpTool()
            result = await tool.execute(
                tool_context=MagicMock(),
                url="https://api.example.com/create",
                method="POST",
                body='{"name": "test"}',
                headers='{"Authorization": "Bearer token"}',
            )
            assert result["status"] == 201

    async def test_ssrf_blocked(self):
        tool = HttpTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            url="http://127.0.0.1/internal",
        )
        assert result["status"] == 0
        assert "SSRF" in result.get("error", "") or "private" in result.get("error", "").lower()

    async def test_ssrf_allowed_with_flag(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {}

        with patch("pyflow.tools.http.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            tool = HttpTool()
            result = await tool.execute(
                tool_context=MagicMock(),
                url="http://127.0.0.1/internal",
                allow_private=True,
            )
            assert result["status"] == 200

    async def test_invalid_json_headers_uses_empty(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {}

        with patch("pyflow.tools.http.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            tool = HttpTool()
            result = await tool.execute(
                tool_context=MagicMock(),
                url="https://api.example.com",
                headers="not valid json",
            )
            assert result["status"] == 200

    async def test_network_error(self):
        with patch("pyflow.tools.http.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.side_effect = httpx.HTTPError("Connection refused")
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            tool = HttpTool()
            result = await tool.execute(
                tool_context=MagicMock(),
                url="https://api.example.com",
            )
            assert result["status"] == 0
            assert "error" in result


class TestHttpToolRegistration:
    def test_auto_registered(self):
        import pyflow.tools  # noqa: F401
        from pyflow.tools.base import get_registered_tools
        assert "http_request" in get_registered_tools()
```

**Step 2: Rewrite HttpTool**

Replace `pyflow/tools/http.py`:

```python
from __future__ import annotations

import httpx
from google.adk.tools.tool_context import ToolContext

from pyflow.tools.base import BasePlatformTool
from pyflow.tools.parsing import safe_json_parse
from pyflow.tools.security import is_private_url


class HttpTool(BasePlatformTool):
    """Make HTTP requests to external APIs with SSRF protection."""

    name = "http_request"
    description = (
        "Make HTTP requests. Supports GET, POST, PUT, DELETE, PATCH. "
        "Pass headers and body as JSON strings."
    )

    async def execute(
        self,
        tool_context: ToolContext,
        url: str,
        method: str = "GET",
        headers: str = "{}",
        body: str = "",
        timeout: int = 30,
        allow_private: bool = False,
    ) -> dict:
        """Make an HTTP request.

        Args:
            url: The URL to request.
            method: HTTP method (GET, POST, PUT, DELETE, PATCH).
            headers: JSON string of headers, e.g. '{"Authorization": "Bearer ..."}'.
            body: JSON string of request body.
            timeout: Request timeout in seconds (1-300).
            allow_private: Allow requests to private network addresses.
        """
        if not allow_private and is_private_url(url):
            return {"status": 0, "error": "SSRF blocked: private/internal URL"}

        timeout = max(1, min(timeout, 300))
        parsed_headers = safe_json_parse(headers, default={})
        parsed_body = safe_json_parse(body)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=parsed_headers,
                    json=parsed_body if parsed_body is not None else None,
                )
                try:
                    resp_body = resp.json()
                except Exception:
                    resp_body = resp.text

                return {
                    "status": resp.status_code,
                    "headers": dict(resp.headers),
                    "body": resp_body,
                }
        except httpx.HTTPError as exc:
            return {"status": 0, "error": str(exc)}
```

**Step 3: Run tests**

Run: `pytest tests/tools/test_http.py -v`
Expected: ALL PASS

**Step 4: Run full suite to check nothing broken**

Run: `pytest -v`
Note: Some tests may fail because they import old `HttpToolConfig`/`HttpToolResponse`. These will be fixed as we migrate each tool. For now, ensure http tests pass.

**Step 5: Commit**

```bash
git add pyflow/tools/http.py tests/tools/test_http.py
git commit -m "refactor: migrate HttpTool to pure function parameters"
```

---

### Task 2.3: Migrate TransformTool

**Files:**
- Modify: `pyflow/tools/transform.py`
- Test: `tests/tools/test_transform.py`

**Step 1: Write tests for new signature**

```python
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pyflow.tools.transform import TransformTool


class TestTransformToolExecute:
    async def test_simple_property(self):
        tool = TransformTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            input_data='{"name": "Alice", "age": 30}',
            expression="$.name",
        )
        assert result["result"] == "Alice"

    async def test_array_indexing(self):
        tool = TransformTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            input_data='{"items": ["a", "b", "c"]}',
            expression="$.items.[1]",
        )
        assert result["result"] == "b"

    async def test_wildcard_returns_list(self):
        tool = TransformTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            input_data='{"items": [{"id": 1}, {"id": 2}]}',
            expression="$.items[*].id",
        )
        assert result["result"] == [1, 2]

    async def test_no_match_returns_none(self):
        tool = TransformTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            input_data='{"name": "Alice"}',
            expression="$.nonexistent",
        )
        assert result["result"] is None

    async def test_invalid_expression_returns_error(self):
        tool = TransformTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            input_data='{"name": "Alice"}',
            expression="$$$invalid",
        )
        assert "error" in result

    async def test_invalid_json_input_returns_error(self):
        tool = TransformTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            input_data="not json",
            expression="$.name",
        )
        assert "error" in result


class TestTransformToolRegistration:
    def test_auto_registered(self):
        import pyflow.tools  # noqa: F401
        from pyflow.tools.base import get_registered_tools
        assert "transform" in get_registered_tools()
```

**Step 2: Rewrite TransformTool**

```python
from __future__ import annotations

from google.adk.tools.tool_context import ToolContext

from pyflow.tools.base import BasePlatformTool
from pyflow.tools.parsing import safe_json_parse


class TransformTool(BasePlatformTool):
    """Apply JSONPath expressions to transform structured data."""

    name = "transform"
    description = "Apply a JSONPath expression to extract or transform data from a JSON input."

    async def execute(
        self,
        tool_context: ToolContext,
        input_data: str,
        expression: str,
    ) -> dict:
        """Apply JSONPath expression to input data.

        Args:
            input_data: JSON string to transform.
            expression: JSONPath expression (e.g. '$.name', '$.items[*].id').
        """
        parsed = safe_json_parse(input_data)
        if parsed is None:
            return {"result": None, "error": "Invalid JSON input"}

        try:
            from jsonpath_ng import parse as jp_parse

            matches = jp_parse(expression).find(parsed)
        except Exception as exc:
            return {"result": None, "error": f"JSONPath error: {exc}"}

        if not matches:
            return {"result": None}
        if len(matches) == 1:
            return {"result": matches[0].value}
        return {"result": [m.value for m in matches]}
```

**Step 3: Run tests**

Run: `pytest tests/tools/test_transform.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add pyflow/tools/transform.py tests/tools/test_transform.py
git commit -m "refactor: migrate TransformTool to pure function parameters"
```

---

### Task 2.4: Migrate ConditionTool

**Files:**
- Modify: `pyflow/tools/condition.py`
- Test: `tests/tools/test_condition.py`

**Step 1: Write tests — now returns explicit errors instead of silent False**

```python
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pyflow.tools.condition import ConditionTool


class TestConditionToolExecute:
    async def test_true_expression(self):
        tool = ConditionTool()
        result = await tool.execute(tool_context=MagicMock(), expression="1 + 1 == 2")
        assert result["result"] is True

    async def test_false_expression(self):
        tool = ConditionTool()
        result = await tool.execute(tool_context=MagicMock(), expression="1 > 2")
        assert result["result"] is False

    async def test_comparison_operators(self):
        tool = ConditionTool()
        result = await tool.execute(
            tool_context=MagicMock(), expression="100 >= 50 and 10 < 20"
        )
        assert result["result"] is True

    async def test_string_comparison(self):
        tool = ConditionTool()
        result = await tool.execute(
            tool_context=MagicMock(), expression="'hello' == 'hello'"
        )
        assert result["result"] is True

    async def test_dangerous_import_rejected(self):
        tool = ConditionTool()
        expr = "__" + "import__('os').system('ls')"
        result = await tool.execute(tool_context=MagicMock(), expression=expr)
        assert result["result"] is False
        assert "error" in result

    async def test_dangerous_eval_rejected(self):
        tool = ConditionTool()
        # Build dynamically to avoid static analysis
        expr = "ev" + "al('1+1')"
        result = await tool.execute(tool_context=MagicMock(), expression=expr)
        assert result["result"] is False
        assert "error" in result

    async def test_syntax_error_returns_error(self):
        tool = ConditionTool()
        result = await tool.execute(tool_context=MagicMock(), expression="if then else")
        assert result["result"] is False
        assert "error" in result


class TestConditionToolRegistration:
    def test_auto_registered(self):
        import pyflow.tools  # noqa: F401
        from pyflow.tools.base import get_registered_tools
        assert "condition" in get_registered_tools()
```

**Step 2: Rewrite ConditionTool**

Keep the AST validation logic (it's good security). Change: return `{"result": False, "error": "..."}` on failure instead of silent `{"result": False}`. Change execute signature to use `tool_context` and `expression` as direct params.

**Step 3: Run tests**

Run: `pytest tests/tools/test_condition.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add pyflow/tools/condition.py tests/tools/test_condition.py
git commit -m "refactor: migrate ConditionTool with explicit error reporting"
```

---

### Task 2.5: Migrate AlertTool (add SSRF protection)

**Files:**
- Modify: `pyflow/tools/alert.py`
- Test: `tests/tools/test_alert.py`

Key change: AlertTool now uses `is_private_url` from shared security module.

**Step 1: Write tests including SSRF**

Add SSRF test:

```python
async def test_ssrf_blocked(self):
    tool = AlertTool()
    result = await tool.execute(
        tool_context=MagicMock(),
        webhook_url="http://169.254.169.254/latest/meta-data",
        message="test",
    )
    assert result["sent"] is False
    assert "SSRF" in result.get("error", "") or "private" in result.get("error", "").lower()
```

**Step 2: Rewrite AlertTool with SSRF protection**

**Step 3: Run tests, commit**

```bash
git commit -m "refactor: migrate AlertTool with SSRF protection"
```

---

### Task 2.6: Migrate StorageTool

**Files:**
- Modify: `pyflow/tools/storage.py`
- Test: `tests/tools/test_storage.py`

Key change: `data` parameter becomes JSON string instead of `Any`.

**Step 1: Write tests with JSON string data**

**Step 2: Rewrite StorageTool**

**Step 3: Run tests, commit**

```bash
git commit -m "refactor: migrate StorageTool to JSON string data parameter"
```

---

### Task 2.7: Update tools/__init__.py and remove old ToolConfig/ToolResponse

**Files:**
- Modify: `pyflow/tools/__init__.py`
- Modify: `pyflow/models/tool.py`

**Step 1: Remove deprecated ToolConfig/ToolResponse from tool.py**

Now that all tools are migrated, remove the deprecated classes entirely.

**Step 2: Update __init__.py imports if needed**

**Step 3: Run full test suite**

Run: `pytest -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git commit -m "refactor: remove deprecated ToolConfig and ToolResponse base classes"
```

---

### Task 2.8: Add ADK built-in tool catalog to ToolRegistry

**Files:**
- Modify: `pyflow/platform/registry/tool_registry.py`
- Test: `tests/platform/registry/test_tool_registry.py`

**Step 1: Write failing test**

```python
class TestBuiltinToolCatalog:
    def test_resolve_exit_loop(self):
        registry = ToolRegistry()
        registry.discover()
        tools = registry.resolve_tools(["exit_loop"])
        assert len(tools) == 1

    def test_custom_takes_priority(self):
        registry = ToolRegistry()
        registry.discover()
        # http_request is a custom tool, should resolve to our HttpTool
        tool = registry.get_function_tool("http_request")
        assert tool is not None
```

**Step 2: Add built-in catalog to ToolRegistry**

```python
from google.adk.tools.exit_loop_tool import exit_loop
from google.adk.tools import FunctionTool

ADK_BUILTIN_TOOLS = {
    "exit_loop": lambda: FunctionTool(func=exit_loop),
}
```

In `get_function_tool()`, check custom registry first, then built-in catalog.

**Step 3: Run tests, commit**

```bash
git commit -m "feat: add ADK built-in tool catalog to ToolRegistry"
```

---

## Phase 3: Orchestration

### Task 3.1: Implement DagAgent

**Files:**
- Create: `pyflow/platform/agents/__init__.py`
- Create: `pyflow/platform/agents/dag_agent.py`
- Test: `tests/platform/agents/test_dag_agent.py`

**Step 1: Write failing tests**

Create `tests/platform/agents/__init__.py` (empty) and `tests/platform/agents/test_dag_agent.py`:

```python
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from pyflow.platform.agents.dag_agent import DagAgent, DagNode


class TestDagValidation:
    def test_valid_dag(self):
        a = MagicMock(name="a")
        b = MagicMock(name="b")
        nodes = [
            DagNode(name="a", agent=a, depends_on=[]),
            DagNode(name="b", agent=b, depends_on=["a"]),
        ]
        dag = DagAgent(name="test_dag", nodes=nodes)
        assert len(dag.nodes) == 2

    def test_detects_cycle(self):
        a = MagicMock(name="a")
        b = MagicMock(name="b")
        nodes = [
            DagNode(name="a", agent=a, depends_on=["b"]),
            DagNode(name="b", agent=b, depends_on=["a"]),
        ]
        with pytest.raises(ValueError, match="cycle"):
            DagAgent(name="test_dag", nodes=nodes)

    def test_unknown_dependency(self):
        a = MagicMock(name="a")
        nodes = [
            DagNode(name="a", agent=a, depends_on=["nonexistent"]),
        ]
        with pytest.raises(ValueError, match="Unknown dependency"):
            DagAgent(name="test_dag", nodes=nodes)

    def test_single_node_no_deps(self):
        a = MagicMock(name="a")
        nodes = [DagNode(name="a", agent=a, depends_on=[])]
        dag = DagAgent(name="test_dag", nodes=nodes)
        assert len(dag.nodes) == 1

    def test_diamond_dag(self):
        """A → B, A → C, B → D, C → D"""
        agents = {n: MagicMock(name=n) for n in "abcd"}
        nodes = [
            DagNode(name="a", agent=agents["a"], depends_on=[]),
            DagNode(name="b", agent=agents["b"], depends_on=["a"]),
            DagNode(name="c", agent=agents["c"], depends_on=["a"]),
            DagNode(name="d", agent=agents["d"], depends_on=["b", "c"]),
        ]
        dag = DagAgent(name="diamond", nodes=nodes)
        assert len(dag.nodes) == 4
```

**Step 2: Implement DagAgent**

Create `pyflow/platform/agents/dag_agent.py`. DagAgent extends `BaseAgent` (which is a Pydantic BaseModel). The `_run_async_impl` method implements the wave execution scheduler.

Key implementation notes:
- `BaseAgent` is Pydantic, so use `model_config = ConfigDict(arbitrary_types_allowed=True)` if needed
- `_run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]`
- Use `asyncio.TaskGroup` for parallel execution within each wave
- Each node's agent is run via its own `run_async(ctx)` method

**Step 3: Run tests, commit**

```bash
git commit -m "feat: implement DagAgent with topological sort and wave execution"
```

---

### Task 3.2: Create callbacks registry

**Files:**
- Create: `pyflow/platform/callbacks.py`
- Test: `tests/platform/test_callbacks.py`

**Step 1: Write failing tests**

```python
from __future__ import annotations

from pyflow.platform.callbacks import register_callback, resolve_callback, CALLBACK_REGISTRY


class TestCallbackRegistry:
    def test_register_and_resolve(self):
        async def my_callback(ctx):
            pass

        register_callback("test_cb", my_callback)
        assert resolve_callback("test_cb") is my_callback

    def test_resolve_unknown_returns_none(self):
        assert resolve_callback("nonexistent") is None

    def test_resolve_none_returns_none(self):
        assert resolve_callback(None) is None
```

**Step 2: Implement callbacks.py**

```python
from __future__ import annotations

from typing import Any, Callable

CALLBACK_REGISTRY: dict[str, Callable] = {}


def register_callback(name: str, fn: Callable) -> None:
    CALLBACK_REGISTRY[name] = fn


def resolve_callback(name: str | None) -> Callable | None:
    if name is None:
        return None
    return CALLBACK_REGISTRY.get(name)
```

**Step 3: Run tests, commit**

```bash
git commit -m "feat: add callback registry for agent lifecycle hooks"
```

---

### Task 3.3: Create plugin registry

**Files:**
- Create: `pyflow/platform/plugins.py`
- Test: `tests/platform/test_plugins.py`

**Step 1: Write failing tests**

```python
from __future__ import annotations

from pyflow.platform.plugins import resolve_plugins


class TestPluginRegistry:
    def test_resolve_logging(self):
        plugins = resolve_plugins(["logging"])
        assert len(plugins) == 1

    def test_resolve_empty_list(self):
        plugins = resolve_plugins([])
        assert plugins == []

    def test_unknown_plugin_skipped(self):
        plugins = resolve_plugins(["nonexistent"])
        assert plugins == []

    def test_resolve_multiple(self):
        plugins = resolve_plugins(["logging"])
        assert len(plugins) >= 1
```

**Step 2: Implement plugins.py**

```python
from __future__ import annotations

from google.adk.plugins import LoggingPlugin

PLUGIN_FACTORIES: dict[str, callable] = {
    "logging": lambda: LoggingPlugin(),
}

# ReflectAndRetryToolPlugin is experimental, import conditionally
try:
    from google.adk.plugins import ReflectAndRetryToolPlugin
    PLUGIN_FACTORIES["reflect_and_retry"] = lambda: ReflectAndRetryToolPlugin()
except ImportError:
    pass


def resolve_plugins(names: list[str]) -> list:
    return [PLUGIN_FACTORIES[name]() for name in names if name in PLUGIN_FACTORIES]
```

**Step 3: Run tests, commit**

```bash
git commit -m "feat: add plugin registry for ADK plugins"
```

---

### Task 3.4: Refactor WorkflowHydrator for 6 orchestration types

**Files:**
- Modify: `pyflow/platform/hydration/hydrator.py`
- Test: `tests/platform/hydration/test_hydrator.py`

This is the largest single task. The hydrator must now:
1. Build agents recursively (supporting `sub_agents` nesting)
2. Handle 6 orchestration types
3. Resolve callbacks from registry
4. Resolve planners for react type

**Step 1: Write failing tests for new orchestration types**

Add to `tests/platform/hydration/test_hydrator.py`:

```python
class TestHydrateReactOrchestration:
    def test_react_adds_planner(self):
        # Workflow with type=react, agent=reasoner, planner=plan_react
        ...

class TestHydrateDagOrchestration:
    def test_dag_creates_dag_agent(self):
        # Workflow with type=dag, nodes with dependencies
        ...

class TestHydrateLlmRoutedOrchestration:
    def test_llm_routed_sets_sub_agents_on_router(self):
        # Workflow with type=llm_routed, router=dispatcher
        ...

class TestHydrateNestedAgents:
    def test_sequential_agent_with_sub_agents(self):
        # AgentConfig type=sequential with sub_agents=["a", "b"]
        ...

class TestHydrateCallbacks:
    def test_callbacks_resolved_from_registry(self):
        # AgentConfig with callbacks={"before_agent": "log_start"}
        ...

class TestHydrateLoopWithMaxIterations:
    def test_max_iterations_passed(self):
        # OrchestrationConfig type=loop, max_iterations=5
        ...
```

**Step 2: Rewrite hydrator**

The new hydrator has these methods:
- `hydrate(workflow: WorkflowDef) -> BaseAgent` — entry point
- `_build_agents(configs: list[AgentConfig]) -> dict[str, BaseAgent]` — build all agents
- `_build_agent(config: AgentConfig, agents: dict) -> BaseAgent` — dispatch by type
- `_build_llm_agent(config: AgentConfig) -> LlmAgent` — with callbacks, tools, model
- `_build_workflow_agent(config: AgentConfig, agents: dict) -> BaseAgent` — sequential/parallel/loop with sub_agents
- `_build_orchestration(workflow: WorkflowDef, agents: dict) -> BaseAgent` — 6-way dispatch
- `_resolve_model(model_str: str)` — LiteLlm for anthropic/openai
- `_resolve_callbacks(callbacks: dict | None) -> dict` — resolve callback names to functions
- `_resolve_planner(planner: str | None)` — PlanReActPlanner or None

**Step 3: Run tests**

Run: `pytest tests/platform/hydration/test_hydrator.py -v`
Expected: ALL PASS

**Step 4: Run full suite**

Run: `pytest -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git commit -m "refactor: hydrator supports 6 orchestration types, nested agents, callbacks"
```

---

## Phase 4: Execution

### Task 4.1: Implement WorkflowExecutor

**Files:**
- Create: `pyflow/platform/executor.py`
- Test: `tests/platform/test_executor.py`

**Step 1: Write failing tests**

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyflow.models.runner import RunResult
from pyflow.models.workflow import RuntimeConfig
from pyflow.platform.executor import WorkflowExecutor


class TestBuildRunner:
    def test_default_runtime_config(self):
        executor = WorkflowExecutor()
        agent = MagicMock()
        runtime = RuntimeConfig()
        with patch("pyflow.platform.executor.Runner") as mock_runner:
            executor.build_runner(agent, runtime)
            mock_runner.assert_called_once()

    def test_sqlite_session_service(self):
        executor = WorkflowExecutor()
        agent = MagicMock()
        runtime = RuntimeConfig(
            session_service="sqlite",
            session_db_url="sqlite+aiosqlite:///test.db",
        )
        with patch("pyflow.platform.executor.Runner") as mock_runner:
            with patch("pyflow.platform.executor.DatabaseSessionService") as mock_db:
                executor.build_runner(agent, runtime)
                mock_db.assert_called_once()

    def test_memory_service_configured(self):
        executor = WorkflowExecutor()
        agent = MagicMock()
        runtime = RuntimeConfig(memory_service="in_memory")
        with patch("pyflow.platform.executor.Runner") as mock_runner:
            executor.build_runner(agent, runtime)
            call_kwargs = mock_runner.call_args[1]
            assert call_kwargs["memory_service"] is not None

    def test_plugins_resolved(self):
        executor = WorkflowExecutor()
        agent = MagicMock()
        runtime = RuntimeConfig(plugins=["logging"])
        with patch("pyflow.platform.executor.Runner") as mock_runner:
            executor.build_runner(agent, runtime)
            call_kwargs = mock_runner.call_args[1]
            assert call_kwargs["plugins"] is not None


class TestRun:
    async def test_returns_run_result(self):
        executor = WorkflowExecutor()
        # Mock runner with run_async that yields a final event
        mock_event = MagicMock()
        mock_event.is_final_response.return_value = True
        mock_event.content.parts = [MagicMock(text="Hello")]
        mock_event.content.role = "model"

        mock_runner = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run_async(**kwargs):
            yield mock_event

        mock_runner.run_async = fake_run_async

        result = await executor.run(mock_runner, user_id="user1", message="hi")
        assert isinstance(result, RunResult)
        assert result.session_id == "sess-1"

    async def test_empty_response(self):
        executor = WorkflowExecutor()
        mock_runner = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_runner.session_service.create_session = AsyncMock(return_value=mock_session)

        async def fake_run_async(**kwargs):
            return
            yield  # make it an async generator

        mock_runner.run_async = fake_run_async

        result = await executor.run(mock_runner, user_id="user1", message="hi")
        assert result.content == ""
```

**Step 2: Implement WorkflowExecutor**

Create `pyflow/platform/executor.py` with `build_runner()`, `run()`, and `run_streaming()` methods.

**Step 3: Run tests, commit**

```bash
git commit -m "feat: implement WorkflowExecutor replacing PlatformRunner and SessionManager"
```

---

### Task 4.2: Remove PlatformRunner and SessionManager

**Files:**
- Delete: `pyflow/platform/runner/engine.py`
- Delete: `pyflow/platform/session/service.py`
- Delete: `tests/platform/runner/test_engine.py`
- Delete: `tests/platform/session/test_service.py`

**Step 1: Delete files**

**Step 2: Run full test suite to confirm nothing depends on deleted files**

Run: `pytest -v`
Expected: ALL PASS (any remaining imports will fail and need fixing)

**Step 3: Commit**

```bash
git commit -m "refactor: remove PlatformRunner and SessionManager wrappers"
```

---

## Phase 5: Integration

### Task 5.1: Refactor PyFlowPlatform

**Files:**
- Modify: `pyflow/platform/app.py`
- Test: `tests/platform/test_app.py`

Replace `PlatformRunner` and `SessionManager` usage with `WorkflowExecutor`. The platform now:
1. Uses `WorkflowExecutor` directly
2. Builds runner per-workflow (each workflow has its own `RuntimeConfig`)
3. Passes `user_id` through instead of hardcoding "default"

**Step 1: Rewrite tests**

Update `tests/platform/test_app.py` to reflect new architecture (no more PlatformRunner, SessionManager).

**Step 2: Rewrite app.py**

**Step 3: Run tests, commit**

```bash
git commit -m "refactor: PyFlowPlatform uses WorkflowExecutor directly"
```

---

### Task 5.2: Update CLI

**Files:**
- Modify: `pyflow/cli.py`
- Test: `tests/test_cli.py`

Add `--user-id` option to `run` command. Update tests.

**Step 1: Update tests**

**Step 2: Update CLI**

**Step 3: Run tests, commit**

```bash
git commit -m "feat: add --user-id to CLI run command"
```

---

### Task 5.3: Update FastAPI server

**Files:**
- Modify: `pyflow/server.py`
- Modify: `pyflow/models/server.py`
- Test: `tests/test_server.py`

Add streaming endpoint. Pass user_id from request headers.

**Step 1: Add StreamEvent model to server.py models**

**Step 2: Add `/api/workflows/{name}/stream` SSE endpoint**

**Step 3: Update tests**

**Step 4: Commit**

```bash
git commit -m "feat: add streaming SSE endpoint and user_id support to server"
```

---

### Task 5.4: Migrate workflow YAMLs

**Files:**
- Modify: `workflows/exchange_tracker.yaml`
- Modify: `workflows/example.yaml`

Add `runtime:` section with defaults. Ensure they still validate.

**Step 1: Update YAMLs**

```yaml
# Add to each workflow:
runtime:
  session_service: in_memory
```

**Step 2: Run validation**

Run: `pyflow validate workflows/exchange_tracker.yaml`
Expected: "Valid workflow: exchange_tracker"

**Step 3: Commit**

```bash
git commit -m "chore: add runtime config to example workflows"
```

---

### Task 5.5: Integration tests

**Files:**
- Modify: `tests/test_integration.py`

Update integration tests to verify:
- Platform boots with new architecture
- WorkflowExecutor is used (not PlatformRunner)
- Workflows with runtime config hydrate correctly
- All 6 orchestration types validate

**Step 1: Update integration tests**

**Step 2: Run full suite**

Run: `pytest -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git commit -m "test: update integration tests for ADK-first architecture"
```

---

## Phase 6: Verification

### Task 6.1: Full test suite

Run: `pytest -v`
Expected: ALL tests PASS (should be ~280+ tests now)

### Task 6.2: Lint and format

Run: `ruff check pyflow/ tests/ --fix && ruff format pyflow/ tests/`
Expected: Clean

### Task 6.3: Final commit

```bash
git commit -m "chore: lint and format after ADK-first redesign"
```

---

## Dependency Summary

**Execution order (tasks that block others):**

```
Phase 1 (1.1-1.7) → Phase 2 (2.1-2.8) → Phase 3 (3.1-3.4) → Phase 4 (4.1-4.2) → Phase 5 (5.1-5.5) → Phase 6
```

Within each phase, tasks are mostly sequential (each builds on the previous). Exceptions:
- Tasks 2.2-2.6 (individual tool migrations) can run in parallel after 2.1
- Tasks 3.1, 3.2, 3.3 can run in parallel (DagAgent, callbacks, plugins are independent)
- Tasks 5.2, 5.3, 5.4 can run in parallel after 5.1

**Total estimated tasks:** 25 tasks across 6 phases
**Total new tests:** ~60 new tests (bringing total to ~280+)
