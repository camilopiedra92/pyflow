from __future__ import annotations

from typing import ClassVar

import httpx
from google.adk.tools.tool_context import ToolContext

from pyflow.models.tool import ToolConfig, ToolResponse
from pyflow.tools.base import BasePlatformTool


class AlertToolConfig(ToolConfig):
    """Configuration for sending webhook alerts."""

    webhook_url: str
    message: str


class AlertToolResponse(ToolResponse):
    """Response from an alert operation."""

    status: int
    sent: bool
    error: str | None = None


class AlertTool(BasePlatformTool):
    """Send alert messages to webhook endpoints."""

    name: ClassVar[str] = "alert"
    description: ClassVar[str] = "Send alert messages to webhook URLs"
    config_model: ClassVar[type[ToolConfig]] = AlertToolConfig
    response_model: ClassVar[type[ToolResponse]] = AlertToolResponse

    async def execute(
        self, config: AlertToolConfig, tool_context: ToolContext | None = None
    ) -> AlertToolResponse:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config.webhook_url,
                    json={"message": config.message},
                    timeout=30,
                )
            return AlertToolResponse(
                status=response.status_code,
                sent=True,
            )
        except httpx.HTTPError as exc:
            return AlertToolResponse(
                status=0,
                sent=False,
                error=str(exc),
            )
