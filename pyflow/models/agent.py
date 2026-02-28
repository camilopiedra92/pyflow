from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator


class AgentConfig(BaseModel):
    """Configuration for an agent within a workflow."""

    name: str
    type: Literal["llm", "sequential", "parallel", "loop"]
    model: str | None = None
    instruction: str | None = None
    tools: list[str] = []
    output_key: str | None = None
    sub_agents: list[str] | None = None

    @model_validator(mode="after")
    def _validate_by_type(self) -> AgentConfig:
        if self.type == "llm":
            if not self.model:
                raise ValueError("llm agent requires 'model'")
            if not self.instruction:
                raise ValueError("llm agent requires 'instruction'")
        else:
            # workflow types: sequential, parallel, loop
            if not self.sub_agents:
                raise ValueError(f"{self.type} agent requires 'sub_agents'")
        return self
