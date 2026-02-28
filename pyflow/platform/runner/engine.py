from __future__ import annotations

from google.adk.agents import BaseAgent
from google.adk.runners import Runner
from google.genai import types
import structlog

from pyflow.models.runner import RunResult
from pyflow.platform.session.service import SessionManager

logger = structlog.get_logger(__name__)


class PlatformRunner:
    """Wraps ADK Runner to execute agents with session management."""

    async def run(
        self,
        agent: BaseAgent,
        input_data: dict,
        session_manager: SessionManager,
    ) -> RunResult:
        """Run an agent with the given input and return the final response."""
        runner = Runner(
            agent=agent,
            app_name=agent.name,
            session_service=session_manager.service,
        )

        session = await session_manager.create_session(app_name=agent.name)

        user_message = types.Content(
            role="user",
            parts=[types.Part(text=str(input_data.get("message", "")))],
        )

        logger.info(
            "runner.executing",
            agent=agent.name,
            session_id=session.id,
        )

        final_response = None
        try:
            async for event in runner.run_async(
                user_id="default",
                session_id=session.id,
                new_message=user_message,
            ):
                if event.is_final_response() and event.content:
                    final_response = event
        except Exception:
            logger.exception("runner.failed", agent=agent.name, session_id=session.id)
            raise

        if final_response and final_response.content:
            text = (
                final_response.content.parts[0].text
                if final_response.content.parts
                else ""
            )
            usage = None
            if hasattr(final_response, "usage_metadata") and final_response.usage_metadata:
                usage = final_response.usage_metadata
            logger.info("runner.completed", agent=agent.name, author=final_response.author)
            return RunResult(
                content=text,
                author=final_response.author,
                usage_metadata=usage,
            )

        logger.info("runner.completed_empty", agent=agent.name)
        return RunResult(author=agent.name)
