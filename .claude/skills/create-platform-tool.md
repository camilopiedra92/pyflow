---
name: create-platform-tool
description: >
  Create a new PyFlow platform tool that integrates into the tool registry.
  Use this skill whenever the user wants to add a new tool, create a utility
  for workflows, build an integration (API client, database connector, file
  processor, notification sender, data validator, etc.), or asks about how
  to extend PyFlow's tool system. Also use this when the user mentions
  "platform tool", "BasePlatformTool", "tool registry", "workflow tool",
  or wants to make something available as a tool in YAML workflows.
---

# Create PyFlow Platform Tool

This skill guides the creation of custom platform tools that auto-register into PyFlow's tool system and become immediately available to any workflow — both for LLM agents (who decide when to call them) and ToolAgents (deterministic execution with fixed config).

## Before You Start

1. **Clarify the tool's purpose** — what does it do, what inputs does it need, what does it return?
2. **Check if it already exists** — read `pyflow/tools/` to see if an existing tool covers the use case. Extend before creating.
3. **Check if a tool is the right abstraction** — if the logic is workflow-specific and won't be reused, a CodeAgent (`type: code`) or ExprAgent (`type: expr`) might be simpler. Tools are for *reusable* operations across workflows.

## Architecture Context

Tools live in `pyflow/tools/` and auto-register at import time via `__init_subclass__`. The registration contract is:

- Inherit from `BasePlatformTool` (in `pyflow/tools/base.py`)
- Set `name: ClassVar[str]` — the string used to reference the tool in YAML workflows
- Set `description: ClassVar[str]` — shown to LLMs so they understand what the tool does
- Implement `async execute(self, tool_context: ToolContext, **typed_params) -> dict`

ADK's `FunctionTool` inspects the `execute()` signature to generate the tool schema. This means parameter names, types, defaults, and docstrings directly become the LLM's understanding of the tool.

## Implementation Checklist

Follow this sequence. Each step has a corresponding section below.

1. Create `pyflow/tools/<tool_name>.py`
2. Create `tests/tools/test_<tool_name>.py` — write tests first (TDD)
3. Implement the tool class
4. Run tests: `source .venv/bin/activate && pytest tests/tools/test_<tool_name>.py -v`
5. Run full suite: `pytest -v`
6. Run linter: `ruff check`

## Step 1: Design the Tool Interface

### Parameter Design

Parameters on `execute()` are the tool's public API. The LLM sees them as function arguments.

**Rules:**
- First parameter is always `self`
- Second parameter is always `tool_context: ToolContext` — provides session state access
- All remaining parameters are the tool's inputs — use explicit typed parameters, not `**kwargs`
- Use `str` for JSON-encoded complex inputs (the LLM sends strings). Parse with `safe_json_parse`
- Provide sensible defaults where possible — fewer required params = easier for the LLM to use
- Use clear, descriptive parameter names — the LLM reads them

**Docstring matters** — ADK extracts the docstring to describe the tool to the LLM. Write an `Args:` section with one line per parameter. Be specific about format expectations.

### Return Format

Always return a `dict`. Follow the conventions established by existing tools:

- **Success**: include the primary result and relevant metadata
- **Error**: include an `"error"` key with a human-readable message
- Never raise exceptions to the caller — catch and return error dicts

Examples from existing tools:
```python
# Success
return {"status": 200, "headers": dict(resp.headers), "body": resp_body}
# Error
return {"status": 0, "error": "SSRF blocked: private/internal URL"}
# Success with flag
return {"content": text, "success": True}
# Error with flag
return {"content": None, "success": False, "error": "File not found"}
```

## Step 2: Write the Tool

### File Template

```python
from __future__ import annotations

from google.adk.tools.tool_context import ToolContext

from pyflow.tools.base import BasePlatformTool


class MyTool(BasePlatformTool):
    name = "my_tool"
    description = "One-line description of what this tool does."

    async def execute(
        self,
        tool_context: ToolContext,
        required_param: str,
        optional_param: str = "default",
    ) -> dict:
        """Detailed description for the LLM.

        Args:
            required_param: What this parameter is and its expected format.
            optional_param: What this parameter is (default: "default").
        """
        try:
            # ... implementation
            return {"result": "value", "success": True}
        except Exception as exc:
            return {"result": None, "success": False, "error": str(exc)}
```

### Reuse Platform Utilities

Do NOT reimplement functionality that already exists. Import from the platform:

| Utility | Import | Use for |
|---------|--------|---------|
| `safe_json_parse` | `from pyflow.tools.parsing import safe_json_parse` | Parsing JSON string inputs safely (returns default on failure) |
| `is_private_url` | `from pyflow.tools.security import is_private_url` | SSRF protection — block requests to private/internal networks |
| `_validate_ast` | `from pyflow.tools.condition import _validate_ast` | Validate Python expressions in AST sandbox |
| `_SAFE_BUILTINS` | `from pyflow.tools.condition import _SAFE_BUILTINS` | Restricted builtins for sandboxed evaluation |

**`safe_json_parse(value, default=None)`** — Use this whenever a parameter accepts JSON strings:
```python
from pyflow.tools.parsing import safe_json_parse

parsed_headers = safe_json_parse(headers, default={})  # returns {} on invalid JSON
parsed_body = safe_json_parse(body)  # returns None on invalid JSON
```

**`is_private_url(url)`** — Use this whenever the tool makes outbound HTTP requests:
```python
from pyflow.tools.security import is_private_url

if is_private_url(url):
    return {"status": 0, "error": "SSRF blocked: private/internal URL"}
```

### Security Rules

- **Outbound HTTP**: Always check `is_private_url()` before making requests, unless the tool explicitly needs internal network access (in which case, add an `allow_private: bool = False` parameter like HttpTool does)
- **User-provided expressions**: Validate with `_validate_ast()` and evaluate only with `_SAFE_BUILTINS`
- **File paths**: Be cautious with user-provided paths — consider path traversal attacks
- **No imports of user-provided module names** — that's what CodeAgent is for
- **No shell commands with user input** — never pass user input to subprocess calls

### Auto-Registration Details

Registration happens automatically when:
1. The class inherits from `BasePlatformTool`
2. The class defines `name` as a string directly in `__dict__` (class-level, not inherited)

This means:
- Setting `name = "my_tool"` as a class variable triggers registration
- Setting `name = None` prevents registration (useful for test stubs and abstract subclasses)
- The tool module just needs to be imported — PyFlow discovers all files in `pyflow/tools/` at boot

No changes needed to any registry, `__init__.py`, or configuration file. Just create the file.

## Step 3: Write Tests

### Test File Template

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pyflow.tools.my_tool import MyTool


class TestMyToolExecute:
    async def test_successful_operation(self):
        tool = MyTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            required_param="value",
        )
        assert isinstance(result, dict)
        assert result["success"] is True

    async def test_error_handling(self):
        tool = MyTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            required_param="bad_value",
        )
        assert result["success"] is False
        assert "error" in result

    def test_auto_registered(self):
        from pyflow.tools.base import get_registered_tools
        assert "my_tool" in get_registered_tools()

    def test_name_and_description(self):
        assert MyTool.name == "my_tool"
        assert MyTool.description  # non-empty
```

### Testing Patterns by Tool Type

**Tools that make HTTP requests** — mock httpx, don't make real calls:
```python
mock_response = MagicMock()
mock_response.status_code = 200
mock_response.json.return_value = {"data": "test"}

mock_client = AsyncMock()
mock_client.request = AsyncMock(return_value=mock_response)
mock_client.__aenter__ = AsyncMock(return_value=mock_client)
mock_client.__aexit__ = AsyncMock(return_value=False)

with patch("pyflow.tools.my_tool.httpx.AsyncClient", return_value=mock_client):
    result = await tool.execute(tool_context=MagicMock(), url="https://example.com")
```

**Tools with SSRF protection** — always test the block:
```python
async def test_ssrf_blocked(self):
    tool = MyTool()
    result = await tool.execute(
        tool_context=MagicMock(),
        url="http://169.254.169.254/latest/",
    )
    assert "SSRF blocked" in result["error"]

async def test_ssrf_blocked_localhost(self):
    tool = MyTool()
    result = await tool.execute(
        tool_context=MagicMock(),
        url="http://localhost:8080/internal",
    )
    assert "SSRF blocked" in result["error"]
```

**Tools that parse JSON input** — test invalid JSON gracefully:
```python
async def test_invalid_json_handled(self):
    tool = MyTool()
    result = await tool.execute(
        tool_context=MagicMock(),
        data="not valid json{{{",
    )
    # Should not raise — should return error dict or use default
```

### Test Conventions

- `tool_context` is always `MagicMock()` — tools receive it but test in isolation
- No `@pytest.mark.asyncio` needed — `asyncio_mode = "auto"` is configured in pyproject.toml
- Test file mirrors source: `pyflow/tools/foo.py` -> `tests/tools/test_foo.py`
- Always include `test_auto_registered` to verify the tool appears in the global registry
- Test both success paths and error paths
- For HTTP tools: test success, SSRF block, network error, and invalid input

## Step 4: Verify

Run these in order:

```bash
source .venv/bin/activate
pytest tests/tools/test_<tool_name>.py -v    # new tool tests
pytest -v                                      # full suite — nothing broken
ruff check                                     # lint clean
```

## Common Patterns

### HTTP Client Tool
If the tool wraps an external API, follow HttpTool's pattern:
- Use `httpx.AsyncClient` with a timeout
- Check `is_private_url()` before requesting
- Clamp timeout to a sensible range
- Parse response as JSON, fall back to text
- Return `{"status": code, "body": data}` on success, `{"status": 0, "error": msg}` on failure

### Data Processing Tool
If the tool transforms data (like TransformTool):
- Accept input as a JSON string parameter
- Parse with `safe_json_parse()` — return error dict on invalid input
- Return `{"result": value}` on success, `{"result": None, "error": msg}` on failure

### File I/O Tool
If the tool reads/writes files (like StorageTool):
- Use `pathlib.Path` for path handling
- Create parent directories with `mkdir(parents=True, exist_ok=True)` on write
- Return `{"content": data, "success": True}` pattern
- Handle FileNotFoundError explicitly

### Stateful Tool (using ToolContext)
If the tool needs to read/write session state:
```python
async def execute(self, tool_context: ToolContext, key: str) -> dict:
    # Read from state
    value = tool_context.state.get(key)
    # Write to state
    tool_context.state["new_key"] = computed_value
    return {"result": computed_value}
```

## What NOT To Do

- **Don't add the tool to any registry manually** — `__init_subclass__` handles it
- **Don't modify `__init__.py`** — tools are discovered by importing the module
- **Don't use `**kwargs` on execute** — ADK needs explicit typed parameters to generate the schema
- **Don't raise exceptions** — catch them and return error dicts
- **Don't reimplement `safe_json_parse` or `is_private_url`** — import from `pyflow.tools.parsing` and `pyflow.tools.security`
- **Don't make synchronous HTTP calls** — use `httpx.AsyncClient`, the platform is async throughout
- **Don't skip the docstring** — it's how the LLM understands the tool's parameters
