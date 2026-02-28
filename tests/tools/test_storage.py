from __future__ import annotations

import pytest
from pydantic import ValidationError

from pyflow.tools.storage import StorageTool, StorageToolConfig, StorageToolResponse


class TestStorageToolConfig:
    def test_defaults(self):
        config = StorageToolConfig(path="/tmp/test.txt")
        assert config.action == "read"
        assert config.data is None

    def test_all_fields(self):
        config = StorageToolConfig(path="/tmp/test.txt", action="write", data="hello")
        assert config.path == "/tmp/test.txt"
        assert config.action == "write"
        assert config.data == "hello"

    def test_invalid_action(self):
        with pytest.raises(ValidationError):
            StorageToolConfig(path="/tmp/test.txt", action="delete")

    def test_path_required(self):
        with pytest.raises(ValidationError):
            StorageToolConfig()


class TestStorageToolResponse:
    def test_fields(self):
        resp = StorageToolResponse(content="hello", success=True)
        assert resp.content == "hello"
        assert resp.success is True

    def test_defaults(self):
        resp = StorageToolResponse()
        assert resp.content is None
        assert resp.success is True


class TestStorageToolExecute:
    async def test_write_and_read(self, tmp_path):
        tool = StorageTool()
        filepath = str(tmp_path / "test.txt")

        # Write
        write_config = StorageToolConfig(path=filepath, action="write", data="hello world")
        write_result = await tool.execute(write_config)
        assert write_result.success is True

        # Read
        read_config = StorageToolConfig(path=filepath, action="read")
        read_result = await tool.execute(read_config)
        assert read_result.success is True
        assert read_result.content == "hello world"

    async def test_append(self, tmp_path):
        tool = StorageTool()
        filepath = str(tmp_path / "append.txt")

        # Write initial
        await tool.execute(StorageToolConfig(path=filepath, action="write", data="line1\n"))
        # Append
        await tool.execute(StorageToolConfig(path=filepath, action="append", data="line2\n"))

        # Read
        result = await tool.execute(StorageToolConfig(path=filepath, action="read"))
        assert result.content == "line1\nline2\n"

    async def test_read_nonexistent(self, tmp_path):
        tool = StorageTool()
        filepath = str(tmp_path / "nonexistent.txt")

        result = await tool.execute(StorageToolConfig(path=filepath, action="read"))
        assert result.success is False
        assert result.content is None

    async def test_write_creates_parent_dirs(self, tmp_path):
        tool = StorageTool()
        filepath = str(tmp_path / "sub" / "dir" / "file.txt")

        result = await tool.execute(StorageToolConfig(path=filepath, action="write", data="nested"))
        assert result.success is True

        read_result = await tool.execute(StorageToolConfig(path=filepath, action="read"))
        assert read_result.content == "nested"

    async def test_write_dict_data(self, tmp_path):
        tool = StorageTool()
        filepath = str(tmp_path / "dict.json")

        result = await tool.execute(
            StorageToolConfig(path=filepath, action="write", data={"key": "value"})
        )
        assert result.success is True

        read_result = await tool.execute(StorageToolConfig(path=filepath, action="read"))
        assert read_result.success is True
        assert "key" in read_result.content

    def test_auto_registered(self):
        from pyflow.tools.base import get_registered_tools

        assert "storage" in get_registered_tools()
