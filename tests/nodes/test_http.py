import pytest
from pyflow.nodes.http import HttpNode
from pyflow.core.context import ExecutionContext


class TestHttpNode:
    def test_node_type(self):
        assert HttpNode.node_type == "http"

    async def test_get_request(self, httpx_mock):
        httpx_mock.add_response(url="https://api.test.com/data", json={"ok": True})
        node = HttpNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {"method": "GET", "url": "https://api.test.com/data"}, ctx
        )
        assert result["status"] == 200
        assert result["body"] == {"ok": True}

    async def test_post_request_with_body(self, httpx_mock):
        httpx_mock.add_response(url="https://api.test.com/submit", json={"created": True})
        node = HttpNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {
                "method": "POST",
                "url": "https://api.test.com/submit",
                "body": {"name": "test"},
            },
            ctx,
        )
        assert result["status"] == 200

    async def test_with_headers(self, httpx_mock):
        httpx_mock.add_response(url="https://api.test.com/auth", json={"ok": True})
        node = HttpNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {
                "method": "GET",
                "url": "https://api.test.com/auth",
                "headers": {"Authorization": "Bearer token123"},
            },
            ctx,
        )
        assert result["status"] == 200
