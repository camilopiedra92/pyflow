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


class TestYnabToolCategories:
    def setup_method(self):
        clear_secrets()
        set_secrets({"ynab_api_token": "test-token"})

    def teardown_method(self):
        clear_secrets()

    async def test_list_categories(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"category_groups": [{"id": "cg-1", "categories": []}]}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(), action="list_categories", budget_id="b-1"
            )

        assert result["success"] is True
        assert "category_groups" in result["data"]

    async def test_update_category(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"category": {"id": "cat-1", "budgeted": 50000}}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        import json
        update_data = json.dumps({"category": {"budgeted": 50000}})

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(),
                action="update_category",
                budget_id="b-1",
                category_id="cat-1",
                data=update_data,
            )

        assert result["success"] is True
        client.request.assert_called_once()
        call_kwargs = client.request.call_args[1]
        assert call_kwargs["method"] == "PATCH"
        assert call_kwargs["json"] == {"category": {"budgeted": 50000}}


class TestYnabToolPayees:
    def setup_method(self):
        clear_secrets()
        set_secrets({"ynab_api_token": "test-token"})

    def teardown_method(self):
        clear_secrets()

    async def test_list_payees(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"payees": [{"id": "p-1", "name": "Amazon"}]}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(), action="list_payees", budget_id="b-1"
            )

        assert result["success"] is True
        assert result["data"]["payees"][0]["name"] == "Amazon"

    async def test_update_payee(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"payee": {"id": "p-1", "name": "Amazon Prime"}}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        import json
        update_data = json.dumps({"payee": {"name": "Amazon Prime"}})

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(),
                action="update_payee",
                budget_id="b-1",
                payee_id="p-1",
                data=update_data,
            )

        assert result["success"] is True
        call_kwargs = client.request.call_args[1]
        assert call_kwargs["method"] == "PATCH"


class TestYnabToolTransactions:
    def setup_method(self):
        clear_secrets()
        set_secrets({"ynab_api_token": "test-token"})

    def teardown_method(self):
        clear_secrets()

    async def test_list_transactions(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"transactions": [{"id": "t-1", "amount": -50000}]}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(), action="list_transactions", budget_id="b-1"
            )

        assert result["success"] is True
        assert result["data"]["transactions"][0]["id"] == "t-1"

    async def test_list_transactions_with_since_date(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"transactions": []}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(),
                action="list_transactions",
                budget_id="b-1",
                since_date="2024-01-01",
            )

        assert result["success"] is True
        call_kwargs = client.request.call_args[1]
        assert call_kwargs["params"] == {"since_date": "2024-01-01"}

    async def test_create_transaction(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"transaction": {"id": "t-new", "amount": -25000}}}
        mock_resp = _mock_ynab_response(201, body)
        client = _mock_client(mock_resp)

        import json
        txn_data = json.dumps({
            "transaction": {
                "account_id": "acc-1",
                "date": "2024-06-15",
                "amount": -25000,
                "payee_name": "Coffee Shop",
            }
        })

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(),
                action="create_transaction",
                budget_id="b-1",
                data=txn_data,
            )

        assert result["success"] is True
        call_kwargs = client.request.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["json"]["transaction"]["amount"] == -25000

    async def test_update_transaction(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"transaction": {"id": "t-1", "memo": "updated"}}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        import json
        update_data = json.dumps({"transaction": {"id": "t-1", "memo": "updated"}})

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(),
                action="update_transaction",
                budget_id="b-1",
                data=update_data,
            )

        assert result["success"] is True
        call_kwargs = client.request.call_args[1]
        assert call_kwargs["method"] == "PATCH"

    async def test_get_transaction(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"transaction": {"id": "t-1", "amount": -10000}}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(),
                action="get_transaction",
                budget_id="b-1",
                transaction_id="t-1",
            )

        assert result["success"] is True
        assert result["data"]["transaction"]["id"] == "t-1"
