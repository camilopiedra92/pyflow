from __future__ import annotations

import os
import time

from pyflow.ai.base import BaseLLMProvider, LLMConfig, LLMResponse, TokenUsage

# Pricing per 1M tokens (input, output) in USD
_GOOGLE_PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-flash-lite": (0.025, 0.10),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.15, 0.60),
}
_DEFAULT_GOOGLE_PRICING = (0.50, 1.50)


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = _GOOGLE_PRICING.get(model, _DEFAULT_GOOGLE_PRICING)
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


class GoogleProvider(BaseLLMProvider):
    async def complete(self, config: LLMConfig) -> LLMResponse:
        try:
            from google import genai
        except ImportError:
            raise ImportError(
                "google-genai package is required for the Google provider. "
                "Install it with: pip install 'pyflow[ai]' or pip install google-genai"
            )

        api_key = config.api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "Google API key is required. Set GOOGLE_API_KEY environment variable "
                "or pass api_key in the config."
            )

        client = genai.Client(api_key=api_key)

        contents = config.prompt
        generate_kwargs: dict = {
            "model": config.model,
            "contents": contents,
        }

        gen_config: dict = {
            "max_output_tokens": config.max_tokens,
            "temperature": config.temperature,
        }
        if config.output_format == "json":
            gen_config["response_mime_type"] = "application/json"
        if config.system:
            generate_kwargs["config"] = genai.types.GenerateContentConfig(
                system_instruction=config.system,
                **gen_config,
            )
        else:
            generate_kwargs["config"] = genai.types.GenerateContentConfig(**gen_config)

        start = time.monotonic()
        response = await client.aio.models.generate_content(**generate_kwargs)
        duration_ms = int((time.monotonic() - start) * 1000)

        text = response.text or ""
        usage_meta = response.usage_metadata
        input_tokens = usage_meta.prompt_token_count or 0
        output_tokens = usage_meta.candidates_token_count or 0
        total_tokens = usage_meta.total_token_count or (input_tokens + output_tokens)

        return LLMResponse(
            content=text,
            model=config.model,
            provider="google",
            usage=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=_estimate_cost(config.model, input_tokens, output_tokens),
            ),
            duration_ms=duration_ms,
        )
