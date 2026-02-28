from __future__ import annotations

from typing import Any

from pydantic import BaseModel, create_model

# JSON Schema type → Python type mapping
_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}


def json_schema_to_pydantic(
    schema: dict[str, Any],
    model_name: str = "DynamicModel",
) -> type[BaseModel]:
    """Convert a JSON Schema object definition into a Pydantic model.

    Supports:
    - Primitive types: string, integer, number, boolean
    - Nested objects (recursively converted)
    - Arrays with typed items (list[T])
    - Required vs optional fields (optional get ``None`` default)
    """
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: dict[str, Any] = {}

    for field_name, field_schema in properties.items():
        python_type = _resolve_type(field_schema, f"{model_name}_{field_name}")
        if field_name in required:
            fields[field_name] = (python_type, ...)
        else:
            fields[field_name] = (python_type | None, None)

    return create_model(model_name, **fields)


def _resolve_type(field_schema: dict[str, Any], name_hint: str) -> type:
    """Resolve a JSON Schema field to a Python type."""
    schema_type = field_schema.get("type", "string")

    if schema_type == "object":
        return json_schema_to_pydantic(field_schema, model_name=name_hint)

    if schema_type == "array":
        items = field_schema.get("items", {"type": "string"})
        item_type = _resolve_type(items, f"{name_hint}_item")
        return list[item_type]

    return _TYPE_MAP.get(schema_type, str)
