from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from pyflow.ai.base import LLMConfig, LLMResponse, TokenUsage
from pyflow.core.context import ExecutionContext
from pyflow.nodes.llm import LLMNode


def _make_llm_response(**overrides) -> LLMResponse:
    defaults = {
        "content": "Test response",
        "model": "test-model",
        "provider": "google",
        "usage": TokenUsage(
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            estimated_cost_usd=0.001,
        ),
        "duration_ms": 150,
    }
    defaults.update(overrides)
    return LLMResponse(**defaults)


class TestLLMNodeType:
    def test_node_type(self):
        assert LLMNode.node_type == "llm"


class TestLLMConfigValidation:
    def test_llm_config_validates_provider_literal(self):
        cfg = LLMConfig(provider="google", model="gemini-2.0-flash", prompt="Hi")
        assert cfg.provider == "google"

        cfg = LLMConfig(provider="anthropic", model="claude-sonnet-4-5-20250514", prompt="Hi")
        assert cfg.provider == "anthropic"

        cfg = LLMConfig(provider="openai", model="gpt-4o", prompt="Hi")
        assert cfg.provider == "openai"

    def test_llm_config_rejects_invalid_provider(self):
        with pytest.raises(ValidationError):
            LLMConfig(provider="invalid", model="some-model", prompt="Hi")

    def test_llm_config_default_temperature(self):
        cfg = LLMConfig(provider="google", model="gemini-2.0-flash", prompt="Hi")
        assert cfg.temperature == 0.7

    def test_llm_config_rejects_temperature_out_of_range(self):
        with pytest.raises(ValidationError):
            LLMConfig(provider="google", model="gemini-2.0-flash", prompt="Hi", temperature=-0.1)
        with pytest.raises(ValidationError):
            LLMConfig(provider="google", model="gemini-2.0-flash", prompt="Hi", temperature=2.1)

    def test_llm_config_default_max_tokens(self):
        cfg = LLMConfig(provider="google", model="gemini-2.0-flash", prompt="Hi")
        assert cfg.max_tokens == 1024

    def test_llm_config_output_format_text_or_json(self):
        cfg = LLMConfig(provider="google", model="gemini-2.0-flash", prompt="Hi")
        assert cfg.output_format == "text"

        cfg = LLMConfig(
            provider="google", model="gemini-2.0-flash", prompt="Hi", output_format="json"
        )
        assert cfg.output_format == "json"

        with pytest.raises(ValidationError):
            LLMConfig(
                provider="google", model="gemini-2.0-flash", prompt="Hi", output_format="xml"
            )


class TestLLMNodeIntegration:
    async def test_llm_node_google_provider(self):
        mock_response = _make_llm_response(provider="google", model="gemini-2.0-flash")
        mock_provider = AsyncMock()
        mock_provider.complete.return_value = mock_response

        with patch("pyflow.nodes.llm._get_provider", return_value=mock_provider):
            node = LLMNode()
            ctx = ExecutionContext(workflow_name="test", run_id="run-1")
            result = await node.execute(
                {
                    "provider": "google",
                    "model": "gemini-2.0-flash",
                    "prompt": "Hello",
                    "api_key": "test-key",
                },
                ctx,
            )

        assert result["provider"] == "google"
        assert result["content"] == "Test response"
        mock_provider.complete.assert_awaited_once()

    async def test_llm_node_anthropic_provider(self):
        mock_response = _make_llm_response(
            provider="anthropic", model="claude-sonnet-4-5-20250514"
        )
        mock_provider = AsyncMock()
        mock_provider.complete.return_value = mock_response

        with patch("pyflow.nodes.llm._get_provider", return_value=mock_provider):
            node = LLMNode()
            ctx = ExecutionContext(workflow_name="test", run_id="run-1")
            result = await node.execute(
                {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5-20250514",
                    "prompt": "Hello",
                    "api_key": "test-key",
                },
                ctx,
            )

        assert result["provider"] == "anthropic"
        assert result["content"] == "Test response"
        mock_provider.complete.assert_awaited_once()

    async def test_llm_node_openai_provider(self):
        mock_response = _make_llm_response(provider="openai", model="gpt-4o")
        mock_provider = AsyncMock()
        mock_provider.complete.return_value = mock_response

        with patch("pyflow.nodes.llm._get_provider", return_value=mock_provider):
            node = LLMNode()
            ctx = ExecutionContext(workflow_name="test", run_id="run-1")
            result = await node.execute(
                {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "prompt": "Hello",
                    "api_key": "test-key",
                },
                ctx,
            )

        assert result["provider"] == "openai"
        assert result["content"] == "Test response"
        mock_provider.complete.assert_awaited_once()

    async def test_llm_node_returns_typed_response(self):
        mock_response = _make_llm_response()
        mock_provider = AsyncMock()
        mock_provider.complete.return_value = mock_response

        with patch("pyflow.nodes.llm._get_provider", return_value=mock_provider):
            node = LLMNode()
            ctx = ExecutionContext(workflow_name="test", run_id="run-1")
            result = await node.execute(
                {
                    "provider": "google",
                    "model": "gemini-2.0-flash",
                    "prompt": "Hello",
                    "api_key": "test-key",
                },
                ctx,
            )

        assert isinstance(result, dict)
        assert "content" in result
        assert "model" in result
        assert "provider" in result
        assert "usage" in result
        assert "duration_ms" in result

    async def test_llm_node_usage_includes_cost(self):
        mock_response = _make_llm_response(
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=200,
                total_tokens=300,
                estimated_cost_usd=0.05,
            )
        )
        mock_provider = AsyncMock()
        mock_provider.complete.return_value = mock_response

        with patch("pyflow.nodes.llm._get_provider", return_value=mock_provider):
            node = LLMNode()
            ctx = ExecutionContext(workflow_name="test", run_id="run-1")
            result = await node.execute(
                {
                    "provider": "google",
                    "model": "gemini-2.0-flash",
                    "prompt": "Hello",
                    "api_key": "test-key",
                },
                ctx,
            )

        usage = result["usage"]
        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 200
        assert usage["total_tokens"] == 300
        assert usage["estimated_cost_usd"] == 0.05
