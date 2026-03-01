from __future__ import annotations

from pyflow.models.agent import OpenApiAuthConfig, OpenApiToolConfig
from pyflow.models.workflow import RuntimeConfig


class TestOpenApiToolConfigFromAgent:
    """Verify OpenApiToolConfig lives in agent.py (not workflow.py)."""

    def test_basic_config(self):
        config = OpenApiToolConfig(spec="specs/petstore.yaml")
        assert config.spec == "specs/petstore.yaml"
        assert config.name_prefix is None

    def test_config_with_prefix_and_auth(self):
        config = OpenApiToolConfig(
            spec="specs/ynab.yaml",
            name_prefix="ynab",
            auth=OpenApiAuthConfig(type="bearer", token_env="PYFLOW_TOKEN"),
        )
        assert config.name_prefix == "ynab"
        assert config.auth.type == "bearer"


class TestRuntimeConfigNoOpenApiTools:
    """Verify openapi_tools was removed from RuntimeConfig."""

    def test_no_openapi_tools_field(self):
        runtime = RuntimeConfig()
        assert not hasattr(runtime, "openapi_tools")
