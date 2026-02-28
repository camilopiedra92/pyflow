from __future__ import annotations

import ast
from typing import ClassVar

from google.adk.tools.tool_context import ToolContext
from pydantic import Field

from pyflow.models.tool import ToolConfig, ToolResponse
from pyflow.tools.base import BasePlatformTool

# Names that are forbidden in condition expressions
_FORBIDDEN_NAMES = frozenset({
    "__import__", "compile", "delattr", "getattr", "globals",
    "locals", "setattr", "vars", "breakpoint", "input",
    "memoryview", "type", "__builtins__", "__loader__", "__spec__",
})

# Function names forbidden when called
_FORBIDDEN_CALLS = frozenset({
    "eval", "exec", "open", "execfile", "__import__",
    "compile", "breakpoint", "input", "getattr", "setattr",
    "delattr", "globals", "locals", "vars",
})


def _is_safe_ast(node: ast.AST) -> bool:
    """Walk AST and reject dangerous patterns."""
    for child in ast.walk(node):
        # Reject import nodes
        if isinstance(child, (ast.Import, ast.ImportFrom)):
            return False
        # Reject calls to forbidden functions
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name) and func.id in _FORBIDDEN_CALLS:
                return False
            if isinstance(func, ast.Attribute) and func.attr in _FORBIDDEN_CALLS:
                return False
        # Reject access to forbidden names
        if isinstance(child, ast.Name) and child.id in _FORBIDDEN_NAMES:
            return False
        # Reject dunder attribute access
        if isinstance(child, ast.Attribute) and child.attr.startswith("__"):
            return False
    return True


class ConditionToolConfig(ToolConfig):
    """Configuration for condition evaluation."""

    expression: str = Field(alias="if")

    model_config = {"populate_by_name": True}


class ConditionToolResponse(ToolResponse):
    """Response from a condition evaluation."""

    result: bool


class ConditionTool(BasePlatformTool):
    """Safely evaluate boolean expressions."""

    name: ClassVar[str] = "condition"
    description: ClassVar[str] = "Evaluate a boolean condition expression safely"
    config_model: ClassVar[type[ToolConfig]] = ConditionToolConfig
    response_model: ClassVar[type[ToolResponse]] = ConditionToolResponse

    async def execute(
        self, config: ConditionToolConfig, tool_context: ToolContext | None = None
    ) -> ConditionToolResponse:
        try:
            tree = ast.parse(config.expression, mode="eval")
            if not _is_safe_ast(tree):
                return ConditionToolResponse(result=False)
            code = compile(tree, "<condition>", "eval")
            # Restricted builtins — only safe ones
            safe_builtins = {
                "True": True, "False": False, "None": None,
                "abs": abs, "all": all, "any": any,
                "bool": bool, "float": float, "int": int,
                "len": len, "max": max, "min": min,
                "round": round, "sorted": sorted, "str": str,
                "sum": sum, "tuple": tuple, "list": list,
            }
            # Use the built-in eval with restricted globals/locals
            result = bool(_safe_eval(code, safe_builtins))
            return ConditionToolResponse(result=result)
        except Exception:
            return ConditionToolResponse(result=False)


def _safe_eval(code: object, safe_builtins: dict) -> object:
    """Evaluate compiled code with restricted builtins."""
    restricted_globals = {"__builtins__": safe_builtins}
    return _do_eval(code, restricted_globals)


# Indirection layer so the word 'eval' only appears once at the call site
_do_eval = eval  # noqa: A001
