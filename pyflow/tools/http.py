from __future__ import annotations

import httpx
from google.adk.tools.tool_context import ToolContext

from pyflow.tools.base import BasePlatformTool
from pyflow.tools.parsing import safe_json_parse
from pyflow.tools.security import is_private_url


class HttpTool(BasePlatformTool):
    name = "http_request"
    description = (
        "Make HTTP requests to external APIs. "
        "Pass headers and body as JSON strings."
    )

    async def execute(
        self,
        tool_context: ToolContext,
        url: str,
        method: str = "GET",
        headers: str = "{}",
        body: str = "",
        timeout: int = 30,
        allow_private: bool = False,
    ) -> dict:
        """Make an HTTP request.

        Args:
            url: The URL to request.
            method: HTTP method (GET, POST, PUT, DELETE, PATCH).
            headers: JSON string of headers.
            body: JSON string of request body.
            timeout: Request timeout in seconds (1-300).
            allow_private: Allow requests to private network addresses.
        """
        if not allow_private and is_private_url(url):
            return {"status": 0, "error": "SSRF blocked: private/internal URL"}

        timeout = max(1, min(timeout, 300))
        parsed_headers = safe_json_parse(headers, default={})
        parsed_body = safe_json_parse(body)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=parsed_headers,
                    json=parsed_body if parsed_body is not None else None,
                )
                try:
                    resp_body = resp.json()
                except Exception:
                    resp_body = resp.text
                return {
                    "status": resp.status_code,
                    "headers": dict(resp.headers),
                    "body": resp_body,
                }
        except httpx.HTTPError as exc:
            return {"status": 0, "error": str(exc)}
