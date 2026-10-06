"""Bounded JSON/schema validation with no references, regex or network resolution."""

from __future__ import annotations

import json
import math
import re
from json.decoder import scanstring  # type: ignore[attr-defined]  # CPython decoder primitive
from typing import Any

MAX_SCHEMA_BYTES = 65536
MAX_SCHEMA_DEPTH = 16
MAX_SCHEMA_NODES = 512
MAX_JSON_DEPTH = 32
MAX_VALIDATION_WORK = 16384
_STRUCTURAL_JSON = re.compile(r'["\[\]{}]')
_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}
_KEYWORDS = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "enum",
    "title",
    "description",
}


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON keys are unsupported")
        result[key] = value
    return result


def _invalid_constant(value: str) -> Any:
    _ = value
    raise ValueError("Nonfinite JSON values are unsupported")


def load_bounded_json(text: str, *, max_bytes: int = 262144) -> Any:
    if not isinstance(text, str) or len(text.encode()) > max_bytes:
        raise ValueError("JSON exceeds the byte bound")
    # Scan container depth before the recursive decoder. Its strict string
    # primitive skips escaped structure in C with bounded temporary allocation.
    depth = 0
    position = 0
    while match := _STRUCTURAL_JSON.search(text, position):
        char = match.group()
        position = match.end()
        if char == '"':
            try:
                decoded, position = scanstring(text, position, True)
                del decoded
            except ValueError as exc:
                raise ValueError("Invalid bounded JSON") from exc
        elif char in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise ValueError("JSON exceeds the depth bound")
        else:
            depth -= 1
    try:
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Invalid bounded JSON") from exc
    _bound_value(value, [MAX_VALIDATION_WORK])
    return value


def _spend(budget: list[int]) -> None:
    budget[0] -= 1
    if budget[0] < 0:
        raise ValueError("Validation exceeds the work bound")


def _bound_value(value: Any, budget: list[int], *, depth: int = 0) -> None:
    _spend(budget)
    if depth > MAX_JSON_DEPTH:
        raise ValueError("JSON exceeds the depth bound")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Nonfinite JSON values are unsupported")
    if isinstance(value, dict):
        for item in value.values():
            _bound_value(item, budget, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            _bound_value(item, budget, depth=depth + 1)


def validate_schema(schema: Any, *, strict: bool) -> None:
    try:
        encoded = json.dumps(schema, allow_nan=False).encode()
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("Invalid schema") from exc
    if len(encoded) > MAX_SCHEMA_BYTES:
        raise ValueError("Schema exceeds the byte bound")
    _check_schema(schema, strict=strict, depth=0, budget=[MAX_SCHEMA_NODES])
    if schema.get("type") != "object":
        raise ValueError("Root schema must be an object")


def _check_schema(schema: Any, *, strict: bool, depth: int, budget: list[int]) -> None:
    _spend(budget)
    if depth > MAX_SCHEMA_DEPTH or not isinstance(schema, dict):
        raise ValueError("Schema exceeds the depth bound or has an invalid shape")
    if set(schema) - _KEYWORDS or schema.get("type") not in _TYPES:
        raise ValueError("Unsupported schema keyword or type")
    for label in ("title", "description"):
        if label in schema and not isinstance(schema[label], str):
            raise ValueError("Schema labels must be strings")
    enum = schema.get("enum")
    if enum is not None:
        if not isinstance(enum, list) or not 1 <= len(enum) <= 128:
            raise ValueError("Schema enum exceeds its bound")
        for value in enum:
            _validate_value(value, {"type": schema["type"]}, budget)
    kind = schema["type"]
    if kind == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if (
            not isinstance(properties, dict)
            or not isinstance(required, list)
            or any(not isinstance(name, str) or name not in properties for name in required)
            or len(set(required)) != len(required)
            or not isinstance(schema.get("additionalProperties", True), bool)
            or "items" in schema
        ):
            raise ValueError("Invalid object schema")
        if strict and (
            schema.get("additionalProperties") is not False or set(required) != set(properties)
        ):
            raise ValueError("Strict objects require all properties and no additional properties")
        for child in properties.values():
            _check_schema(child, strict=strict, depth=depth + 1, budget=budget)
    elif kind == "array":
        if (
            set(schema) & {"properties", "required", "additionalProperties"}
            or "items" not in schema
        ):
            raise ValueError("Arrays require an items schema")
        _check_schema(schema["items"], strict=strict, depth=depth + 1, budget=budget)
    elif set(schema) & {"properties", "required", "additionalProperties", "items"}:
        raise ValueError("Schema keywords do not apply to this type")


def validate_value(value: Any, schema: dict[str, Any]) -> None:
    _validate_value(value, schema, [MAX_VALIDATION_WORK])


def _validate_value(value: Any, schema: dict[str, Any], budget: list[int]) -> None:
    _spend(budget)
    kind = schema["type"]
    valid = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }[kind]
    if not valid or (isinstance(value, float) and not math.isfinite(value)):
        raise ValueError("Generated value does not match its schema type")
    if "enum" in schema and not any(
        type(value) is type(item) and value == item for item in schema["enum"]
    ):
        raise ValueError("Generated value does not match its schema enum")
    if isinstance(value, dict):
        if any(key not in value for key in schema.get("required", [])):
            raise ValueError("Generated object is missing required properties")
        properties = schema.get("properties", {})
        for key, item in value.items():
            _spend(budget)
            if key in properties:
                _validate_value(item, properties[key], budget)
            elif schema.get("additionalProperties") is False:
                raise ValueError("Generated object has additional properties")
    elif isinstance(value, list) and "items" in schema:
        for item in value:
            _validate_value(item, schema["items"], budget)
