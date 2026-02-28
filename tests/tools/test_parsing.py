from __future__ import annotations

from pyflow.tools.parsing import safe_json_parse


class TestSafeJsonParse:
    def test_valid_json_object(self):
        assert safe_json_parse('{"key": "value"}') == {"key": "value"}

    def test_valid_json_array(self):
        assert safe_json_parse("[1, 2, 3]") == [1, 2, 3]

    def test_empty_string(self):
        assert safe_json_parse("") is None

    def test_none_input(self):
        assert safe_json_parse(None) is None

    def test_invalid_json(self):
        assert safe_json_parse("not json") is None

    def test_custom_default(self):
        assert safe_json_parse("bad", default={}) == {}
