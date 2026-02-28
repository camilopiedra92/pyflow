from __future__ import annotations

from pathlib import Path

from pyflow.models.agent import OpenApiToolConfig
from pyflow.models.project import ProjectConfig


class TestProjectConfig:
    def test_default_empty_dict(self):
        config = ProjectConfig()
        assert config.openapi_tools == {}

    def test_loads_from_yaml(self, tmp_path):
        yaml_content = """\
openapi_tools:
  ynab:
    spec: specs/ynab-v1-openapi.yaml
    auth:
      type: bearer
      token_env: PYFLOW_YNAB_API_TOKEN
    tool_filter: agents.budget_analyst.predicates.read_only
"""
        yaml_file = tmp_path / "pyflow.yaml"
        yaml_file.write_text(yaml_content)

        config = ProjectConfig.from_yaml(yaml_file)

        assert "ynab" in config.openapi_tools
        assert config.openapi_tools["ynab"].spec == "specs/ynab-v1-openapi.yaml"
        assert config.openapi_tools["ynab"].auth.type == "bearer"
        assert config.openapi_tools["ynab"].auth.token_env == "PYFLOW_YNAB_API_TOKEN"
        assert config.openapi_tools["ynab"].tool_filter == "agents.budget_analyst.predicates.read_only"

    def test_returns_empty_when_file_missing(self, tmp_path):
        config = ProjectConfig.from_yaml(tmp_path / "nonexistent.yaml")
        assert config.openapi_tools == {}

    def test_validates_openapi_tool_config_instances(self):
        config = ProjectConfig(
            openapi_tools={
                "petstore": {"spec": "specs/petstore.yaml"},
                "ynab": {
                    "spec": "specs/ynab.yaml",
                    "auth": {"type": "bearer", "token_env": "TOKEN"},
                },
            }
        )
        assert isinstance(config.openapi_tools["petstore"], OpenApiToolConfig)
        assert isinstance(config.openapi_tools["ynab"], OpenApiToolConfig)
        assert config.openapi_tools["petstore"].auth.type == "none"
        assert config.openapi_tools["ynab"].auth.type == "bearer"

    def test_empty_yaml_file(self, tmp_path):
        """Empty YAML file returns empty config (yaml.safe_load returns None)."""
        yaml_file = tmp_path / "pyflow.yaml"
        yaml_file.write_text("")

        config = ProjectConfig.from_yaml(yaml_file)
        assert config.openapi_tools == {}

    def test_multiple_openapi_tools(self, tmp_path):
        yaml_content = """\
openapi_tools:
  ynab:
    spec: specs/ynab.yaml
  stripe:
    spec: specs/stripe.yaml
    auth:
      type: apikey
      token_env: STRIPE_KEY
"""
        yaml_file = tmp_path / "pyflow.yaml"
        yaml_file.write_text(yaml_content)

        config = ProjectConfig.from_yaml(yaml_file)
        assert len(config.openapi_tools) == 2
        assert config.openapi_tools["stripe"].auth.type == "apikey"
