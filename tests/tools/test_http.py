from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from pyflow.tools.http import HttpTool


class TestHttpToolExecute:
    async def test_get_request(self):
        tool = HttpTool()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({"content-type": "application/json"})
        mock_response.json.return_value = {"data": "test"}
        mock_response.text = '{"data": "test"}'

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pyflow.tools.http.httpx.AsyncClient", return_value=mock_client):
            result = await tool.execute(
                tool_context=MagicMock(),
                url="https://example.com/api",
            )

        assert isinstance(result, dict)
        assert result["status"] == 200
        assert result["body"] == {"data": "test"}
        mock_client.request.assert_called_once_with(
            method="GET",
            url="https://example.com/api",
            headers={},
            json=None,
        )

    async def test_post_with_json_body_and_headers(self):
        tool = HttpTool()

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = httpx.Headers({"content-type": "application/json"})
        mock_response.json.return_value = {"created": True}
        mock_response.text = '{"created": true}'

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        headers_json = json.dumps({"Authorization": "Bearer token123"})
        body_json = json.dumps({"key": "value"})

        with patch("pyflow.tools.http.httpx.AsyncClient", return_value=mock_client):
            result = await tool.execute(
                tool_context=MagicMock(),
                url="https://example.com/api",
                method="POST",
                headers=headers_json,
                body=body_json,
            )

        assert result["status"] == 201
        assert result["body"] == {"created": True}
        mock_client.request.assert_called_once_with(
            method="POST",
            url="https://example.com/api",
            headers={"Authorization": "Bearer token123"},
            json={"key": "value"},
        )

    async def test_ssrf_blocked_by_default(self):
        tool = HttpTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            url="http://169.254.169.254/latest/meta-data/",
        )
        assert result["status"] == 0
        assert "SSRF blocked" in result["error"]

    async def test_ssrf_allowed_with_flag(self):
        tool = HttpTool()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({"content-type": "application/json"})
        mock_response.json.return_value = {"local": True}
        mock_response.text = '{"local": true}'

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pyflow.tools.http.httpx.AsyncClient", return_value=mock_client):
            result = await tool.execute(
                tool_context=MagicMock(),
                url="http://localhost:8080/api",
                allow_private=True,
            )

        assert result["status"] == 200
        assert result["body"] == {"local": True}

    async def test_network_error(self):
        tool = HttpTool()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=httpx.HTTPError("connection failed"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pyflow.tools.http.httpx.AsyncClient", return_value=mock_client):
            result = await tool.execute(
                tool_context=MagicMock(),
                url="https://example.com/fail",
            )

        assert result["status"] == 0
        assert "connection failed" in result["error"]

    async def test_invalid_json_headers_gracefully_handled(self):
        """Invalid JSON headers string should fall back to empty dict."""
        tool = HttpTool()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({})
        mock_response.json.return_value = {}
        mock_response.text = "{}"

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pyflow.tools.http.httpx.AsyncClient", return_value=mock_client):
            result = await tool.execute(
                tool_context=MagicMock(),
                url="https://example.com/api",
                headers="not valid json{{{",
            )

        assert result["status"] == 200
        # Invalid JSON headers should fall back to empty dict
        mock_client.request.assert_called_once()
        call_kwargs = mock_client.request.call_args[1]
        assert call_kwargs["headers"] == {}  # safe_json_parse returns default={}

    async def test_timeout_clamped(self):
        """Timeout values are clamped to [1, 300]."""
        tool = HttpTool()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({})
        mock_response.json.return_value = {}
        mock_response.text = "{}"

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pyflow.tools.http.httpx.AsyncClient", return_value=mock_client) as mock_cls:
            await tool.execute(
                tool_context=MagicMock(),
                url="https://example.com/api",
                timeout=0,
            )
            # Should be clamped to 1
            mock_cls.assert_called_once_with(timeout=1)

    def test_auto_registered(self):
        from pyflow.tools.base import get_registered_tools

        assert "http_request" in get_registered_tools()

    def test_name_and_description(self):
        assert HttpTool.name == "http_request"
        assert HttpTool.description
