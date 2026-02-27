from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport
from pyflow.server import create_app

FIXTURES = Path(__file__).parent / "fixtures"


class TestServer:
    async def test_health_check(self):
        app = create_app(FIXTURES)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_list_workflows(self):
        app = create_app(FIXTURES)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/workflows")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    async def test_trigger_workflow_with_non_network_workflow(self):
        """Trigger multi-step-test which uses condition+transform nodes (no HTTP)."""
        app = create_app(FIXTURES)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/trigger/multi-step-test")
        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert "results" in data
        assert data["results"]["start"] == "ok"

    async def test_trigger_nonexistent_workflow_returns_404(self):
        app = create_app(FIXTURES)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/trigger/nonexistent-workflow")
        assert response.status_code == 404

    async def test_error_response_no_internal_details(self):
        app = create_app(FIXTURES)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/trigger/nonexistent-workflow")
        data = response.json()
        assert "detail" in data
        # Should not leak stack traces or internal paths
        assert "Traceback" not in data["detail"]


class TestServerAuth:
    async def test_trigger_returns_401_without_api_key(self):
        with patch.dict(os.environ, {"PYFLOW_API_KEY": "secret-key-123"}):
            app = create_app(FIXTURES)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/trigger/multi-step-test")
        assert response.status_code == 401

    async def test_trigger_succeeds_with_correct_api_key(self):
        with patch.dict(os.environ, {"PYFLOW_API_KEY": "secret-key-123"}):
            app = create_app(FIXTURES)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/trigger/multi-step-test",
                headers={"Authorization": "Bearer secret-key-123"},
            )
        assert response.status_code == 200

    async def test_trigger_returns_401_with_wrong_api_key(self):
        with patch.dict(os.environ, {"PYFLOW_API_KEY": "secret-key-123"}):
            app = create_app(FIXTURES)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/trigger/multi-step-test",
                headers={"Authorization": "Bearer wrong-key"},
            )
        assert response.status_code == 401

    async def test_health_works_without_api_key(self):
        with patch.dict(os.environ, {"PYFLOW_API_KEY": "secret-key-123"}):
            app = create_app(FIXTURES)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
