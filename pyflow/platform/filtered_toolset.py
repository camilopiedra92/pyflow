from __future__ import annotations

from fnmatch import fnmatch
from typing import TYPE_CHECKING

from google.adk.tools.base_toolset import BaseToolset

if TYPE_CHECKING:
    from google.adk.auth.auth_config import AuthConfig
    from google.adk.tools.base_tool import BaseTool
    from google.adk.tools.base_toolset import ReadonlyContext


class FilteredToolset(BaseToolset):
    """Wraps an existing toolset and exposes only tools matching fnmatch glob patterns.

    Used for per-agent filtering of shared OpenAPI toolsets. The inner toolset is
    shared across agents and should NOT be closed by this wrapper.

    Example YAML::

        tools:
          - ynab: ["get*"]      # only GET operations
          - stripe: ["list*", "get*"]
    """

    def __init__(self, inner: BaseToolset, patterns: list[str]) -> None:
        super().__init__()
        self._inner = inner
        self._patterns = patterns

    async def get_tools(
        self,
        readonly_context: ReadonlyContext | None = None,
    ) -> list[BaseTool]:
        all_tools = await self._inner.get_tools(readonly_context)
        return [t for t in all_tools if self._matches(t.name)]

    def _matches(self, name: str) -> bool:
        return any(fnmatch(name, p) for p in self._patterns)

    async def close(self) -> None:
        pass  # inner is shared, don't close

    def get_auth_config(self) -> AuthConfig | None:
        return self._inner.get_auth_config()
