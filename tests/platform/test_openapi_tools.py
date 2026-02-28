from __future__ import annotations

from pyflow.models.workflow import OpenApiToolConfig, RuntimeConfig


class TestOpenApiToolConfig:
    def test_basic_config(self):
        config = OpenApiToolConfig(spec="specs/petstore.yaml")
        assert config.spec == "specs/petstore.yaml"
        assert config.name_prefix is None

    def test_config_with_prefix(self):
        config = OpenApiToolConfig(spec="specs/ynab.yaml", name_prefix="ynab")
        assert config.name_prefix == "ynab"

    def test_runtime_config_with_openapi(self):
        runtime = RuntimeConfig(
            openapi_tools=[OpenApiToolConfig(spec="specs/petstore.yaml", name_prefix="pet")]
        )
        assert len(runtime.openapi_tools) == 1

    def test_runtime_config_default_empty(self):
        runtime = RuntimeConfig()
        assert runtime.openapi_tools == []
