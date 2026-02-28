from __future__ import annotations

from typing import Any, ClassVar, Literal

import httpx
from google.adk.tools.tool_context import ToolContext
from pydantic import Field

from pyflow.models.tool import ToolConfig, ToolResponse
from pyflow.tools.base import BasePlatformTool


class HttpToolConfig(ToolConfig):
    """Configuration for HTTP requests."""

    url: str
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = "GET"
    headers: dict[str, str] = {}
    body: Any = None
    timeout: int = Field(default=30, ge=1, le=300)


class HttpToolResponse(ToolResponse):
    """Response from an HTTP request."""

    status: int
    headers: dict[str, str]
    body: Any


class HttpTool(BasePlatformTool):
    """Make HTTP requests to external APIs."""

    name: ClassVar[str] = "http_request"
    description: ClassVar[str] = "Make HTTP requests to external APIs and services"
    config_model: ClassVar[type[ToolConfig]] = HttpToolConfig
    response_model: ClassVar[type[ToolResponse]] = HttpToolResponse

    async def execute(
        self, config: HttpToolConfig, tool_context: ToolContext | None = None
    ) -> HttpToolResponse:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=config.method,
                    url=config.url,
                    headers=config.headers,
                    json=config.body if config.body is not None else None,
                    timeout=config.timeout,
                )
            try:
                body = response.json()
            except Exception:
                body = response.text
            return HttpToolResponse(
                status=response.status_code,
                headers=dict(response.headers),
                body=body,
            )
        except httpx.HTTPError as exc:
            return HttpToolResponse(
                status=0,
                headers={},
                body={"error": str(exc)},
            )
