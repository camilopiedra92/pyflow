from __future__ import annotations

import structlog

from pyflow.ai.base import BaseLLMProvider, LLMConfig, LLMResponse
from pyflow.core.context import ExecutionContext
from pyflow.core.node import BaseNode

logger = structlog.get_logger()

_PROVIDERS: dict[str, type[BaseLLMProvider]] = {}


def _get_provider(name: str) -> BaseLLMProvider:
    if name not in _PROVIDERS:
        if name == "google":
            from pyflow.ai.providers.google import GoogleProvider

            _PROVIDERS["google"] = GoogleProvider
        elif name == "anthropic":
            from pyflow.ai.providers.anthropic import AnthropicProvider

            _PROVIDERS["anthropic"] = AnthropicProvider
        elif name == "openai":
            from pyflow.ai.providers.openai import OpenAIProvider

            _PROVIDERS["openai"] = OpenAIProvider
        else:
            raise ValueError(
                f"Unknown LLM provider: '{name}'. "
                f"Supported providers: google, anthropic, openai"
            )
    return _PROVIDERS[name]()


class LLMNode(BaseNode[LLMConfig, LLMResponse]):
    node_type = "llm"
    config_model = LLMConfig
    response_model = LLMResponse

    async def execute(self, config: dict | LLMConfig, context: ExecutionContext) -> object:
        if isinstance(config, dict):
            cfg = LLMConfig(**config)
        else:
            cfg = config

        log = logger.bind(
            provider=cfg.provider,
            model=cfg.model,
            max_tokens=cfg.max_tokens,
        )
        log.info("llm.start")

        provider = _get_provider(cfg.provider)
        response = await provider.complete(cfg)

        log.info(
            "llm.complete",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            estimated_cost_usd=response.usage.estimated_cost_usd,
            duration_ms=response.duration_ms,
        )

        return response.model_dump()
