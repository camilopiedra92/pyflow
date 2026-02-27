from __future__ import annotations

import ast

# Safe subset of builtins exposed to eval expressions.
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

_ALLOWED_CALL_NAMES = set(_SAFE_BUILTINS.keys()) - {
    "True",
    "False",
    "None",
}

# AST node types that are safe to evaluate.
_SAFE_AST_NODES = (
    ast.Expression,
    ast.Compare,
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.Name,
    ast.Constant,
    ast.Attribute,
    ast.Subscript,
    ast.Index,
    ast.Load,
    ast.Slice,
    ast.Tuple,
    ast.List,
    ast.Dict,
    ast.Set,
    ast.IfExp,
    # Operators
    ast.And,
    ast.Or,
    ast.Not,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Is,
    ast.IsNot,
    ast.In,
    ast.NotIn,
    ast.USub,
    ast.UAdd,
    ast.Invert,
    ast.Call,
    ast.keyword,
    ast.Starred,
    ast.JoinedStr,
    ast.FormattedValue,
)

# Dunder attributes that must never be accessed.
_BLOCKED_ATTRS = frozenset({
    "__class__",
    "__mro__",
    "__subclasses__",
    "__globals__",
    "__builtins__",
    "__code__",
    "__func__",
    "__self__",
    "__module__",
    "__dict__",
    "__bases__",
    "__init__",
    "__new__",
    "__del__",
    "__getattr__",
    "__setattr__",
    "__delattr__",
    "__import__",
    "__loader__",
    "__spec__",
    "__qualname__",
})


class UnsafeExpressionError(Exception):
    """Raised when an expression contains unsafe constructs."""


def _validate_ast(node: ast.AST) -> None:
    """Walk the AST and reject any unsafe constructs."""
    if not isinstance(node, _SAFE_AST_NODES):
        raise UnsafeExpressionError(
            f"Disallowed expression construct: {type(node).__name__}"
        )

    # Block dunder attribute access
    if isinstance(node, ast.Attribute) and node.attr in _BLOCKED_ATTRS:
        raise UnsafeExpressionError(
            f"Access to '{node.attr}' is not allowed"
        )

    # Only allow calls to whitelisted function names
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name):
            if func.id not in _ALLOWED_CALL_NAMES:
                raise UnsafeExpressionError(
                    f"Call to '{func.id}' is not allowed"
                )
        elif isinstance(func, ast.Attribute):
            # Allow method calls on data (e.g. mylist.append), but block dunders
            if func.attr in _BLOCKED_ATTRS:
                raise UnsafeExpressionError(
                    f"Call to '{func.attr}' is not allowed"
                )
        else:
            raise UnsafeExpressionError("Only named function calls are allowed")

    for child in ast.iter_child_nodes(node):
        _validate_ast(child)


def safe_eval(expression: str, variables: dict | None = None) -> object:
    """Evaluate an expression after AST validation.

    Only allows safe operations: comparisons, boolean logic, arithmetic,
    attribute/subscript access on data, and calls to whitelisted builtins.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise UnsafeExpressionError(f"Invalid expression syntax: {exc}") from exc

    _validate_ast(tree.body)

    code = compile(tree, "<safe_eval>", "eval")
    globals_ = {"__builtins__": _SAFE_BUILTINS}
    locals_ = variables or {}
    return eval(code, globals_, locals_)  # noqa: S307
