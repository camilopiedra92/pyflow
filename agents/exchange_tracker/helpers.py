from __future__ import annotations

import json


def parse_currency_request(parsed_input: str = "") -> dict:
    """Parse LLM JSON output into structured currency request fields."""
    try:
        data = json.loads(parsed_input) if isinstance(parsed_input, str) else parsed_input
    except (json.JSONDecodeError, TypeError):
        data = {}
    return {
        "base": data.get("base", "USD"),
        "target": data.get("target", "EUR"),
        "threshold": data.get("threshold"),
    }
