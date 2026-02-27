from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, field_validator


class OnError(StrEnum):
    SKIP = "skip"
    STOP = "stop"
    RETRY = "retry"


class NodeDef(BaseModel):
    id: str
    type: str
    config: dict = {}
    depends_on: list[str] = []
    when: str | None = None
    on_error: OnError = OnError.STOP
    retry: dict | None = None


class TriggerDef(BaseModel):
    type: str
    config: dict = {}


class WorkflowDef(BaseModel):
    name: str
    description: str | None = None
    trigger: TriggerDef
    nodes: list[NodeDef]

    @field_validator("nodes")
    @classmethod
    def validate_unique_ids(cls, nodes: list[NodeDef]) -> list[NodeDef]:
        ids = [n.id for n in nodes]
        duplicates = [i for i in ids if ids.count(i) > 1]
        if duplicates:
            raise ValueError(f"Duplicate node id: {duplicates[0]}")
        return nodes
