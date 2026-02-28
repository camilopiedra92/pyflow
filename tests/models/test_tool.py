from __future__ import annotations

from pyflow.models.tool import ToolMetadata


class TestToolMetadata:
    def test_creation_with_all_fields(self):
        meta = ToolMetadata(
            name="http_request",
            description="Make HTTP requests",
            version="2.0.0",
            tags=["http", "network"],
        )
        assert meta.name == "http_request"
        assert meta.description == "Make HTTP requests"
        assert meta.version == "2.0.0"
        assert meta.tags == ["http", "network"]

    def test_defaults(self):
        meta = ToolMetadata(name="test_tool", description="A test tool")
        assert meta.version == "1.0.0"
        assert meta.tags == []

    def test_name_required(self):
        import pytest

        with pytest.raises(Exception):
            ToolMetadata(description="missing name")

    def test_description_required(self):
        import pytest

        with pytest.raises(Exception):
            ToolMetadata(name="tool_without_desc")
