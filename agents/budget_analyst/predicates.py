"""ToolPredicate callables for the budget_analyst workflow.

These follow ADK's ToolPredicate protocol: (tool, readonly_context) -> bool.
Referenced by FQN in workflow.yaml tool_filter field.
"""

from __future__ import annotations


def read_only(tool, readonly_context=None) -> bool:
    """Only expose read operations (GET endpoints) from the YNAB API."""
    return tool.name.startswith("get_")
