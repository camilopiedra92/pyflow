from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyflow.models.a2a import AgentCard
from pyflow.models.platform import PlatformConfig
from pyflow.models.runner import RunResult
from pyflow.models.tool import ToolMetadata
from pyflow.models.workflow import WorkflowDef
from pyflow.platform.app import PyFlowPlatform
from pyflow.tools.base import get_secret, clear_secrets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def platform() -> PyFlowPlatform:
    """A default platform instance (not booted, dotenv disabled for test isolation)."""
    return PyFlowPlatform(PlatformConfig(load_dotenv=False))


@pytest.fixture
def custom_config() -> PlatformConfig:
    return PlatformConfig(
        host="127.0.0.1",
        port=9000,
        workflows_dir="custom_workflows",
        log_level="DEBUG",
    )


# ---------------------------------------------------------------------------
# Init tests
# ---------------------------------------------------------------------------


def test_init_defaults(platform: PyFlowPlatform) -> None:
    assert platform.config == PlatformConfig(load_dotenv=False)
    assert platform.tools is not None
    assert platform.workflows is not None
    assert platform.executor is not None
    assert platform.is_booted is False


def test_init_custom_config(custom_config: PlatformConfig) -> None:
    p = PyFlowPlatform(config=custom_config)
    assert p.config.host == "127.0.0.1"
    assert p.config.port == 9000
    assert p.config.workflows_dir == "custom_workflows"
    assert p.config.log_level == "DEBUG"


# ---------------------------------------------------------------------------
# Boot lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_boot_lifecycle() -> None:
    p = PyFlowPlatform(PlatformConfig(load_dotenv=False))

    p.tools.discover = MagicMock()
    p.workflows.discover = MagicMock()
    p.workflows.hydrate = MagicMock()

    await p.boot()

    p.tools.discover.assert_called_once()
    p.workflows.discover.assert_called_once_with(Path(p.config.workflows_dir))
    p.workflows.hydrate.assert_called_once_with(p.tools)


@pytest.mark.asyncio
async def test_boot_sets_booted_flag() -> None:
    p = PyFlowPlatform(PlatformConfig(load_dotenv=False))

    p.tools.discover = MagicMock()
    p.workflows.discover = MagicMock()
    p.workflows.hydrate = MagicMock()

    assert p.is_booted is False
    await p.boot()
    assert p.is_booted is True


@pytest.mark.asyncio
async def test_boot_generates_agent_cards() -> None:
    """boot() generates and caches A2A agent cards from workflows."""
    p = PyFlowPlatform(PlatformConfig(load_dotenv=False))

    p.tools.discover = MagicMock()
    p.workflows.discover = MagicMock()
    p.workflows.hydrate = MagicMock()
    p.workflows.list_workflows = MagicMock(return_value=[])

    await p.boot()

    assert p._agent_cards == []


# ---------------------------------------------------------------------------
# Before-boot guard tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_workflow_before_boot_raises(platform: PyFlowPlatform) -> None:
    with pytest.raises(RuntimeError, match="not booted"):
        await platform.run_workflow("test", {"message": "hi"})


def test_list_tools_before_boot_raises(platform: PyFlowPlatform) -> None:
    with pytest.raises(RuntimeError, match="not booted"):
        platform.list_tools()


def test_list_workflows_before_boot_raises(platform: PyFlowPlatform) -> None:
    with pytest.raises(RuntimeError, match="not booted"):
        platform.list_workflows()


def test_agent_cards_before_boot_raises(platform: PyFlowPlatform) -> None:
    with pytest.raises(RuntimeError, match="not booted"):
        platform.agent_cards()


# ---------------------------------------------------------------------------
# Delegation tests (after boot)
# ---------------------------------------------------------------------------


def _make_booted_platform() -> PyFlowPlatform:
    """Create a platform with mocked sub-components that's marked as booted."""
    p = PyFlowPlatform()
    p._booted = True
    return p


@pytest.mark.asyncio
async def test_run_workflow_delegates_to_executor() -> None:
    p = _make_booted_platform()

    fake_agent = MagicMock()
    fake_hw = MagicMock()
    fake_hw.agent = fake_agent

    p.workflows.get = MagicMock(return_value=fake_hw)
    expected = RunResult(content="done")
    fake_runner = MagicMock()
    p.executor.build_runner = MagicMock(return_value=fake_runner)
    p.executor.run = AsyncMock(return_value=expected)

    result = await p.run_workflow("my_wf", {"message": "hello"})

    p.workflows.get.assert_called_once_with("my_wf")
    p.executor.build_runner.assert_called_once_with(fake_agent, fake_hw.definition.runtime)
    p.executor.run.assert_awaited_once_with(fake_runner, user_id="default", message="hello")
    assert isinstance(result, RunResult)
    assert result.content == "done"


@pytest.mark.asyncio
async def test_run_workflow_unhydrated_raises() -> None:
    p = _make_booted_platform()

    fake_hw = MagicMock()
    fake_hw.agent = None

    p.workflows.get = MagicMock(return_value=fake_hw)

    with pytest.raises(RuntimeError, match="not hydrated"):
        await p.run_workflow("my_wf", {"message": "hello"})


def test_list_tools_delegates_to_registry() -> None:
    p = _make_booted_platform()
    expected = [ToolMetadata(name="http", description="HTTP requests")]
    p.tools.list_tools = MagicMock(return_value=expected)

    result = p.list_tools()

    p.tools.list_tools.assert_called_once()
    assert result == expected


def test_list_workflows_delegates_to_registry() -> None:
    p = _make_booted_platform()
    p.workflows.list_workflows = MagicMock(return_value=[])

    result = p.list_workflows()

    p.workflows.list_workflows.assert_called_once()
    assert result == []


def test_agent_cards_returns_cached_cards() -> None:
    """agent_cards() returns cards cached during boot."""
    p = _make_booted_platform()
    fake_card = AgentCard(name="test", url="http://localhost:8000/a2a/test")
    p._agent_cards = [fake_card]

    result = p.agent_cards()

    assert len(result) == 1
    assert result[0].name == "test"


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shutdown_cleans_up() -> None:
    p = _make_booted_platform()

    await p.shutdown()

    assert p.is_booted is False


# ---------------------------------------------------------------------------
# Boot injects secrets
# ---------------------------------------------------------------------------


class TestBootInjectsSecrets:
    def setup_method(self):
        clear_secrets()

    def teardown_method(self):
        clear_secrets()

    @pytest.mark.asyncio
    async def test_boot_calls_set_secrets(self):
        config = PlatformConfig(secrets={"ynab_api_token": "test-token"}, load_dotenv=False)
        p = PyFlowPlatform(config=config)
        p.tools.discover = MagicMock()
        p.workflows.discover = MagicMock()
        p.workflows.hydrate = MagicMock()

        await p.boot()

        assert get_secret("ynab_api_token") == "test-token"

    @pytest.mark.asyncio
    async def test_boot_without_secrets_is_fine(self):
        p = PyFlowPlatform(PlatformConfig(load_dotenv=False))
        p.tools.discover = MagicMock()
        p.workflows.discover = MagicMock()
        p.workflows.hydrate = MagicMock()

        await p.boot()

        assert get_secret("nonexistent") is None
