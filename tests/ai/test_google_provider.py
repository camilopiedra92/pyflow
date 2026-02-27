from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyflow.ai.base import LLMConfig


class TestGoogleProvider:
    def _make_config(self, **overrides) -> LLMConfig:
        defaults = {
            "provider": "google",
            "model": "gemini-2.0-flash",
            "prompt": "Hello",
            "api_key": "test-key",
        }
        defaults.update(overrides)
        return LLMConfig(**defaults)

    def _mock_genai(self):
        """Create a mock google.genai module with proper async support."""
        mock_genai = MagicMock()
        mock_genai.types = MagicMock()
        mock_genai.types.GenerateContentConfig = MagicMock(return_value={})
        return mock_genai

    def _install_mock_genai(self, mock_genai):
        """Return a dict suitable for patch.dict(sys.modules, ...)."""
        mock_google = MagicMock()
        mock_google.genai = mock_genai
        return {"google": mock_google, "google.genai": mock_genai}

    async def test_google_complete_returns_llm_response(self):
        mock_genai = self._mock_genai()

        # Mock the response objects
        usage_metadata = SimpleNamespace(
            prompt_token_count=10,
            candidates_token_count=20,
            total_token_count=30,
        )
        mock_response = SimpleNamespace(text="Hello world", usage_metadata=usage_metadata)

        mock_generate = AsyncMock(return_value=mock_response)
        mock_aio_models = MagicMock()
        mock_aio_models.generate_content = mock_generate
        mock_aio = MagicMock()
        mock_aio.models = mock_aio_models
        mock_client_instance = MagicMock()
        mock_client_instance.aio = mock_aio
        mock_genai.Client.return_value = mock_client_instance

        modules_patch = self._install_mock_genai(mock_genai)
        with patch.dict(sys.modules, modules_patch):
            import importlib
            from pyflow.ai.providers import google as google_mod
            importlib.reload(google_mod)

            provider = google_mod.GoogleProvider()
            config = self._make_config()
            response = await provider.complete(config)

        assert response.content == "Hello world"
        assert response.provider == "google"
        assert response.model == "gemini-2.0-flash"
        assert response.usage.input_tokens == 10
        assert response.usage.output_tokens == 20
        assert response.usage.total_tokens == 30
        assert response.usage.estimated_cost_usd >= 0
        assert response.duration_ms >= 0

    async def test_google_missing_api_key_raises_error(self):
        """Provider raises ValueError when no API key is provided."""
        mock_genai = self._mock_genai()
        modules_patch = self._install_mock_genai(mock_genai)

        # The provider module is already imported. We just need the
        # "from google import genai" inside complete() to succeed and
        # then hit the API key check.  Patch sys.modules AND clear env.
        with (
            patch.dict(sys.modules, modules_patch),
            patch.dict("os.environ", {}, clear=True),
        ):
            from pyflow.ai.providers.google import GoogleProvider

            provider = GoogleProvider()
            config = self._make_config(api_key=None)

            with pytest.raises(ValueError, match="Google API key is required"):
                await provider.complete(config)

    async def test_google_missing_sdk_raises_import_error(self):
        from pyflow.ai.providers.google import GoogleProvider

        provider = GoogleProvider()
        config = self._make_config()

        real_import = __import__

        def fail_google(name, *args, **kwargs):
            if name == "google":
                raise ImportError("No module named 'google'")
            return real_import(name, *args, **kwargs)

        saved = {}
        for key in list(sys.modules.keys()):
            if key == "google" or key.startswith("google."):
                saved[key] = sys.modules.pop(key)
        try:
            with patch("builtins.__import__", side_effect=fail_google):
                with pytest.raises(ImportError, match="google-genai"):
                    await provider.complete(config)
        finally:
            sys.modules.update(saved)
