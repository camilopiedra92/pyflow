from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import ValidationError

from pyflow.tools.http import HttpTool, HttpToolConfig, HttpToolResponse, _is_private_url


class TestHttpToolConfig:
    def test_defaults(self):
        config = HttpToolConfig(url="https://example.com")
        assert config.method == "GET"
        assert config.headers == {}
        assert config.body is None
        assert config.timeout == 30

    def test_all_fields(self):
        config = HttpToolConfig(
            url="https://api.example.com/data",
            method="POST",
            headers={"Authorization": "Bearer token"},
            body={"key": "value"},
            timeout=60,
        )
        assert config.url == "https://api.example.com/data"
        assert config.method == "POST"
        assert config.headers == {"Authorization": "Bearer token"}
        assert config.body == {"key": "value"}
        assert config.timeout == 60

    def test_invalid_method(self):
        with pytest.raises(ValidationError):
            HttpToolConfig(url="https://example.com", method="INVALID")

    def test_timeout_min(self):
        with pytest.raises(ValidationError):
            HttpToolConfig(url="https://example.com", timeout=0)

    def test_timeout_max(self):
        with pytest.raises(ValidationError):
            HttpToolConfig(url="https://example.com", timeout=301)

    def test_url_required(self):
        with pytest.raises(ValidationError):
            HttpToolConfig()

    def test_allow_private_default_false(self):
        config = HttpToolConfig(url="https://example.com")
        assert config.allow_private is False

    def test_allow_private_explicit(self):
        config = HttpToolConfig(url="http://localhost:8080", allow_private=True)
        assert config.allow_private is True


class TestSSRFProtection:
    """Test that private/internal network URLs are blocked by default."""

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/admin",
        "http://localhost/secret",
        "http://localhost:8080/api",
        "http://10.0.0.1/internal",
        "http://10.255.255.255/data",
        "http://172.16.0.1/data",
        "http://172.31.255.255/data",
        "http://192.168.1.1/router",
        "http://192.168.0.100:3000/api",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/ipv6-loopback",
        "http://0.0.0.0/zero",
    ])
    def test_private_url_detected(self, url):
        assert _is_private_url(url) is True

    @pytest.mark.parametrize("url", [
        "https://api.example.com/data",
        "https://8.8.8.8/dns",
        "https://httpbin.org/get",
        "http://93.184.216.34/public",
    ])
    def test_public_url_allowed(self, url):
        assert _is_private_url(url) is False

    async def test_ssrf_blocked_by_default(self):
        tool = HttpTool()
        config = HttpToolConfig(url="http://169.254.169.254/latest/meta-data/")
        result = await tool.execute(config)
        assert result.status == 0
        assert "blocked" in str(result.body).lower() or "private" in str(result.body).lower()

    async def test_ssrf_allowed_when_configured(self):
        tool = HttpTool()
        config = HttpToolConfig(url="http://localhost:8080/api", allow_private=True)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({"content-type": "application/json"})
        mock_response.json.return_value = {"local": True}
        mock_response.text = '{"local": true}'

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.execute(config)

        assert result.status == 200


class TestHttpToolResponse:
    def test_fields(self):
        resp = HttpToolResponse(status=200, headers={"content-type": "application/json"}, body={"ok": True})
        assert resp.status == 200
        assert resp.headers == {"content-type": "application/json"}
        assert resp.body == {"ok": True}


class TestHttpToolExecute:
    async def test_get_request(self):
        tool = HttpTool()
        config = HttpToolConfig(url="https://example.com/api")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({"content-type": "application/json"})
        mock_response.json.return_value = {"data": "test"}
        mock_response.text = '{"data": "test"}'

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.execute(config)

        assert isinstance(result, HttpToolResponse)
        assert result.status == 200
        mock_client.request.assert_called_once()

    async def test_post_with_body(self):
        tool = HttpTool()
        config = HttpToolConfig(
            url="https://example.com/api",
            method="POST",
            body={"key": "value"},
            headers={"Content-Type": "application/json"},
        )

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = httpx.Headers({"content-type": "application/json"})
        mock_response.json.return_value = {"created": True}
        mock_response.text = '{"created": true}'

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.execute(config)

        assert result.status == 201

    async def test_http_error_handled(self):
        tool = HttpTool()
        config = HttpToolConfig(url="https://example.com/fail")

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=httpx.HTTPError("connection failed"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.execute(config)

        assert result.status == 0
        assert "connection failed" in str(result.body)

    def test_auto_registered(self):
        from pyflow.tools.base import get_registered_tools

        assert "http_request" in get_registered_tools()

    def test_name_and_description(self):
        assert HttpTool.name == "http_request"
        assert HttpTool.description
