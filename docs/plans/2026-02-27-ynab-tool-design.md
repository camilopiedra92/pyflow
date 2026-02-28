# YNAB Tool Design

## Overview

Add a `YnabTool` to PyFlow that provides full CRUD access to the YNAB (You Need A Budget) API v1. Single tool with action-based dispatch, following the `StorageTool` pattern.

## Tool Structure

Single `YnabTool` class in `pyflow/tools/ynab.py` with `name = "ynab"`. The `action` parameter selects the operation.

### Actions

| Action | HTTP | Endpoint | Description |
|---|---|---|---|
| `list_budgets` | GET | `/budgets` | List all budgets |
| `get_budget` | GET | `/budgets/{budget_id}` | Get budget details |
| `list_accounts` | GET | `/budgets/{id}/accounts` | List accounts in a budget |
| `get_account` | GET | `/budgets/{id}/accounts/{id}` | Get account details |
| `list_categories` | GET | `/budgets/{id}/categories` | List categories |
| `get_category` | GET | `/budgets/{id}/categories/{id}` | Get category details |
| `update_category` | PATCH | `/budgets/{id}/categories/{id}` | Update category |
| `list_payees` | GET | `/budgets/{id}/payees` | List payees |
| `update_payee` | PATCH | `/budgets/{id}/payees/{id}` | Update payee name |
| `list_transactions` | GET | `/budgets/{id}/transactions` | List transactions |
| `get_transaction` | GET | `/budgets/{id}/transactions/{id}` | Get transaction details |
| `create_transaction` | POST | `/budgets/{id}/transactions` | Create transaction(s) |
| `update_transaction` | PATCH | `/budgets/{id}/transactions` | Update transaction(s) |
| `list_scheduled_transactions` | GET | `/budgets/{id}/scheduled_transactions` | List scheduled transactions |
| `create_scheduled_transaction` | POST | `/budgets/{id}/scheduled_transactions` | Create scheduled transaction |
| `update_scheduled_transaction` | PUT | `/budgets/{id}/scheduled_transactions/{id}` | Update scheduled transaction |
| `delete_scheduled_transaction` | DELETE | `/budgets/{id}/scheduled_transactions/{id}` | Delete scheduled transaction |
| `list_months` | GET | `/budgets/{id}/months` | List budget months |
| `get_month_category` | GET | `/budgets/{id}/months/{month}/categories/{id}` | Get category for a month |

### Execute Signature

```python
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
```

## Secrets Architecture

Module-level secret store in `pyflow/tools/base.py`, following the same pattern as `_TOOL_AUTO_REGISTRY`:

```python
_PLATFORM_SECRETS: dict[str, str] = {}

def set_secrets(secrets: dict[str, str]) -> None:
    _PLATFORM_SECRETS.update(secrets)

def get_secret(name: str) -> str | None:
    return _PLATFORM_SECRETS.get(name)
```

`PlatformConfig` gets a new field:

```python
class PlatformConfig(BaseModel):
    # ... existing fields ...
    secrets: dict[str, str] = Field(default_factory=dict)
```

Platform boot calls `set_secrets(config.secrets)` during initialization. The YNAB tool reads its token via `get_secret("ynab_api_token")`.

## HTTP Client

Uses `httpx.AsyncClient` (already a project dependency). Base URL: `https://api.ynab.com/v1`. Auth header: `Authorization: Bearer {token}`.

## Error Handling

Consistent return format:
- Success: `{"success": True, "data": {...}}`
- Error: `{"success": False, "error": "message"}`

Handles: 401 (bad token), 404 (not found), 400 (validation), 429 (rate limit).

## Files

| File | Change |
|---|---|
| `pyflow/tools/ynab.py` | New — YnabTool implementation |
| `pyflow/tools/base.py` | Add secret store (`_PLATFORM_SECRETS`, `set_secrets`, `get_secret`) |
| `pyflow/tools/__init__.py` | Add YnabTool import for auto-registration |
| `pyflow/models/platform.py` | Add `secrets` field to PlatformConfig |
| `pyflow/platform/app.py` | Call `set_secrets()` during platform boot |
| `tests/test_tools/test_ynab.py` | New — tests with httpx mocks |
| `tests/test_tools/test_base.py` | Tests for secret store functions |
| `tests/test_models/test_platform.py` | Tests for secrets field |
