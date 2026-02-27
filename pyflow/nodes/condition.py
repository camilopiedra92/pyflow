from __future__ import annotations

from pyflow.core.context import ExecutionContext
from pyflow.core.node import BaseNode


class ConditionNode(BaseNode):
    node_type = "condition"

    async def execute(self, config: dict, context: ExecutionContext) -> object:
        expression = config["if"]
        result = eval(expression, {"__builtins__": {}}, context.all_results())  # noqa: S307
        return bool(result)
