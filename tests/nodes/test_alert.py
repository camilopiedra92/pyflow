from __future__ import annotations

import httpx
import pytest

from pyflow.core.context import ExecutionContext
from pyflow.nodes.alert import AlertNode


class TestAlertNode:
    def test_node_type(self):
        assert AlertNode.node_type == "alert"

    async def test_sends_post_to_webhook(self, httpx_mock):
        httpx_mock.add_response(
            url="https://hooks.slack.com/test",
            json={"ok": True},
        )
        node = AlertNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {"webhook_url": "https://hooks.slack.com/test", "message": "Hello"},
            ctx,
        )
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "POST"
        assert request.url == "https://hooks.slack.com/test"
        import json

        assert json.loads(request.content) == {"text": "Hello"}

    async def test_returns_status_and_sent(self, httpx_mock):
        httpx_mock.add_response(
            url="https://hooks.slack.com/test",
            status_code=200,
            json={"ok": True},
        )
        node = AlertNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {"webhook_url": "https://hooks.slack.com/test", "message": "Hello"},
            ctx,
        )
        assert result["status"] == 200
        assert result["sent"] is True

    async def test_handles_network_error(self, httpx_mock):
        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
        node = AlertNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {"webhook_url": "https://hooks.slack.com/test", "message": "Hello"},
            ctx,
        )
        assert result["sent"] is False
        assert "error" in result
        assert "Connection refused" in result["error"]

    async def test_requires_webhook_url(self):
        node = AlertNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        with pytest.raises(KeyError):
            await node.execute({"message": "Hello"}, ctx)

    async def test_requires_message(self):
        node = AlertNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        with pytest.raises(KeyError):
            await node.execute({"webhook_url": "https://hooks.slack.com/test"}, ctx)
