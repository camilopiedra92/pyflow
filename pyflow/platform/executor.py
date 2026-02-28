from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import AsyncGenerator
from zoneinfo import ZoneInfo

from google.adk.agents import BaseAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# TODO(ADK>=1.27): Remove when ADK fixes response logging for function_call parts
logging.getLogger("google_genai.types").setLevel(logging.ERROR)

from pyflow.models.runner import RunResult, UsageSummary
from pyflow.models.workflow import RuntimeConfig
from pyflow.platform.metrics_plugin import MetricsPlugin
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
        """Build a fully-configured ADK Runner from workflow runtime config.

        Wraps the agent in an ADK App to unlock context caching, event compaction,
        resumability, and app-level plugins. The Runner is then constructed with
        app= instead of agent=.
        """
        from google.adk.apps import App, ResumabilityConfig
        from google.adk.apps.app import ContextCacheConfig
        from google.adk.apps.compaction import EventsCompactionConfig
        from google.adk.plugins.global_instruction_plugin import GlobalInstructionPlugin

        app_plugins = resolve_plugins(runtime.plugins) or []
        # Always inject GlobalInstructionPlugin for datetime awareness
        app_plugins.insert(
            0,
            GlobalInstructionPlugin(
                global_instruction="NOW: {current_datetime} ({timezone})."
            ),
        )
        # Always include MetricsPlugin for per-run usage tracking
        metrics = MetricsPlugin()
        app_plugins.append(metrics)

        app_kwargs: dict = {
            "name": self._app_name,
            "root_agent": agent,
            "plugins": app_plugins,
        }

        if runtime.context_cache_intervals is not None:
            cache_kwargs: dict = {"cache_intervals": runtime.context_cache_intervals}
            if runtime.context_cache_ttl is not None:
                cache_kwargs["ttl_seconds"] = runtime.context_cache_ttl
            if runtime.context_cache_min_tokens is not None:
                cache_kwargs["min_tokens"] = runtime.context_cache_min_tokens
            app_kwargs["context_cache_config"] = ContextCacheConfig(**cache_kwargs)

        if runtime.compaction_interval is not None and runtime.compaction_overlap is not None:
            app_kwargs["events_compaction_config"] = EventsCompactionConfig(
                compaction_interval=runtime.compaction_interval,
                overlap_size=runtime.compaction_overlap,
            )

        if runtime.resumable:
            app_kwargs["resumability_config"] = ResumabilityConfig(is_resumable=True)

        app = App(**app_kwargs)

        return Runner(
            app=app,
            session_service=self._build_session_service(runtime),
            memory_service=self._build_memory_service(runtime),
            artifact_service=self._build_artifact_service(runtime),
            credential_service=self._build_credential_service(runtime),
        )

    def _get_metrics_plugin(self, runner: Runner) -> MetricsPlugin | None:
        """Find the MetricsPlugin from runner's plugin list."""
        for plugin in runner.plugin_manager.plugins:
            if isinstance(plugin, MetricsPlugin):
                return plugin
        return None

    async def _get_or_create_session(self, runner, user_id, session_id):
        """Get existing session or create a new one with datetime state."""
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
        return session

    async def run(
        self,
        agent: BaseAgent,
        runtime: RuntimeConfig,
        user_id: str = "default",
        message: str = "",
        session_id: str | None = None,
    ) -> RunResult:
        """Execute a workflow and collect results."""
        runner = self.build_runner(agent, runtime)
        metrics = self._get_metrics_plugin(runner)

        session = await self._get_or_create_session(runner, user_id, session_id)

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

        author = getattr(final_event, "author", "") or "" if final_event else ""

        return RunResult(
            content=text,
            author=author,
            usage=metrics.summary() if metrics else UsageSummary(),
            session_id=session.id,
        )

    async def run_streaming(
        self,
        agent: BaseAgent,
        runtime: RuntimeConfig,
        user_id: str = "default",
        message: str = "",
        session_id: str | None = None,
    ) -> AsyncGenerator:
        """Yield events as they arrive for streaming APIs."""
        runner = self.build_runner(agent, runtime)
        session = await self._get_or_create_session(runner, user_id, session_id)
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
                path = runtime.session_db_path or "pyflow_sessions.db"
                from google.adk.sessions.sqlite_session_service import SqliteSessionService

                return SqliteSessionService(db_path=path)
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

    def _build_credential_service(self, runtime: RuntimeConfig):
        match runtime.credential_service:
            case "in_memory":
                from google.adk.auth.credential_service.in_memory_credential_service import (
                    InMemoryCredentialService,
                )

                return InMemoryCredentialService()
            case "none":
                return None
