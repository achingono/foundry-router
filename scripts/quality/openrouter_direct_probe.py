"""Bounded OpenRouter direct envelope probes; never router traffic.

Test-only diagnostic tooling. Sends at most one request per fixed model,
straight at the provider, to capture envelope STRUCTURE (field names, finish
reasons, content classification with byte lengths, usage integers). Content
values, error bodies, and credentials are never persisted, printed, or logged.
Each model is probed at most once ever: existing outcomes are resumed, never
replayed, and results live in one canonical file with atomic writes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
from zen_openrouter_live_budget import locked, write_atomic

from foundry_router.api.adapters.google_schema import load_bounded_json

ROOT = Path(__file__).resolve().parents[2]
STAGE_DIR = ROOT / "docs/plans/zen-openrouter-live-verification"
RESULTS_NAME = "results-probe.json"
IDENTITY_SUFFIX = ".identity"
MAX_RESULTS_BYTES = 65536

PROBE_URL = "https://openrouter.ai/api/v1/chat/completions"
PROMPT = "Reply with the word ready."
MAX_COMPLETION_TOKENS = 128
PROBE_TIMEOUT_SECONDS = 120
MAX_BODY_BYTES = 1024 * 1024
MAX_FRAME_BYTES = 256 * 1024
MAX_REQUEST_BYTES = 4096

PROBES: tuple[tuple[str, str], ...] = (
    ("probe-gemma", "google/gemma-4-26b-a4b-it:free"),
    ("probe-openai", "openai/gpt-4o-mini"),
    ("probe-anthropic", "anthropic/claude-haiku-4.5"),
)

STREAM_PROBES: tuple[tuple[str, str], ...] = (
    ("probe-gemma-stream", "google/gemma-4-26b-a4b-it:free"),
    ("probe-openai-stream", "openai/gpt-4o-mini"),
    ("probe-anthropic-stream", "anthropic/claude-haiku-4.5"),
)

ALL_PROBE_IDS = {probe for probe, _ in (*PROBES, *STREAM_PROBES)}
PROBE_MODELS = dict((*PROBES, *STREAM_PROBES))
MAX_STREAM_EVENTS = 4096

CONTENT_KINDS = {
    "missing",
    "empty",
    "whitespace",
    "text",
    "refusal",
    "tool_calls",
    "list-parts",
    "other",
}

FINISH_REASONS = {"stop", "length", "tool_calls", "content_filter"}

MAX_FIELD_NAMES = 64
MAX_FIELD_NAME_BYTES = 128
HTTP_STATUS_MIN = 100
HTTP_STATUS_MAX = 599
MAX_FINISH_REASON_BYTES = 1024
MAX_ATTEMPT_BYTES = 8192

ERROR_CATEGORIES = {
    "transport_failure",
    "encoded_response",
    "response_bound_exceeded",
    "malformed_response",
    "request_bound_exceeded",
}

EXPECTED_TOP_FIELDS = {
    "id",
    "choices",
    "created",
    "model",
    "object",
    "system_fingerprint",
    "usage",
}


def build_body(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
    }


def _strict_ints(payload: Any, *names: str) -> tuple[int, ...] | None:
    if not isinstance(payload, dict):
        return None
    values = []
    for name in names:
        value = payload.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        values.append(value)
    return tuple(values)


def _bounded_names(values: Any) -> tuple[list[str], bool]:
    """Field names only when bounded; otherwise invalid metadata without values."""
    if not isinstance(values, list):
        return [], False
    names = [value for value in values if isinstance(value, str)]
    if (
        len(names) != len(values)
        or len(names) > MAX_FIELD_NAMES
        or any(len(name.encode("utf-8", "ignore")) > MAX_FIELD_NAME_BYTES for name in names)
    ):
        return [], False
    return sorted(names), True


def classify_envelope(payload: Any) -> dict[str, Any]:  # noqa: PLR0911, PLR0912, PLR0915 -- fixed structural checklist
    """Structural summary only; never returns content values."""
    summary: dict[str, Any] = {
        "top_fields": [],
        "extra_top_fields": [],
        "finish_reason": None,
        "unexpected_finish_reason": False,
        "finish_reason_length": None,
        "message_fields": [],
        "extra_message_fields": [],
        "content_kind": "missing",
        "content_length": 0,
        "usage": None,
        "usage_valid": False,
        "metadata_valid": True,
    }
    if not isinstance(payload, dict):
        summary["content_kind"] = "other"
        summary["metadata_valid"] = False
        return summary
    top_fields, top_ok = _bounded_names(sorted(str(key) for key in payload))
    summary["top_fields"] = top_fields
    summary["extra_top_fields"] = sorted(set(top_fields) - EXPECTED_TOP_FIELDS)
    if not top_ok:
        summary["metadata_valid"] = False
        return summary
    choices = payload.get("choices")
    choice = choices[0] if isinstance(choices, list) and len(choices) == 1 else None
    if not isinstance(choice, dict):
        summary["metadata_valid"] = False
        return summary
    finish = choice.get("finish_reason")
    if finish is None:
        pass
    elif isinstance(finish, str) and finish in FINISH_REASONS:
        summary["finish_reason"] = finish
    elif isinstance(finish, str):
        # Arbitrary provider strings are never persisted or displayed.
        summary["unexpected_finish_reason"] = True
        summary["finish_reason_length"] = len(finish.encode("utf-8", "ignore"))
    else:
        summary["metadata_valid"] = False
        return summary
    message = choice.get("message")
    if not isinstance(message, dict):
        summary["metadata_valid"] = False
        return summary
    message_fields, message_ok = _bounded_names(sorted(str(key) for key in message))
    summary["message_fields"] = message_fields
    summary["extra_message_fields"] = sorted(
        set(message_fields) - {"role", "content", "refusal", "tool_calls"}
    )
    if not message_ok:
        summary["metadata_valid"] = False
        return summary
    refusal = message.get("refusal")
    calls = message.get("tool_calls")
    content = message.get("content")
    if isinstance(refusal, str) and refusal:
        summary["content_kind"] = "refusal"
        summary["content_length"] = len(refusal.encode("utf-8", "ignore"))
    elif isinstance(calls, list) and calls:
        summary["content_kind"] = "tool_calls"
    elif content is None:
        summary["content_kind"] = "missing"
    elif isinstance(content, str):
        summary["content_length"] = len(content.encode("utf-8", "ignore"))
        if not content:
            summary["content_kind"] = "empty"
        elif not content.strip():
            summary["content_kind"] = "whitespace"
        else:
            summary["content_kind"] = "text"
    elif isinstance(content, list):
        summary["content_kind"] = "list-parts"
        summary["content_length"] = len(
            json.dumps(content, sort_keys=True).encode("utf-8", "ignore")
        )
    else:
        summary["content_kind"] = "other"
    usage = payload.get("usage")
    counts = _strict_ints(usage, "prompt_tokens", "completion_tokens", "total_tokens")
    if counts is not None:
        summary["usage"] = {
            "prompt_tokens": counts[0],
            "completion_tokens": counts[1],
            "total_tokens": counts[2],
        }
        summary["usage_valid"] = counts[2] == counts[0] + counts[1]
    return summary


RESULT_KEYS = {
    "probe_id",
    "model",
    "kind",
    "http_status",
    "dispatched",
    "elapsed_seconds",
    "structure",
    "error_category",
}

STRUCTURE_KEYS = {
    "top_fields",
    "extra_top_fields",
    "finish_reason",
    "unexpected_finish_reason",
    "finish_reason_length",
    "message_fields",
    "extra_message_fields",
    "content_kind",
    "content_length",
    "usage",
    "usage_valid",
    "metadata_valid",
}


def _bounded_name_list(values: Any) -> bool:
    return (
        isinstance(values, list)
        and len(values) <= MAX_FIELD_NAMES
        and all(
            isinstance(value, str) and len(value.encode("utf-8", "ignore")) <= MAX_FIELD_NAME_BYTES
            for value in values
        )
    )


def validate_probe_result(result: Any) -> None:  # noqa: PLR0912 -- bounded evidence schema
    """Bounded schema for persisted and displayed probe outcomes."""
    if not isinstance(result, dict) or set(result) != RESULT_KEYS:
        raise ValueError("Invalid probe result")
    probe_id = result.get("probe_id")
    if probe_id not in PROBE_MODELS or result.get("model") != PROBE_MODELS[probe_id]:
        raise ValueError("Invalid probe binding")
    status = result.get("http_status")
    if status is not None and (
        type(status) is not int or not HTTP_STATUS_MIN <= status <= HTTP_STATUS_MAX
    ):
        raise ValueError("Invalid probe status")
    if type(result.get("dispatched")) is not bool:
        raise ValueError("Invalid probe dispatch flag")
    elapsed = result.get("elapsed_seconds")
    if (
        type(elapsed) not in {int, float}
        or isinstance(elapsed, bool)
        or not 0 <= elapsed <= PROBE_TIMEOUT_SECONDS + 60
    ):
        raise ValueError("Invalid probe elapsed time")
    if result.get("error_category") is not None and result["error_category"] not in (
        ERROR_CATEGORIES | {None}
    ):
        raise ValueError("Invalid probe error category")
    if result.get("kind") not in {"nonstream", "stream"}:
        raise ValueError("Invalid probe kind")
    structure = result.get("structure")
    if structure is None:
        return
    if result["kind"] == "stream":
        _validate_stream_structure(structure)
        if len(json.dumps(result).encode("utf-8")) > MAX_ATTEMPT_BYTES:
            raise ValueError("Invalid probe result size")
        return
    if not isinstance(structure, dict) or set(structure) != STRUCTURE_KEYS:
        raise ValueError("Invalid probe structure")
    if not _bounded_name_list(structure.get("top_fields")) or not _bounded_name_list(
        structure.get("extra_top_fields")
    ):
        raise ValueError("Invalid probe field names")
    if not _bounded_name_list(structure.get("message_fields")) or not _bounded_name_list(
        structure.get("extra_message_fields")
    ):
        raise ValueError("Invalid probe field names")
    finish = structure.get("finish_reason")
    if finish is not None and finish not in FINISH_REASONS:
        raise ValueError("Invalid probe finish reason")
    if type(structure.get("unexpected_finish_reason")) is not bool:
        raise ValueError("Invalid probe finish flag")
    length = structure.get("finish_reason_length")
    if length is not None and (
        type(length) is not int or not 0 <= length <= MAX_FINISH_REASON_BYTES
    ):
        raise ValueError("Invalid probe finish length")
    if structure.get("content_kind") not in CONTENT_KINDS:
        raise ValueError("Invalid probe content kind")
    content_length = structure.get("content_length")
    if type(content_length) is not int or not 0 <= content_length <= MAX_BODY_BYTES:
        raise ValueError("Invalid probe content length")
    usage = structure.get("usage")
    if usage is not None and (
        not isinstance(usage, dict)
        or set(usage) != {"prompt_tokens", "completion_tokens", "total_tokens"}
        or any(type(usage[name]) is not int or usage[name] < 0 for name in usage)
    ):
        raise ValueError("Invalid probe usage")
    if (
        type(structure.get("usage_valid")) is not bool
        or type(structure.get("metadata_valid")) is not bool
    ):
        raise ValueError("Invalid probe validity flags")
    if len(json.dumps(result).encode("utf-8")) > MAX_ATTEMPT_BYTES:
        raise ValueError("Invalid probe result size")


def _validate_stream_structure(structure: Any) -> None:
    if not isinstance(structure, dict) or set(structure) != STRUCTURE_STREAM_KEYS:
        raise ValueError("Invalid probe structure")
    if (
        type(structure.get("event_count")) is not int
        or not 0 <= structure["event_count"] <= MAX_STREAM_EVENTS
    ):
        raise ValueError("Invalid probe event count")
    key_sets = structure.get("delta_key_sets")
    if (
        not isinstance(key_sets, list)
        or len(key_sets) > MAX_STREAM_EVENTS
        or any(
            not isinstance(entry, list)
            or len(entry) > MAX_FIELD_NAMES
            or any(
                not isinstance(name, str)
                or len(name.encode("utf-8", "ignore")) > MAX_FIELD_NAME_BYTES
                for name in entry
            )
            for entry in key_sets
        )
    ):
        raise ValueError("Invalid probe delta keys")
    if type(structure.get("reasoning_delta_seen")) is not bool:
        raise ValueError("Invalid probe reasoning flag")
    for name in ("reasoning_delta_bytes", "text_delta_bytes"):
        value = structure.get(name)
        if type(value) is not int or not 0 <= value <= MAX_BODY_BYTES:
            raise ValueError("Invalid probe delta bytes")
    reasons = structure.get("finish_reasons")
    if (
        not isinstance(reasons, list)
        or len(reasons) > MAX_STREAM_EVENTS
        or any(reason not in FINISH_REASONS for reason in reasons)
    ):
        raise ValueError("Invalid probe finish reasons")
    for name in ("unexpected_finish_seen", "done_seen", "truncated"):
        if type(structure.get(name)) is not bool:
            raise ValueError("Invalid probe stream flag")
    usage = structure.get("usage")
    if usage is not None and (
        not isinstance(usage, dict)
        or set(usage) != {"prompt_tokens", "completion_tokens", "total_tokens"}
        or any(type(usage[name]) is not int or usage[name] < 0 for name in usage)
    ):
        raise ValueError("Invalid probe usage")
    if (
        type(structure.get("usage_valid")) is not bool
        or type(structure.get("metadata_valid")) is not bool
    ):
        raise ValueError("Invalid probe validity flags")


STRUCTURE_STREAM_KEYS = {
    "event_count",
    "delta_key_sets",
    "reasoning_delta_seen",
    "reasoning_delta_bytes",
    "text_delta_bytes",
    "finish_reasons",
    "unexpected_finish_seen",
    "done_seen",
    "truncated",
    "usage",
    "usage_valid",
    "metadata_valid",
}


def _split_sse_frame(buffer: bytes) -> tuple[bytes | None, bytes]:
    """Earliest event boundary; same semantics as the router's splitter."""
    candidates = [(buffer.find(d), d) for d in (b"\r\n\r\n", b"\n\n")]
    found = [(index, delimiter) for index, delimiter in candidates if index >= 0]
    if not found:
        return None, buffer
    index, delimiter = min(found)
    return buffer[: index + len(delimiter)], buffer[index + len(delimiter) :]


def _stream_event_payload(frame: bytes) -> dict[str, Any] | None:
    """One parsed data event, or None for keepalives, [DONE], and malformed frames."""
    text = frame.decode("utf-8", "ignore")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("data:"):
            continue
        data = stripped[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            event = load_bounded_json(data, max_bytes=MAX_FRAME_BYTES)
        except (ValueError, TypeError):
            return None
        if isinstance(event, dict):
            return event
    return None


def _serialized_size(data: Any) -> int:
    return len(json.dumps(data).encode("utf-8"))


def _check_envelope_size(data: Any) -> None:
    if _serialized_size(data) > MAX_RESULTS_BYTES:
        raise ValueError("Probe record exceeds bound")


def new_stream_state() -> dict[str, Any]:
    return {
        "event_count": 0,
        "delta_key_sets": [],
        "reasoning_delta_seen": False,
        "reasoning_delta_bytes": 0,
        "text_delta_bytes": 0,
        "finish_reasons": [],
        "unexpected_finish_seen": False,
        "done_seen": False,
        "truncated": False,
        "usage": None,
        "usage_valid": False,
        "metadata_valid": True,
    }


def classify_stream_frame(frame: bytes, state: dict[str, Any]) -> None:  # noqa: PLR0912 -- fixed per-frame checklist
    """Fold one raw frame into structural stream state; values never retained."""
    if len(frame) > MAX_FRAME_BYTES:
        state["metadata_valid"] = False
        return
    text = frame.decode("utf-8", "ignore")
    if "[DONE]" in text:
        state["done_seen"] = True
    event = _stream_event_payload(frame)
    if event is None:
        return
    if state["event_count"] >= MAX_STREAM_EVENTS:
        state["metadata_valid"] = False
        return
    state["event_count"] += 1
    choices = event.get("choices")
    choice = choices[0] if isinstance(choices, list) and len(choices) == 1 else None
    usage = event.get("usage")
    if usage is not None:
        counts = _strict_ints(usage, "prompt_tokens", "completion_tokens", "total_tokens")
        if counts is None:
            state["metadata_valid"] = False
        else:
            state["usage"] = {
                "prompt_tokens": counts[0],
                "completion_tokens": counts[1],
                "total_tokens": counts[2],
            }
            state["usage_valid"] = counts[2] == counts[0] + counts[1]
    if not isinstance(choice, dict):
        if choices:
            state["metadata_valid"] = False
        return
    delta = choice.get("delta")
    if isinstance(delta, dict):
        names, ok = _bounded_names(sorted(str(key) for key in delta))
        if not ok:
            state["metadata_valid"] = False
        elif names not in state["delta_key_sets"]:
            state["delta_key_sets"].append(names)
        reasoning = delta.get("reasoning")
        if isinstance(reasoning, str):
            state["reasoning_delta_seen"] = True
            state["reasoning_delta_bytes"] += len(reasoning.encode("utf-8", "ignore"))
        content = delta.get("content")
        if isinstance(content, str):
            state["text_delta_bytes"] += len(content.encode("utf-8", "ignore"))
    finish = choice.get("finish_reason")
    if finish is None:
        pass
    elif isinstance(finish, str) and finish in FINISH_REASONS:
        if finish not in state["finish_reasons"]:
            state["finish_reasons"].append(finish)
    elif isinstance(finish, str):
        state["unexpected_finish_seen"] = True
    else:
        state["metadata_valid"] = False


def _check_envelope_size(data: Any) -> None:
    if _serialized_size(data) > MAX_RESULTS_BYTES:
        raise ValueError("Probe record exceeds bound")


def load_probe_results(path: Path, *, data: Any = None) -> dict[str, Any]:
    if data is None:
        if not path.exists():
            return {"probe": "openrouter-direct", "reserved": [], "attempts": []}
        if path.stat().st_size > MAX_RESULTS_BYTES:
            raise ValueError("Invalid probe results")
        data = load_bounded_json(path.read_text(), max_bytes=MAX_RESULTS_BYTES)
    if (
        not isinstance(data, dict)
        or set(data) != {"probe", "reserved", "attempts"}
        or data.get("probe") != "openrouter-direct"
        or not isinstance(data.get("reserved"), list)
        or not isinstance(data.get("attempts"), list)
    ):
        raise ValueError("Invalid probe results")
    _check_envelope_size(data)
    seen = set()
    allowed = {probe for probe, _ in (*PROBES, *STREAM_PROBES)}
    reserved = data["reserved"]
    if any(probe not in allowed for probe in reserved) or len(set(reserved)) != len(reserved):
        raise ValueError("Invalid probe reservations")
    for attempt in data["attempts"]:
        validate_probe_result(attempt)
        if attempt["probe_id"] in seen:
            raise ValueError("Duplicate probe result")
        seen.add(attempt["probe_id"])
    recorded = {attempt["probe_id"] for attempt in data["attempts"]}
    if any(probe not in recorded for probe in reserved):
        # A reservation without an outcome blocks replay pending review.
        raise ValueError("Unresolved probe reservation")
    if any(probe not in reserved for probe in recorded):
        # An outcome without a prior reservation is an impossible state.
        raise ValueError("Unreserved probe outcome")
    return data


def _identity_path(results_path: Path) -> Path:
    return results_path.with_name(results_path.name + IDENTITY_SUFFIX)


def ensure_probe_initialized(results_path: Path) -> None:
    """One-time durable initialization; missing initialized state refuses.

    The identity sidecar survives results loss: deleting results after a first
    initialization is detected and blocks instead of resetting the budget.
    """
    identity = _identity_path(results_path)
    if not results_path.exists() and not identity.exists():
        write_atomic(identity, {"probe": "openrouter-direct"})
        return
    if not results_path.exists() or not identity.exists():
        raise ValueError("Initialized probe state is missing")
    try:
        marker = load_bounded_json(identity.read_bytes().decode(), max_bytes=1024)
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError("Invalid probe identity") from exc
    if marker != {"probe": "openrouter-direct"}:
        raise ValueError("Invalid probe identity")


class _EntryMarker(httpx.AsyncBaseTransport):
    """Records transport entry: lack of headers does not prove zero egress."""

    def __init__(self, transport: httpx.AsyncBaseTransport):
        self.transport = transport
        self.entered = False

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.entered = True
        return await self.transport.handle_async_request(request)

    async def aclose(self) -> None:
        await self.transport.aclose()


async def run_probe(  # noqa: PLR0911 -- fixed outcome checklist
    probe_id: str, model: str, credential: str, transport: httpx.AsyncBaseTransport
) -> dict[str, Any]:
    """One bounded direct request; returns structural evidence only."""
    if PROBE_MODELS.get(probe_id) != model:
        raise ValueError("Probe/model binding mismatch")
    started = time.monotonic()
    result: dict[str, Any] = {
        "probe_id": probe_id,
        "model": model,
        "kind": "nonstream",
        "http_status": None,
        "dispatched": False,
        "elapsed_seconds": 0.0,
        "structure": None,
        "error_category": None,
    }

    def finish(category: str | None) -> dict[str, Any]:
        result["error_category"] = category
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        validate_probe_result(result)
        return result

    body = build_body(model)
    raw_body = json.dumps(body).encode()
    if len(raw_body) > MAX_REQUEST_BYTES:
        return finish("request_bound_exceeded")
    marker = _EntryMarker(transport)
    try:
        async with asyncio.timeout(PROBE_TIMEOUT_SECONDS):
            async with httpx.AsyncClient(
                transport=marker, timeout=PROBE_TIMEOUT_SECONDS, trust_env=False
            ) as client:
                # Stream so bounds apply while reading: headers mark dispatch,
                # raw identity bytes are counted as they arrive, and the
                # response closes on every exit path below.
                async with client.stream(
                    "POST",
                    PROBE_URL,
                    headers={
                        "authorization": "Bearer " + credential,
                        "accept-encoding": "identity",
                        "content-type": "application/json",
                    },
                    content=raw_body,
                ) as response:
                    result["dispatched"] = True
                    result["http_status"] = response.status_code
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        return finish("encoded_response")
                    if response.status_code != HTTPStatus.OK:
                        return finish(None)
                    chunks = bytearray()
                    try:
                        async for chunk in response.aiter_bytes():
                            if len(chunks) + len(chunk) > MAX_BODY_BYTES:
                                return finish("response_bound_exceeded")
                            chunks.extend(chunk)
                    except (OSError, RuntimeError, httpx.HTTPError, ValueError):
                        return finish("transport_failure")
    except (TimeoutError, OSError, RuntimeError, httpx.HTTPError, ValueError):
        # Transport entry may precede headers: preserve conservative dispatch
        # intent instead of reporting zero egress. Raised values carry no
        # trusted content; never persist them.
        result["dispatched"] = marker.entered
        return finish("transport_failure")
    try:
        payload = load_bounded_json(bytes(chunks).decode("utf-8"), max_bytes=MAX_BODY_BYTES)
    except (ValueError, UnicodeError):
        return finish("malformed_response")
    result["structure"] = classify_envelope(payload)
    return finish(None)


def build_stream_body(model: str) -> dict[str, Any]:
    body = build_body(model)
    body["stream"] = True
    body["stream_options"] = {"include_usage": True}
    return body


async def run_stream_probe(  # noqa: PLR0911, PLR0912 -- fixed outcome checklist
    probe_id: str, model: str, credential: str, transport: httpx.AsyncBaseTransport
) -> dict[str, Any]:
    """One bounded direct stream; returns structural evidence only."""
    if PROBE_MODELS.get(probe_id) != model:
        raise ValueError("Probe/model binding mismatch")
    started = time.monotonic()
    result: dict[str, Any] = {
        "probe_id": probe_id,
        "model": model,
        "kind": "stream",
        "http_status": None,
        "dispatched": False,
        "elapsed_seconds": 0.0,
        "structure": None,
        "error_category": None,
    }

    def finish(category: str | None) -> dict[str, Any]:
        result["error_category"] = category
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        validate_probe_result(result)
        return result

    body = build_stream_body(model)
    raw_body = json.dumps(body).encode()
    if len(raw_body) > MAX_REQUEST_BYTES:
        return finish("request_bound_exceeded")
    marker = _EntryMarker(transport)
    state = new_stream_state()
    try:
        async with asyncio.timeout(PROBE_TIMEOUT_SECONDS):
            async with httpx.AsyncClient(
                transport=marker, timeout=PROBE_TIMEOUT_SECONDS, trust_env=False
            ) as client:
                async with client.stream(
                    "POST",
                    PROBE_URL,
                    headers={
                        "authorization": "Bearer " + credential,
                        "accept-encoding": "identity",
                        "content-type": "application/json",
                    },
                    content=raw_body,
                ) as response:
                    result["dispatched"] = True
                    result["http_status"] = response.status_code
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        return finish("encoded_response")
                    if response.status_code != HTTPStatus.OK:
                        return finish(None)
                    observed = 0
                    pending = bytearray()
                    try:
                        async for chunk in response.aiter_bytes():
                            observed += len(chunk)
                            if observed > MAX_BODY_BYTES:
                                return finish("response_bound_exceeded")
                            pending.extend(chunk)
                            if len(pending) > MAX_FRAME_BYTES:
                                return finish("response_bound_exceeded")
                            while True:
                                event, rest = _split_sse_frame(bytes(pending))
                                if event is None:
                                    break
                                pending = bytearray(rest)
                                if len(event) > MAX_FRAME_BYTES:
                                    return finish("response_bound_exceeded")
                                classify_stream_frame(event, state)
                    except (OSError, RuntimeError, httpx.HTTPError, ValueError):
                        return finish("transport_failure")
                    if pending.strip():
                        state["truncated"] = True
    except (TimeoutError, OSError, RuntimeError, httpx.HTTPError, ValueError):
        result["dispatched"] = marker.entered
        return finish("transport_failure")
    result["structure"] = state
    return finish(None)


def execute_probes(
    *,
    stage_dir: Path | None = None,
    credential: str | None = None,
    transport_factory: Any = None,
) -> dict[str, Any]:
    """Probe each unrecorded model once; never replay recorded outcomes."""
    if not credential or not credential.strip():
        raise ValueError("Verification credential unavailable")
    # Resolve at call time so tests can isolate the directory.
    directory = stage_dir if stage_dir is not None else STAGE_DIR
    results_path = directory / "results-probe.json"
    with locked(directory / "stage"):
        ensure_probe_initialized(results_path)
        results = load_probe_results(results_path)
        recorded = {item["probe_id"] for item in results["attempts"]}
        factory = transport_factory or (
            lambda: httpx.AsyncHTTPTransport(trust_env=False, retries=0)
        )
        for probe_id, model in (*PROBES, *STREAM_PROBES):
            if probe_id in recorded:
                continue
            # Durably reserve the slot before egress; a crash or failed write
            # afterwards blocks replay pending review instead of resending.
            results["reserved"].append(probe_id)
            _check_envelope_size(results)
            write_atomic(results_path, results)
            runner = run_stream_probe if probe_id.endswith("-stream") else run_probe
            outcome = asyncio.run(runner(probe_id, model, credential, factory()))
            validate_probe_result(outcome)
            results["attempts"].append(outcome)
            load_probe_results(results_path, data=results)
            _check_envelope_size(results)
            write_atomic(results_path, results)
            recorded.add(probe_id)
        return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--openrouter-key-env", default="OPENROUTER_API_KEY")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status": "refused", "probes": 0}))
        return 2
    logging.disable(logging.CRITICAL)
    try:
        key = os.environ.get(args.openrouter_key_env, "")
        results = execute_probes(credential=key)
    except (OSError, ValueError, RuntimeError):
        print(json.dumps({"status": "refused_or_interrupted", "probes": "unknown"}))
        return 2
    summary = {}
    for item in results["attempts"]:
        structure = item["structure"] or {}
        entry = {
            "http_status": item["http_status"],
            "finish_reason": structure.get("finish_reason"),
            "content_kind": structure.get("content_kind"),
            "usage_valid": structure.get("usage_valid"),
            "error_category": item["error_category"],
        }
        if item.get("kind") == "stream":
            entry.update(
                {
                    "event_count": structure.get("event_count"),
                    "reasoning_delta_seen": structure.get("reasoning_delta_seen"),
                    "done_seen": structure.get("done_seen"),
                    "truncated": structure.get("truncated"),
                }
            )
        summary[item["probe_id"]] = entry
    print(json.dumps({"probe": "openrouter-direct", "results": summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
