from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pyflow.core.context import ExecutionContext


class BaseNode(ABC):
    node_type: ClassVar[str]

    @abstractmethod
    async def execute(self, config: dict, context: ExecutionContext) -> object:
        ...


class NodeRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, type[BaseNode]] = {}

    def register(self, node_cls: type[BaseNode]) -> None:
        name = node_cls.node_type
        if name in self._registry:
            raise ValueError(f"Node type '{name}' already registered")
        self._registry[name] = node_cls

    def get(self, node_type: str) -> type[BaseNode]:
        if node_type not in self._registry:
            raise KeyError(f"Unknown node type: '{node_type}'")
        return self._registry[node_type]

    def list_types(self) -> list[str]:
        return list(self._registry.keys())
