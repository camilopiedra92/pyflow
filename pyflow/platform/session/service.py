from __future__ import annotations

from google.adk.sessions import InMemorySessionService, Session
import structlog

logger = structlog.get_logger(__name__)


class SessionManager:
    """Wraps ADK InMemorySessionService with lifecycle management."""

    def __init__(self) -> None:
        self._service: InMemorySessionService | None = None

    async def initialize(self) -> None:
        """Create the underlying ADK session service."""
        self._service = InMemorySessionService()
        logger.info("session_manager.initialized")

    @property
    def service(self) -> InMemorySessionService:
        """Access the underlying service, raising if not yet initialized."""
        if self._service is None:
            raise RuntimeError("SessionManager not initialized. Call initialize() first.")
        return self._service

    async def create_session(
        self, app_name: str, user_id: str = "default"
    ) -> Session:
        """Create a new session for the given app and user."""
        session = await self.service.create_session(app_name=app_name, user_id=user_id)
        logger.info("session.created", app_name=app_name, user_id=user_id, session_id=session.id)
        return session

    async def cleanup(self) -> None:
        """Tear down the session service."""
        self._service = None
        logger.info("session_manager.cleaned_up")
