from __future__ import annotations

import ast

from google.adk.tools.tool_context import ToolContext

from pyflow.tools.base import BasePlatformTool

# Names that are forbidden in condition expressions
_FORBIDDEN_NAMES = frozenset(
    {
        "__import__",
        "compile",
        "delattr",
        "getattr",
        "globals",
        "locals",
        "setattr",
        "vars",
        "breakpoint",
        "input",
        "memoryview",
        "type",
        "__builtins__",
        "__loader__",
        "__spec__",
    }
)

# Function names forbidden when called
_FORBIDDEN_CALLS = frozenset(
    {
        "eval",
        "exec",
        "open",
        "execfile",
        "__import__",
        "compile",
        "breakpoint",
        "input",
        "getattr",
        "setattr",
        "delattr",
        "globals",
        "locals",
        "vars",
    }
)

# Restricted builtins — only safe ones
_SAFE_BUILTINS = {
    "True": True,
    "False": False,
    "None": None,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "float": float,
    "int": int,
    "len": len,
    "max": max,
    "min": min,
    "round": round,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "list": list,
}


def _validate_ast(expression: str) -> None:
    """Parse and validate an expression AST, raising ValueError if unsafe."""
    tree = ast.parse(expression, mode="eval")
    for child in ast.walk(tree):
        # Reject import nodes
        if isinstance(child, (ast.Import, ast.ImportFrom)):
            raise ValueError("Import statements are not allowed")
        # Reject calls to forbidden functions
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name) and func.id in _FORBIDDEN_CALLS:
                raise ValueError(f"Call to '{func.id}' is not allowed")
            if isinstance(func, ast.Attribute) and func.attr in _FORBIDDEN_CALLS:
                raise ValueError(f"Call to '{func.attr}' is not allowed")
        # Reject access to forbidden names
        if isinstance(child, ast.Name) and child.id in _FORBIDDEN_NAMES:
            raise ValueError(f"Access to '{child.id}' is not allowed")
        # Reject dunder attribute access
        if isinstance(child, ast.Attribute) and child.attr.startswith("__"):
            raise ValueError(f"Access to '{child.attr}' is not allowed")


class ConditionTool(BasePlatformTool):
    name = "condition"
    description = "Evaluate a boolean expression safely. Returns true or false."

    async def execute(self, tool_context: ToolContext, expression: str) -> dict:
        """Evaluate a boolean expression.

        Args:
            expression: A Python boolean expression (e.g. '1 + 1 == 2', 'x > 5 and y < 10').
        """
        try:
            _validate_ast(expression)
        except (ValueError, SyntaxError) as exc:
            return {"status": "error", "result": False, "error": str(exc)}

        try:
            # Security: AST validation above is the actual security boundary,
            # not the restricted builtins alone.
            result = bool(eval(expression, {"__builtins__": _SAFE_BUILTINS}))  # noqa: S307
            return {"status": "success", "result": result, "error": None}
        except Exception as exc:
            return {"status": "error", "result": False, "error": f"Evaluation error: {exc}"}
