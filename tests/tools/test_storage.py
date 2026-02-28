from __future__ import annotations

import json
from unittest.mock import MagicMock

from pyflow.tools.storage import StorageTool


class TestStorageToolExecute:
    async def test_write_and_read(self, tmp_path):
        tool = StorageTool()
        filepath = str(tmp_path / "test.txt")

        # Write
        write_result = await tool.execute(
            tool_context=MagicMock(),
            path=filepath,
            action="write",
            data="hello world",
        )
        assert write_result["success"] is True
        assert write_result["content"] == "hello world"

        # Read
        read_result = await tool.execute(
            tool_context=MagicMock(),
            path=filepath,
            action="read",
        )
        assert read_result["success"] is True
        assert read_result["content"] == "hello world"

    async def test_append(self, tmp_path):
        tool = StorageTool()
        filepath = str(tmp_path / "append.txt")

        # Write initial
        await tool.execute(
            tool_context=MagicMock(), path=filepath, action="write", data="line1\n"
        )
        # Append
        await tool.execute(
            tool_context=MagicMock(), path=filepath, action="append", data="line2\n"
        )

        # Read
        result = await tool.execute(
            tool_context=MagicMock(), path=filepath, action="read"
        )
        assert result["content"] == "line1\nline2\n"

    async def test_read_nonexistent_file(self, tmp_path):
        tool = StorageTool()
        filepath = str(tmp_path / "nonexistent.txt")

        result = await tool.execute(
            tool_context=MagicMock(), path=filepath, action="read"
        )
        assert result["success"] is False
        assert result["content"] is None
        assert result["error"] == "File not found"

    async def test_write_creates_nested_dirs(self, tmp_path):
        tool = StorageTool()
        filepath = str(tmp_path / "sub" / "dir" / "file.txt")

        result = await tool.execute(
            tool_context=MagicMock(), path=filepath, action="write", data="nested"
        )
        assert result["success"] is True

        read_result = await tool.execute(
            tool_context=MagicMock(), path=filepath, action="read"
        )
        assert read_result["content"] == "nested"

    async def test_dict_data_as_json_string(self, tmp_path):
        tool = StorageTool()
        filepath = str(tmp_path / "dict.json")

        data_str = json.dumps({"key": "value"})
        result = await tool.execute(
            tool_context=MagicMock(), path=filepath, action="write", data=data_str
        )
        assert result["success"] is True

        read_result = await tool.execute(
            tool_context=MagicMock(), path=filepath, action="read"
        )
        assert read_result["success"] is True
        parsed = json.loads(read_result["content"])
        assert parsed == {"key": "value"}

    async def test_unknown_action(self, tmp_path):
        tool = StorageTool()
        filepath = str(tmp_path / "test.txt")

        result = await tool.execute(
            tool_context=MagicMock(), path=filepath, action="delete"
        )
        assert result["success"] is False
        assert "Unknown action" in result["error"]

    def test_auto_registered(self):
        from pyflow.tools.base import get_registered_tools

        assert "storage" in get_registered_tools()
