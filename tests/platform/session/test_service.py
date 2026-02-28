from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyflow.platform.session.service import SessionManager


class TestSessionManagerInitialize:
    async def test_initialize_creates_service(self) -> None:
        manager = SessionManager()
        assert manager._service is None
        await manager.initialize()
        assert manager._service is not None

    async def test_service_raises_before_init(self) -> None:
        manager = SessionManager()
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = manager.service


class TestSessionManagerCreateSession:
    async def test_create_session(self) -> None:
        manager = SessionManager()
        await manager.initialize()

        mock_session = MagicMock()
        mock_session.id = "session-123"

        with patch.object(
            manager._service, "create_session", new_callable=AsyncMock, return_value=mock_session
        ):
            session = await manager.create_session(app_name="test-app", user_id="user-1")
            assert session.id == "session-123"
            manager._service.create_session.assert_awaited_once_with(
                app_name="test-app", user_id="user-1"
            )

    async def test_create_session_default_user_id(self) -> None:
        manager = SessionManager()
        await manager.initialize()

        mock_session = MagicMock()
        mock_session.id = "session-456"

        with patch.object(
            manager._service, "create_session", new_callable=AsyncMock, return_value=mock_session
        ):
            session = await manager.create_session(app_name="test-app")
            assert session.id == "session-456"
            manager._service.create_session.assert_awaited_once_with(
                app_name="test-app", user_id="default"
            )


class TestSessionManagerCleanup:
    async def test_cleanup_resets_service(self) -> None:
        manager = SessionManager()
        await manager.initialize()
        assert manager._service is not None

        await manager.cleanup()
        assert manager._service is None

        with pytest.raises(RuntimeError, match="not initialized"):
            _ = manager.service
