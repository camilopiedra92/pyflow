from __future__ import annotations

from pathlib import Path

import structlog

from pyflow.models.a2a import AgentCard
from pyflow.models.platform import PlatformConfig
from pyflow.models.runner import RunResult
from pyflow.models.tool import ToolMetadata
from pyflow.models.workflow import WorkflowDef
from pyflow.platform.a2a.cards import AgentCardGenerator
from pyflow.platform.executor import WorkflowExecutor
from pyflow.platform.registry.tool_registry import ToolRegistry
from pyflow.platform.registry.workflow_registry import WorkflowRegistry

logger = structlog.get_logger()


class PyFlowPlatform:
    """Central platform orchestrator — owns all registries and manages lifecycle."""

    def __init__(self, config: PlatformConfig | None = None):
        self.config = config or PlatformConfig()
        self.tools = ToolRegistry()
        self.workflows = WorkflowRegistry()
        self.executor = WorkflowExecutor()
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

        self._booted = True
        log.info("platform.ready")

    def _ensure_booted(self) -> None:
        if not self._booted:
            raise RuntimeError("Platform not booted. Call boot() first.")

    async def run_workflow(
        self, name: str, input_data: dict, user_id: str = "default",
    ) -> RunResult:
        """Execute a workflow by name."""
        self._ensure_booted()
        hw = self.workflows.get(name)
        if hw.agent is None:
            raise RuntimeError(f"Workflow '{name}' not hydrated.")
        runtime = hw.definition.runtime
        runner = self.executor.build_runner(hw.agent, runtime)
        message = input_data.get("message", "")
        return await self.executor.run(runner, user_id=user_id, message=message)

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
        """Auto-generate A2A agent cards from workflow registry."""
        self._ensure_booted()
        return self._a2a.generate_all(self.workflows.list_workflows())

    @property
    def is_booted(self) -> bool:
        return self._booted
