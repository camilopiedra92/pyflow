from __future__ import annotations

import httpx
from google.adk.tools.tool_context import ToolContext

from pyflow.tools.base import BasePlatformTool
from pyflow.tools.security import is_private_url


class AlertTool(BasePlatformTool):
    name = "alert"
    description = "Send an alert message to a webhook URL."

    async def execute(
        self,
        tool_context: ToolContext,
        webhook_url: str,
        message: str,
    ) -> dict:
        """Send an alert to a webhook.

        Args:
            webhook_url: The webhook URL to POST the alert to.
            message: The alert message to send.
        """
        if is_private_url(webhook_url):
            return {"status": 0, "sent": False, "error": "SSRF blocked: private/internal URL"}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(webhook_url, json={"message": message})
                return {"status": resp.status_code, "sent": True, "error": None}
        except httpx.HTTPError as exc:
            return {"status": 0, "sent": False, "error": str(exc)}
