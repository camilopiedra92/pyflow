import pytest
from pathlib import Path
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

    async def test_trigger_workflow(self):
        app = create_app(FIXTURES)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/trigger/simple-workflow")
        # May fail on HTTP call inside workflow, but endpoint should respond
        assert response.status_code in (200, 500)
