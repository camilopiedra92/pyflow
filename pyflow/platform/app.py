from __future__ import annotations

import functools
import os
from pathlib import Path

import structlog
from dotenv import load_dotenv

from pyflow.models.a2a import AgentCard
from pyflow.models.platform import PlatformConfig
from pyflow.models.runner import RunResult
from pyflow.models.tool import ToolMetadata
from pyflow.models.workflow import WorkflowDef
from pyflow.platform.a2a.cards import AgentCardGenerator
from pyflow.platform.executor import WorkflowExecutor
from pyflow.platform.registry.tool_registry import ToolRegistry
from pyflow.platform.registry.workflow_registry import WorkflowRegistry
from pyflow.tools.base import set_secrets

logger = structlog.get_logger()

_ADK_DISABLE_LOAD_DOTENV_ENV_VAR = "ADK_DISABLE_LOAD_DOTENV"


@functools.lru_cache(maxsize=1)
def _get_explicit_env_keys() -> frozenset[str]:
    """Snapshot env var keys before any .env loading.

    Mirrors ADK's pattern: explicit env vars (set before .env load)
    are preserved and never overwritten by .env files.
    """
    return frozenset(os.environ)


def _load_dotenv_for_platform(workflows_dir: str) -> None:
    """Load .env file from the workflows directory or its parents.

    Follows the same pattern as ADK's ``load_dotenv_for_agent``:
    - Walks from workflows_dir up to root looking for .env
    - Loads with override=True so later .env files win
    - Preserves explicit env vars (set before first .env load)
    - Respects ADK_DISABLE_LOAD_DOTENV to skip loading
    """
    if os.environ.get(_ADK_DISABLE_LOAD_DOTENV_ENV_VAR, "").lower() in ("1", "true"):
        logger.info("dotenv.skipped", reason=_ADK_DISABLE_LOAD_DOTENV_ENV_VAR)
        return

    starting = os.path.abspath(workflows_dir)
    dotenv_path = _walk_to_root_until_found(starting, ".env")
    if not dotenv_path:
        logger.debug("dotenv.not_found", starting_dir=starting)
        return

    explicit_keys = _get_explicit_env_keys()
    explicit_env = {k: os.environ[k] for k in explicit_keys if k in os.environ}

    load_dotenv(dotenv_path, override=True)
    os.environ.update(explicit_env)
    logger.info("dotenv.loaded", path=dotenv_path)


def _walk_to_root_until_found(folder: str, filename: str) -> str:
    """Walk up from folder to root looking for filename."""
    checkpath = os.path.join(folder, filename)
    if os.path.exists(checkpath) and os.path.isfile(checkpath):
        return checkpath
    parent = os.path.dirname(folder)
    if parent == folder:
        return ""
    return _walk_to_root_until_found(parent, filename)


class PyFlowPlatform:
    """Central platform orchestrator — owns all registries and manages lifecycle."""

    def __init__(self, config: PlatformConfig | None = None):
        self.config = config or PlatformConfig()
        self.tools = ToolRegistry()
        self.workflows = WorkflowRegistry()
        self.executor = WorkflowExecutor(tz_name=self.config.timezone)
        self._a2a = AgentCardGenerator(base_url=f"http://{self.config.host}:{self.config.port}")
        self._agent_cards: list[AgentCard] = []
        self._booted = False

    async def boot(self) -> None:
        """Platform lifecycle: load env -> discover -> validate -> hydrate -> ready."""
        log = logger.bind(phase="boot")

        # 0a. Load .env file (ADK-aligned: walk from workflows_dir to root)
        if self.config.load_dotenv:
            _load_dotenv_for_platform(self.config.workflows_dir)

        # 0b. Inject secrets for platform tools
        if self.config.secrets:
            set_secrets(self.config.secrets)
            log.info("secrets.loaded", count=len(self.config.secrets))

        # 1. Discover tools
        self.tools.discover()
        log.info("tools.discovered", count=len(self.tools))

        # 2. Discover workflows
        workflows_path = Path(self.config.workflows_dir)
        self.workflows.discover(workflows_path)
        log.info("workflows.discovered", count=len(self.workflows))

        # 2b. Register OpenAPI tools from all workflows
        # base_dir = project root (parent of workflows_dir) for resolving shared spec paths
        project_root = workflows_path.parent
        for hw in self.workflows.all():
            if hw.definition.openapi_tools:
                self.tools.register_openapi_tools(
                    hw.definition.openapi_tools, project_root
                )
        log.info("openapi_tools.registered")

        # 3. Hydrate workflows (resolve tool refs -> ADK agents)
        self.workflows.hydrate(self.tools)
        log.info("workflows.hydrated")

        # 4. Generate A2A agent cards from workflows with a2a: section
        self._agent_cards = self._a2a.generate_cards(self.workflows.list_workflows())
        log.info("a2a.cards_generated", count=len(self._agent_cards))

        self._booted = True
        log.info("platform.ready")

    def _ensure_booted(self) -> None:
        if not self._booted:
            raise RuntimeError("Platform not booted. Call boot() first.")

    async def run_workflow(
        self,
        name: str,
        input_data: dict,
        user_id: str = "default",
    ) -> RunResult:
        """Execute a workflow by name."""
        self._ensure_booted()
        hw = self.workflows.get(name)
        if hw.agent is None:
            raise RuntimeError(f"Workflow '{name}' not hydrated.")
        message = input_data.get("message", "")
        return await self.executor.run(
            agent=hw.agent, runtime=hw.definition.runtime, user_id=user_id, message=message
        )

    async def shutdown(self) -> None:
        """Cleanup platform resources."""
        self._booted = False
        logger.info("platform.shutdown")

    def list_tools(self) -> list[ToolMetadata]:
        self._ensure_booted()
        return self.tools.list_tools()

    def list_workflows(self) -> list[WorkflowDef]:
        self._ensure_booted()
        return self.workflows.list_workflows()

    def agent_cards(self) -> list[AgentCard]:
        """Return A2A agent cards generated at boot from workflow definitions."""
        self._ensure_booted()
        return self._agent_cards

    @property
    def is_booted(self) -> bool:
        return self._booted
