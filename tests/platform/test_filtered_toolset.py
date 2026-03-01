from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pyflow.platform.filtered_toolset import FilteredToolset


def _make_tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


@pytest.fixture
def inner_toolset():
    toolset = AsyncMock()
    toolset.get_tools = AsyncMock(
        return_value=[
            _make_tool("get_budgets"),
            _make_tool("get_user"),
            _make_tool("create_budget"),
            _make_tool("list_accounts"),
            _make_tool("delete_transaction"),
        ]
    )
    toolset.get_auth_config = MagicMock(return_value=MagicMock())
    return toolset


class TestFilteredToolset:
    async def test_filters_by_exact_name(self, inner_toolset):
        fs = FilteredToolset(inner_toolset, ["get_budgets"])
        tools = await fs.get_tools()
        assert [t.name for t in tools] == ["get_budgets"]

    async def test_filters_by_glob_prefix(self, inner_toolset):
        fs = FilteredToolset(inner_toolset, ["get*"])
        tools = await fs.get_tools()
        assert sorted(t.name for t in tools) == ["get_budgets", "get_user"]

    async def test_filters_multiple_patterns(self, inner_toolset):
        fs = FilteredToolset(inner_toolset, ["get*", "list*"])
        tools = await fs.get_tools()
        assert sorted(t.name for t in tools) == ["get_budgets", "get_user", "list_accounts"]

    async def test_empty_patterns_matches_nothing(self, inner_toolset):
        fs = FilteredToolset(inner_toolset, [])
        tools = await fs.get_tools()
        assert tools == []

    async def test_delegates_get_tools_to_inner(self, inner_toolset):
        fs = FilteredToolset(inner_toolset, ["get*"])
        await fs.get_tools()
        inner_toolset.get_tools.assert_awaited_once()

    def test_delegates_auth_config(self, inner_toolset):
        fs = FilteredToolset(inner_toolset, ["get*"])
        result = fs.get_auth_config()
        assert result is inner_toolset.get_auth_config.return_value

    async def test_close_does_not_close_inner(self, inner_toolset):
        fs = FilteredToolset(inner_toolset, ["get*"])
        await fs.close()
        inner_toolset.close.assert_not_awaited()

    async def test_readonly_context_forwarded(self, inner_toolset):
        ctx = MagicMock()
        fs = FilteredToolset(inner_toolset, ["get*"])
        await fs.get_tools(readonly_context=ctx)
        inner_toolset.get_tools.assert_awaited_once_with(ctx)
