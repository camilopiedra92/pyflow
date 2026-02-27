from __future__ import annotations

import asyncio
import uuid

import structlog

from pyflow.core.context import ExecutionContext
from pyflow.core.models import NodeDef, OnError, WorkflowDef
from pyflow.core.node import BaseNode, NodeRegistry
from pyflow.core.safe_eval import safe_eval
from pyflow.core.template import resolve_templates

logger = structlog.get_logger()


class WorkflowEngine:
    def __init__(self, registry: NodeRegistry) -> None:
        self._registry = registry

    async def run(
        self,
        workflow: WorkflowDef,
        run_id: str | None = None,
        initial_context: dict[str, object] | None = None,
    ) -> ExecutionContext:
        run_id = run_id or str(uuid.uuid4())
        ctx = ExecutionContext(workflow_name=workflow.name, run_id=run_id)
        if initial_context:
            for key, value in initial_context.items():
                ctx.set_result(key, value)
        log = logger.bind(workflow=workflow.name, run_id=run_id)

        nodes_by_id = {n.id: n for n in workflow.nodes}
        self._validate_depends_on(nodes_by_id)
        self._check_for_cycles(nodes_by_id)

        log.info("workflow.start", node_count=len(workflow.nodes))
        await self._execute_dag(nodes_by_id, ctx, log)
        log.info("workflow.complete")
        return ctx

    def _validate_depends_on(self, nodes: dict[str, NodeDef]) -> None:
        for node_id, node_def in nodes.items():
            for dep in node_def.depends_on:
                if dep not in nodes:
                    raise ValueError(
                        f"Node '{node_id}' depends on '{dep}', which does not exist"
                    )

    def _check_for_cycles(self, nodes: dict[str, NodeDef]) -> None:
        visited: set[str] = set()
        in_stack: set[str] = set()

        def dfs(node_id: str) -> None:
            visited.add(node_id)
            in_stack.add(node_id)
            for dep in nodes[node_id].depends_on:
                if dep in in_stack:
                    raise ValueError(f"Cycle detected involving node '{dep}'")
                if dep not in visited and dep in nodes:
                    dfs(dep)
            in_stack.discard(node_id)

        for nid in nodes:
            if nid not in visited:
                dfs(nid)

    async def _execute_dag(
        self,
        nodes: dict[str, NodeDef],
        ctx: ExecutionContext,
        log: structlog.stdlib.BoundLogger,
    ) -> None:
        completed: set[str] = set()
        failed_stop = False

        while len(completed) < len(nodes) and not failed_stop:
            ready = [
                n
                for n in nodes.values()
                if n.id not in completed
                and all(d in completed for d in n.depends_on)
            ]
            if not ready:
                break

            tasks = []
            for node_def in ready:
                tasks.append(self._execute_node(node_def, ctx, log))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for node_def, result in zip(ready, results):
                if isinstance(result, BaseException):
                    log.error(
                        "node.unhandled_error",
                        node_id=node_def.id,
                        error=str(result),
                    )
                    ctx.set_error(node_def.id, str(result))
                elif isinstance(result, _StopSentinel):
                    failed_stop = True
                completed.add(node_def.id)

    async def _execute_node(
        self,
        node_def: NodeDef,
        ctx: ExecutionContext,
        log: structlog.stdlib.BoundLogger,
    ) -> object:
        nlog = log.bind(node_id=node_def.id, node_type=node_def.type)

        # Check 'when' condition
        if node_def.when:
            try:
                result = safe_eval(node_def.when, ctx.all_results())
                if not result:
                    nlog.info("node.skipped", reason="when condition false")
                    return None
            except Exception:
                nlog.info("node.skipped", reason="when condition evaluation failed")
                return None

        # Resolve templates in config
        config = resolve_templates(node_def.config, ctx)

        # Get node class and execute
        node_cls = self._registry.get(node_def.type)
        node = node_cls()

        try:
            nlog.info("node.start")
            result = await node.execute(config, ctx)
            ctx.set_result(node_def.id, result)
            nlog.info("node.complete")
            return result
        except Exception as exc:
            nlog.error("node.error", error=str(exc))
            ctx.set_error(node_def.id, str(exc))

            if node_def.on_error == OnError.RETRY:
                result = await self._retry_node(node, config, ctx, node_def, nlog)
                if result is not _RETRY_FAILED:
                    return result

            if node_def.on_error == OnError.STOP:
                return _StopSentinel()

            # on_error == skip: continue
            return None

    async def _retry_node(
        self,
        node: BaseNode,
        config: dict,
        ctx: ExecutionContext,
        node_def: NodeDef,
        log: structlog.stdlib.BoundLogger,
    ) -> object:
        max_retries = (node_def.retry or {}).get("max_retries", 3)
        delay = (node_def.retry or {}).get("delay", 1)

        for attempt in range(1, max_retries + 1):
            await asyncio.sleep(delay * (2 ** (attempt - 1)))
            try:
                log.info("node.retry", attempt=attempt)
                result = await node.execute(config, ctx)
                ctx.set_result(node_def.id, result)
                return result
            except Exception as exc:
                log.error("node.retry_failed", attempt=attempt, error=str(exc))

        return _RETRY_FAILED


class _StopSentinel:
    pass


_RETRY_FAILED = object()
