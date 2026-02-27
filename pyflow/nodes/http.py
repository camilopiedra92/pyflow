from __future__ import annotations

import httpx

from pyflow.core.context import ExecutionContext
from pyflow.core.node import BaseNode


class HttpNode(BaseNode):
    node_type = "http"

    async def execute(self, config: dict, context: ExecutionContext) -> object:
        method = config.get("method", "GET").upper()
        url = config["url"]
        headers = config.get("headers", {})
        body = config.get("body")

        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, headers=headers, json=body)

        try:
            response_body = response.json()
        except Exception:
            response_body = response.text

        return {
            "status": response.status_code,
            "headers": dict(response.headers),
            "body": response_body,
        }
