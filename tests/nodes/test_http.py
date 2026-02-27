import socket
from unittest.mock import patch

import pytest
from pyflow.nodes.http import HttpNode, SSRFError
from pyflow.core.context import ExecutionContext

# Fake DNS resolution returning a public IP for test hostnames.
_FAKE_ADDRINFO = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]


@pytest.fixture(autouse=True)
def _bypass_ssrf_dns():
    """Patch DNS resolution so test hostnames resolve to a public IP."""
    with patch("pyflow.nodes.http.socket.getaddrinfo", return_value=_FAKE_ADDRINFO):
        yield


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

    async def test_ssrf_blocks_localhost(self):
        node = HttpNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        with pytest.raises(SSRFError, match="localhost"):
            await node.execute({"url": "http://localhost/admin"}, ctx)

    async def test_ssrf_blocks_private_ip(self):
        private_addrinfo = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.1", 0))
        ]
        with patch(
            "pyflow.nodes.http.socket.getaddrinfo", return_value=private_addrinfo
        ):
            node = HttpNode()
            ctx = ExecutionContext(workflow_name="test", run_id="run-1")
            with pytest.raises(SSRFError, match="private/internal"):
                await node.execute({"url": "http://internal.corp/secret"}, ctx)

    async def test_ssrf_allow_private_networks(self, httpx_mock):
        httpx_mock.add_response(url="http://localhost/admin", json={"ok": True})
        node = HttpNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {"url": "http://localhost/admin", "allow_private_networks": True}, ctx
        )
        assert result["status"] == 200

    async def test_ssrf_blocks_127_0_0_1(self):
        loopback_addrinfo = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))
        ]
        with patch(
            "pyflow.nodes.http.socket.getaddrinfo", return_value=loopback_addrinfo
        ):
            node = HttpNode()
            ctx = ExecutionContext(workflow_name="test", run_id="run-1")
            with pytest.raises(SSRFError):
                await node.execute({"url": "http://some-host.com/admin"}, ctx)

    async def test_ssrf_blocks_10_x_network(self):
        private_addrinfo = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.1", 0))
        ]
        with patch(
            "pyflow.nodes.http.socket.getaddrinfo", return_value=private_addrinfo
        ):
            node = HttpNode()
            ctx = ExecutionContext(workflow_name="test", run_id="run-1")
            with pytest.raises(SSRFError, match="private/internal"):
                await node.execute({"url": "http://internal.example.com/data"}, ctx)

    async def test_ssrf_blocks_metadata_ip(self):
        metadata_addrinfo = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", 0))
        ]
        with patch(
            "pyflow.nodes.http.socket.getaddrinfo", return_value=metadata_addrinfo
        ):
            node = HttpNode()
            ctx = ExecutionContext(workflow_name="test", run_id="run-1")
            with pytest.raises(SSRFError):
                await node.execute(
                    {"url": "http://metadata.google.internal/computeMetadata"}, ctx
                )

    async def test_ssrf_allows_public_ip(self, httpx_mock):
        httpx_mock.add_response(url="https://example.com/api", json={"ok": True})
        node = HttpNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute({"url": "https://example.com/api"}, ctx)
        assert result["status"] == 200

    async def test_timeout_config(self, httpx_mock):
        httpx_mock.add_response(url="https://api.test.com/slow", json={"ok": True})
        node = HttpNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {"url": "https://api.test.com/slow", "timeout": 5}, ctx
        )
        assert result["status"] == 200

    async def test_raise_for_status_error(self, httpx_mock):
        httpx_mock.add_response(
            url="https://api.test.com/fail", status_code=500, json={"error": "bad"}
        )
        node = HttpNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        with pytest.raises(Exception):
            await node.execute(
                {"url": "https://api.test.com/fail", "raise_for_status": True}, ctx
            )

    async def test_raise_for_status_disabled(self, httpx_mock):
        httpx_mock.add_response(
            url="https://api.test.com/fail", status_code=500, json={"error": "bad"}
        )
        node = HttpNode()
        ctx = ExecutionContext(workflow_name="test", run_id="run-1")
        result = await node.execute(
            {"url": "https://api.test.com/fail", "raise_for_status": False}, ctx
        )
        assert result["status"] == 500
