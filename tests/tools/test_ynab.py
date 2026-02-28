from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from pyflow.tools.base import clear_secrets, set_secrets


class TestYnabToolBasics:
    def setup_method(self):
        clear_secrets()
        set_secrets({"ynab_api_token": "test-token-123"})

    def teardown_method(self):
        clear_secrets()

    def test_auto_registered(self):
        from pyflow.tools.ynab import YnabTool  # noqa: F401
        from pyflow.tools.base import get_registered_tools

        assert "ynab" in get_registered_tools()

    def test_name_and_description(self):
        from pyflow.tools.ynab import YnabTool

        assert YnabTool.name == "ynab"
        assert "YNAB" in YnabTool.description


class TestYnabToolMissingToken:
    def setup_method(self):
        clear_secrets()

    def teardown_method(self):
        clear_secrets()

    async def test_returns_error_when_no_token(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        result = await tool.execute(tool_context=MagicMock(), action="list_budgets")
        assert result["success"] is False
        assert "token" in result["error"].lower()


class TestYnabToolUnknownAction:
    def setup_method(self):
        clear_secrets()
        set_secrets({"ynab_api_token": "test-token"})

    def teardown_method(self):
        clear_secrets()

    async def test_unknown_action(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        result = await tool.execute(tool_context=MagicMock(), action="explode")
        assert result["success"] is False
        assert "Unknown action" in result["error"]


def _mock_ynab_response(status_code: int, json_body: dict):
    """Helper to create a mock httpx response for YNAB API calls."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = json_body
    mock_response.text = str(json_body)
    mock_response.raise_for_status = MagicMock()
    if status_code >= 400:
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock_response
        )
    return mock_response


def _mock_client(mock_response):
    """Helper to create a mock httpx.AsyncClient."""
    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestYnabToolBudgets:
    def setup_method(self):
        clear_secrets()
        set_secrets({"ynab_api_token": "test-token"})

    def teardown_method(self):
        clear_secrets()

    async def test_list_budgets(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"budgets": [{"id": "budget-1", "name": "My Budget"}]}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(tool_context=MagicMock(), action="list_budgets")

        assert result["success"] is True
        assert result["data"]["budgets"][0]["id"] == "budget-1"
        client.request.assert_called_once_with(
            method="GET",
            url="https://api.ynab.com/v1/budgets",
            headers={"Authorization": "Bearer test-token"},
            json=None,
            params=None,
        )

    async def test_get_budget(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"budget": {"id": "budget-1", "name": "My Budget"}}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(), action="get_budget", budget_id="budget-1"
            )

        assert result["success"] is True
        assert result["data"]["budget"]["id"] == "budget-1"

    async def test_get_budget_missing_budget_id(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        result = await tool.execute(tool_context=MagicMock(), action="get_budget")
        assert result["success"] is False
        assert "budget_id" in result["error"]


class TestYnabToolAccounts:
    def setup_method(self):
        clear_secrets()
        set_secrets({"ynab_api_token": "test-token"})

    def teardown_method(self):
        clear_secrets()

    async def test_list_accounts(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"accounts": [{"id": "acc-1", "name": "Checking"}]}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(), action="list_accounts", budget_id="budget-1"
            )

        assert result["success"] is True
        assert result["data"]["accounts"][0]["name"] == "Checking"

    async def test_get_account(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"account": {"id": "acc-1", "name": "Checking"}}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(),
                action="get_account",
                budget_id="budget-1",
                account_id="acc-1",
            )

        assert result["success"] is True
        assert result["data"]["account"]["id"] == "acc-1"
