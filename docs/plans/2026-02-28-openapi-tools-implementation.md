# OpenAPI Tools Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the custom YnabTool with ADK-native OpenAPIToolset support, enabling any OpenAPI-spec'd API to be consumed declaratively via YAML.

**Architecture:** Add `openapi_tools` field to `AgentConfig` (not RuntimeConfig). The hydrator creates `OpenAPIToolset` instances and passes them directly to `LlmAgent(tools=[...])` — ADK handles expansion, auth, and lifecycle natively. Remove YnabTool and its tests. YNAB becomes the first consumer via its official OpenAPI spec.

**Tech Stack:** google-adk `OpenAPIToolset`/`BaseToolset`, Pydantic v2 models, ADK auth helpers (`token_to_scheme_credential`, `OAuth2Auth`)

**Design Doc:** `docs/plans/2026-02-28-openapi-tools-design.md`

---

### Task 1: Add OpenApiAuthConfig and OpenApiToolConfig models to agent.py

**Files:**
- Modify: `pyflow/models/agent.py`
- Create: `tests/models/test_openapi_config.py`

**Step 1: Write the failing tests**

Create `tests/models/test_openapi_config.py`:

```python
from __future__ import annotations

import pytest

from pyflow.models.agent import AgentConfig, OpenApiAuthConfig, OpenApiToolConfig


class TestOpenApiAuthConfig:
    def test_default_none(self):
        auth = OpenApiAuthConfig()
        assert auth.type == "none"
        assert auth.token_env is None

    def test_bearer(self):
        auth = OpenApiAuthConfig(type="bearer", token_env="PYFLOW_YNAB_API_TOKEN")
        assert auth.type == "bearer"
        assert auth.token_env == "PYFLOW_YNAB_API_TOKEN"

    def test_apikey(self):
        auth = OpenApiAuthConfig(
            type="apikey",
            token_env="PYFLOW_MY_API_KEY",
            apikey_location="query",
            apikey_name="api_key",
        )
        assert auth.apikey_location == "query"
        assert auth.apikey_name == "api_key"

    def test_apikey_defaults(self):
        auth = OpenApiAuthConfig(type="apikey", token_env="KEY")
        assert auth.apikey_location == "query"
        assert auth.apikey_name == "apikey"

    def test_oauth2(self):
        auth = OpenApiAuthConfig(
            type="oauth2",
            authorization_url="https://accounts.example.com/auth",
            token_url="https://accounts.example.com/token",
            scopes={"read": "Read access"},
            client_id_env="PYFLOW_CLIENT_ID",
            client_secret_env="PYFLOW_CLIENT_SECRET",
        )
        assert auth.type == "oauth2"
        assert auth.scopes == {"read": "Read access"}


class TestOpenApiToolConfig:
    def test_basic_spec(self):
        config = OpenApiToolConfig(spec="specs/petstore.yaml")
        assert config.spec == "specs/petstore.yaml"
        assert config.name_prefix is None
        assert config.auth.type == "none"

    def test_with_prefix_and_auth(self):
        config = OpenApiToolConfig(
            spec="specs/ynab.json",
            name_prefix="ynab",
            auth=OpenApiAuthConfig(type="bearer", token_env="PYFLOW_YNAB_TOKEN"),
        )
        assert config.name_prefix == "ynab"
        assert config.auth.type == "bearer"


class TestAgentConfigOpenApiTools:
    def test_default_empty(self):
        agent = AgentConfig(
            name="test", type="llm", model="gemini-2.5-flash", instruction="Do stuff"
        )
        assert agent.openapi_tools == []

    def test_with_openapi_tools(self):
        agent = AgentConfig(
            name="test",
            type="llm",
            model="gemini-2.5-flash",
            instruction="Do stuff",
            openapi_tools=[
                OpenApiToolConfig(
                    spec="specs/ynab.json",
                    auth=OpenApiAuthConfig(type="bearer", token_env="TOKEN"),
                )
            ],
        )
        assert len(agent.openapi_tools) == 1
        assert agent.openapi_tools[0].auth.type == "bearer"
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/models/test_openapi_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'OpenApiAuthConfig' from 'pyflow.models.agent'`

**Step 3: Add the models to agent.py**

Add these classes to `pyflow/models/agent.py` (before `AgentConfig`):

```python
class OpenApiAuthConfig(BaseModel):
    """Authentication configuration for OpenAPI toolsets."""

    type: Literal["none", "bearer", "apikey", "oauth2"] = "none"
    # bearer: env var containing the token
    token_env: str | None = None
    # apikey
    apikey_location: Literal["header", "query"] = "query"
    apikey_name: str = "apikey"
    # oauth2: authorization code flow
    authorization_url: str | None = None
    token_url: str | None = None
    scopes: dict[str, str] | None = None
    client_id_env: str | None = None
    client_secret_env: str | None = None


class OpenApiToolConfig(BaseModel):
    """Configuration for auto-generating tools from an OpenAPI spec."""

    spec: str
    name_prefix: str | None = None
    auth: OpenApiAuthConfig = OpenApiAuthConfig()
```

Add to `AgentConfig`:

```python
    # OpenAPI tools
    openapi_tools: list[OpenApiToolConfig] = []
```

Place it after the `agent_tools` field (line 38).

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/models/test_openapi_config.py -v`
Expected: All 9 tests PASS.

**Step 5: Run full test suite to verify no regressions**

Run: `source .venv/bin/activate && pytest -v`
Expected: All 547 tests PASS (no regressions — new field has a default empty list).

**Step 6: Commit**

```bash
git add pyflow/models/agent.py tests/models/test_openapi_config.py
git commit -m "feat: add OpenApiAuthConfig and OpenApiToolConfig models to AgentConfig"
```

---

### Task 2: Remove OpenApiToolConfig from RuntimeConfig and update old tests

**Files:**
- Modify: `pyflow/models/workflow.py` — remove `OpenApiToolConfig` class and `RuntimeConfig.openapi_tools` field
- Modify: `tests/platform/test_openapi_tools.py` — rewrite to test new location

**Step 1: Rewrite tests/platform/test_openapi_tools.py**

Replace the entire file content with tests that import from the new location:

```python
from __future__ import annotations

from pyflow.models.agent import OpenApiAuthConfig, OpenApiToolConfig
from pyflow.models.workflow import RuntimeConfig


class TestOpenApiToolConfigFromAgent:
    """Verify OpenApiToolConfig lives in agent.py (not workflow.py)."""

    def test_basic_config(self):
        config = OpenApiToolConfig(spec="specs/petstore.yaml")
        assert config.spec == "specs/petstore.yaml"
        assert config.name_prefix is None

    def test_config_with_prefix_and_auth(self):
        config = OpenApiToolConfig(
            spec="specs/ynab.yaml",
            name_prefix="ynab",
            auth=OpenApiAuthConfig(type="bearer", token_env="PYFLOW_TOKEN"),
        )
        assert config.name_prefix == "ynab"
        assert config.auth.type == "bearer"


class TestRuntimeConfigNoOpenApiTools:
    """Verify openapi_tools was removed from RuntimeConfig."""

    def test_no_openapi_tools_field(self):
        runtime = RuntimeConfig()
        assert not hasattr(runtime, "openapi_tools")
```

**Step 2: Run the rewritten tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/platform/test_openapi_tools.py -v`
Expected: FAIL — `RuntimeConfig` still has `openapi_tools` attribute so `test_no_openapi_tools_field` fails.

**Step 3: Remove from workflow.py**

In `pyflow/models/workflow.py`:
1. Delete the `OpenApiToolConfig` class (lines 41-46):
   ```python
   class OpenApiToolConfig(BaseModel):
       """Configuration for auto-generating tools from an OpenAPI spec."""

       spec: str  # Path to OpenAPI spec file (YAML or JSON)
       name_prefix: str | None = None
   ```
2. Delete the `openapi_tools` field from `RuntimeConfig` (line 71):
   ```python
       openapi_tools: list[OpenApiToolConfig] = []
   ```

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/platform/test_openapi_tools.py -v`
Expected: All 3 tests PASS.

**Step 5: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`
Expected: All tests PASS. (The old openapi tests were replaced in step 1.)

**Step 6: Commit**

```bash
git add pyflow/models/workflow.py tests/platform/test_openapi_tools.py
git commit -m "refactor: move OpenApiToolConfig from RuntimeConfig to AgentConfig"
```

---

### Task 3: Add _resolve_openapi_auth helper to hydrator

**Files:**
- Create: `tests/platform/hydration/test_openapi_auth.py`
- Modify: `pyflow/platform/hydration/hydrator.py`

**Step 1: Write failing tests**

Create `tests/platform/hydration/test_openapi_auth.py`:

```python
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from pyflow.models.agent import OpenApiAuthConfig
from pyflow.platform.hydration.hydrator import _resolve_openapi_auth


class TestResolveOpenApiAuthNone:
    def test_none_returns_none_tuple(self):
        auth = OpenApiAuthConfig(type="none")
        scheme, credential = _resolve_openapi_auth(auth)
        assert scheme is None
        assert credential is None


class TestResolveOpenApiAuthBearer:
    def test_bearer_returns_http_scheme(self):
        auth = OpenApiAuthConfig(type="bearer", token_env="TEST_TOKEN")
        with patch.dict(os.environ, {"TEST_TOKEN": "my-secret-token"}):
            scheme, credential = _resolve_openapi_auth(auth)
        assert scheme is not None
        assert credential is not None

    def test_bearer_missing_env_returns_empty_token(self):
        auth = OpenApiAuthConfig(type="bearer", token_env="MISSING_VAR")
        with patch.dict(os.environ, {}, clear=True):
            scheme, credential = _resolve_openapi_auth(auth)
        # Should still return objects (ADK will fail at request time, not at config time)
        assert scheme is not None


class TestResolveOpenApiAuthApiKey:
    def test_apikey_returns_scheme(self):
        auth = OpenApiAuthConfig(
            type="apikey",
            token_env="TEST_API_KEY",
            apikey_location="query",
            apikey_name="api_key",
        )
        with patch.dict(os.environ, {"TEST_API_KEY": "key123"}):
            scheme, credential = _resolve_openapi_auth(auth)
        assert scheme is not None
        assert credential is not None


class TestResolveOpenApiAuthOAuth2:
    def test_oauth2_returns_scheme_and_credential(self):
        auth = OpenApiAuthConfig(
            type="oauth2",
            authorization_url="https://example.com/auth",
            token_url="https://example.com/token",
            scopes={"read": "Read access"},
            client_id_env="TEST_CLIENT_ID",
            client_secret_env="TEST_CLIENT_SECRET",
        )
        env = {"TEST_CLIENT_ID": "id123", "TEST_CLIENT_SECRET": "secret456"}
        with patch.dict(os.environ, env):
            scheme, credential = _resolve_openapi_auth(auth)
        assert scheme is not None
        assert credential is not None
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/platform/hydration/test_openapi_auth.py -v`
Expected: FAIL — `ImportError: cannot import name '_resolve_openapi_auth'`

**Step 3: Implement _resolve_openapi_auth in hydrator.py**

Add this function to `pyflow/platform/hydration/hydrator.py` (before the `WorkflowHydrator` class, after the imports):

```python
import os


def _resolve_openapi_auth(auth):
    """Map OpenApiAuthConfig to ADK auth_scheme + auth_credential.

    Returns (auth_scheme, auth_credential) tuple. Both are None for type='none'.
    """
    from pyflow.models.agent import OpenApiAuthConfig

    match auth.type:
        case "none":
            return None, None
        case "bearer":
            from google.adk.tools.openapi_tool.auth.auth_helpers import (
                token_to_scheme_credential,
            )

            token = os.environ.get(auth.token_env or "", "")
            return token_to_scheme_credential("http", "header", "Authorization", token)
        case "apikey":
            from google.adk.tools.openapi_tool.auth.auth_helpers import (
                token_to_scheme_credential,
            )

            key = os.environ.get(auth.token_env or "", "")
            return token_to_scheme_credential(
                "apikey", auth.apikey_location, auth.apikey_name, key
            )
        case "oauth2":
            from fastapi.openapi.models import OAuth2, OAuthFlowAuthorizationCode, OAuthFlows
            from google.adk.auth import AuthCredential, AuthCredentialTypes, OAuth2Auth

            auth_scheme = OAuth2(
                flows=OAuthFlows(
                    authorizationCode=OAuthFlowAuthorizationCode(
                        authorizationUrl=auth.authorization_url or "",
                        tokenUrl=auth.token_url or "",
                        scopes=auth.scopes or {},
                    )
                )
            )
            auth_credential = AuthCredential(
                auth_type=AuthCredentialTypes.OAUTH2,
                oauth2=OAuth2Auth(
                    client_id=os.environ.get(auth.client_id_env or "", ""),
                    client_secret=os.environ.get(auth.client_secret_env or "", ""),
                ),
            )
            return auth_scheme, auth_credential
        case _:
            return None, None
```

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/platform/hydration/test_openapi_auth.py -v`
Expected: All 5 tests PASS.

**Step 5: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add pyflow/platform/hydration/hydrator.py tests/platform/hydration/test_openapi_auth.py
git commit -m "feat: add _resolve_openapi_auth helper for OpenAPI toolset auth"
```

---

### Task 4: Wire OpenAPIToolset into hydrator's _build_llm_agent

**Files:**
- Create: `tests/platform/hydration/test_openapi_hydration.py`
- Modify: `pyflow/platform/hydration/hydrator.py` — update `__init__`, `hydrate`, `_build_llm_agent`, `build_root_agent`

**Step 1: Write failing tests**

Create `tests/platform/hydration/test_openapi_hydration.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pyflow.models.agent import AgentConfig, OpenApiAuthConfig, OpenApiToolConfig
from pyflow.models.workflow import OrchestrationConfig, WorkflowDef
from pyflow.platform.hydration.hydrator import WorkflowHydrator
from pyflow.platform.registry.tool_registry import ToolRegistry


# Minimal valid OpenAPI 3.0 spec for testing
MINI_SPEC = json.dumps({
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "servers": [{"url": "https://api.example.com"}],
    "paths": {
        "/items": {
            "get": {
                "operationId": "listItems",
                "summary": "List all items",
                "responses": {"200": {"description": "OK"}},
            }
        }
    },
})


def _make_workflow_with_openapi(
    spec_path: str = "specs/test.json",
    auth: OpenApiAuthConfig | None = None,
) -> WorkflowDef:
    return WorkflowDef(
        name="test_openapi",
        agents=[
            AgentConfig(
                name="agent1",
                type="llm",
                model="gemini-2.5-flash",
                instruction="Use the API",
                openapi_tools=[
                    OpenApiToolConfig(
                        spec=spec_path,
                        auth=auth or OpenApiAuthConfig(),
                    )
                ],
            )
        ],
        orchestration=OrchestrationConfig(type="react", agent="agent1"),
    )


class TestHydratorOpenApiTools:
    def test_openapi_toolset_appended_to_agent_tools(self, tmp_path):
        """When an agent has openapi_tools, hydrator creates OpenAPIToolset and appends it."""
        spec_file = tmp_path / "specs" / "test.json"
        spec_file.parent.mkdir(parents=True)
        spec_file.write_text(MINI_SPEC)

        registry = MagicMock(spec=ToolRegistry)
        registry.resolve_tools.return_value = []

        hydrator = WorkflowHydrator(registry, base_dir=tmp_path)
        workflow = _make_workflow_with_openapi(spec_path="specs/test.json")

        with patch(
            "pyflow.platform.hydration.hydrator.OpenAPIToolset"
        ) as MockToolset:
            mock_instance = MagicMock()
            MockToolset.return_value = mock_instance

            agent = hydrator.hydrate(workflow)

        # OpenAPIToolset should have been created
        MockToolset.assert_called_once()
        call_kwargs = MockToolset.call_args
        assert "spec_str" in call_kwargs.kwargs or len(call_kwargs.args) > 0

    def test_openapi_toolset_with_bearer_auth(self, tmp_path):
        """Bearer auth config is passed to OpenAPIToolset."""
        spec_file = tmp_path / "specs" / "test.json"
        spec_file.parent.mkdir(parents=True)
        spec_file.write_text(MINI_SPEC)

        registry = MagicMock(spec=ToolRegistry)
        registry.resolve_tools.return_value = []

        auth = OpenApiAuthConfig(type="bearer", token_env="TEST_TOKEN")
        hydrator = WorkflowHydrator(registry, base_dir=tmp_path)
        workflow = _make_workflow_with_openapi(auth=auth)

        with patch(
            "pyflow.platform.hydration.hydrator.OpenAPIToolset"
        ) as MockToolset, patch.dict("os.environ", {"TEST_TOKEN": "abc123"}):
            mock_instance = MagicMock()
            MockToolset.return_value = mock_instance

            agent = hydrator.hydrate(workflow)

        MockToolset.assert_called_once()
        call_kwargs = MockToolset.call_args.kwargs
        assert call_kwargs.get("auth_scheme") is not None
        assert call_kwargs.get("auth_credential") is not None

    def test_multiple_openapi_toolsets(self, tmp_path):
        """Agent can have multiple openapi_tools entries."""
        for name in ("spec1.json", "spec2.json"):
            spec_file = tmp_path / "specs" / name
            spec_file.parent.mkdir(parents=True, exist_ok=True)
            spec_file.write_text(MINI_SPEC)

        registry = MagicMock(spec=ToolRegistry)
        registry.resolve_tools.return_value = []

        workflow = WorkflowDef(
            name="multi_openapi",
            agents=[
                AgentConfig(
                    name="agent1",
                    type="llm",
                    model="gemini-2.5-flash",
                    instruction="Use APIs",
                    openapi_tools=[
                        OpenApiToolConfig(spec="specs/spec1.json"),
                        OpenApiToolConfig(spec="specs/spec2.json"),
                    ],
                )
            ],
            orchestration=OrchestrationConfig(type="react", agent="agent1"),
        )

        hydrator = WorkflowHydrator(registry, base_dir=tmp_path)

        with patch(
            "pyflow.platform.hydration.hydrator.OpenAPIToolset"
        ) as MockToolset:
            MockToolset.return_value = MagicMock()
            agent = hydrator.hydrate(workflow)

        assert MockToolset.call_count == 2

    def test_no_openapi_tools_unchanged(self):
        """Agent without openapi_tools works as before."""
        registry = MagicMock(spec=ToolRegistry)
        registry.resolve_tools.return_value = [MagicMock()]

        workflow = WorkflowDef(
            name="no_openapi",
            agents=[
                AgentConfig(
                    name="agent1",
                    type="llm",
                    model="gemini-2.5-flash",
                    instruction="No OpenAPI",
                    tools=["http_request"],
                )
            ],
            orchestration=OrchestrationConfig(type="react", agent="agent1"),
        )

        hydrator = WorkflowHydrator(registry)
        agent = hydrator.hydrate(workflow)
        # Should work fine — no OpenAPI involved
        assert agent is not None


class TestBuildRootAgentOpenApi:
    def test_build_root_agent_passes_base_dir(self, tmp_path):
        """build_root_agent should derive base_dir from caller_file's parent."""
        # We test that WorkflowHydrator receives base_dir when built via build_root_agent
        workflow_yaml = tmp_path / "workflow.yaml"
        workflow_yaml.write_text(
            "name: test\n"
            "agents:\n"
            "  - name: a1\n"
            "    type: llm\n"
            "    model: gemini-2.5-flash\n"
            "    instruction: hi\n"
            "orchestration:\n"
            "  type: react\n"
            "  agent: a1\n"
        )
        agent_py = tmp_path / "agent.py"
        agent_py.write_text("")  # Dummy caller file

        with patch(
            "pyflow.platform.hydration.hydrator.WorkflowHydrator"
        ) as MockHydrator:
            mock_instance = MagicMock()
            mock_instance.hydrate.return_value = MagicMock()
            MockHydrator.return_value = mock_instance

            from pyflow.platform.hydration.hydrator import build_root_agent

            build_root_agent(str(agent_py))

        # Verify base_dir was passed
        call_kwargs = MockHydrator.call_args
        # base_dir should be tmp_path (parent of agent.py)
        assert call_kwargs.kwargs.get("base_dir") == tmp_path or (
            len(call_kwargs.args) > 1 and call_kwargs.args[1] == tmp_path
        )
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/platform/hydration/test_openapi_hydration.py -v`
Expected: FAIL — `WorkflowHydrator` doesn't accept `base_dir` parameter yet.

**Step 3: Update WorkflowHydrator**

In `pyflow/platform/hydration/hydrator.py`, make these changes:

1. Add import at the top (after existing imports):
   ```python
   from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset
   ```

2. Update `__init__` to accept `base_dir`:
   ```python
   def __init__(self, tool_registry: ToolRegistry, base_dir: Path | None = None) -> None:
       self._tool_registry = tool_registry
       self._base_dir = base_dir or Path(".")
   ```

3. Update `_build_llm_agent` — after `tools = ...` (line 99), add OpenAPI resolution:
   ```python
   tools = self._tool_registry.resolve_tools(config.tools) if config.tools else []

   # Resolve OpenAPI toolsets
   for openapi_cfg in config.openapi_tools:
       spec_path = self._base_dir / openapi_cfg.spec
       spec_str = spec_path.read_text()
       spec_type = "json" if spec_path.suffix == ".json" else "yaml"
       auth_scheme, auth_credential = _resolve_openapi_auth(openapi_cfg.auth)
       kwargs_openapi: dict = {
           "spec_str": spec_str,
           "spec_str_type": spec_type,
       }
       if auth_scheme is not None:
           kwargs_openapi["auth_scheme"] = auth_scheme
       if auth_credential is not None:
           kwargs_openapi["auth_credential"] = auth_credential
       tools.append(OpenAPIToolset(**kwargs_openapi))
   ```

4. Update `build_root_agent` to pass `base_dir`:
   ```python
   def build_root_agent(caller_file: str) -> BaseAgent:
       from pyflow.platform.registry.tool_registry import ToolRegistry

       workflow_dir = Path(caller_file).parent
       workflow_path = workflow_dir / "workflow.yaml"
       tools = ToolRegistry()
       tools.discover()
       workflow = WorkflowDef.from_yaml(workflow_path)
       hydrator = WorkflowHydrator(tools, base_dir=workflow_dir)
       return hydrator.hydrate(workflow)
   ```

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/platform/hydration/test_openapi_hydration.py -v`
Expected: All 5 tests PASS.

**Step 5: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`
Expected: All tests PASS. Existing hydrator tests don't pass `base_dir`, which defaults to `Path(".")`.

**Step 6: Commit**

```bash
git add pyflow/platform/hydration/hydrator.py tests/platform/hydration/test_openapi_hydration.py
git commit -m "feat: wire OpenAPIToolset into hydrator for LLM agents"
```

---

### Task 5: Download YNAB spec and update budget_analyst workflow

**Files:**
- Create: `agents/budget_analyst/specs/ynab-v1-swagger.json`
- Modify: `agents/budget_analyst/workflow.yaml`

**Step 1: Download the YNAB spec**

```bash
source .venv/bin/activate && mkdir -p agents/budget_analyst/specs && curl -sS "https://api.youneedabudget.com/papi/spec-v1-swagger.json" -o agents/budget_analyst/specs/ynab-v1-swagger.json
```

Verify it's valid JSON:
```bash
python -c "import json; json.load(open('agents/budget_analyst/specs/ynab-v1-swagger.json')); print('Valid JSON')"
```

**Step 2: Update budget_analyst/workflow.yaml**

Replace the entire file with:

```yaml
name: budget_analyst
description: "Personal budget analyst powered by YNAB — answers natural language questions about your finances"

agents:
  - name: analyst
    type: llm
    model: gemini-2.5-flash
    description: "Personal budget analyst with YNAB access — answers finance questions"
    temperature: 0.2
    max_output_tokens: 4096
    openapi_tools:
      - spec: specs/ynab-v1-swagger.json
        auth:
          type: bearer
          token_env: PYFLOW_YNAB_API_TOKEN
    instruction: >
      You are a personal budget analyst with access to the user's YNAB (You Need A Budget) data.
      Answer questions about their budgets, accounts, categories, transactions, and spending patterns.

      WORKFLOW:
      1. ALWAYS start by calling the appropriate budget listing tool to discover available budgets.
         Use the first budget's ID for all subsequent calls unless the user specifies otherwise.
      2. When the user asks about a time period (e.g. "this month"), use since_date based on today's date.
         For "this month", use the first day of the current month.
      3. Present your findings in a clear, human-readable format.

      CRITICAL — TOKEN BUDGET:
      - NEVER call transaction listing without since_date. Unfiltered responses are huge and will fail.

      IMPORTANT NOTES:
      - YNAB amounts are in "milliunits": divide by 1000 to get the real amount (e.g. -50000 = -$50.00).
      - Always convert milliunits to currency format in your responses.
      - Negative amounts = outflows (spending), positive amounts = inflows (income).
      - Use type_filter "uncategorized" or "unapproved" to find transactions needing attention.

      FORMAT:
      - Use currency formatting ($X.XX) for all amounts.
      - Group related data logically (by category, account, date range).
      - Highlight overspending or notable patterns.
      - Be concise but thorough.
    output_key: analysis

orchestration:
  type: react
  agent: analyst
  planner: plan_react

runtime:
  session_service: in_memory
  plugins: [logging]

a2a:
  version: "1.0.0"
  skills:
    - id: budget_analysis
      name: "Budget Analysis"
      description: "Analyze your YNAB budget — spending, balances, categories, and trends"
      tags:
        - finance
        - budget
        - ynab
```

**Step 3: Validate the updated workflow YAML loads**

```bash
source .venv/bin/activate && python -c "
from pyflow.models.workflow import WorkflowDef
from pathlib import Path
w = WorkflowDef.from_yaml(Path('agents/budget_analyst/workflow.yaml'))
print(f'Workflow: {w.name}')
print(f'Agent openapi_tools: {len(w.agents[0].openapi_tools)}')
print(f'Spec: {w.agents[0].openapi_tools[0].spec}')
print(f'Auth type: {w.agents[0].openapi_tools[0].auth.type}')
print('OK')
"
```

Expected: Prints workflow details and "OK".

**Step 4: Commit**

```bash
git add agents/budget_analyst/specs/ynab-v1-swagger.json agents/budget_analyst/workflow.yaml
git commit -m "feat: migrate budget_analyst to OpenAPI spec for YNAB"
```

---

### Task 6: Delete YnabTool and its tests

**Files:**
- Delete: `pyflow/tools/ynab.py`
- Delete: `tests/tools/test_ynab.py`
- Modify: `pyflow/tools/__init__.py` — remove YnabTool import

**Step 1: Remove YnabTool import from __init__.py**

In `pyflow/tools/__init__.py`:
1. Delete line 10: `from pyflow.tools.ynab import YnabTool  # noqa: F401`
2. Remove `"YnabTool"` from the `__all__` list

The file should look like:

```python
from __future__ import annotations

# Import all tool modules to trigger auto-registration via __init_subclass__
from pyflow.tools.alert import AlertTool  # noqa: F401
from pyflow.tools.base import get_registered_tools  # noqa: F401
from pyflow.tools.condition import ConditionTool  # noqa: F401
from pyflow.tools.http import HttpTool  # noqa: F401
from pyflow.tools.storage import StorageTool  # noqa: F401
from pyflow.tools.transform import TransformTool  # noqa: F401

__all__ = [
    "AlertTool",
    "ConditionTool",
    "HttpTool",
    "StorageTool",
    "TransformTool",
    "get_registered_tools",
]
```

**Step 2: Delete YnabTool source and tests**

```bash
rm pyflow/tools/ynab.py tests/tools/test_ynab.py
```

**Step 3: Update test_base.py — remove "ynab" assertion**

In `tests/tools/test_base.py`, line 47, delete:
```python
        assert "ynab" in tools
```

**Step 4: Update test_metrics_plugin.py — change "ynab" to a generic name**

In `tests/platform/test_metrics_plugin.py`, line 175, change:
```python
        tool.name = "ynab"
```
to:
```python
        tool.name = "http_request"
```

And line 185, change:
```python
            assert call_kwargs[1]["tool"] == "ynab"
```
to:
```python
            assert call_kwargs[1]["tool"] == "http_request"
```

**Step 5: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`
Expected: All tests PASS (with fewer tests — the 22 YnabTool tests are gone).

**Step 6: Commit**

```bash
git add -A pyflow/tools/ynab.py tests/tools/test_ynab.py pyflow/tools/__init__.py tests/tools/test_base.py tests/platform/test_metrics_plugin.py
git commit -m "refactor: remove YnabTool — replaced by OpenAPIToolset"
```

---

### Task 7: Update docs — CLAUDE.md, README.md, concepts.md, .env.example

**Files:**
- Modify: `CLAUDE.md` — remove YnabTool reference, update OpenApiToolConfig location, update RuntimeConfig docs
- Modify: `README.md` — remove ynab.py from architecture, update features
- Modify: `docs/concepts.md` — update openapi_tools location
- Modify: `docs/adk-alignment.md` — update OpenAPIToolset description
- Modify: `.env.example` — keep YNAB env var (still needed for OpenAPI auth)

**Step 1: Update CLAUDE.md**

Key changes:
- Line 58: Change `pyflow/tools/ynab.py — YnabTool (YNAB budget API...)` → remove this line entirely
- Line 59 (models): Change `WorkflowDef, OrchestrationConfig, A2AConfig, RuntimeConfig, McpServerConfig, OpenApiToolConfig` → `WorkflowDef, OrchestrationConfig, A2AConfig, RuntimeConfig, McpServerConfig`
- Add to models line: mention `pyflow/models/agent.py` includes `OpenApiAuthConfig, OpenApiToolConfig`
- Line 97: Remove `openapi_tools (OpenAPI spec auto-generation)` from RuntimeConfig description
- Add new key pattern: `openapi_tools` on `AgentConfig` — declare OpenAPI specs per-agent, hydrator creates `OpenAPIToolset` (ADK `BaseToolset`) at hydration time

**Step 2: Update README.md**

Key changes:
- Remove `ynab.py` from the architecture tree
- Update feature list to mention OpenAPI tools at agent level
- Update tool count (one fewer custom tool)

**Step 3: Update docs/concepts.md**

Key changes:
- Update RuntimeConfig example to remove `openapi_tools: []`
- Add AgentConfig example showing `openapi_tools` with auth

**Step 4: Update docs/adk-alignment.md**

Key change:
- Update OpenAPIToolset line to reflect it's now on AgentConfig, not RuntimeConfig

**Step 5: Commit**

```bash
git add CLAUDE.md README.md docs/concepts.md docs/adk-alignment.md
git commit -m "docs: update docs for OpenAPI tools migration to AgentConfig"
```

---

### Task 8: Final verification — full test suite + linting

**Files:** None (verification only)

**Step 1: Run full test suite**

```bash
source .venv/bin/activate && pytest -v
```

Expected: All tests PASS.

**Step 2: Run linter**

```bash
source .venv/bin/activate && ruff check pyflow/ tests/
```

Expected: No errors.

**Step 3: Run formatter**

```bash
source .venv/bin/activate && ruff format --check pyflow/ tests/
```

Expected: No formatting issues.

**Step 4: Verify test count makes sense**

Old: 547 tests. Removed: ~22 YnabTool tests. Added: ~14 new tests (9 model + 5 auth resolver + 5 hydration - 5 old openapi config). Expected: ~539 tests (give or take a few depending on exact counts).

**Step 5: Final commit if any fixups needed**

Only if linting or formatting required changes.
