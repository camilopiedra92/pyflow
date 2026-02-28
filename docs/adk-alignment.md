# PyFlow ADK Alignment

PyFlow extends Google ADK — it does not replace it. This document explains the relationship.

## Architecture

PyFlow wraps ADK's `App` model with a YAML-driven workflow layer:

- **Foundation**: Google ADK 1.26+ (`App`, `Runner`, `BaseAgent`, `FunctionTool`, plugins)
- **PyFlow layer**: Workflow YAML schema, tool auto-registration, workflow hydration, custom agent types

## What PyFlow Adds

### Custom Agent Types (not in ADK)
- `DagAgent` — wave-based DAG orchestration (no ADK equivalent)
- `ExprAgent` — inline safe Python expressions (AST-validated sandbox)
- `CodeAgent` — arbitrary Python function execution
- `ToolAgent` — single-tool execution without LLM

### Workflow YAML Schema
PyFlow's `WorkflowDef` YAML is fundamentally different from ADK's `AgentConfig`:
- Multi-agent orchestration in a single file (`sequential`, `parallel`, `loop`, `react`, `dag`, `llm_routed`)
- Tool references by registry name or FQN (`tools: ["http_request", "mypackage.tools.custom"]`)
- Agent-as-tool composition (`agent_tools` field)
- A2A protocol configuration (opt-in per workflow)
- MCP server connections (`mcp_servers` in runtime config)
- OpenAPI tool generation (`openapi_tools` on agent config)

### Self-Registering Tools
Platform tools inherit from `BasePlatformTool` and auto-register via `__init_subclass__`.
ADK tools are also available by name (`exit_loop`, `google_search`, `transfer_to_agent`, etc.).

## ADK Features Used

| Feature | How PyFlow Uses It |
|---------|-------------------|
| `App` model | Wraps every workflow agent — enables caching, compaction, resumability |
| `GlobalInstructionPlugin` | Injects `NOW: {datetime} ({timezone})` into all LLM agents at runtime |
| `Runner` + services | Session, memory, artifact, credential services configured via `runtime:` YAML |
| `SqliteSessionService` | Direct SQLite sessions via `session_service: sqlite` + `session_db_path` |
| `LlmAgent` | All `type: llm` agents hydrated as ADK `LlmAgent` |
| `SequentialAgent/ParallelAgent/LoopAgent` | Used for orchestration wrappers |
| `LiteLlm` | Wraps `anthropic/` and `openai/` model strings for multi-provider support |
| `FunctionTool` | All platform tools converted via `as_function_tool()` |
| `AgentTool` | Agent-as-tool composition via `agent_tools` YAML field |
| Plugins (7 registered) | `logging`, `debug_logging`, `reflect_and_retry`, `context_filter`, `save_files_as_artifacts`, `multimodal_tool_results`, `bigquery_analytics` |
| `McpToolset` | MCP server connections configurable via `mcp_servers` in workflow YAML |
| `OpenAPIToolset` | OpenAPI spec → auto-generated tools via `openapi_tools` on agent config (per-agent, created at hydration time) |
| Planners | `PlanReActPlanner`, `BuiltInPlanner` for react orchestration |
| Callbacks (FQN) | `before_agent`, `before_model`, etc. resolved via Python FQN |
| OpenTelemetry | Opt-in distributed tracing via `telemetry_enabled`/`telemetry_export` in PlatformConfig |
| `adk eval` | Agent packages compatible with ADK evaluation framework |

## ADK Features Intentionally Not Used

| Feature | Reason |
|---------|--------|
| `to_a2a()` | `@a2a_experimental`, requires `a2a-sdk` (not installed), single-agent only. PyFlow's multi-workflow A2A routing has no ADK equivalent |
| `get_fast_api_app()` | Assumes filesystem `AgentLoader`, no support for pre-hydrated workflows. PyFlow's custom server is simpler for the multi-workflow use case |
| Agent Config YAML | Experimental, Gemini-only, LlmAgent-only. PyFlow's YAML supports all agent types, all models, full orchestration |
| `AnthropicLlm` / direct model wrappers | `LiteLlm` covers all non-Gemini models uniformly |

## ADK Compatibility

Each agent package (`agents/*/`) exports `root_agent` via `__init__.py`, making it compatible with:
- `adk web` — ADK's dev UI
- `adk eval` — ADK's evaluation framework
- `adk deploy` — ADK's deployment tooling
- Standard ADK `Runner` usage

The `build_root_agent(__file__)` factory in each package handles hydration from `workflow.yaml`.
