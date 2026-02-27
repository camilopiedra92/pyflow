from __future__ import annotations

import json
from pathlib import Path

from pyflow.core.context import ExecutionContext
from pyflow.core.node import BaseNode
from pyflow.nodes.schemas import StorageConfig


class StorageNode(BaseNode[StorageConfig, object]):
    node_type = "storage"
    config_model = StorageConfig

    async def execute(self, config: dict | StorageConfig, context: ExecutionContext) -> object:
        if isinstance(config, StorageConfig):
            path = Path(config.path)
            action = config.action
            data = config.data
        else:
            path = Path(config["path"])
            action = config.get("action", "read")
            data = config.get("data")

        if action == "read":
            if not path.exists():
                return []
            return json.loads(path.read_text(encoding="utf-8"))

        if action == "write":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return data

        if action == "append":
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                existing = json.loads(path.read_text(encoding="utf-8"))
            else:
                existing = []
            existing.append(data)
            path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            return existing

        raise ValueError(f"Unknown storage action: '{action}'")
