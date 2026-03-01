from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from pyflow.tools.alert import AlertTool


class TestAlertToolExecute:
    async def test_successful_post(self):
        tool = AlertTool()

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pyflow.tools.alert.httpx.AsyncClient", return_value=mock_client):
            result = await tool.execute(
                tool_context=MagicMock(),
                webhook_url="https://hooks.example.com/abc",
                message="Server is down!",
            )

        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert result["status_code"] == 200
        assert result["sent"] is True
        assert result["error"] is None
        mock_client.post.assert_called_once_with(
            "https://hooks.example.com/abc",
            json={"message": "Server is down!"},
        )

    async def test_ssrf_blocked(self):
        tool = AlertTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            webhook_url="http://169.254.169.254/latest/",
            message="test",
        )
        assert result["status"] == "error"
        assert result["status_code"] == 0
        assert result["sent"] is False
        assert "SSRF blocked" in result["error"]

    async def test_ssrf_blocked_localhost(self):
        tool = AlertTool()
        result = await tool.execute(
            tool_context=MagicMock(),
            webhook_url="http://localhost:8080/webhook",
            message="test",
        )
        assert result["status"] == "error"
        assert result["sent"] is False
        assert "SSRF blocked" in result["error"]

    async def test_http_error(self):
        tool = AlertTool()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pyflow.tools.alert.httpx.AsyncClient", return_value=mock_client):
            result = await tool.execute(
                tool_context=MagicMock(),
                webhook_url="https://hooks.example.com/abc",
                message="test",
            )

        assert result["status"] == "error"
        assert result["sent"] is False
        assert result["status_code"] == 0
        assert "timeout" in result["error"]

    async def test_server_error_status(self):
        tool = AlertTool()

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pyflow.tools.alert.httpx.AsyncClient", return_value=mock_client):
            result = await tool.execute(
                tool_context=MagicMock(),
                webhook_url="https://hooks.example.com/abc",
                message="test",
            )

        assert result["status"] == "success"
        assert result["status_code"] == 500
        assert result["sent"] is True  # sent but server returned error

    def test_auto_registered(self):
        from pyflow.tools.base import get_registered_tools

        assert "alert" in get_registered_tools()
