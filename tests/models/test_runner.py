from __future__ import annotations

import pytest

from pyflow.models.runner import RunResult


class TestRunResult:
    def test_creation_with_all_fields(self):
        result = RunResult(
            content="Hello, world!",
            author="agent_1",
            usage_metadata={"input_tokens": 10, "output_tokens": 20},
        )
        assert result.content == "Hello, world!"
        assert result.author == "agent_1"
        assert result.usage_metadata == {"input_tokens": 10, "output_tokens": 20}

    def test_defaults(self):
        result = RunResult()
        assert result.content == ""
        assert result.author == ""
        assert result.usage_metadata is None

    def test_with_usage_metadata_object(self):
        """usage_metadata accepts Any type, including arbitrary objects."""

        class FakeUsage:
            input_tokens = 5

        usage = FakeUsage()
        result = RunResult(content="ok", author="bot", usage_metadata=usage)
        assert result.usage_metadata is usage
        assert result.usage_metadata.input_tokens == 5

    def test_serialization(self):
        result = RunResult(content="hi", author="bot", usage_metadata={"tokens": 42})
        data = result.model_dump()
        assert data == {"content": "hi", "author": "bot", "usage_metadata": {"tokens": 42}}
