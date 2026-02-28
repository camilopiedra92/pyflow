# YNAB Tool Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `YnabTool` to PyFlow with full CRUD access to the YNAB API v1, plus a generic secrets store for platform tools.

**Architecture:** Single `YnabTool` class with action-based dispatch (like `StorageTool`). Module-level secret store in `base.py` (like `_TOOL_AUTO_REGISTRY`). Uses `httpx.AsyncClient` for HTTP. Platform boot injects secrets from `PlatformConfig.secrets`.

**Tech Stack:** Python 3.12, httpx, Pydantic v2, pytest + pytest-asyncio, unittest.mock

---

### Task 1: Secret Store in base.py

**Files:**
- Modify: `pyflow/tools/base.py`
- Test: `tests/tools/test_base.py`

**Step 1: Write the failing tests**

Add to `tests/tools/test_base.py`:

```python
from pyflow.tools.base import get_secret, set_secrets, clear_secrets


class TestSecretStore:
    def setup_method(self):
        clear_secrets()

    def teardown_method(self):
        clear_secrets()

    def test_get_secret_returns_none_when_empty(self):
        assert get_secret("nonexistent") is None

    def test_set_and_get_secret(self):
        set_secrets({"my_key": "my_value"})
        assert get_secret("my_key") == "my_value"

    def test_set_secrets_merges(self):
        set_secrets({"a": "1"})
        set_secrets({"b": "2"})
        assert get_secret("a") == "1"
        assert get_secret("b") == "2"

    def test_clear_secrets_removes_all(self):
        set_secrets({"a": "1"})
        clear_secrets()
        assert get_secret("a") is None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_base.py::TestSecretStore -v`
Expected: FAIL — `ImportError: cannot import name 'get_secret'`

**Step 3: Write minimal implementation**

Add to `pyflow/tools/base.py` (after `_TOOL_AUTO_REGISTRY`):

```python
_PLATFORM_SECRETS: dict[str, str] = {}


def set_secrets(secrets: dict[str, str]) -> None:
    """Store secrets for platform tools."""
    _PLATFORM_SECRETS.update(secrets)


def get_secret(name: str) -> str | None:
    """Retrieve a secret by name. Returns None if not found."""
    return _PLATFORM_SECRETS.get(name)


def clear_secrets() -> None:
    """Clear all stored secrets. Used in tests."""
    _PLATFORM_SECRETS.clear()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_base.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add pyflow/tools/base.py tests/tools/test_base.py
git commit -m "feat: add module-level secret store to tools base"
```

---

### Task 2: PlatformConfig.secrets field

**Files:**
- Modify: `pyflow/models/platform.py`
- Test: `tests/models/test_platform.py`

**Step 1: Write the failing tests**

Add to `tests/models/test_platform.py`:

```python
class TestPlatformConfigSecrets:
    def test_secrets_default_empty(self):
        config = PlatformConfig()
        assert config.secrets == {}

    def test_secrets_accepts_dict(self):
        config = PlatformConfig(secrets={"ynab_api_token": "abc123"})
        assert config.secrets["ynab_api_token"] == "abc123"

    def test_secrets_multiple_keys(self):
        config = PlatformConfig(secrets={"key1": "val1", "key2": "val2"})
        assert len(config.secrets) == 2
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/models/test_platform.py::TestPlatformConfigSecrets -v`
Expected: FAIL — `ValidationError` (field not recognized)

**Step 3: Write minimal implementation**

In `pyflow/models/platform.py`, add `secrets` field:

```python
from pydantic import BaseModel, Field

class PlatformConfig(BaseModel):
    """Global platform configuration."""

    tools_dir: str = "pyflow/tools"
    workflows_dir: str = "workflows"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    secrets: dict[str, str] = Field(default_factory=dict)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/models/test_platform.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add pyflow/models/platform.py tests/models/test_platform.py
git commit -m "feat: add secrets field to PlatformConfig"
```

---

### Task 3: Platform boot injects secrets

**Files:**
- Modify: `pyflow/platform/app.py`
- Test: `tests/platform/test_app.py`

**Step 1: Write the failing test**

Add to `tests/platform/test_app.py`:

```python
from pyflow.tools.base import get_secret, clear_secrets


class TestBootInjectsSecrets:
    def setup_method(self):
        clear_secrets()

    def teardown_method(self):
        clear_secrets()

    async def test_boot_calls_set_secrets(self):
        config = PlatformConfig(secrets={"ynab_api_token": "test-token"})
        p = PyFlowPlatform(config=config)
        p.tools.discover = MagicMock()
        p.workflows.discover = MagicMock()
        p.workflows.hydrate = MagicMock()

        await p.boot()

        assert get_secret("ynab_api_token") == "test-token"

    async def test_boot_without_secrets_is_fine(self):
        p = PyFlowPlatform()
        p.tools.discover = MagicMock()
        p.workflows.discover = MagicMock()
        p.workflows.hydrate = MagicMock()

        await p.boot()

        assert get_secret("nonexistent") is None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/platform/test_app.py::TestBootInjectsSecrets -v`
Expected: FAIL — `get_secret("ynab_api_token")` returns `None`

**Step 3: Write minimal implementation**

In `pyflow/platform/app.py`, add the import and call in `boot()`:

```python
from pyflow.tools.base import set_secrets
```

Add at the start of `boot()`, before tool discovery:

```python
# 0. Inject secrets for platform tools
if self.config.secrets:
    set_secrets(self.config.secrets)
    log.info("secrets.loaded", count=len(self.config.secrets))
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/platform/test_app.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add pyflow/platform/app.py tests/platform/test_app.py
git commit -m "feat: inject platform secrets during boot"
```

---

### Task 4: YnabTool — core structure and read-only budget/account actions

**Files:**
- Create: `pyflow/tools/ynab.py`
- Test: `tests/tools/test_ynab.py`

**Step 1: Write the failing tests**

Create `tests/tools/test_ynab.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_ynab.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pyflow.tools.ynab'`

**Step 3: Write minimal implementation**

Create `pyflow/tools/ynab.py`:

```python
from __future__ import annotations

import httpx
from google.adk.tools.tool_context import ToolContext

from pyflow.tools.base import BasePlatformTool, get_secret
from pyflow.tools.parsing import safe_json_parse

YNAB_BASE_URL = "https://api.ynab.com/v1"


class YnabTool(BasePlatformTool):
    name = "ynab"
    description = "Interact with YNAB (You Need A Budget) API. Manage budgets, accounts, categories, payees, and transactions."

    async def execute(
        self,
        tool_context: ToolContext,
        action: str,
        budget_id: str = "",
        account_id: str = "",
        category_id: str = "",
        payee_id: str = "",
        transaction_id: str = "",
        scheduled_transaction_id: str = "",
        month: str = "",
        data: str = "{}",
        since_date: str = "",
        type_filter: str = "",
    ) -> dict:
        """Interact with YNAB API.

        Args:
            action: The operation to perform (e.g. list_budgets, create_transaction).
            budget_id: YNAB budget ID (required for most actions).
            account_id: YNAB account ID.
            category_id: YNAB category ID.
            payee_id: YNAB payee ID.
            transaction_id: YNAB transaction ID.
            scheduled_transaction_id: YNAB scheduled transaction ID.
            month: Budget month in YYYY-MM-DD format (first day of month).
            data: JSON string for create/update payloads.
            since_date: Filter transactions since this date (YYYY-MM-DD).
            type_filter: Filter transaction type (uncategorized, unapproved).
        """
        token = get_secret("ynab_api_token")
        if not token:
            return {"success": False, "error": "YNAB API token not configured. Set 'ynab_api_token' in platform secrets."}

        route = self._resolve_route(
            action, budget_id, account_id, category_id,
            payee_id, transaction_id, scheduled_transaction_id, month,
        )
        if route is None:
            return {"success": False, "error": f"Unknown action: {action}"}

        method, path, required_error = route
        if required_error:
            return {"success": False, "error": required_error}

        url = f"{YNAB_BASE_URL}{path}"
        params = {}
        if since_date and action in ("list_transactions",):
            params["since_date"] = since_date
        if type_filter and action in ("list_transactions",):
            params["type"] = type_filter

        headers = {"Authorization": f"Bearer {token}"}
        parsed_data = safe_json_parse(data) if method in ("POST", "PUT", "PATCH") else None

        return await self._request(method, url, headers, parsed_data, params)

    def _resolve_route(
        self,
        action: str,
        budget_id: str,
        account_id: str,
        category_id: str,
        payee_id: str,
        transaction_id: str,
        scheduled_transaction_id: str,
        month: str,
    ) -> tuple[str, str, str] | None:
        """Map action to (HTTP method, URL path, error_or_empty).

        Returns None if action is unknown.
        """
        def require(*fields: tuple[str, str]) -> str:
            missing = [name for name, val in fields if not val]
            return f"Missing required parameter(s): {', '.join(missing)}" if missing else ""

        routes: dict[str, tuple[str, str, str]] = {
            "list_budgets": ("GET", "/budgets", ""),
            "get_budget": (
                "GET", f"/budgets/{budget_id}",
                require(("budget_id", budget_id)),
            ),
            "list_accounts": (
                "GET", f"/budgets/{budget_id}/accounts",
                require(("budget_id", budget_id)),
            ),
            "get_account": (
                "GET", f"/budgets/{budget_id}/accounts/{account_id}",
                require(("budget_id", budget_id), ("account_id", account_id)),
            ),
            "list_categories": (
                "GET", f"/budgets/{budget_id}/categories",
                require(("budget_id", budget_id)),
            ),
            "get_category": (
                "GET", f"/budgets/{budget_id}/categories/{category_id}",
                require(("budget_id", budget_id), ("category_id", category_id)),
            ),
            "update_category": (
                "PATCH", f"/budgets/{budget_id}/categories/{category_id}",
                require(("budget_id", budget_id), ("category_id", category_id)),
            ),
            "list_payees": (
                "GET", f"/budgets/{budget_id}/payees",
                require(("budget_id", budget_id)),
            ),
            "update_payee": (
                "PATCH", f"/budgets/{budget_id}/payees/{payee_id}",
                require(("budget_id", budget_id), ("payee_id", payee_id)),
            ),
            "list_transactions": (
                "GET", f"/budgets/{budget_id}/transactions",
                require(("budget_id", budget_id)),
            ),
            "get_transaction": (
                "GET", f"/budgets/{budget_id}/transactions/{transaction_id}",
                require(("budget_id", budget_id), ("transaction_id", transaction_id)),
            ),
            "create_transaction": (
                "POST", f"/budgets/{budget_id}/transactions",
                require(("budget_id", budget_id)),
            ),
            "update_transaction": (
                "PATCH", f"/budgets/{budget_id}/transactions",
                require(("budget_id", budget_id)),
            ),
            "list_scheduled_transactions": (
                "GET", f"/budgets/{budget_id}/scheduled_transactions",
                require(("budget_id", budget_id)),
            ),
            "create_scheduled_transaction": (
                "POST", f"/budgets/{budget_id}/scheduled_transactions",
                require(("budget_id", budget_id)),
            ),
            "update_scheduled_transaction": (
                "PUT", f"/budgets/{budget_id}/scheduled_transactions/{scheduled_transaction_id}",
                require(("budget_id", budget_id), ("scheduled_transaction_id", scheduled_transaction_id)),
            ),
            "delete_scheduled_transaction": (
                "DELETE", f"/budgets/{budget_id}/scheduled_transactions/{scheduled_transaction_id}",
                require(("budget_id", budget_id), ("scheduled_transaction_id", scheduled_transaction_id)),
            ),
            "list_months": (
                "GET", f"/budgets/{budget_id}/months",
                require(("budget_id", budget_id)),
            ),
            "get_month_category": (
                "GET", f"/budgets/{budget_id}/months/{month}/categories/{category_id}",
                require(("budget_id", budget_id), ("month", month), ("category_id", category_id)),
            ),
        }
        return routes.get(action)

    async def _request(
        self,
        method: str,
        url: str,
        headers: dict,
        json_body: dict | None,
        params: dict | None = None,
    ) -> dict:
        """Make an HTTP request to the YNAB API."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_body,
                    params=params or None,
                )
                body = resp.json()
                if resp.status_code >= 400:
                    error_detail = body.get("error", {}).get("detail", resp.text)
                    return {"success": False, "error": f"YNAB API error ({resp.status_code}): {error_detail}"}
                return {"success": True, "data": body.get("data", body)}
        except httpx.HTTPError as exc:
            return {"success": False, "error": str(exc)}
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_ynab.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add pyflow/tools/ynab.py tests/tools/test_ynab.py
git commit -m "feat: add YnabTool with budget and account actions"
```

---

### Task 5: YnabTool — category, payee, and transaction actions

**Files:**
- Test: `tests/tools/test_ynab.py`

**Step 1: Write the failing tests**

Add to `tests/tools/test_ynab.py`:

```python
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
```

**Step 2: Run tests to verify they pass**

These should already pass because Task 4 implemented all 19 actions. Run:

Run: `pytest tests/tools/test_ynab.py -v`
Expected: ALL PASS (the routing was already implemented)

**Step 3: Commit**

```bash
git add tests/tools/test_ynab.py
git commit -m "test: add category, payee, and transaction tests for YnabTool"
```

---

### Task 6: YnabTool — scheduled transactions and months tests

**Files:**
- Test: `tests/tools/test_ynab.py`

**Step 1: Write tests**

Add to `tests/tools/test_ynab.py`:

```python
class TestYnabToolScheduledTransactions:
    def setup_method(self):
        clear_secrets()
        set_secrets({"ynab_api_token": "test-token"})

    def teardown_method(self):
        clear_secrets()

    async def test_list_scheduled_transactions(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"scheduled_transactions": [{"id": "st-1"}]}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(),
                action="list_scheduled_transactions",
                budget_id="b-1",
            )

        assert result["success"] is True

    async def test_create_scheduled_transaction(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"scheduled_transaction": {"id": "st-new"}}}
        mock_resp = _mock_ynab_response(201, body)
        client = _mock_client(mock_resp)

        import json
        st_data = json.dumps({"scheduled_transaction": {"amount": -10000, "frequency": "monthly"}})

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(),
                action="create_scheduled_transaction",
                budget_id="b-1",
                data=st_data,
            )

        assert result["success"] is True
        call_kwargs = client.request.call_args[1]
        assert call_kwargs["method"] == "POST"

    async def test_update_scheduled_transaction(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"scheduled_transaction": {"id": "st-1"}}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        import json
        update_data = json.dumps({"scheduled_transaction": {"amount": -20000}})

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(),
                action="update_scheduled_transaction",
                budget_id="b-1",
                scheduled_transaction_id="st-1",
                data=update_data,
            )

        assert result["success"] is True
        call_kwargs = client.request.call_args[1]
        assert call_kwargs["method"] == "PUT"

    async def test_delete_scheduled_transaction(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"scheduled_transaction": {"id": "st-1", "deleted": True}}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(),
                action="delete_scheduled_transaction",
                budget_id="b-1",
                scheduled_transaction_id="st-1",
            )

        assert result["success"] is True
        call_kwargs = client.request.call_args[1]
        assert call_kwargs["method"] == "DELETE"


class TestYnabToolMonths:
    def setup_method(self):
        clear_secrets()
        set_secrets({"ynab_api_token": "test-token"})

    def teardown_method(self):
        clear_secrets()

    async def test_list_months(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"months": [{"month": "2024-06-01"}]}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(), action="list_months", budget_id="b-1"
            )

        assert result["success"] is True

    async def test_get_month_category(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"data": {"category": {"id": "cat-1", "budgeted": 100000}}}
        mock_resp = _mock_ynab_response(200, body)
        client = _mock_client(mock_resp)

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(),
                action="get_month_category",
                budget_id="b-1",
                month="2024-06-01",
                category_id="cat-1",
            )

        assert result["success"] is True
        call_kwargs = client.request.call_args[1]
        assert "/months/2024-06-01/categories/cat-1" in call_kwargs["url"]


class TestYnabToolErrorHandling:
    def setup_method(self):
        clear_secrets()
        set_secrets({"ynab_api_token": "test-token"})

    def teardown_method(self):
        clear_secrets()

    async def test_api_401_error(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        body = {"error": {"id": "401", "name": "unauthorized", "detail": "Invalid token"}}
        mock_resp = _mock_ynab_response(401, body)
        client = _mock_client(mock_resp)

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(), action="list_budgets"
            )

        assert result["success"] is False
        assert "401" in result["error"]

    async def test_network_error(self):
        from pyflow.tools.ynab import YnabTool

        tool = YnabTool()
        client = AsyncMock()
        client.request = AsyncMock(side_effect=httpx.HTTPError("connection refused"))
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("pyflow.tools.ynab.httpx.AsyncClient", return_value=client):
            result = await tool.execute(
                tool_context=MagicMock(), action="list_budgets"
            )

        assert result["success"] is False
        assert "connection refused" in result["error"]
```

**Step 2: Run tests**

Run: `pytest tests/tools/test_ynab.py -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/tools/test_ynab.py
git commit -m "test: add scheduled transaction, month, and error handling tests for YnabTool"
```

---

### Task 7: Register YnabTool in __init__.py

**Files:**
- Modify: `pyflow/tools/__init__.py`
- Test: `tests/tools/test_base.py`

**Step 1: Write the failing test**

Add to the `TestGetRegisteredTools.test_includes_builtin_tools` test in `tests/tools/test_base.py`:

```python
assert "ynab" in tools
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_base.py::TestGetRegisteredTools::test_includes_builtin_tools -v`
Expected: FAIL — `AssertionError: assert 'ynab' in tools`

**Step 3: Write minimal implementation**

In `pyflow/tools/__init__.py`, add the import:

```python
from pyflow.tools.ynab import YnabTool  # noqa: F401
```

And add `"YnabTool"` to `__all__`.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_base.py -v`
Expected: ALL PASS

**Step 5: Run full test suite**

Run: `pytest -v`
Expected: ALL PASS (all 361+ tests)

**Step 6: Commit**

```bash
git add pyflow/tools/__init__.py tests/tools/test_base.py
git commit -m "feat: register YnabTool in tools package"
```
