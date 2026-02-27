from __future__ import annotations

import pytest
from pyflow.core.safe_eval import UnsafeExpressionError, safe_eval


class TestSafeEvalBlocking:
    def test_blocks_import(self):
        with pytest.raises(UnsafeExpressionError):
            safe_eval("__import__('os')")

    def test_blocks_class_mro_subclasses(self):
        with pytest.raises(UnsafeExpressionError):
            safe_eval("''.__class__.__mro__[1].__subclasses__()")

    def test_blocks_exec(self):
        with pytest.raises(UnsafeExpressionError):
            safe_eval("exec('print(1)')")

    def test_blocks_eval(self):
        with pytest.raises(UnsafeExpressionError):
            safe_eval("eval('1+1')")

    def test_blocks_open(self):
        with pytest.raises(UnsafeExpressionError):
            safe_eval("open('/etc/passwd')")

    def test_blocks_dunder_globals(self):
        with pytest.raises(UnsafeExpressionError):
            safe_eval("x.__globals__", {"x": lambda: None})

    def test_blocks_dunder_builtins(self):
        with pytest.raises(UnsafeExpressionError):
            safe_eval("x.__builtins__", {"x": {}})


class TestSafeEvalAllowed:
    def test_comparison(self):
        assert safe_eval("x > 10", {"x": 42}) is True
        assert safe_eval("x < 10", {"x": 42}) is False

    def test_equality(self):
        assert safe_eval("x == 'hello'", {"x": "hello"}) is True

    def test_arithmetic(self):
        assert safe_eval("x + y", {"x": 10, "y": 20}) == 30
        assert safe_eval("x * y", {"x": 3, "y": 7}) == 21

    def test_string_operations(self):
        assert safe_eval("x.upper()", {"x": "hello"}) == "HELLO"
        assert safe_eval("x.startswith('he')", {"x": "hello"}) is True

    def test_len(self):
        assert safe_eval("len(items)", {"items": [1, 2, 3]}) == 3

    def test_boolean_logic(self):
        assert safe_eval("x > 0 and y > 0", {"x": 1, "y": 2}) is True
        assert safe_eval("x > 0 or y > 0", {"x": -1, "y": 2}) is True

    def test_min_max(self):
        assert safe_eval("min(x, y)", {"x": 5, "y": 3}) == 3
        assert safe_eval("max(x, y)", {"x": 5, "y": 3}) == 5

    def test_subscript_access(self):
        assert safe_eval("data['key']", {"data": {"key": "value"}}) == "value"

    def test_in_operator(self):
        assert safe_eval("'a' in items", {"items": ["a", "b"]}) is True

    def test_ternary_expression(self):
        assert safe_eval("'yes' if x else 'no'", {"x": True}) == "yes"


class TestSafeEvalWithContext:
    def test_uses_context_variables(self):
        variables = {"step1": {"status": "ok", "count": 5}, "step2": "done"}
        assert safe_eval("step1['status'] == 'ok'", variables) is True
        assert safe_eval("step1['count'] > 3", variables) is True
        assert safe_eval("step2 == 'done'", variables) is True

    def test_missing_variable_raises(self):
        with pytest.raises(NameError):
            safe_eval("nonexistent > 0", {})

    def test_no_variables(self):
        assert safe_eval("1 + 2") == 3
        assert safe_eval("True") is True
