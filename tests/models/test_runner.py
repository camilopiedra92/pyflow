from __future__ import annotations


from pyflow.models.runner import RunResult, UsageSummary


class TestUsageSummary:
    def test_defaults(self):
        usage = UsageSummary()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cached_tokens == 0
        assert usage.total_tokens == 0
        assert usage.duration_ms == 0
        assert usage.steps == 0
        assert usage.llm_calls == 0
        assert usage.tool_calls == 0
        assert usage.model is None

    def test_with_values(self):
        usage = UsageSummary(
            input_tokens=1000,
            output_tokens=200,
            cached_tokens=500,
            total_tokens=1700,
            duration_ms=3200,
            steps=5,
            llm_calls=3,
            tool_calls=2,
            model="gemini-2.5-flash",
        )
        assert usage.input_tokens == 1000
        assert usage.model == "gemini-2.5-flash"

    def test_serialization(self):
        usage = UsageSummary(input_tokens=10, output_tokens=5, total_tokens=15)
        data = usage.model_dump()
        assert data["input_tokens"] == 10
        assert data["model"] is None


class TestRunResult:
    def test_creation_with_all_fields(self):
        usage = UsageSummary(input_tokens=10, output_tokens=20, total_tokens=30)
        result = RunResult(
            content="Hello, world!",
            author="agent_1",
            usage=usage,
        )
        assert result.content == "Hello, world!"
        assert result.author == "agent_1"
        assert result.usage.input_tokens == 10

    def test_defaults(self):
        result = RunResult()
        assert result.content == ""
        assert result.author == ""
        assert result.usage is None

    def test_run_result_with_session_id(self):
        result = RunResult(content="hello", session_id="sess-123")
        assert result.session_id == "sess-123"

    def test_run_result_session_id_default(self):
        result = RunResult()
        assert result.session_id is None

    def test_serialization(self):
        usage = UsageSummary(input_tokens=42, output_tokens=10, total_tokens=52)
        result = RunResult(content="hi", author="bot", usage=usage)
        data = result.model_dump()
        assert data["content"] == "hi"
        assert data["author"] == "bot"
        assert data["usage"]["input_tokens"] == 42
        assert data["session_id"] is None

    def test_serialization_no_usage(self):
        result = RunResult(content="hi", author="bot")
        data = result.model_dump()
        assert data["usage"] is None
