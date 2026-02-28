from __future__ import annotations

from pyflow.models.tool import ToolConfig, ToolMetadata, ToolResponse


class TestToolConfig:
    def test_base_config_instantiation(self):
        config = ToolConfig()
        assert isinstance(config, ToolConfig)

    def test_base_config_is_extensible(self):
        class MyConfig(ToolConfig):
            url: str
            timeout: int = 30

        cfg = MyConfig(url="https://example.com")
        assert cfg.url == "https://example.com"
        assert cfg.timeout == 30


class TestToolResponse:
    def test_base_response_instantiation(self):
        resp = ToolResponse()
        assert isinstance(resp, ToolResponse)

    def test_base_response_is_extensible(self):
        class MyResponse(ToolResponse):
            status: int
            body: str

        resp = MyResponse(status=200, body="ok")
        assert resp.status == 200
        assert resp.body == "ok"


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
