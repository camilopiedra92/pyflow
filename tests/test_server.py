from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport

from pyflow.models.a2a import AgentCard
from pyflow.models.runner import RunResult
from pyflow.models.tool import ToolMetadata
from pyflow.models.workflow import WorkflowDef


def _make_workflow(name: str = "test-wf", description: str = "A test workflow") -> WorkflowDef:
    """Create a minimal WorkflowDef for testing."""
    return WorkflowDef(
        name=name,
        description=description,
        agents=[
            {
                "name": "agent1",
                "type": "llm",
                "model": "gemini-2.5-flash",
                "instruction": "Do something",
            }
        ],
        orchestration={"type": "sequential", "agents": ["agent1"]},
    )


@pytest.fixture
async def client():
    """Create an async test client with a mocked PyFlowPlatform."""
    mock_platform = MagicMock()
    mock_platform.is_booted = True
    # Sync methods
    mock_platform.list_tools.return_value = []
    mock_platform.list_workflows.return_value = []
    mock_platform.agent_cards.return_value = []
    # Async methods
    mock_platform.boot = AsyncMock()
    mock_platform.shutdown = AsyncMock()
    mock_platform.run_workflow = AsyncMock()

    with patch("pyflow.server.PyFlowPlatform") as MockPlatform:
        MockPlatform.return_value = mock_platform

        from pyflow.server import app

        # Inject mock platform directly into app state (bypasses lifespan)
        app.state.platform = mock_platform

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac._mock_platform = mock_platform
            yield ac

        # Clean up state
        if hasattr(app.state, "platform"):
            del app.state.platform


class TestHealth:
    async def test_health_endpoint(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["booted"] is True


class TestTools:
    async def test_list_tools_empty(self, client: AsyncClient):
        response = await client.get("/api/tools")
        assert response.status_code == 200
        assert response.json() == {"tools": []}

    async def test_list_tools_with_data(self, client: AsyncClient):
        tools = [
            ToolMetadata(name="http_request", description="Make HTTP requests", tags=["http"]),
            ToolMetadata(name="transform", description="Transform data"),
        ]
        client._mock_platform.list_tools.return_value = tools

        response = await client.get("/api/tools")
        assert response.status_code == 200
        data = response.json()
        assert len(data["tools"]) == 2
        assert data["tools"][0]["name"] == "http_request"
        assert data["tools"][0]["description"] == "Make HTTP requests"
        assert data["tools"][0]["tags"] == ["http"]
        assert data["tools"][1]["name"] == "transform"


class TestWorkflows:
    async def test_list_workflows_empty(self, client: AsyncClient):
        response = await client.get("/api/workflows")
        assert response.status_code == 200
        assert response.json() == {"workflows": []}

    async def test_list_workflows_with_data(self, client: AsyncClient):
        wf = _make_workflow()
        client._mock_platform.list_workflows.return_value = [wf]

        response = await client.get("/api/workflows")
        assert response.status_code == 200
        data = response.json()
        assert len(data["workflows"]) == 1
        assert data["workflows"][0]["name"] == "test-wf"

    async def test_run_workflow_success(self, client: AsyncClient):
        run_result = RunResult(content="done", author="test-agent")
        client._mock_platform.run_workflow.return_value = run_result

        response = await client.post(
            "/api/workflows/test/run",
            json={"message": "hello", "data": {}},
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["content"] == "done"
        assert data["result"]["author"] == "test-agent"
        client._mock_platform.run_workflow.assert_awaited_once_with(
            "test",
            {"message": "hello", "data": {}},
            user_id="default",
        )

    async def test_run_workflow_with_user_id(self, client: AsyncClient):
        run_result = RunResult(content="done", author="test-agent")
        client._mock_platform.run_workflow.return_value = run_result

        response = await client.post(
            "/api/workflows/test/run",
            json={"message": "hello", "data": {}, "user_id": "alice"},
        )
        assert response.status_code == 200
        client._mock_platform.run_workflow.assert_awaited_once_with(
            "test",
            {"message": "hello", "data": {}},
            user_id="alice",
        )

    async def test_run_workflow_user_id_default(self, client: AsyncClient):
        """user_id defaults to 'default' when omitted from request body."""
        run_result = RunResult(content="ok", author="agent")
        client._mock_platform.run_workflow.return_value = run_result

        response = await client.post(
            "/api/workflows/test/run",
            json={"message": "hi"},
        )
        assert response.status_code == 200
        client._mock_platform.run_workflow.assert_awaited_once_with(
            "test",
            {"message": "hi", "data": {}},
            user_id="default",
        )

    async def test_run_workflow_not_found(self, client: AsyncClient):
        client._mock_platform.run_workflow.side_effect = KeyError("test")

        response = await client.post(
            "/api/workflows/test/run",
            json={"message": "", "data": {}},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_run_workflow_internal_error(self, client: AsyncClient):
        client._mock_platform.run_workflow.side_effect = RuntimeError("boom")

        response = await client.post(
            "/api/workflows/test/run",
            json={"message": "", "data": {}},
        )
        assert response.status_code == 500
        data = response.json()
        assert "internal" in data["detail"].lower()
        # Should not leak the actual error message
        assert "boom" not in data["detail"]


class TestA2A:
    async def test_agent_cards_endpoint(self, client: AsyncClient):
        client._mock_platform.agent_cards.return_value = [
            AgentCard(name="test-wf", url="http://localhost:8000/a2a/test-wf")
        ]

        response = await client.get("/.well-known/agent-card.json")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "test-wf"

    async def test_a2a_execute_success(self, client: AsyncClient):
        run_result = RunResult(content="a2a result", author="a2a-agent")
        client._mock_platform.run_workflow.return_value = run_result

        response = await client.post(
            "/a2a/test-wf",
            json={"message": "run it", "data": {}},
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["content"] == "a2a result"
        assert data["result"]["author"] == "a2a-agent"
        client._mock_platform.run_workflow.assert_awaited_once_with(
            "test-wf",
            {"message": "run it", "data": {}},
            user_id="default",
        )

    async def test_a2a_execute_with_user_id(self, client: AsyncClient):
        run_result = RunResult(content="a2a result", author="a2a-agent")
        client._mock_platform.run_workflow.return_value = run_result

        response = await client.post(
            "/a2a/test-wf",
            json={"message": "run it", "data": {}, "user_id": "bob"},
        )
        assert response.status_code == 200
        client._mock_platform.run_workflow.assert_awaited_once_with(
            "test-wf",
            {"message": "run it", "data": {}},
            user_id="bob",
        )

    async def test_a2a_execute_not_found(self, client: AsyncClient):
        client._mock_platform.run_workflow.side_effect = KeyError("test-wf")

        response = await client.post(
            "/a2a/unknown-wf",
            json={"message": "", "data": {}},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_a2a_execute_internal_error(self, client: AsyncClient):
        client._mock_platform.run_workflow.side_effect = RuntimeError("kaboom")

        response = await client.post(
            "/a2a/test-wf",
            json={"message": "", "data": {}},
        )
        assert response.status_code == 500
        data = response.json()
        assert "internal" in data["detail"].lower()
        assert "kaboom" not in data["detail"]


class TestStreaming:
    async def test_stream_endpoint_exists(self, client: AsyncClient):
        """The /api/workflows/{name}/stream endpoint is routable."""
        # Set up the mock to raise KeyError (workflow not found) so we get a 404
        # rather than hitting real executor code — proving the route exists.
        client._mock_platform.workflows = MagicMock()
        client._mock_platform.workflows.get.side_effect = KeyError("test")

        response = await client.post(
            "/api/workflows/test/stream",
            json={"message": "hello"},
        )
        assert response.status_code == 404

    async def test_stream_workflow_not_found(self, client: AsyncClient):
        """Streaming endpoint returns 404 for unknown workflow."""
        client._mock_platform.workflows = MagicMock()
        client._mock_platform.workflows.get.side_effect = KeyError("unknown")

        response = await client.post(
            "/api/workflows/unknown/stream",
            json={"message": "hello"},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_stream_returns_sse_content_type(self, client: AsyncClient):
        """Streaming endpoint returns SSE content type for valid workflow."""
        mock_hw = MagicMock()
        mock_hw.agent = MagicMock()
        mock_hw.definition.runtime = MagicMock()

        client._mock_platform.workflows = MagicMock()
        client._mock_platform.workflows.get.return_value = mock_hw

        mock_runner = MagicMock()
        client._mock_platform.executor = MagicMock()
        client._mock_platform.executor.build_runner.return_value = mock_runner

        # Return an empty async generator
        async def _empty_gen(*args, **kwargs):
            return
            yield  # makes it an async generator

        client._mock_platform.executor.run_streaming = _empty_gen

        response = await client.post(
            "/api/workflows/test-wf/stream",
            json={"message": "hello"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
