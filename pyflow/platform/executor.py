from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import AsyncGenerator
from zoneinfo import ZoneInfo

from google.adk.agents import BaseAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Suppress "non-text parts in the response" warning from google.genai SDK.
# ADK's _build_response_log() accesses resp.text on responses containing
# function_call parts, which is expected in ReAct tool-calling loops.
logging.getLogger("google_genai.types").setLevel(logging.ERROR)

from pyflow.models.runner import RunResult
from pyflow.models.workflow import RuntimeConfig
from pyflow.platform.plugins import resolve_plugins


def _detect_system_timezone() -> str:
    """Detect the local system IANA timezone name (e.g. 'America/Bogota').

    Falls back to 'UTC' if detection fails.
    """
    import time

    # time.tzname gives abbreviations like ('EST', 'EDT') — not usable with ZoneInfo.
    # On macOS/Linux, /etc/localtime is a symlink into the zoneinfo database.
    try:
        from pathlib import Path

        target = Path("/etc/localtime").resolve()
        parts = target.parts
        # e.g. /usr/share/zoneinfo/America/Bogota -> 'America/Bogota'
        if "zoneinfo" in parts:
            idx = parts.index("zoneinfo")
            return "/".join(parts[idx + 1 :])
    except (OSError, ValueError):
        pass

    # Windows: try tzlocal if available
    try:
        import tzlocal

        return str(tzlocal.get_localzone())
    except ImportError:
        pass

    # Last resort: check TZ env var
    tz_env = time.tzname[0] if time.tzname else ""
    try:
        ZoneInfo(tz_env)
        return tz_env
    except (KeyError, Exception):
        return "UTC"


class WorkflowExecutor:
    """Configures and runs ADK Runner based on workflow RuntimeConfig."""

    def __init__(self, app_name: str = "pyflow", tz_name: str = ""):
        self._app_name = app_name
        self._tz_name = tz_name or _detect_system_timezone()

    def _datetime_state(self) -> dict[str, str]:
        """Build session state with current date/time in the configured timezone."""
        tz = ZoneInfo(self._tz_name)
        now = datetime.now(tz)
        return {
            "current_date": now.strftime("%Y-%m-%d"),
            "current_datetime": now.isoformat(),
            "timezone": self._tz_name,
        }

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
        state = self._datetime_state()
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
                    state=state,
                )
        else:
            session = await runner.session_service.create_session(
                app_name=self._app_name,
                user_id=user_id,
                state=state,
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
            text = "".join(p.text for p in final_event.content.parts if p.text)
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
            state=self._datetime_state(),
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
