from __future__ import annotations

from unittest.mock import MagicMock

from agents.budget_analyst.predicates import read_only


class TestReadOnlyPredicate:
    def test_allows_get_operations(self):
        tool = MagicMock()
        tool.name = "get_budgets"
        assert read_only(tool) is True

    def test_allows_get_transactions(self):
        tool = MagicMock()
        tool.name = "get_transactions_by_month"
        assert read_only(tool) is True

    def test_blocks_post_operations(self):
        tool = MagicMock()
        tool.name = "create_transaction"
        assert read_only(tool) is False

    def test_blocks_update_operations(self):
        tool = MagicMock()
        tool.name = "update_category"
        assert read_only(tool) is False

    def test_blocks_delete_operations(self):
        tool = MagicMock()
        tool.name = "delete_transaction"
        assert read_only(tool) is False

    def test_accepts_readonly_context(self):
        """Predicate follows ADK ToolPredicate protocol with optional context."""
        tool = MagicMock()
        tool.name = "get_accounts"
        ctx = MagicMock()
        assert read_only(tool, readonly_context=ctx) is True
