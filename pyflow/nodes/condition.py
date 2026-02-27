from __future__ import annotations

from pyflow.core.context import ExecutionContext
from pyflow.core.node import BaseNode
from pyflow.core.safe_eval import safe_eval


class ConditionNode(BaseNode):
    node_type = "condition"

    async def execute(self, config: dict, context: ExecutionContext) -> object:
        expression = config["if"]
        result = safe_eval(expression, context.all_results())
        return bool(result)
