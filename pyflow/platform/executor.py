from __future__ import annotations

from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from pyflow.models.runner import RunResult
from pyflow.models.workflow import RuntimeConfig
from pyflow.platform.plugins import resolve_plugins


class WorkflowExecutor:
    """Configures and runs ADK Runner based on workflow RuntimeConfig."""

    def __init__(self, app_name: str = "pyflow"):
        self._app_name = app_name

    def build_runner(self, agent: BaseAgent, runtime: RuntimeConfig) -> Runner:
        """Build a fully-configured ADK Runner from workflow runtime config."""
        return Runner(
            agent=agent,
            app_name=self._app_name,
            session_service=self._build_session_service(runtime),
            memory_service=self._build_memory_service(runtime),
            artifact_service=self._build_artifact_service(runtime),
            plugins=resolve_plugins(runtime.plugins) or None,
        )

    async def run(
        self,
        runner: Runner,
        user_id: str = "default",
        message: str = "",
        session_id: str | None = None,
    ) -> RunResult:
        """Execute a workflow and collect results."""
        if session_id:
            session = await runner.session_service.get_session(
                app_name=self._app_name,
                user_id=user_id,
                session_id=session_id,
            )
            if session is None:
                session = await runner.session_service.create_session(
                    app_name=self._app_name,
                    user_id=user_id,
                )
        else:
            session = await runner.session_service.create_session(
                app_name=self._app_name,
                user_id=user_id,
            )

        content = types.Content(
            role="user",
            parts=[types.Part(text=message)],
        )

        final_event = None
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.is_final_response() and event.content:
                final_event = event

        if final_event and final_event.content and final_event.content.parts:
            text = final_event.content.parts[0].text or ""
        else:
            text = ""

        author = ""
        if final_event and hasattr(final_event, "author"):
            author = final_event.author or ""

        usage = None
        if final_event and hasattr(final_event, "usage_metadata"):
            usage = final_event.usage_metadata

        return RunResult(
            content=text,
            author=author,
            usage_metadata=usage,
            session_id=session.id,
        )

    async def run_streaming(
        self,
        runner: Runner,
        user_id: str = "default",
        message: str = "",
    ) -> AsyncGenerator:
        """Yield events as they arrive for streaming APIs."""
        session = await runner.session_service.create_session(
            app_name=self._app_name,
            user_id=user_id,
        )
        content = types.Content(
            role="user",
            parts=[types.Part(text=message)],
        )

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            yield event

    def _build_session_service(self, runtime: RuntimeConfig):
        match runtime.session_service:
            case "in_memory":
                return InMemorySessionService()
            case "sqlite":
                url = runtime.session_db_url or "sqlite+aiosqlite:///pyflow_sessions.db"
                from google.adk.sessions.database_session_service import DatabaseSessionService

                return DatabaseSessionService(db_url=url)
            case "database":
                if not runtime.session_db_url:
                    raise ValueError("database session_service requires session_db_url")
                from google.adk.sessions.database_session_service import DatabaseSessionService

                return DatabaseSessionService(db_url=runtime.session_db_url)

    def _build_memory_service(self, runtime: RuntimeConfig):
        match runtime.memory_service:
            case "in_memory":
                from google.adk.memory.in_memory_memory_service import InMemoryMemoryService

                return InMemoryMemoryService()
            case "none":
                return None

    def _build_artifact_service(self, runtime: RuntimeConfig):
        match runtime.artifact_service:
            case "in_memory":
                from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService

                return InMemoryArtifactService()
            case "file":
                from google.adk.artifacts.file_artifact_service import FileArtifactService

                return FileArtifactService(root_dir=runtime.artifact_dir or "./artifacts")
            case "none":
                return None
