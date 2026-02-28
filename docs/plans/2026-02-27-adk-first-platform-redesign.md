# PyFlow ADK-First Platform Redesign

**Date:** 2026-02-27
**Status:** Approved
**Branch:** `feat/pyflow-core`

## Problem Statement

PyFlow wraps Google ADK with thin custom layers that add maintenance burden without value. The platform uses ~15% of ADK's capabilities — no plugins, no memory, no artifacts, no callbacks, no planners, no streaming. The tool system has a custom schema generation layer (70 lines) that silently hides complex types (`dict`, `list`, `Any`) from the LLM. Only 3 orchestration types work (sequential, parallel, loop) despite the model defining more. `AgentConfig.type` supports "sequential"/"parallel"/"loop" but the hydrator only handles "llm" — the rest raise `ValueError` at runtime.

## Design Principles

1. **Don't wrap what ADK does well** — use ADK Runner, session services, plugins, memory, and artifacts directly
2. **Hybrid orchestration** — ADK-native for sequential/parallel/loop/react/llm-routed; custom `DagAgent` only where ADK has no solution
3. **YAML is the configuration layer** — workflows define runtime config, agent composition, and orchestration in YAML; PyFlow hydrates to ADK primitives
4. **Zero silent failures** — tools return explicit errors, never silently swallow exceptions

## Architecture Overview

```
PyFlow Platform
├── YAML Workflows ──→ Pydantic Validation ──→ ADK Runtime
│                                               ├── Runner (direct, with plugins)
│                                               ├── Session Services (configurable)
│                                               ├── Memory Services (configurable)
│                                               ├── Artifact Services (configurable)
│                                               └── Callbacks (per-agent)
├── Custom Agents
│   └── DagAgent (topological sort + wave execution)
└── Tool Auto-Discovery
    ├── Custom tools (BasePlatformTool)
    └── ADK built-in tools (google_search, exit_loop, etc.)
```

## Section 1: Workflow YAML Schema

### RuntimeConfig (NEW)

Each workflow can configure its ADK runtime services:

```yaml
runtime:
  session_service: in_memory    # | sqlite | database
  session_db_url: null          # connection string for database
  memory_service: none          # | in_memory
  artifact_service: none        # | in_memory | file
  artifact_dir: null            # directory for file artifacts
  plugins:                      # ADK plugins
    - logging
    - reflect_and_retry
```

### 6 Orchestration Types

```yaml
# 1. sequential — ADK SequentialAgent
orchestration:
  type: sequential
  agents: [a, b, c]

# 2. parallel — ADK ParallelAgent
orchestration:
  type: parallel
  agents: [a, b, c]

# 3. loop — ADK LoopAgent
orchestration:
  type: loop
  agents: [checker, fixer]
  max_iterations: 5

# 4. react — ADK PlanReActPlanner (NEW)
orchestration:
  type: react
  agent: reasoner
  planner: plan_react           # | built_in

# 5. dag — Custom DagAgent (NEW)
orchestration:
  type: dag
  nodes:
    - agent: fetcher
      depends_on: []
    - agent: enricher_a
      depends_on: [fetcher]
    - agent: enricher_b
      depends_on: [fetcher]
    - agent: merger
      depends_on: [enricher_a, enricher_b]

# 6. llm_routed — ADK agent transfer (NEW)
orchestration:
  type: llm_routed
  router: dispatcher
  agents: [support, sales, billing]
```

### Hierarchical Agent Composition

Agents of type sequential/parallel/loop can contain sub_agents, enabling arbitrary nesting:

```yaml
agents:
  - name: pipeline
    type: sequential
    sub_agents: [fetch_stage, process, validate]
  - name: fetch_stage
    type: parallel
    sub_agents: [fetch_a, fetch_b]
  - name: fetch_a
    type: llm
    model: gemini-2.5-flash
    instruction: "Fetch from API A"
    tools: [http_request]
    output_key: data_a
  - name: fetch_b
    type: llm
    model: gemini-2.5-flash
    instruction: "Fetch from API B"
    tools: [http_request]
    output_key: data_b
  - name: process
    type: llm
    model: anthropic/claude-sonnet-4-20250514
    instruction: "Merge {data_a} and {data_b}"
    output_key: merged
  - name: validate
    type: llm
    model: gemini-2.5-flash
    instruction: "Validate {merged}"
    tools: [condition]
```

### Agent Callbacks (NEW)

```yaml
agents:
  - name: researcher
    type: llm
    callbacks:
      before_agent: log_start
      after_agent: log_output
      before_tool: validate_input
      after_tool: log_tool_result
```

## Section 2: Pydantic Models

### New Models

```python
class RuntimeConfig(BaseModel):
    session_service: Literal["in_memory", "sqlite", "database"] = "in_memory"
    session_db_url: str | None = None
    memory_service: Literal["in_memory", "none"] = "none"
    artifact_service: Literal["in_memory", "file", "none"] = "none"
    artifact_dir: str | None = None
    plugins: list[str] = []

class DagNode(BaseModel):
    agent: str
    depends_on: list[str] = []
```

### Modified Models

**OrchestrationConfig** — expanded to 6 types with type-specific validation:

```python
class OrchestrationConfig(BaseModel):
    type: Literal["sequential", "parallel", "loop", "react", "dag", "llm_routed"]
    agents: list[str] | None = None
    nodes: list[DagNode] | None = None
    agent: str | None = None
    router: str | None = None
    planner: str | None = None
    max_iterations: int | None = None
```

**AgentConfig** — add callbacks:

```python
class AgentConfig(BaseModel):
    # ... existing fields ...
    callbacks: dict[str, str] | None = None
```

**WorkflowDef** — add runtime:

```python
class WorkflowDef(BaseModel):
    # ... existing fields ...
    runtime: RuntimeConfig = RuntimeConfig()
```

### Eliminated Models

- `ToolConfig` base class (empty, no longer needed)
- `ToolResponse` base class (empty, no longer needed)
- `AgentCardSkill` (duplicate of `SkillDef` — unified)

## Section 3: Tool System

### Current Problem

`as_function_tool()` manually converts Pydantic models to function signatures, silently hiding complex types:

```python
# Current: 70 lines of custom schema generation
# dict, list, Any types → SILENTLY EXCLUDED from LLM schema
# Result: LLM cannot pass headers or body to HttpTool
```

### New Approach

Tools define `execute()` with native Python parameters. ADK `FunctionTool` inspects the function directly:

```python
class BasePlatformTool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "name") and isinstance(cls.__dict__.get("name"), str):
            _TOOL_AUTO_REGISTRY[cls.name] = cls

    @abstractmethod
    async def execute(self, tool_context: ToolContext, **kwargs) -> dict:
        ...

    @classmethod
    def as_function_tool(cls) -> FunctionTool:
        instance = cls()
        return FunctionTool(func=instance.execute)
```

### Tool Parameter Strategy

Complex types (`dict`, `list`) become JSON strings so the LLM can pass them:

```python
class HttpTool(BasePlatformTool):
    name = "http_request"
    description = "Make HTTP requests to external APIs"

    async def execute(
        self,
        tool_context: ToolContext,
        url: str,
        method: str = "GET",
        headers: str = "{}",       # JSON string — visible to LLM
        body: str = "",            # JSON string — visible to LLM
        timeout: int = 30,
        allow_private: bool = False,
    ) -> dict:
        ...
```

### Shared Utilities (eliminate duplication)

```python
# pyflow/tools/security.py — shared between HttpTool and AlertTool
def is_private_url(url: str) -> bool: ...

# pyflow/tools/parsing.py — shared
def safe_json_parse(value: str, default=None): ...
```

### ADK Built-in Tool Catalog

ToolRegistry resolves custom tools first, then ADK built-in tools:

```python
ADK_BUILTIN_TOOLS = {
    "google_search": lambda: GoogleSearchTool(),
    "exit_loop": lambda: ExitLoopTool(),
    "load_memory": lambda: LoadMemoryTool(),
    "transfer_to_agent": lambda: TransferToAgentTool(),
}
```

### Eliminated Code

- `_is_adk_safe()` — no longer needed
- `_safe_annotation()` — no longer needed
- `as_function_tool()` schema generation — 70 lines replaced by 3-line delegation to ADK
- `config_model` / `response_model` class vars — parameters are function args

## Section 4: Runner, Plugins, Memory, Artifacts

### WorkflowExecutor (replaces PlatformRunner + SessionManager)

```python
class WorkflowExecutor:
    def build_runner(self, agent: BaseAgent, runtime: RuntimeConfig) -> Runner:
        return Runner(
            agent=agent,
            app_name=self._app_name,
            session_service=self._build_session_service(runtime),
            memory_service=self._build_memory_service(runtime),
            artifact_service=self._build_artifact_service(runtime),
            plugins=self._resolve_plugins(runtime.plugins),
        )

    async def run(self, runner, user_id, message, session_id=None) -> RunResult:
        ...

    async def run_streaming(self, runner, user_id, message, session_id=None):
        async for event in runner.run_async(...):
            yield event
```

### Session Services (configurable per workflow)

| Config Value | ADK Service |
|---|---|
| `in_memory` | `InMemorySessionService` |
| `sqlite` | `DatabaseSessionService(db_url="sqlite:///...")` |
| `database` | `DatabaseSessionService(db_url=config.session_db_url)` |

### Memory Services

| Config Value | ADK Service |
|---|---|
| `none` | `None` (no memory) |
| `in_memory` | `InMemoryMemoryService` |

### Artifact Services

| Config Value | ADK Service |
|---|---|
| `none` | `None` (no artifacts) |
| `in_memory` | `InMemoryArtifactService` |
| `file` | `FileArtifactService(base_dir=config.artifact_dir)` |

### Plugin Registry

```python
PLUGIN_REGISTRY = {
    "logging": lambda: LoggingPlugin(),
    "reflect_and_retry": lambda: ReflectAndRetryToolPlugin(),
}
```

### Callbacks Registry

```python
CALLBACK_REGISTRY: dict[str, Callable] = {}

def register_callback(name: str, fn: Callable):
    CALLBACK_REGISTRY[name] = fn
```

Hydrator resolves callback names to functions and passes them to LlmAgent constructor.

### Streaming API

New FastAPI endpoint:

```python
@app.post("/api/workflows/{name}/stream")
async def stream_workflow(name: str, input: WorkflowInput):
    async def event_generator():
        async for event in executor.run_streaming(runner, user_id, input.message):
            yield f"data: {json.dumps(event_to_dict(event))}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Eliminated Code

- `PlatformRunner` (74 lines) — replaced by `WorkflowExecutor`
- `SessionManager` (47 lines) — ADK services used directly
- Hardcoded `user_id="default"` — now parameterized

## Section 5: Custom DagAgent

The only truly custom component. Extends `BaseAgent` with topological sort and wave execution.

### Algorithm

1. Parse DAG nodes with dependency edges
2. Validate acyclicity using Kahn's algorithm (at init time)
3. At runtime, scheduler loop:
   - Find all "ready" nodes (dependencies satisfied, not yet started)
   - Launch ready nodes in parallel with `asyncio.TaskGroup`
   - When batch completes, check for newly unblocked nodes
   - Repeat until all nodes executed

### Data Flow

Agents communicate via `session.state` using ADK's native `output_key` mechanism. Template variables `{var_name}` in instructions resolve against `session.state`.

### Implementation Location

`pyflow/platform/agents/dag_agent.py`

## Section 6: Migration Plan

### Phase 1: Foundation

- 1.1 New models: `RuntimeConfig`, `DagNode`, expanded `OrchestrationConfig`
- 1.2 Unify `SkillDef` / `AgentCardSkill`
- 1.3 Tool utilities: `security.py`, `parsing.py`

### Phase 2: Tool System

- 2.1 Refactor `BasePlatformTool` (remove schema gen, execute with kwargs)
- 2.2 Migrate each tool (http, transform, condition, alert, storage)
- 2.3 ADK built-in tool catalog in `ToolRegistry`
- 2.4 Update tool tests

### Phase 3: Orchestration

- 3.1 `DagAgent` implementation + tests
- 3.2 Callbacks registry
- 3.3 Plugin registry
- 3.4 Refactor Hydrator (6 types, nested agents, callbacks, planners)
- 3.5 Update hydrator tests

### Phase 4: Execution

- 4.1 `WorkflowExecutor` (replaces PlatformRunner + SessionManager)
- 4.2 Streaming support
- 4.3 Update executor tests
- 4.4 Remove PlatformRunner and SessionManager

### Phase 5: Integration

- 5.1 Refactor `PyFlowPlatform` app.py
- 5.2 Update CLI (user_id, --stream)
- 5.3 Update Server (streaming endpoint, user_id)
- 5.4 Migrate workflow YAMLs (add runtime:)
- 5.5 Update A2A cards
- 5.6 Integration tests

### Phase 6: Verification

- 6.1 All tests passing
- 6.2 New tests for DAG, streaming, plugins, memory, callbacks
- 6.3 Validate example workflows
- 6.4 ruff lint/format clean

## File Change Map

### New Files

| File | Purpose |
|---|---|
| `pyflow/platform/executor.py` | WorkflowExecutor |
| `pyflow/platform/agents/dag_agent.py` | DagAgent |
| `pyflow/platform/agents/__init__.py` | Custom agent exports |
| `pyflow/platform/callbacks.py` | Callback registry |
| `pyflow/platform/plugins.py` | Plugin registry |
| `pyflow/tools/security.py` | Shared SSRF protection |
| `pyflow/tools/parsing.py` | Shared JSON parsing |

### Deleted Files

| File | Reason |
|---|---|
| `pyflow/platform/runner/engine.py` | Replaced by WorkflowExecutor |
| `pyflow/platform/session/service.py` | ADK services used directly |

### Modified Files

| File | Changes |
|---|---|
| `pyflow/models/workflow.py` | Add RuntimeConfig, DagNode, expand OrchestrationConfig |
| `pyflow/models/agent.py` | Add callbacks field |
| `pyflow/models/tool.py` | Remove ToolConfig/ToolResponse, keep ToolMetadata |
| `pyflow/models/runner.py` | Add session_id to RunResult |
| `pyflow/models/server.py` | Add StreamEvent model |
| `pyflow/models/a2a.py` | Remove AgentCardSkill, use SkillDef |
| `pyflow/tools/base.py` | Remove schema gen, delegate to ADK FunctionTool |
| `pyflow/tools/http.py` | Params as function args, headers/body as JSON strings |
| `pyflow/tools/transform.py` | Input as JSON string, explicit error logging |
| `pyflow/tools/condition.py` | Return explicit error instead of silent False |
| `pyflow/tools/alert.py` | Add SSRF protection, params as function args |
| `pyflow/tools/storage.py` | Data as JSON string, async file I/O |
| `pyflow/platform/app.py` | Use WorkflowExecutor, remove SessionManager |
| `pyflow/platform/hydration/hydrator.py` | 6 orchestration types, nested agents, callbacks, planners |
| `pyflow/platform/registry/tool_registry.py` | ADK built-in tool catalog |
| `pyflow/platform/a2a/cards.py` | Use unified SkillDef |
| `pyflow/cli.py` | user_id param, --stream flag |
| `pyflow/server.py` | Streaming endpoint, user_id from request |
| `workflows/exchange_tracker.yaml` | Add runtime: section |

## Expected Metrics

| Metric | Before | After |
|---|---|---|
| Platform code lines | ~500 | ~400 |
| Tool code lines | ~550 | ~400 |
| Orchestration types | 3 | 6 |
| ADK features used | ~15% | ~60% |
| Tests | 221 | ~280+ |
| Workarounds | 5+ | 0 |
| Silent failures | 5 tools | 0 |

## New Dependencies

```toml
[project.optional-dependencies]
sqlite = ["sqlalchemy>=2.0"]  # for DatabaseSessionService (optional)
```

No hard dependencies added. Everything else ships with `google-adk>=1.25`.
