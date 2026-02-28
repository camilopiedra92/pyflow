from __future__ import annotations

import httpx
from google.adk.tools.tool_context import ToolContext

from pyflow.tools.base import BasePlatformTool, get_secret
from pyflow.tools.parsing import safe_json_parse

YNAB_BASE_URL = "https://api.ynab.com/v1"


class YnabTool(BasePlatformTool):
    name = "ynab"
    description = (
        "Interact with YNAB (You Need A Budget) API. "
        "Manage budgets, accounts, categories, payees, and transactions."
    )

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
            action: The operation (list_budgets, get_budget, list_accounts,
                get_account, list_categories, get_category, update_category,
                list_payees, update_payee, list_transactions, get_transaction,
                create_transaction, update_transaction, list_scheduled_transactions,
                create_scheduled_transaction, update_scheduled_transaction,
                delete_scheduled_transaction, list_months, get_month_category).
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
            return {
                "success": False,
                "error": (
                    "YNAB API token not configured. "
                    "Set 'ynab_api_token' in platform secrets."
                ),
            }

        route = self._resolve_route(
            action,
            budget_id,
            account_id,
            category_id,
            payee_id,
            transaction_id,
            scheduled_transaction_id,
            month,
        )
        if route is None:
            return {"success": False, "error": f"Unknown action: {action}"}

        method, path, required_error = route
        if required_error:
            return {"success": False, "error": required_error}

        url = f"{YNAB_BASE_URL}{path}"
        params: dict[str, str] = {}
        if since_date and action in ("list_transactions",):
            params["since_date"] = since_date
        if type_filter and action in ("list_transactions",):
            params["type"] = type_filter

        headers = {"Authorization": f"Bearer {token}"}
        parsed_data = (
            safe_json_parse(data) if method in ("POST", "PUT", "PATCH") else None
        )

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
            return (
                f"Missing required parameter(s): {', '.join(missing)}"
                if missing
                else ""
            )

        routes: dict[str, tuple[str, str, str]] = {
            "list_budgets": ("GET", "/budgets", ""),
            "get_budget": (
                "GET",
                f"/budgets/{budget_id}",
                require(("budget_id", budget_id)),
            ),
            "list_accounts": (
                "GET",
                f"/budgets/{budget_id}/accounts",
                require(("budget_id", budget_id)),
            ),
            "get_account": (
                "GET",
                f"/budgets/{budget_id}/accounts/{account_id}",
                require(("budget_id", budget_id), ("account_id", account_id)),
            ),
            "list_categories": (
                "GET",
                f"/budgets/{budget_id}/categories",
                require(("budget_id", budget_id)),
            ),
            "get_category": (
                "GET",
                f"/budgets/{budget_id}/categories/{category_id}",
                require(("budget_id", budget_id), ("category_id", category_id)),
            ),
            "update_category": (
                "PATCH",
                f"/budgets/{budget_id}/categories/{category_id}",
                require(("budget_id", budget_id), ("category_id", category_id)),
            ),
            "list_payees": (
                "GET",
                f"/budgets/{budget_id}/payees",
                require(("budget_id", budget_id)),
            ),
            "update_payee": (
                "PATCH",
                f"/budgets/{budget_id}/payees/{payee_id}",
                require(("budget_id", budget_id), ("payee_id", payee_id)),
            ),
            "list_transactions": (
                "GET",
                f"/budgets/{budget_id}/transactions",
                require(("budget_id", budget_id)),
            ),
            "get_transaction": (
                "GET",
                f"/budgets/{budget_id}/transactions/{transaction_id}",
                require(
                    ("budget_id", budget_id),
                    ("transaction_id", transaction_id),
                ),
            ),
            "create_transaction": (
                "POST",
                f"/budgets/{budget_id}/transactions",
                require(("budget_id", budget_id)),
            ),
            "update_transaction": (
                "PATCH",
                f"/budgets/{budget_id}/transactions",
                require(("budget_id", budget_id)),
            ),
            "list_scheduled_transactions": (
                "GET",
                f"/budgets/{budget_id}/scheduled_transactions",
                require(("budget_id", budget_id)),
            ),
            "create_scheduled_transaction": (
                "POST",
                f"/budgets/{budget_id}/scheduled_transactions",
                require(("budget_id", budget_id)),
            ),
            "update_scheduled_transaction": (
                "PUT",
                f"/budgets/{budget_id}/scheduled_transactions/{scheduled_transaction_id}",
                require(
                    ("budget_id", budget_id),
                    ("scheduled_transaction_id", scheduled_transaction_id),
                ),
            ),
            "delete_scheduled_transaction": (
                "DELETE",
                f"/budgets/{budget_id}/scheduled_transactions/{scheduled_transaction_id}",
                require(
                    ("budget_id", budget_id),
                    ("scheduled_transaction_id", scheduled_transaction_id),
                ),
            ),
            "list_months": (
                "GET",
                f"/budgets/{budget_id}/months",
                require(("budget_id", budget_id)),
            ),
            "get_month_category": (
                "GET",
                f"/budgets/{budget_id}/months/{month}/categories/{category_id}",
                require(
                    ("budget_id", budget_id),
                    ("month", month),
                    ("category_id", category_id),
                ),
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
                    return {
                        "success": False,
                        "error": (
                            f"YNAB API error ({resp.status_code}): {error_detail}"
                        ),
                    }
                return {"success": True, "data": body.get("data", body)}
        except httpx.HTTPError as exc:
            return {"success": False, "error": str(exc)}
