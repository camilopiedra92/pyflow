from __future__ import annotations

from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext

from pyflow.tools.base import (
    BasePlatformTool,
    get_registered_tools,
    _TOOL_AUTO_REGISTRY,
    get_secret,
    set_secrets,
    clear_secrets,
)


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


class TestGetRegisteredTools:
    def test_returns_dict_copy(self):
        tools = get_registered_tools()
        assert isinstance(tools, dict)
        assert "dummy" in tools

    def test_includes_builtin_tools(self):
        import pyflow.tools  # noqa: F401

        tools = get_registered_tools()
        assert "http_request" in tools
        assert "transform" in tools
        assert "condition" in tools
        assert "alert" in tools
        assert "storage" in tools
        assert "ynab" in tools


class TestAsFunctionTool:
    def test_returns_function_tool(self):
        tool = _DummyTool.as_function_tool()
        assert isinstance(tool, FunctionTool)


class TestMetadata:
    def test_returns_tool_metadata(self):
        meta = _DummyTool.metadata()
        assert meta.name == "dummy"
        assert meta.description == "A dummy tool for testing"


class TestSecretStore:
    def setup_method(self):
        clear_secrets()

    def teardown_method(self):
        clear_secrets()

    def test_get_secret_returns_none_when_empty(self):
        assert get_secret("nonexistent") is None

    def test_set_and_get_secret(self):
        set_secrets({"my_key": "my_value"})
        assert get_secret("my_key") == "my_value"

    def test_set_secrets_merges(self):
        set_secrets({"a": "1"})
        set_secrets({"b": "2"})
        assert get_secret("a") == "1"
        assert get_secret("b") == "2"

    def test_clear_secrets_removes_all(self):
        set_secrets({"a": "1"})
        clear_secrets()
        assert get_secret("a") is None

    def test_get_secret_from_env_var(self, monkeypatch):
        monkeypatch.setenv("PYFLOW_MY_SECRET", "from-env")
        assert get_secret("my_secret") == "from-env"

    def test_env_var_takes_priority_over_dict(self, monkeypatch):
        set_secrets({"my_secret": "from-dict"})
        monkeypatch.setenv("PYFLOW_MY_SECRET", "from-env")
        assert get_secret("my_secret") == "from-env"

    def test_dict_fallback_when_no_env_var(self):
        set_secrets({"my_secret": "from-dict"})
        assert get_secret("my_secret") == "from-dict"

    def test_none_when_neither_env_nor_dict(self):
        assert get_secret("nonexistent") is None
