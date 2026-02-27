from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    provider: Literal["google", "anthropic", "openai"]
    model: str
    prompt: str
    system: str | None = None
    max_tokens: int = Field(default=1024, ge=1, le=100000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    output_format: Literal["text", "json"] = "text"
    api_key: str | None = Field(
        default=None, description="Override API key, otherwise uses env var"
    )


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float


class LLMResponse(BaseModel):
    content: str
    model: str
    provider: str
    usage: TokenUsage
    duration_ms: int


class BaseLLMProvider(ABC):
    @abstractmethod
    async def complete(self, config: LLMConfig) -> LLMResponse: ...
