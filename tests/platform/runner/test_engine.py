from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyflow.platform.runner.engine import PlatformRunner
from pyflow.platform.session.service import SessionManager


def _make_event(*, is_final: bool = False, text: str = "", author: str = "agent") -> MagicMock:
    """Create a mock ADK Event."""
    event = MagicMock()
    event.is_final_response.return_value = is_final

    if is_final and text:
        part = MagicMock()
        part.text = text
        event.content = MagicMock()
        event.content.parts = [part]
    elif is_final:
        event.content = MagicMock()
        event.content.parts = []
    else:
        event.content = None

    event.author = author
    return event


class TestPlatformRunnerRun:
    async def test_run_returns_final_response(self) -> None:
        runner = PlatformRunner()

        mock_agent = MagicMock()
        mock_agent.name = "test-agent"

        mock_session = MagicMock()
        mock_session.id = "session-1"

        session_manager = MagicMock(spec=SessionManager)
        session_manager.service = MagicMock()
        session_manager.create_session = AsyncMock(return_value=mock_session)

        events = [
            _make_event(is_final=False),
            _make_event(is_final=True, text="Hello world", author="test-agent"),
        ]

        async def mock_run_async(**kwargs):
            for event in events:
                yield event

        with patch("pyflow.platform.runner.engine.Runner") as MockRunner:
            mock_runner_instance = MagicMock()
            mock_runner_instance.run_async = mock_run_async
            MockRunner.return_value = mock_runner_instance

            result = await runner.run(
                agent=mock_agent,
                input_data={"message": "Hi there"},
                session_manager=session_manager,
            )

        assert result["content"] == "Hello world"
        assert result["author"] == "test-agent"

    async def test_run_empty_response(self) -> None:
        runner = PlatformRunner()

        mock_agent = MagicMock()
        mock_agent.name = "test-agent"

        mock_session = MagicMock()
        mock_session.id = "session-1"

        session_manager = MagicMock(spec=SessionManager)
        session_manager.service = MagicMock()
        session_manager.create_session = AsyncMock(return_value=mock_session)

        # No final events
        events = [
            _make_event(is_final=False),
            _make_event(is_final=False),
        ]

        async def mock_run_async(**kwargs):
            for event in events:
                yield event

        with patch("pyflow.platform.runner.engine.Runner") as MockRunner:
            mock_runner_instance = MagicMock()
            mock_runner_instance.run_async = mock_run_async
            MockRunner.return_value = mock_runner_instance

            result = await runner.run(
                agent=mock_agent,
                input_data={"message": "Hi"},
                session_manager=session_manager,
            )

        assert result["content"] == ""
        assert result["author"] == "test-agent"

    async def test_run_builds_user_message_from_input(self) -> None:
        runner = PlatformRunner()

        mock_agent = MagicMock()
        mock_agent.name = "test-agent"

        mock_session = MagicMock()
        mock_session.id = "session-1"

        session_manager = MagicMock(spec=SessionManager)
        session_manager.service = MagicMock()
        session_manager.create_session = AsyncMock(return_value=mock_session)

        captured_kwargs: dict = {}

        async def mock_run_async(**kwargs):
            captured_kwargs.update(kwargs)
            event = _make_event(is_final=True, text="Response", author="test-agent")
            yield event

        with patch("pyflow.platform.runner.engine.Runner") as MockRunner:
            mock_runner_instance = MagicMock()
            mock_runner_instance.run_async = mock_run_async
            MockRunner.return_value = mock_runner_instance

            with patch("pyflow.platform.runner.engine.types") as mock_types:
                mock_content = MagicMock()
                mock_types.Content.return_value = mock_content
                mock_part = MagicMock()
                mock_types.Part.return_value = mock_part

                await runner.run(
                    agent=mock_agent,
                    input_data={"message": "Test message"},
                    session_manager=session_manager,
                )

                # Verify Content was built with role="user" and correct Part
                mock_types.Part.assert_called_once_with(text="Test message")
                mock_types.Content.assert_called_once_with(
                    role="user", parts=[mock_part]
                )

            # Verify run_async was called with the built message
            assert captured_kwargs["user_id"] == "default"
            assert captured_kwargs["session_id"] == "session-1"
            assert captured_kwargs["new_message"] == mock_content

    async def test_run_handles_empty_message_input(self) -> None:
        runner = PlatformRunner()

        mock_agent = MagicMock()
        mock_agent.name = "test-agent"

        mock_session = MagicMock()
        mock_session.id = "session-1"

        session_manager = MagicMock(spec=SessionManager)
        session_manager.service = MagicMock()
        session_manager.create_session = AsyncMock(return_value=mock_session)

        async def mock_run_async(**kwargs):
            event = _make_event(is_final=True, text="OK", author="test-agent")
            yield event

        with patch("pyflow.platform.runner.engine.Runner") as MockRunner:
            mock_runner_instance = MagicMock()
            mock_runner_instance.run_async = mock_run_async
            MockRunner.return_value = mock_runner_instance

            with patch("pyflow.platform.runner.engine.types") as mock_types:
                mock_types.Part.return_value = MagicMock()
                mock_types.Content.return_value = MagicMock()

                # Empty dict — no "message" key
                await runner.run(
                    agent=mock_agent,
                    input_data={},
                    session_manager=session_manager,
                )

                mock_types.Part.assert_called_once_with(text="")

    async def test_run_includes_usage_metadata(self) -> None:
        runner = PlatformRunner()

        mock_agent = MagicMock()
        mock_agent.name = "test-agent"

        mock_session = MagicMock()
        mock_session.id = "session-1"

        session_manager = MagicMock(spec=SessionManager)
        session_manager.service = MagicMock()
        session_manager.create_session = AsyncMock(return_value=mock_session)

        event = _make_event(is_final=True, text="Hello", author="test-agent")
        event.usage_metadata = {"prompt_tokens": 10, "completion_tokens": 20}

        async def mock_run_async(**kwargs):
            yield event

        with patch("pyflow.platform.runner.engine.Runner") as MockRunner:
            mock_runner_instance = MagicMock()
            mock_runner_instance.run_async = mock_run_async
            MockRunner.return_value = mock_runner_instance

            result = await runner.run(
                agent=mock_agent,
                input_data={"message": "Hi"},
                session_manager=session_manager,
            )

        assert result["usage_metadata"] == {"prompt_tokens": 10, "completion_tokens": 20}

    async def test_run_empty_response_has_null_usage_metadata(self) -> None:
        runner = PlatformRunner()

        mock_agent = MagicMock()
        mock_agent.name = "test-agent"

        mock_session = MagicMock()
        mock_session.id = "session-1"

        session_manager = MagicMock(spec=SessionManager)
        session_manager.service = MagicMock()
        session_manager.create_session = AsyncMock(return_value=mock_session)

        async def mock_run_async(**kwargs):
            yield _make_event(is_final=False)

        with patch("pyflow.platform.runner.engine.Runner") as MockRunner:
            mock_runner_instance = MagicMock()
            mock_runner_instance.run_async = mock_run_async
            MockRunner.return_value = mock_runner_instance

            result = await runner.run(
                agent=mock_agent,
                input_data={"message": "Hi"},
                session_manager=session_manager,
            )

        assert result["usage_metadata"] is None

    async def test_run_propagates_runner_errors(self) -> None:
        runner = PlatformRunner()

        mock_agent = MagicMock()
        mock_agent.name = "test-agent"

        mock_session = MagicMock()
        mock_session.id = "session-1"

        session_manager = MagicMock(spec=SessionManager)
        session_manager.service = MagicMock()
        session_manager.create_session = AsyncMock(return_value=mock_session)

        async def mock_run_async(**kwargs):
            raise RuntimeError("LLM provider unavailable")
            yield  # noqa: RUF027 — make this an async generator

        with patch("pyflow.platform.runner.engine.Runner") as MockRunner:
            mock_runner_instance = MagicMock()
            mock_runner_instance.run_async = mock_run_async
            MockRunner.return_value = mock_runner_instance

            with pytest.raises(RuntimeError, match="LLM provider unavailable"):
                await runner.run(
                    agent=mock_agent,
                    input_data={"message": "Hi"},
                    session_manager=session_manager,
                )
