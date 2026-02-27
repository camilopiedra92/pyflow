from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class OnError(StrEnum):
    SKIP = "skip"
    STOP = "stop"
    RETRY = "retry"


class NodeDef(BaseModel):
    id: str
    type: str
    config: dict = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    when: str | None = None
    on_error: OnError = OnError.STOP
    retry: dict | None = None


class TriggerDef(BaseModel):
    type: str
    config: dict = Field(default_factory=dict)


class WorkflowDef(BaseModel):
    name: str
    description: str | None = None
    trigger: TriggerDef
    nodes: list[NodeDef]

    @field_validator("nodes")
    @classmethod
    def validate_unique_ids(cls, nodes: list[NodeDef]) -> list[NodeDef]:
        seen: set[str] = set()
        for node in nodes:
            if node.id in seen:
                raise ValueError(f"Duplicate node id: {node.id}")
            seen.add(node.id)
        return nodes
