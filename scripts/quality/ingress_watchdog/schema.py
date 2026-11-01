"""Strict canonical JSON used for signed watchdog objects."""

from __future__ import annotations

import json
from typing import cast

from .errors import ProtocolError

type JsonValue = bool | int | str | list[JsonValue] | dict[str, JsonValue] | None
MAX_SIGNED_OBJECT_BYTES = 64 * 1024
MAX_INTEGER = 2**63 - 1


def _validate_value(value: object, path: str = "$") -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        if not -MAX_INTEGER <= value <= MAX_INTEGER:
            raise ProtocolError(f"integer out of bounds at {path}")
        return
    if isinstance(value, str):
        try:
            value.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ProtocolError(f"non-ASCII string at {path}") from exc
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProtocolError(f"non-string key at {path}")
            try:
                key.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ProtocolError(f"non-ASCII key at {path}") from exc
            _validate_value(item, f"{path}.{key}")
        return
    raise ProtocolError(f"unsupported JSON value at {path}")


def canonical_json(value: object, *, max_bytes: int = MAX_SIGNED_OBJECT_BYTES) -> bytes:
    """Return one deterministic ASCII JSON encoding, rejecting floats and Unicode."""
    _validate_value(value)
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ProtocolError("value cannot be encoded as canonical JSON") from exc
    if len(encoded) > max_bytes:
        raise ProtocolError("canonical JSON exceeds the configured byte limit")
    return encoded


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_integer(raw: str) -> int:
    value = int(raw)
    if not -MAX_INTEGER <= value <= MAX_INTEGER:
        raise ProtocolError("JSON integer out of bounds")
    return value


def _reject_float(_: str) -> None:
    raise ProtocolError("floating-point JSON values are not permitted")


def _reject_constant(_: str) -> None:
    raise ProtocolError("non-standard JSON constants are not permitted")


def parse_canonical_json(
    encoded: bytes,
    *,
    max_bytes: int = MAX_SIGNED_OBJECT_BYTES,
) -> JsonValue:
    """Parse only bounded JSON whose bytes exactly match the canonical encoding."""
    if not encoded or len(encoded) > max_bytes:
        raise ProtocolError("JSON input is empty or exceeds the configured byte limit")
    try:
        value = json.loads(
            encoded.decode("ascii"),
            object_pairs_hook=_object_pairs,
            parse_int=_parse_integer,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except ProtocolError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise ProtocolError("invalid canonical JSON") from exc
    _validate_value(value)
    if canonical_json(value, max_bytes=max_bytes) != encoded:
        raise ProtocolError("JSON is not canonically encoded")
    return cast("JsonValue", value)


def require_exact_keys(value: object, required: set[str], *, label: str) -> dict[str, object]:
    """Require a JSON object with exactly the supplied key set."""
    if not isinstance(value, dict):
        raise ProtocolError(f"{label} must be an object")
    if set(value) != required:
        raise ProtocolError(f"{label} has missing or unknown fields")
    return value
