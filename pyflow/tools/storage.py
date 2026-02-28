from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar, Literal

from google.adk.tools.tool_context import ToolContext

from pyflow.models.tool import ToolConfig, ToolResponse
from pyflow.tools.base import BasePlatformTool


class StorageToolConfig(ToolConfig):
    """Configuration for file storage operations."""

    path: str
    action: Literal["read", "write", "append"] = "read"
    data: Any = None


class StorageToolResponse(ToolResponse):
    """Response from a storage operation."""

    content: str | None = None
    success: bool = True


class StorageTool(BasePlatformTool):
    """Read, write, and append to local files."""

    name: ClassVar[str] = "storage"
    description: ClassVar[str] = "Read, write, and append data to local files"
    config_model: ClassVar[type[ToolConfig]] = StorageToolConfig
    response_model: ClassVar[type[ToolResponse]] = StorageToolResponse

    async def execute(
        self, config: StorageToolConfig, tool_context: ToolContext | None = None
    ) -> StorageToolResponse:
        filepath = Path(config.path)

        if config.action == "read":
            return self._read(filepath)
        elif config.action == "write":
            return self._write(filepath, config.data)
        elif config.action == "append":
            return self._append(filepath, config.data)
        return StorageToolResponse(success=False)

    @staticmethod
    def _read(filepath: Path) -> StorageToolResponse:
        try:
            content = filepath.read_text(encoding="utf-8")
            return StorageToolResponse(content=content, success=True)
        except FileNotFoundError:
            return StorageToolResponse(content=None, success=False)

    @staticmethod
    def _write(filepath: Path, data: Any) -> StorageToolResponse:
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            text = json.dumps(data) if not isinstance(data, str) else data
            filepath.write_text(text, encoding="utf-8")
            return StorageToolResponse(success=True)
        except Exception:
            return StorageToolResponse(success=False)

    @staticmethod
    def _append(filepath: Path, data: Any) -> StorageToolResponse:
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            text = json.dumps(data) if not isinstance(data, str) else data
            with filepath.open("a", encoding="utf-8") as f:
                f.write(text)
            return StorageToolResponse(success=True)
        except Exception:
            return StorageToolResponse(success=False)
