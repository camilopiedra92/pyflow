# PyFlow ADK Platform Migration Design

**Date:** 2026-02-27
**Status:** Approved
**Scope:** Full migration from custom DAG engine to Google ADK platform

## Summary

Replace PyFlow's custom DAG engine, node system, and multi-provider AI layer with Google ADK as the sole runtime. PyFlow becomes an **agent platform** that exposes self-registering tools consumed by YAML-defined or Python-defined workflows, all powered by ADK's Runner, Session, and A2A subsystems.

## Architecture

### Layered Design

```
┌─────────────────────────────────────────────────────┐
│                    API / A2A Layer                    │
│  FastAPI · CLI · agent-card.json · WebSocket         │
├─────────────────────────────────────────────────────┤
│                  Workflow Layer                       │
│  YAML workflows → auto-hydrated → ADK Agents         │
│  LlmAgent · SequentialAgent · ParallelAgent · Loop   │
├─────────────────────────────────────────────────────┤
│                  Platform Core                       │
│  ToolRegistry · WorkflowRegistry · SessionManager    │
│  ConfigLoader · Auto-Discovery · Lifecycle           │
├─────────────────────────────────────────────────────┤
│                  Tool Layer                           │
│  Self-registering FunctionTools with Pydantic schemas │
│  http · transform · storage · alert · condition      │
├─────────────────────────────────────────────────────┤
│                  Google ADK Runtime                   │
│  Runner · InMemorySessionService · LiteLLM · A2A     │
└─────────────────────────────────────────────────────┘
```

### Directory Structure

```
pyflow/
├── platform/                        # Core platform infrastructure
│   ├── __init__.py
│   ├── app.py                       # PyFlowPlatform singleton orchestrator
│   ├── registry/
│   │   ├── __init__.py
│   │   ├── tool_registry.py         # ToolRegistry: auto-discover + register tools
│   │   ├── workflow_registry.py     # WorkflowRegistry: discover + hydrate workflows
│   │   └── discovery.py             # Filesystem scanner for tools/ and workflows/
│   ├── session/
│   │   ├── __init__.py
│   │   └── service.py               # SessionManager wrapping ADK SessionService
│   ├── runner/
│   │   ├── __init__.py
│   │   └── engine.py                # PlatformRunner wrapping ADK Runner
│   ├── hydration/
│   │   ├── __init__.py
│   │   └── hydrator.py              # YAML → Pydantic → ADK Agent auto-hydration
│   └── a2a/
│       ├── __init__.py
│       └── cards.py                 # Auto-generate agent-card.json from registry
│
├── tools/                           # Platform-exposed tools (self-registering)
│   ├── __init__.py                  # Auto-discovery via __init_subclass__
│   ├── base.py                      # BasePlatformTool ABC + ToolConfig/ToolResponse
│   ├── http.py                      # HttpTool + HttpToolConfig + HttpToolResponse
│   ├── transform.py                 # TransformTool + TransformToolConfig
│   ├── condition.py                 # ConditionTool + ConditionToolConfig
│   ├── alert.py                     # AlertTool + AlertToolConfig + AlertToolResponse
│   └── storage.py                   # StorageTool + StorageToolConfig
│
├── models/                          # Pydantic models (shared vocabulary)
│   ├── __init__.py
│   ├── tool.py                      # ToolMetadata, ToolConfig base, ToolResponse base
│   ├── workflow.py                  # WorkflowDef, AgentDef, StepDef
│   ├── agent.py                     # AgentConfig (model, instruction, tools ref)
│   └── platform.py                  # PlatformConfig, RegistryConfig
│
├── workflows/                       # User-defined workflow YAMLs (auto-discovered)
│   └── example.yaml
│
├── cli.py                           # Typer CLI (run, serve, validate, list)
├── server.py                        # FastAPI + A2A endpoints
└── logging.py                       # structlog config
```

## Tool Layer

### Self-Registration Pattern

Tools auto-register via `__init_subclass__`. Creating a class that inherits `BasePlatformTool` is sufficient for registration — no decorators or manual imports needed.

```python
class BasePlatformTool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    config_model: ClassVar[type[ToolConfig]]
    response_model: ClassVar[type[ToolResponse]]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, 'name'):
            _AUTO_REGISTRY[cls.name] = cls

    @abstractmethod
    async def execute(self, config: ToolConfig, ctx: ToolContext) -> ToolResponse: ...

    def as_function_tool(self) -> FunctionTool:
        """Convert to ADK FunctionTool with auto-generated schema."""
        ...
```

### Tool Anatomy

Each tool module contains:
- **Pydantic config model** — validated input schema
- **Pydantic response model** — typed output schema
- **Tool class** — async execute() logic
- **Auto-registration** — via inheritance

## Auto-Hydration Pipeline

```
YAML file → YAML parse → Pydantic WorkflowDef → Hydrator → ADK Agent tree
                           (validates all       (resolves tool refs
                            fields + defaults)   against ToolRegistry)
```

### Workflow YAML Format

```yaml
name: exchange_tracker
description: "Track exchange rates and alert on thresholds"

agents:
  - name: fetcher
    type: llm
    model: gemini-2.0-flash
    instruction: "Fetch the current USD/MXN exchange rate"
    tools: [http_request]
    output_key: rate_data

  - name: analyzer
    type: llm
    model: anthropic/claude-sonnet-4-20250514
    instruction: "Analyze rate from {rate_data}, decide if alert needed"
    tools: [condition, alert]
    output_key: analysis

orchestration:
  type: sequential
  agents: [fetcher, analyzer]

a2a:
  version: "1.0.0"
  skills:
    - id: rate_tracking
      name: "Exchange Rate Tracking"
      tags: [finance, monitoring]
```

### Hydrator

The hydrator:
1. Parses YAML into `WorkflowDef` (Pydantic validates)
2. For each agent, resolves `tools: [name]` against `ToolRegistry`
3. Creates ADK `LlmAgent` with resolved `FunctionTool` instances
4. Wraps agents in `SequentialAgent`/`ParallelAgent`/`LoopAgent` per orchestration type
5. Uses `LiteLlm(model=...)` for non-Gemini models (Anthropic, OpenAI)

## Platform Core

### PyFlowPlatform

Singleton that owns all registries and manages lifecycle:

```python
class PyFlowPlatform:
    async def boot(self) -> None:
        self.tools.discover()              # scan tools/, register all
        self.workflows.discover()          # scan workflows/, parse YAMLs
        self.workflows.hydrate(self.tools) # resolve tool refs → ADK agents
        await self.sessions.initialize()

    async def run_workflow(self, name: str, input: dict) -> dict:
        agent = self.workflows.get(name).agent
        return await self.runner.run(agent, input, self.sessions)

    def agent_cards(self) -> list[dict]:
        return [w.to_agent_card() for w in self.workflows.all()]
```

### Registries

- **ToolRegistry**: Collects tools from `__init_subclass__` auto-registry + filesystem scan
- **WorkflowRegistry**: Scans `workflows/` directory for YAML files, validates, stores hydrated agents

## API / A2A Layer

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/.well-known/agent-card.json` | A2A discovery |
| POST | `/a2a/{workflow_name}` | A2A execution |
| POST | `/api/workflows/{name}/run` | REST execution |
| GET | `/api/workflows` | List workflows |
| GET | `/api/tools` | List platform tools |
| GET | `/health` | Health check |

## Deletion Map

| Current File | Action |
|---|---|
| `pyflow/core/engine.py` | Delete → ADK Runner |
| `pyflow/core/context.py` | Delete → ADK Session |
| `pyflow/core/node.py` | Delete → BasePlatformTool |
| `pyflow/core/template.py` | Delete → ADK state refs |
| `pyflow/core/safe_eval.py` | Delete → ADK agent logic |
| `pyflow/core/models.py` | Replace → `pyflow/models/` |
| `pyflow/core/loader.py` | Replace → `pyflow/platform/hydration/` |
| `pyflow/nodes/*` | Migrate → `pyflow/tools/*` |
| `pyflow/ai/*` | Delete → ADK + LiteLLM |

## Dependencies

```toml
[project.dependencies]
google-adk = ">=1.25"
pydantic = ">=2.0"
pyyaml = ">=6.0"
httpx = ">=0.27"
fastapi = ">=0.115"
uvicorn = ">=0.30"
typer = ">=0.12"
structlog = ">=24.0"
jsonpath-ng = ">=1.6"

[project.optional-dependencies]
litellm = ["litellm>=1.0"]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24", "ruff>=0.5"]
```

## Testing Strategy

- TDD: tests before implementation for every module
- Mock ADK Runner/Session for unit tests
- Mock LLM responses for tool tests
- Integration tests with real ADK agents (optional, behind env flag)
- Target: 100% coverage on platform core + tools
