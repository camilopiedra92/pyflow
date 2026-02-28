from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from pyflow.models.agent import AgentConfig, OpenApiAuthConfig, OpenApiToolConfig
from pyflow.models.workflow import OrchestrationConfig, WorkflowDef
from pyflow.platform.hydration.hydrator import WorkflowHydrator
from pyflow.platform.registry.tool_registry import ToolRegistry


# Minimal valid OpenAPI 3.0 spec for testing
MINI_SPEC = json.dumps({
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "servers": [{"url": "https://api.example.com"}],
    "paths": {
        "/items": {
            "get": {
                "operationId": "listItems",
                "summary": "List all items",
                "responses": {"200": {"description": "OK"}},
            }
        }
    },
})


def _make_workflow_with_openapi(
    spec_path: str = "specs/test.json",
    auth: OpenApiAuthConfig | None = None,
) -> WorkflowDef:
    return WorkflowDef(
        name="test_openapi",
        agents=[
            AgentConfig(
                name="agent1",
                type="llm",
                model="gemini-2.5-flash",
                instruction="Use the API",
                openapi_tools=[
                    OpenApiToolConfig(
                        spec=spec_path,
                        auth=auth or OpenApiAuthConfig(),
                    )
                ],
            )
        ],
        orchestration=OrchestrationConfig(type="react", agent="agent1"),
    )


class TestHydratorOpenApiTools:
    def test_openapi_toolset_appended_to_agent_tools(self, tmp_path):
        """When an agent has openapi_tools, hydrator creates OpenAPIToolset and appends it."""
        spec_file = tmp_path / "specs" / "test.json"
        spec_file.parent.mkdir(parents=True)
        spec_file.write_text(MINI_SPEC)

        registry = MagicMock(spec=ToolRegistry)
        registry.resolve_tools.return_value = []

        hydrator = WorkflowHydrator(registry, base_dir=tmp_path)
        workflow = _make_workflow_with_openapi(spec_path="specs/test.json")

        with patch(
            "pyflow.platform.hydration.hydrator.OpenAPIToolset"
        ) as MockToolset:
            mock_instance = MagicMock()
            MockToolset.return_value = mock_instance

            hydrator.hydrate(workflow)

        # OpenAPIToolset should have been created
        MockToolset.assert_called_once()
        call_kwargs = MockToolset.call_args
        assert "spec_str" in call_kwargs.kwargs or len(call_kwargs.args) > 0

    def test_openapi_toolset_with_bearer_auth(self, tmp_path):
        """Bearer auth config is passed to OpenAPIToolset."""
        spec_file = tmp_path / "specs" / "test.json"
        spec_file.parent.mkdir(parents=True)
        spec_file.write_text(MINI_SPEC)

        registry = MagicMock(spec=ToolRegistry)
        registry.resolve_tools.return_value = []

        auth = OpenApiAuthConfig(type="bearer", token_env="TEST_TOKEN")
        hydrator = WorkflowHydrator(registry, base_dir=tmp_path)
        workflow = _make_workflow_with_openapi(auth=auth)

        with patch(
            "pyflow.platform.hydration.hydrator.OpenAPIToolset"
        ) as MockToolset, patch.dict("os.environ", {"TEST_TOKEN": "abc123"}):
            mock_instance = MagicMock()
            MockToolset.return_value = mock_instance

            hydrator.hydrate(workflow)

        MockToolset.assert_called_once()
        call_kwargs = MockToolset.call_args.kwargs
        assert call_kwargs.get("auth_scheme") is not None
        assert call_kwargs.get("auth_credential") is not None

    def test_multiple_openapi_toolsets(self, tmp_path):
        """Agent can have multiple openapi_tools entries."""
        for name in ("spec1.json", "spec2.json"):
            spec_file = tmp_path / "specs" / name
            spec_file.parent.mkdir(parents=True, exist_ok=True)
            spec_file.write_text(MINI_SPEC)

        registry = MagicMock(spec=ToolRegistry)
        registry.resolve_tools.return_value = []

        workflow = WorkflowDef(
            name="multi_openapi",
            agents=[
                AgentConfig(
                    name="agent1",
                    type="llm",
                    model="gemini-2.5-flash",
                    instruction="Use APIs",
                    openapi_tools=[
                        OpenApiToolConfig(spec="specs/spec1.json"),
                        OpenApiToolConfig(spec="specs/spec2.json"),
                    ],
                )
            ],
            orchestration=OrchestrationConfig(type="react", agent="agent1"),
        )

        hydrator = WorkflowHydrator(registry, base_dir=tmp_path)

        with patch(
            "pyflow.platform.hydration.hydrator.OpenAPIToolset"
        ) as MockToolset:
            MockToolset.return_value = MagicMock()
            hydrator.hydrate(workflow)

        assert MockToolset.call_count == 2

    def test_no_openapi_tools_unchanged(self):
        """Agent without openapi_tools works as before."""
        registry = MagicMock(spec=ToolRegistry)
        registry.resolve_tools.return_value = [MagicMock()]

        workflow = WorkflowDef(
            name="no_openapi",
            agents=[
                AgentConfig(
                    name="agent1",
                    type="llm",
                    model="gemini-2.5-flash",
                    instruction="No OpenAPI",
                    tools=["http_request"],
                )
            ],
            orchestration=OrchestrationConfig(type="react", agent="agent1"),
        )

        hydrator = WorkflowHydrator(registry)
        agent = hydrator.hydrate(workflow)
        assert agent is not None


class TestBuildRootAgentOpenApi:
    def test_build_root_agent_passes_project_root(self, tmp_path):
        """build_root_agent should derive base_dir as project root (grandparent of package)."""
        # Simulate: project_root/agents/my_agent/workflow.yaml
        pkg_dir = tmp_path / "agents" / "my_agent"
        pkg_dir.mkdir(parents=True)
        workflow_yaml = pkg_dir / "workflow.yaml"
        workflow_yaml.write_text(
            "name: test\n"
            "agents:\n"
            "  - name: a1\n"
            "    type: llm\n"
            "    model: gemini-2.5-flash\n"
            "    instruction: hi\n"
            "orchestration:\n"
            "  type: react\n"
            "  agent: a1\n"
        )
        agent_py = pkg_dir / "agent.py"
        agent_py.write_text("")

        with patch(
            "pyflow.platform.hydration.hydrator.WorkflowHydrator"
        ) as MockHydrator:
            mock_instance = MagicMock()
            mock_instance.hydrate.return_value = MagicMock()
            MockHydrator.return_value = mock_instance

            from pyflow.platform.hydration.hydrator import build_root_agent

            build_root_agent(str(agent_py))

        call_kwargs = MockHydrator.call_args
        # base_dir should be tmp_path (project root = grandparent of agent package)
        assert call_kwargs.kwargs.get("base_dir") == tmp_path or (
            len(call_kwargs.args) > 1 and call_kwargs.args[1] == tmp_path
        )
