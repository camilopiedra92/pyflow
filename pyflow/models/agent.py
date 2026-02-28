from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, model_validator


class AgentConfig(BaseModel):
    """Configuration for an agent within a workflow."""

    name: str
    type: Literal["llm", "sequential", "parallel", "loop", "code", "tool", "expr"]
    model: str | None = None
    instruction: str | None = None
    tools: list[str] = []
    output_key: str | None = None
    sub_agents: list[str] | None = None
    callbacks: dict[str, str] | None = None
    description: str = ""
    include_contents: Literal["default", "none"] = "default"
    # LLM schema fields
    output_schema: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None
    # LLM generation config fields
    temperature: float | None = None
    max_output_tokens: int | None = None
    top_p: float | None = None
    top_k: int | None = None
    # CodeAgent fields
    function: str | None = None
    input_keys: list[str] | None = None
    # ToolAgent fields
    tool: str | None = None
    tool_config: dict[str, Any] | None = None
    # ExprAgent fields
    expression: str | None = None
    # AgentTool fields
    agent_tools: list[str] | None = None

    @model_validator(mode="after")
    def _validate_by_type(self) -> AgentConfig:
        if self.type == "llm":
            if not self.model:
                raise ValueError("llm agent requires 'model'")
            if not self.instruction:
                raise ValueError("llm agent requires 'instruction'")
        elif self.type == "code":
            if not self.function:
                raise ValueError("code agent requires 'function'")
            if not self.output_key:
                raise ValueError("code agent requires 'output_key'")
        elif self.type == "tool":
            if not self.tool:
                raise ValueError("tool agent requires 'tool'")
            if not self.output_key:
                raise ValueError("tool agent requires 'output_key'")
        elif self.type == "expr":
            if not self.expression:
                raise ValueError("expr agent requires 'expression'")
            if not self.output_key:
                raise ValueError("expr agent requires 'output_key'")
        else:
            # workflow types: sequential, parallel, loop
            if not self.sub_agents:
                raise ValueError(f"{self.type} agent requires 'sub_agents'")
        return self
