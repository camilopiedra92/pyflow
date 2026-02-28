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

### Self-Registering Tools
Platform tools inherit from `BasePlatformTool` and auto-register via `__init_subclass__`.
ADK tools are also available by name (`exit_loop`, `google_search`, `transfer_to_agent`, etc.).

## ADK Features Used

| Feature | How PyFlow Uses It |
|---------|-------------------|
| `App` model | Wraps every workflow agent — enables caching, compaction, resumability |
| `GlobalInstructionPlugin` | Injects `NOW: {datetime} ({timezone})` into all LLM agents at runtime |
| `Runner` + services | Session, memory, artifact, credential services configured via `runtime:` YAML |
| `LlmAgent` | All `type: llm` agents hydrated as ADK `LlmAgent` |
| `SequentialAgent/ParallelAgent/LoopAgent` | Used for orchestration wrappers |
| `LiteLlm` | Wraps `anthropic/` and `openai/` model strings for multi-provider support |
| `FunctionTool` | All platform tools converted via `as_function_tool()` |
| `AgentTool` | Agent-as-tool composition via `agent_tools` YAML field |
| Plugins (7 available) | `logging`, `debug_logging`, `reflect_and_retry`, `context_filter`, `save_files_as_artifacts`, `multimodal_tool_results` |
| Planners | `PlanReActPlanner`, `BuiltInPlanner` for react orchestration |
| Callbacks (FQN) | `before_agent`, `before_model`, etc. resolved via Python FQN |

## ADK Compatibility

Each agent package (`agents/*/`) exports `root_agent` via `__init__.py`, making it compatible with:
- `adk web` — ADK's dev UI
- `adk deploy` — ADK's deployment tooling
- Standard ADK `Runner` usage

The `build_root_agent(__file__)` factory in each package handles hydration from `workflow.yaml`.
