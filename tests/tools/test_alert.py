from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import ValidationError

from pyflow.tools.alert import AlertTool, AlertToolConfig, AlertToolResponse


class TestAlertToolConfig:
    def test_fields(self):
        config = AlertToolConfig(webhook_url="https://hooks.example.com/abc", message="alert!")
        assert config.webhook_url == "https://hooks.example.com/abc"
        assert config.message == "alert!"

    def test_webhook_url_required(self):
        with pytest.raises(ValidationError):
            AlertToolConfig(message="test")

    def test_message_required(self):
        with pytest.raises(ValidationError):
            AlertToolConfig(webhook_url="https://hooks.example.com/abc")


class TestAlertToolResponse:
    def test_fields(self):
        resp = AlertToolResponse(status=200, sent=True)
        assert resp.status == 200
        assert resp.sent is True
        assert resp.error is None

    def test_with_error(self):
        resp = AlertToolResponse(status=0, sent=False, error="connection refused")
        assert resp.sent is False
        assert resp.error == "connection refused"


class TestAlertToolExecute:
    async def test_successful_post(self):
        tool = AlertTool()
        config = AlertToolConfig(
            webhook_url="https://hooks.example.com/abc",
            message="Server is down!",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.execute(config)

        assert isinstance(result, AlertToolResponse)
        assert result.status == 200
        assert result.sent is True
        assert result.error is None
        mock_client.post.assert_called_once_with(
            "https://hooks.example.com/abc",
            json={"message": "Server is down!"},
            timeout=30,
        )

    async def test_http_error(self):
        tool = AlertTool()
        config = AlertToolConfig(
            webhook_url="https://hooks.example.com/abc",
            message="test",
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.execute(config)

        assert result.sent is False
        assert result.status == 0
        assert "timeout" in result.error

    async def test_server_error_status(self):
        tool = AlertTool()
        config = AlertToolConfig(
            webhook_url="https://hooks.example.com/abc",
            message="test",
        )

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tool.execute(config)

        assert result.status == 500
        assert result.sent is True  # sent but server returned error

    def test_auto_registered(self):
        from pyflow.tools.base import get_registered_tools

        assert "alert" in get_registered_tools()
