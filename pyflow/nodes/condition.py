from __future__ import annotations

from pyflow.core.context import ExecutionContext
from pyflow.core.node import BaseNode
from pyflow.core.safe_eval import safe_eval
from pyflow.nodes.schemas import ConditionConfig


class ConditionNode(BaseNode[ConditionConfig, bool]):
    node_type = "condition"
    config_model = ConditionConfig

    async def execute(self, config: dict | ConditionConfig, context: ExecutionContext) -> object:
        if isinstance(config, ConditionConfig):
            expression = config.if_
        else:
            expression = config["if"]

        result = safe_eval(expression, context.all_results())
        return bool(result)
