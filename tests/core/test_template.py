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
