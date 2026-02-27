from __future__ import annotations

from pyflow.core.context import ExecutionContext
from pyflow.core.node import BaseNode

# Safe subset of builtins exposed to condition expressions.
_SAFE_BUILTINS = {
    "True": True,
    "False": False,
    "None": None,
    "len": len,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "round": round,
    "sorted": sorted,
    "any": any,
    "all": all,
    "isinstance": isinstance,
    "type": type,
}


class ConditionNode(BaseNode):
    node_type = "condition"

    async def execute(self, config: dict, context: ExecutionContext) -> object:
        expression = config["if"]
        globals_ = {"__builtins__": _SAFE_BUILTINS}
        result = eval(expression, globals_, context.all_results())  # noqa: S307
        return bool(result)
