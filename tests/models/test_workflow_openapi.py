from __future__ import annotations

from pyflow.models.agent import OpenApiToolConfig
from pyflow.models.workflow import WorkflowDef


def _minimal_workflow(**kwargs) -> WorkflowDef:
    """Build a minimal WorkflowDef with optional overrides."""
    defaults = {
        "name": "test_wf",
        "agents": [
            {
                "name": "a1",
                "type": "llm",
                "model": "gemini-2.5-flash",
                "instruction": "Do stuff",
            }
        ],
        "orchestration": {"type": "react", "agent": "a1"},
    }
    defaults.update(kwargs)
    return WorkflowDef(**defaults)


class TestWorkflowDefOpenApiTools:
    def test_default_empty_dict(self):
        wf = _minimal_workflow()
        assert wf.openapi_tools == {}

    def test_with_openapi_tools(self):
        wf = _minimal_workflow(
            openapi_tools={
                "ynab": {
                    "spec": "specs/ynab-v1-openapi.yaml",
                    "auth": {"type": "bearer", "token_env": "PYFLOW_YNAB_API_TOKEN"},
                }
            }
        )
        assert "ynab" in wf.openapi_tools
        assert wf.openapi_tools["ynab"].spec == "specs/ynab-v1-openapi.yaml"
        assert wf.openapi_tools["ynab"].auth.type == "bearer"

    def test_multiple_openapi_tools(self):
        wf = _minimal_workflow(
            openapi_tools={
                "ynab": {"spec": "specs/ynab.yaml"},
                "stripe": {
                    "spec": "specs/stripe.json",
                    "auth": {"type": "apikey", "token_env": "STRIPE_KEY"},
                },
            }
        )
        assert len(wf.openapi_tools) == 2
        assert wf.openapi_tools["stripe"].auth.type == "apikey"

    def test_openapi_tools_from_yaml(self, tmp_path):
        yaml_content = """\
name: test_yaml
agents:
  - name: a1
    type: llm
    model: gemini-2.5-flash
    instruction: Use API
    tools: [ynab]
openapi_tools:
  ynab:
    spec: specs/ynab.yaml
    auth:
      type: bearer
      token_env: PYFLOW_YNAB_TOKEN
orchestration:
  type: react
  agent: a1
"""
        yaml_file = tmp_path / "workflow.yaml"
        yaml_file.write_text(yaml_content)
        wf = WorkflowDef.from_yaml(yaml_file)
        assert "ynab" in wf.openapi_tools
        assert wf.openapi_tools["ynab"].auth.token_env == "PYFLOW_YNAB_TOKEN"
        assert "ynab" in wf.agents[0].tools

    def test_openapi_tools_pydantic_model(self):
        """OpenApiToolConfig instances are created from dict values."""
        wf = _minimal_workflow(
            openapi_tools={"petstore": {"spec": "specs/petstore.yaml"}}
        )
        cfg = wf.openapi_tools["petstore"]
        assert isinstance(cfg, OpenApiToolConfig)
        assert cfg.auth.type == "none"
