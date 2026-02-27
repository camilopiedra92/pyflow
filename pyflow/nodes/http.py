from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from pyflow.core.context import ExecutionContext
from pyflow.core.node import BaseNode


_MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10 MB


class SSRFError(ValueError):
    """Raised when a URL targets a private/internal network."""


def _validate_url(url: str, *, allow_private: bool = False) -> None:
    """Validate that a URL does not target private/internal networks."""
    parsed = urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        raise SSRFError(f"Invalid URL: no hostname in '{url}'")

    if hostname in ("localhost", "0.0.0.0"):
        if not allow_private:
            raise SSRFError(f"Requests to '{hostname}' are blocked")
        return

    try:
        resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SSRFError(f"Cannot resolve hostname '{hostname}'") from exc

    if not allow_private:
        for _family, _type, _proto, _canonname, sockaddr in resolved:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise SSRFError(
                    f"Requests to private/internal address '{ip}' "
                    f"(resolved from '{hostname}') are blocked"
                )


class HttpNode(BaseNode):
    node_type = "http"

    async def execute(self, config: dict, context: ExecutionContext) -> object:
        method = config.get("method", "GET").upper()
        url = config["url"]
        headers = config.get("headers", {})
        body = config.get("body")
        timeout = config.get("timeout", 30)
        raise_for_status = config.get("raise_for_status", True)
        max_response_size = config.get("max_response_size", _MAX_RESPONSE_SIZE)
        allow_private = config.get("allow_private_networks", False)

        _validate_url(url, allow_private=allow_private)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method, url, headers=headers, json=body)

        if raise_for_status:
            response.raise_for_status()

        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > max_response_size:
            raise ValueError(
                f"Response size {content_length} exceeds limit of {max_response_size} bytes"
            )
        if len(response.content) > max_response_size:
            raise ValueError(
                f"Response size {len(response.content)} exceeds limit of "
                f"{max_response_size} bytes"
            )

        try:
            response_body = response.json()
        except Exception:
            response_body = response.text

        return {
            "status": response.status_code,
            "headers": dict(response.headers),
            "body": response_body,
        }
