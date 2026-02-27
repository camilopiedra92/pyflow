from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyflow.ai.base import LLMConfig


class TestAnthropicProvider:
    def _make_config(self, **overrides) -> LLMConfig:
        defaults = {
            "provider": "anthropic",
            "model": "claude-sonnet-4-5-20250514",
            "prompt": "Hello",
            "api_key": "test-key",
        }
        defaults.update(overrides)
        return LLMConfig(**defaults)

    async def test_anthropic_complete_returns_llm_response(self):
        # Build a mock anthropic module
        mock_anthropic_mod = MagicMock()

        # Build the mock response
        text_block = SimpleNamespace(type="text", text="Hello from Claude")
        usage = SimpleNamespace(input_tokens=15, output_tokens=25)
        mock_response = SimpleNamespace(
            content=[text_block],
            model="claude-sonnet-4-5-20250514",
            usage=usage,
        )

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_client.close = AsyncMock()
        mock_anthropic_mod.AsyncAnthropic.return_value = mock_client

        with patch.dict(sys.modules, {"anthropic": mock_anthropic_mod}):
            import importlib
            from pyflow.ai.providers import anthropic as anthropic_mod
            importlib.reload(anthropic_mod)

            provider = anthropic_mod.AnthropicProvider()
            config = self._make_config()
            response = await provider.complete(config)

        assert response.content == "Hello from Claude"
        assert response.provider == "anthropic"
        assert response.model == "claude-sonnet-4-5-20250514"
        assert response.usage.input_tokens == 15
        assert response.usage.output_tokens == 25
        assert response.usage.total_tokens == 40
        assert response.usage.estimated_cost_usd >= 0
        assert response.duration_ms >= 0

    async def test_anthropic_missing_api_key_raises_error(self):
        mock_anthropic_mod = MagicMock()

        with (
            patch.dict(sys.modules, {"anthropic": mock_anthropic_mod}),
            patch.dict("os.environ", {}, clear=True),
        ):
            import importlib
            from pyflow.ai.providers import anthropic as anthropic_mod
            importlib.reload(anthropic_mod)

            provider = anthropic_mod.AnthropicProvider()
            config = self._make_config(api_key=None)

            with pytest.raises(ValueError, match="Anthropic API key is required"):
                await provider.complete(config)

    async def test_anthropic_missing_sdk_raises_import_error(self):
        from pyflow.ai.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider()
        config = self._make_config()

        real_import = __import__

        def fail_anthropic(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("No module named 'anthropic'")
            return real_import(name, *args, **kwargs)

        saved = {}
        for key in list(sys.modules.keys()):
            if key == "anthropic" or key.startswith("anthropic."):
                saved[key] = sys.modules.pop(key)
        try:
            with patch("builtins.__import__", side_effect=fail_anthropic):
                with pytest.raises(ImportError, match="anthropic"):
                    await provider.complete(config)
        finally:
            sys.modules.update(saved)
