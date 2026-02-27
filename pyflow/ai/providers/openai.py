from __future__ import annotations

import os
import time

from pyflow.ai.base import BaseLLMProvider, LLMConfig, LLMResponse, TokenUsage

# Pricing per 1M tokens (input, output) in USD
_OPENAI_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o3-mini": (1.10, 4.40),
}
_DEFAULT_OPENAI_PRICING = (2.50, 10.00)


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = _OPENAI_PRICING.get(model, _DEFAULT_OPENAI_PRICING)
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


class OpenAIProvider(BaseLLMProvider):
    async def complete(self, config: LLMConfig) -> LLMResponse:
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai package is required for the OpenAI provider. "
                "Install it with: pip install 'pyflow[ai]' or pip install openai"
            )

        api_key = config.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable "
                "or pass api_key in the config."
            )

        client = openai.AsyncOpenAI(api_key=api_key)

        messages: list[dict] = []
        if config.system:
            messages.append({"role": "system", "content": config.system})
        messages.append({"role": "user", "content": config.prompt})

        create_kwargs: dict = {
            "model": config.model,
            "messages": messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
        }
        if config.output_format == "json":
            create_kwargs["response_format"] = {"type": "json_object"}

        start = time.monotonic()
        try:
            response = await client.chat.completions.create(**create_kwargs)
        finally:
            await client.close()
        duration_ms = int((time.monotonic() - start) * 1000)

        choice = response.choices[0]
        text = choice.message.content or ""

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        return LLMResponse(
            content=text,
            model=response.model,
            provider="openai",
            usage=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                estimated_cost_usd=_estimate_cost(config.model, input_tokens, output_tokens),
            ),
            duration_ms=duration_ms,
        )
