from __future__ import annotations

from pyflow.models.workflow import RuntimeConfig
from pyflow.platform.executor import WorkflowExecutor


class TestSqliteSessionService:
    def test_sqlite_uses_dedicated_service(self):
        """'sqlite' maps to SqliteSessionService, not DatabaseSessionService."""
        executor = WorkflowExecutor()
        runtime = RuntimeConfig(session_service="sqlite", session_db_path="test.db")
        service = executor._build_session_service(runtime)
        from google.adk.sessions.sqlite_session_service import SqliteSessionService
        assert isinstance(service, SqliteSessionService)

    def test_sqlite_default_path(self):
        """'sqlite' without session_db_path uses default path."""
        executor = WorkflowExecutor()
        runtime = RuntimeConfig(session_service="sqlite")
        service = executor._build_session_service(runtime)
        from google.adk.sessions.sqlite_session_service import SqliteSessionService
        assert isinstance(service, SqliteSessionService)
