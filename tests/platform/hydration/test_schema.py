from __future__ import annotations

from pydantic import BaseModel

from pyflow.platform.hydration.schema import json_schema_to_pydantic


class TestFlatObject:
    def test_string_and_integer_fields(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name", "age"],
        }
        Model = json_schema_to_pydantic(schema, "Person")
        assert issubclass(Model, BaseModel)
        instance = Model(name="Alice", age=30)
        assert instance.name == "Alice"
        assert instance.age == 30

    def test_number_and_boolean_fields(self):
        schema = {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "passed": {"type": "boolean"},
            },
            "required": ["score", "passed"],
        }
        Model = json_schema_to_pydantic(schema, "Result")
        instance = Model(score=95.5, passed=True)
        assert instance.score == 95.5
        assert instance.passed is True


class TestRequiredVsOptional:
    def test_optional_fields_default_to_none(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "nickname": {"type": "string"},
            },
            "required": ["name"],
        }
        Model = json_schema_to_pydantic(schema, "User")
        instance = Model(name="Bob")
        assert instance.name == "Bob"
        assert instance.nickname is None

    def test_all_optional(self):
        schema = {
            "type": "object",
            "properties": {
                "a": {"type": "string"},
                "b": {"type": "integer"},
            },
        }
        Model = json_schema_to_pydantic(schema, "AllOptional")
        instance = Model()
        assert instance.a is None
        assert instance.b is None


class TestNestedObject:
    def test_nested_object_creates_submodel(self):
        schema = {
            "type": "object",
            "properties": {
                "address": {
                    "type": "object",
                    "properties": {
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                    },
                    "required": ["street", "city"],
                },
            },
            "required": ["address"],
        }
        Model = json_schema_to_pydantic(schema, "WithAddress")
        instance = Model(address={"street": "123 Main", "city": "Springfield"})
        assert instance.address.street == "123 Main"
        assert instance.address.city == "Springfield"


class TestArrayTypes:
    def test_array_of_strings(self):
        schema = {
            "type": "object",
            "properties": {
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["tags"],
        }
        Model = json_schema_to_pydantic(schema, "Tagged")
        instance = Model(tags=["a", "b", "c"])
        assert instance.tags == ["a", "b", "c"]

    def test_array_of_integers(self):
        schema = {
            "type": "object",
            "properties": {
                "scores": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["scores"],
        }
        Model = json_schema_to_pydantic(schema, "Scores")
        instance = Model(scores=[1, 2, 3])
        assert instance.scores == [1, 2, 3]

    def test_array_default_items_type(self):
        schema = {
            "type": "object",
            "properties": {
                "items": {"type": "array"},
            },
            "required": ["items"],
        }
        Model = json_schema_to_pydantic(schema, "DefaultArray")
        instance = Model(items=["x", "y"])
        assert instance.items == ["x", "y"]


class TestDefaults:
    def test_empty_properties(self):
        schema = {"type": "object"}
        Model = json_schema_to_pydantic(schema, "Empty")
        instance = Model()
        assert isinstance(instance, BaseModel)

    def test_unknown_type_falls_back_to_str(self):
        schema = {
            "type": "object",
            "properties": {
                "data": {"type": "unknown_type"},
            },
            "required": ["data"],
        }
        Model = json_schema_to_pydantic(schema, "Fallback")
        instance = Model(data="hello")
        assert instance.data == "hello"
