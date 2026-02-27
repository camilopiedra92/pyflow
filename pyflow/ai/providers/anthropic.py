from __future__ import annotations

import os
import time

from pyflow.ai.base import BaseLLMProvider, LLMConfig, LLMResponse, TokenUsage

# Pricing per 1M tokens (input, output) in USD
_ANTHROPIC_PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-5-20250514": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-opus-4-20250514": (15.00, 75.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-haiku-20241022": (0.80, 4.00),
}
_DEFAULT_ANTHROPIC_PRICING = (3.00, 15.00)


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = _ANTHROPIC_PRICING.get(model, _DEFAULT_ANTHROPIC_PRICING)
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


class AnthropicProvider(BaseLLMProvider):
    async def complete(self, config: LLMConfig) -> LLMResponse:
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic package is required for the Anthropic provider. "
                "Install it with: pip install 'pyflow[ai]' or pip install anthropic"
            )

        api_key = config.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key in the config."
            )

        client = anthropic.AsyncAnthropic(api_key=api_key)

        messages = [{"role": "user", "content": config.prompt}]
        create_kwargs: dict = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "messages": messages,
            "temperature": config.temperature,
        }
        if config.system:
            create_kwargs["system"] = config.system

        start = time.monotonic()
        try:
            response = await client.messages.create(**create_kwargs)
        finally:
            await client.close()
        duration_ms = int((time.monotonic() - start) * 1000)

        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        return LLMResponse(
            content=text,
            model=response.model,
            provider="anthropic",
            usage=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                estimated_cost_usd=_estimate_cost(config.model, input_tokens, output_tokens),
            ),
            duration_ms=duration_ms,
        )
