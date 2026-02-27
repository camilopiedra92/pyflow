from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyflow.ai.base import LLMConfig


class TestOpenAIProvider:
    def _make_config(self, **overrides) -> LLMConfig:
        defaults = {
            "provider": "openai",
            "model": "gpt-4o",
            "prompt": "Hello",
            "api_key": "test-key",
        }
        defaults.update(overrides)
        return LLMConfig(**defaults)

    async def test_openai_complete_returns_llm_response(self):
        mock_openai_mod = MagicMock()

        message = SimpleNamespace(content="Hello from GPT")
        choice = SimpleNamespace(message=message)
        usage = SimpleNamespace(prompt_tokens=12, completion_tokens=18)
        mock_response = SimpleNamespace(
            choices=[choice],
            model="gpt-4o",
            usage=usage,
        )

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client.close = AsyncMock()
        mock_openai_mod.AsyncOpenAI.return_value = mock_client

        with patch.dict(sys.modules, {"openai": mock_openai_mod}):
            import importlib
            from pyflow.ai.providers import openai as openai_mod
            importlib.reload(openai_mod)

            provider = openai_mod.OpenAIProvider()
            config = self._make_config()
            response = await provider.complete(config)

        assert response.content == "Hello from GPT"
        assert response.provider == "openai"
        assert response.model == "gpt-4o"
        assert response.usage.input_tokens == 12
        assert response.usage.output_tokens == 18
        assert response.usage.total_tokens == 30
        assert response.usage.estimated_cost_usd >= 0
        assert response.duration_ms >= 0

    async def test_openai_missing_api_key_raises_error(self):
        mock_openai_mod = MagicMock()

        with (
            patch.dict(sys.modules, {"openai": mock_openai_mod}),
            patch.dict("os.environ", {}, clear=True),
        ):
            from pyflow.ai.providers.openai import OpenAIProvider

            provider = OpenAIProvider()
            config = self._make_config(api_key=None)

            with pytest.raises(ValueError, match="OpenAI API key is required"):
                await provider.complete(config)

    async def test_openai_missing_sdk_raises_import_error(self):
        from pyflow.ai.providers.openai import OpenAIProvider

        provider = OpenAIProvider()
        config = self._make_config()

        real_import = __import__

        def fail_openai(name, *args, **kwargs):
            if name == "openai":
                raise ImportError("No module named 'openai'")
            return real_import(name, *args, **kwargs)

        saved = {}
        for key in list(sys.modules.keys()):
            if key == "openai" or key.startswith("openai."):
                saved[key] = sys.modules.pop(key)
        try:
            with patch("builtins.__import__", side_effect=fail_openai):
                with pytest.raises(ImportError, match="openai"):
                    await provider.complete(config)
        finally:
            sys.modules.update(saved)
