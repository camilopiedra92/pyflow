from __future__ import annotations

from pathlib import Path

import structlog

from pyflow.models.platform import PlatformConfig
from pyflow.models.tool import ToolMetadata
from pyflow.models.workflow import WorkflowDef
from pyflow.platform.a2a.cards import AgentCardGenerator
from pyflow.platform.registry.tool_registry import ToolRegistry
from pyflow.platform.registry.workflow_registry import WorkflowRegistry
from pyflow.platform.runner.engine import PlatformRunner
from pyflow.platform.session.service import SessionManager

logger = structlog.get_logger()


class PyFlowPlatform:
    """Central platform orchestrator — owns all registries and manages lifecycle."""

    def __init__(self, config: PlatformConfig | None = None):
        self.config = config or PlatformConfig()
        self.tools = ToolRegistry()
        self.workflows = WorkflowRegistry()
        self.sessions = SessionManager()
        self.runner = PlatformRunner()
        self._a2a = AgentCardGenerator(
            base_url=f"http://{self.config.host}:{self.config.port}"
        )
        self._booted = False

    async def boot(self) -> None:
        """Platform lifecycle: discover -> validate -> hydrate -> ready."""
        log = logger.bind(phase="boot")

        # 1. Discover tools
        self.tools.discover()
        log.info("tools.discovered", count=len(self.tools))

        # 2. Discover workflows
        workflows_path = Path(self.config.workflows_dir)
        self.workflows.discover(workflows_path)
        log.info("workflows.discovered", count=len(self.workflows))

        # 3. Hydrate workflows (resolve tool refs -> ADK agents)
        self.workflows.hydrate(self.tools)
        log.info("workflows.hydrated")

        # 4. Initialize sessions
        await self.sessions.initialize()
        log.info("sessions.initialized")

        self._booted = True
        log.info("platform.ready")

    def _ensure_booted(self) -> None:
        if not self._booted:
            raise RuntimeError("Platform not booted. Call boot() first.")

    async def run_workflow(self, name: str, input_data: dict) -> dict:
        """Execute a workflow by name."""
        self._ensure_booted()
        hw = self.workflows.get(name)
        if hw.agent is None:
            raise RuntimeError(f"Workflow '{name}' not hydrated.")
        return await self.runner.run(hw.agent, input_data, self.sessions)

    async def shutdown(self) -> None:
        """Cleanup platform resources."""
        await self.sessions.cleanup()
        self._booted = False
        logger.info("platform.shutdown")

    def list_tools(self) -> list[ToolMetadata]:
        self._ensure_booted()
        return self.tools.list_tools()

    def list_workflows(self) -> list[WorkflowDef]:
        self._ensure_booted()
        return self.workflows.list_workflows()

    def agent_cards(self) -> list[dict]:
        """Auto-generate A2A agent cards from workflow registry."""
        self._ensure_booted()
        return self._a2a.generate_all(self.workflows.list_workflows())

    @property
    def is_booted(self) -> bool:
        return self._booted
