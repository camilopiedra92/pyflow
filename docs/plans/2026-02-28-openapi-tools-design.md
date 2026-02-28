# OpenAPI Tools Integration Design

## Summary

Replace the custom `YnabTool` (257 lines, god-tool pattern) with ADK-native `OpenAPIToolset` support. This enables any OpenAPI-spec'd API to be consumed declaratively via YAML, with typed individual tools auto-generated from the spec.

## Goals

1. **Better LLM UX**: Individual typed tools per API operation (vs single god-tool with action dispatch)
2. **Less custom code**: Eliminate 257 lines of YnabTool + 580 lines of tests
3. **Generic pattern**: Any OpenAPI spec becomes usable via 3 lines of YAML
4. **ADK-aligned**: Use `OpenAPIToolset` (extends `BaseToolset`) natively — zero workarounds

## Key ADK Facts

- `OpenAPIToolset` extends `BaseToolset`, generating `RestApiTool` per spec operation
- `LlmAgent` accepts `BaseToolset` directly in `tools=` parameter (`ToolUnion = Union[Callable, BaseTool, BaseToolset]`)
- ADK expands toolsets dynamically at runtime via `get_tools_with_prefix(ctx)`
- ADK handles auth credential injection via `get_auth_config()`
- Tool names derived from `operationId` (snake_case, max 60 chars)
- Tool descriptions from `summary`/`description` in the spec

## Design

### 1. Model Changes

**New: `OpenApiAuthConfig`** in `pyflow/models/agent.py`:

```python
class OpenApiAuthConfig(BaseModel):
    """Authentication config for OpenAPI toolsets."""
    type: Literal["none", "bearer", "apikey", "oauth2"] = "none"

    # bearer: env var containing the token
    token_env: str | None = None

    # apikey: location + param name + env var
    apikey_location: Literal["header", "query"] = "query"
    apikey_name: str = "apikey"

    # oauth2: authorization code flow
    authorization_url: str | None = None
    token_url: str | None = None
    scopes: dict[str, str] | None = None
    client_id_env: str | None = None
    client_secret_env: str | None = None
```

**Move + extend `OpenApiToolConfig`** to `pyflow/models/agent.py`:

```python
class OpenApiToolConfig(BaseModel):
    """Configuration for auto-generating tools from an OpenAPI spec."""
    spec: str                              # Path to spec (relative to workflow YAML)
    name_prefix: str | None = None
    auth: OpenApiAuthConfig = OpenApiAuthConfig()
```

**Add to `AgentConfig`**:

```python
class AgentConfig(BaseModel):
    ...
    openapi_tools: list[OpenApiToolConfig] = []
```

**Remove from `RuntimeConfig`**: Delete `openapi_tools` field and `OpenApiToolConfig` import.

### 2. Hydrator Changes

In `_build_llm_agent()`, after resolving platform tools:

```python
for openapi_cfg in config.openapi_tools:
    spec_path = workflow_base_dir / openapi_cfg.spec
    spec_str = spec_path.read_text()
    spec_type = "json" if spec_path.suffix == ".json" else "yaml"
    auth_scheme, auth_credential = _resolve_openapi_auth(openapi_cfg.auth)
    toolset = OpenAPIToolset(
        spec_str=spec_str,
        spec_str_type=spec_type,
        auth_scheme=auth_scheme,
        auth_credential=auth_credential,
    )
    tools.append(toolset)
```

New helper function `_resolve_openapi_auth()`:

```python
def _resolve_openapi_auth(auth: OpenApiAuthConfig):
    """Map OpenApiAuthConfig to ADK auth_scheme + auth_credential."""
    match auth.type:
        case "none":
            return None, None
        case "bearer":
            token = os.environ.get(auth.token_env, "")
            return token_to_scheme_credential("http", "header", "Authorization", token)
        case "apikey":
            key = os.environ.get(auth.token_env, "")
            return token_to_scheme_credential("apikey", auth.apikey_location, auth.apikey_name, key)
        case "oauth2":
            auth_scheme = OAuth2(flows=OAuthFlows(
                authorizationCode=OAuthFlowAuthorizationCode(
                    authorizationUrl=auth.authorization_url,
                    tokenUrl=auth.token_url,
                    scopes=auth.scopes or {},
                )
            ))
            auth_credential = AuthCredential(
                auth_type=AuthCredentialTypes.OAUTH2,
                oauth2=OAuth2Auth(
                    client_id=os.environ.get(auth.client_id_env, ""),
                    client_secret=os.environ.get(auth.client_secret_env, ""),
                ),
            )
            return auth_scheme, auth_credential
```

### 3. Spec File Path Resolution

The `spec` path is resolved relative to the workflow YAML file's directory. The hydrator needs the workflow's base directory passed through. For `build_root_agent()`, this is `Path(caller_file).parent`.

Example: If workflow is at `agents/budget_analyst/workflow.yaml` and spec is `specs/ynab-v1-swagger.json`, the full path is `agents/budget_analyst/specs/ynab-v1-swagger.json`.

### 4. Eliminations

| File | Action |
|------|--------|
| `pyflow/tools/ynab.py` | Delete (257 lines) |
| `tests/tools/test_ynab.py` | Delete (580 lines) |
| `pyflow/models/workflow.py` `OpenApiToolConfig` | Delete (moved to agent.py) |
| `pyflow/models/workflow.py` `RuntimeConfig.openapi_tools` | Delete field |
| `tests/platform/test_openapi_tools.py` | Rewrite for new location |

### 5. New Files

| File | Purpose |
|------|---------|
| `agents/budget_analyst/specs/ynab-v1-swagger.json` | Official YNAB OpenAPI spec |

### 6. Updated Workflow YAML

```yaml
name: budget_analyst
description: "Personal budget analyst powered by YNAB"

agents:
  - name: analyst
    type: llm
    model: gemini-2.5-flash
    temperature: 0.2
    max_output_tokens: 4096
    openapi_tools:
      - spec: specs/ynab-v1-swagger.json
        auth:
          type: bearer
          token_env: PYFLOW_YNAB_API_TOKEN
    instruction: >
      You are a personal budget analyst with access to the user's YNAB data.
      Use the available YNAB API tools to answer questions about budgets,
      accounts, categories, transactions, and spending patterns.

      CRITICAL — TOKEN BUDGET:
      - NEVER call list_transactions without since_date. Unfiltered responses are huge and will fail.

      IMPORTANT NOTES:
      - YNAB amounts are in "milliunits": divide by 1000 to get the real amount (e.g. -50000 = -$50.00).
      - Always convert milliunits to currency format in your responses.
      - Negative amounts = outflows (spending), positive amounts = inflows (income).

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
      tags: [finance, budget, ynab]
```

### 7. Testing Strategy

- **Model tests**: `OpenApiAuthConfig` validation (all auth types, missing fields)
- **Hydrator tests**: Mock `OpenAPIToolset`, verify it's created with correct auth and appended to agent tools
- **Auth resolver tests**: Verify each auth type maps to correct ADK objects
- **Integration test**: Hydrate a workflow with `openapi_tools` config, verify agent has toolset in tools list
- **No real API calls**: All tests mock the spec file and OpenAPIToolset

### 8. Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| `openapi_tools` on AgentConfig, not RuntimeConfig | Principle of least privilege — each agent declares its own API access |
| Remove `RuntimeConfig.openapi_tools` | Single source of truth — one place to declare, not two |
| Pass `OpenAPIToolset` as `BaseToolset` (not individual tools) | ADK-native — let ADK handle expansion, auth injection, lifecycle |
| Auth config as separate model | Clean separation; extensible for future auth types |
| Spec files versioned in repo | Predictable, no runtime fetching, explicit updates |
| No custom wrapper around RestApiTool | YAGNI — ADK tools work as-is |

## YNAB Spec Source

Official spec: `https://api.youneedabudget.com/papi/spec-v1-swagger.json`

YNAB publishes and maintains this spec. See: https://dev.to/ynab/how-we-use-openapi-swagger-for-the-ynab-api-5453
