from __future__ import annotations

import json
from typing import Any


def safe_json_parse(value: str | None, default: Any = None) -> Any:
    """Parse JSON string safely, return default on failure."""
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default
