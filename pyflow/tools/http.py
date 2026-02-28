from __future__ import annotations

import ipaddress
from typing import Any, ClassVar, Literal
from urllib.parse import urlparse

import httpx
from google.adk.tools.tool_context import ToolContext
from pydantic import Field

from pyflow.models.tool import ToolConfig, ToolResponse
from pyflow.tools.base import BasePlatformTool

# Hostnames that resolve to private/loopback addresses
_PRIVATE_HOSTNAMES = frozenset({"localhost"})


def _is_private_url(url: str) -> bool:
    """Check if a URL targets a private or internal network address."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        # Check well-known private hostnames
        if hostname.lower() in _PRIVATE_HOSTNAMES:
            return True

        # Strip IPv6 brackets if present
        clean = hostname.strip("[]")

        # Try parsing as IP address
        addr = ipaddress.ip_address(clean)
        return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved
    except (ValueError, TypeError):
        # Not an IP — assume it's a public hostname
        return False


class HttpToolConfig(ToolConfig):
    """Configuration for HTTP requests."""

    url: str
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = "GET"
    headers: dict[str, str] = {}
    body: Any = None
    timeout: int = Field(default=30, ge=1, le=300)
    allow_private: bool = Field(
        default=False,
        description="Allow requests to private/internal network addresses (SSRF protection bypass)",
    )


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
        if not config.allow_private and _is_private_url(config.url):
            return HttpToolResponse(
                status=0,
                headers={},
                body={"error": "Request blocked: URL targets a private/internal network address"},
            )
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
