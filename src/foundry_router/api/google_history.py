"""Signed structural projection; ordinary tool/media/history validation is still required."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NoReturn, cast

from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.api.adapters.google_tools import request_context
from foundry_router.api.google_state import (
    ProviderStateError,
    canonical_bytes,
    check_state_deadline,
    history_digests,
)

if TYPE_CHECKING:
    from foundry_router.config.google_features import GoogleFeatureProfile

STATE_FIELD = "foundry_provider_state"
_SIGNED_ID_BYTES = 128


def _reject() -> NoReturn:
    raise ProviderStateError("Invalid provider state")


def _identity(value: Any) -> None:
    if not isinstance(value, str) or not value:
        _reject()
    try:
        length = len(value.encode("utf-8"))
    except UnicodeError:
        _reject()
    if length > _SIGNED_ID_BYTES:
        _reject()


def project_item(item: Any) -> dict[str, Any]:
    """Preserve accepted content exactly; normalize only type/status defaults."""
    if not isinstance(item, dict):
        _reject()
    kind = item.get("type", "message")
    if kind == "message":
        allowed = {"type", "id", "role", "content", "status"}
        if item.get("role") == "assistant":
            allowed.add(STATE_FIELD)
            if not {"type", "id", "status"} <= item.keys():
                _reject()
            _identity(item["id"])
            content = item.get("content")
            if (
                not isinstance(content, list)
                or len(content) != 1
                or not isinstance(content[0], dict)
                or set(content[0]) != {"type", "text", "annotations"}
                or content[0]["type"] != "output_text"
                or not isinstance(content[0]["text"], str)
                or not content[0]["text"]
                or content[0]["annotations"] != []
            ):
                _reject()
        elif not isinstance(item.get("role"), str) or item["role"] not in {
            "user",
            "system",
            "developer",
        }:
            _reject()
        if "content" not in item or not isinstance(item["content"], (str, list)):
            _reject()
    elif kind == "function_call":
        allowed = {"type", "id", "call_id", "name", "arguments", "status", STATE_FIELD}
        if not {"type", "id", "call_id", "name", "arguments", "status"} <= item.keys():
            _reject()
        for name in ("id", "call_id", "name"):
            _identity(item[name])
        if not isinstance(item["arguments"], str):
            _reject()
    elif kind == "function_call_output":
        allowed = {"type", "id", "call_id", "output", "status"}
        if "call_id" not in item or not isinstance(item.get("output"), str):
            _reject()
        _identity(item["call_id"])
    else:
        _reject()
    if set(item) - allowed or item.get("status", "completed") != "completed":
        _reject()
    if "id" in item:
        _identity(item["id"])
    projected = {name: value for name, value in item.items() if name != STATE_FIELD}
    projected["type"] = kind
    projected["status"] = "completed"
    # JSON round trip creates an owned snapshot without retaining caller-owned objects.
    return cast(
        "dict[str, Any]", load_bounded_json(canonical_bytes(projected).decode(), max_bytes=2097152)
    )


def project_history(
    body: dict[str, Any], *, deadline: float | None = None
) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    history = body.get("input")
    if not isinstance(history, list) or not 1 <= len(history) <= 256:
        _reject()
    projected = []
    for item in history:
        check_state_deadline(deadline)
        projected.append(project_item(item))
    return tuple(projected), history_digests(projected)


def carrier_tokens(body: dict[str, Any]) -> tuple[str, ...]:
    """Count every wrapper occurrence before any decryption; dedupe work separately."""
    negotiation = body.get(STATE_FIELD)
    if negotiation != {"version": 1} or type(negotiation.get("version")) is not int:
        _reject()
    history = body.get("input")
    if not isinstance(history, list) or not 1 <= len(history) <= 256:
        _reject()
    tokens = []
    total = 0
    for item in history:
        if not isinstance(item, dict):
            _reject()
        signed = item.get("type") == "function_call" or item.get("role") == "assistant"
        carrier = item.get(STATE_FIELD)
        if signed:
            if (
                not isinstance(carrier, dict)
                or set(carrier) != {"version", "token"}
                or type(carrier["version"]) is not int
                or carrier["version"] != 1
                or not isinstance(carrier["token"], str)
                or not 1 <= len(carrier["token"]) <= 131072
                or not carrier["token"].isascii()
            ):
                _reject()
            total += len(canonical_bytes(carrier, max_bytes=131200))
            tokens.append(carrier["token"])
        elif STATE_FIELD in item:
            _reject()
    if total > 524288 or len(set(tokens)) > 16:
        _reject()
    return tuple(tokens)


def project_context(body: dict[str, Any], profile: GoogleFeatureProfile) -> dict[str, Any]:
    """Bind every signed-v1 generation setting while permitting transport/budget changes."""
    allowed = {
        "model",
        "input",
        "instructions",
        "tools",
        "tool_choice",
        "parallel_tool_calls",
        "text",
        "stream",
        "max_output_tokens",
        "metadata",
        STATE_FIELD,
    }
    if set(body) - allowed or not isinstance(body.get("instructions", ""), str):
        _reject()
    metadata = body.get("metadata", {})
    if not isinstance(metadata, dict) or len(canonical_bytes(metadata, max_bytes=128)) > 128:
        _reject()
    try:
        context = request_context(body, profile)
    except (ValueError, TypeError, RecursionError):
        _reject()
    return {
        "instructions": body.get("instructions", ""),
        "tools": list(context.tools.values()),
        "tool_choice": context.choice,
        "parallel_tool_calls": context.parallel,
        "text_format": context.text_format,
    }
