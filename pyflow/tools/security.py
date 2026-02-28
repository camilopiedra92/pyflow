from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


def is_private_url(url: str) -> bool:
    """Check if URL points to a private/internal network address."""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    if hostname in ("localhost", ""):
        return True

    clean = hostname.strip("[]")

    try:
        addr = ipaddress.ip_address(clean)
        return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved
    except ValueError:
        return False
