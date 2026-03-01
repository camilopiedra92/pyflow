from __future__ import annotations

import json
from pathlib import Path

from google.adk.tools.tool_context import ToolContext

from pyflow.tools.base import BasePlatformTool
from pyflow.tools.parsing import safe_json_parse


class StorageTool(BasePlatformTool):
    name = "storage"
    description = "Read, write, or append data to local files."

    async def execute(
        self,
        tool_context: ToolContext,
        path: str,
        action: str = "read",
        data: str = "",
    ) -> dict:
        """Manage local file storage.

        Args:
            path: File path to read/write/append.
            action: One of 'read', 'write', 'append'.
            data: Data to write/append (JSON string for structured data, plain text otherwise).
        """
        file_path = Path(path)
        try:
            if action == "read":
                if not file_path.exists():
                    return {
                        "status": "error",
                        "content": None,
                        "error": "File not found",
                    }
                return {
                    "status": "success",
                    "content": file_path.read_text(encoding="utf-8"),
                    "error": None,
                }
            elif action == "write":
                file_path.parent.mkdir(parents=True, exist_ok=True)
                parsed = safe_json_parse(data)
                text = json.dumps(parsed) if parsed is not None else data
                file_path.write_text(text, encoding="utf-8")
                return {"status": "success", "content": text, "error": None}
            elif action == "append":
                file_path.parent.mkdir(parents=True, exist_ok=True)
                parsed = safe_json_parse(data)
                text = json.dumps(parsed) if parsed is not None else data
                with file_path.open("a", encoding="utf-8") as f:
                    f.write(text)
                return {"status": "success", "content": text, "error": None}
            else:
                return {
                    "status": "error",
                    "content": None,
                    "error": f"Unknown action: {action}",
                }
        except Exception as exc:
            return {"status": "error", "content": None, "error": str(exc)}
