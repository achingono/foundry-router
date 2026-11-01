"""Bounded inspection of Responses API bodies without changing streamed bytes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .errors import ProtocolError

MAX_INSPECTED_RESPONSE_BYTES = 1_048_576
MAX_SSE_EVENT_BYTES = 65_536
MAX_TOKEN_COUNT = 1_000_000_000
HTTP_OK = 200
COMPLETED_EVENT = "response.completed"
FAILED_EVENTS = frozenset({"error", "response.failed", "response.incomplete"})


@dataclass(frozen=True, slots=True)
class ResponseEvidence:
    case_id: str
    status_code: int
    response_sha256: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    issued_utc_ns: int
    completed: bool
    clean_eof: bool


@dataclass(frozen=True, slots=True)
class ResponseLimits:
    max_input_tokens: int
    max_output_tokens: int
    max_response_bytes: int = MAX_INSPECTED_RESPONSE_BYTES
    max_event_bytes: int = MAX_SSE_EVENT_BYTES


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("response JSON contains duplicate fields")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise ProtocolError("response JSON contains a non-finite number")


def _parse_json_object(encoded: bytes) -> dict[str, object]:
    try:
        value = json.loads(
            encoded.decode("utf-8"),
            object_pairs_hook=_object_pairs,
            parse_constant=_reject_constant,
        )
    except ProtocolError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise ProtocolError("response body is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ProtocolError("response JSON must be an object")
    return value


def _token_count(usage: object, key: str, *, maximum: int) -> int:
    if not isinstance(usage, dict):
        raise ProtocolError("response usage is missing")
    value = usage.get(key)
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= maximum
        or value > MAX_TOKEN_COUNT
    ):
        raise ProtocolError(f"response {key} is invalid or exceeds its approved bound")
    return value


def _parse_sse_fields(frame: bytes) -> tuple[str | None, list[str]]:
    if b"\r" in frame.replace(b"\r\n", b""):
        raise ProtocolError("SSE event has invalid line endings")
    try:
        lines = frame.replace(b"\r\n", b"\n").decode("utf-8").split("\n")
    except UnicodeDecodeError as exc:
        raise ProtocolError("SSE event is not valid UTF-8") from exc
    event_name: str | None = None
    data_lines: list[str] = []
    for line in lines:
        if not line or line.startswith(":"):
            continue
        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if field == "event":
            if event_name is not None:
                raise ProtocolError("SSE event name is duplicated")
            event_name = value
        elif field == "data":
            data_lines.append(value)
        else:
            raise ProtocolError("unsupported SSE field")
    return event_name, data_lines


class ResponseInspector:
    """Inspect one HTTP 200 response while allowing the caller to pass bytes through."""

    def __init__(
        self,
        *,
        case_id: str,
        status_code: int,
        streaming: bool,
        limits: ResponseLimits,
    ) -> None:
        if not case_id or not case_id.isascii():
            raise ProtocolError("response case ID is invalid")
        if status_code != HTTP_OK:
            raise ProtocolError("only HTTP 200 responses may be inspected as successful")
        if not 0 < limits.max_input_tokens <= MAX_TOKEN_COUNT:
            raise ProtocolError("input-token inspection bound is invalid")
        if not 0 < limits.max_output_tokens <= MAX_TOKEN_COUNT:
            raise ProtocolError("output-token inspection bound is invalid")
        if not 0 < limits.max_response_bytes <= MAX_INSPECTED_RESPONSE_BYTES:
            raise ProtocolError("response byte limit is invalid")
        if not 0 < limits.max_event_bytes <= MAX_SSE_EVENT_BYTES:
            raise ProtocolError("SSE event byte limit is invalid")
        self._case_id = case_id
        self._status_code = status_code
        self._streaming = streaming
        self._max_input_tokens = limits.max_input_tokens
        self._max_output_tokens = limits.max_output_tokens
        self._max_response_bytes = limits.max_response_bytes
        self._max_event_bytes = limits.max_event_bytes
        self._body = bytearray()
        self._event_buffer = bytearray()
        self._response_hash = hashlib.sha256()
        self._response_bytes = 0
        self._completed_usage: tuple[int, int, int] | None = None
        self._done = False
        self._finished = False

    def feed(self, chunk: bytes) -> bytes:
        """Return the exact input chunk while inspecting it under strict size bounds."""
        if self._finished:
            raise ProtocolError("response data arrived after EOF")
        try:
            return self._feed(chunk)
        except ProtocolError:
            self._finished = True
            raise

    def _feed(self, chunk: bytes) -> bytes:
        if not isinstance(chunk, bytes):
            raise ProtocolError("response chunk must be bytes")
        self._response_bytes += len(chunk)
        if self._response_bytes > self._max_response_bytes:
            raise ProtocolError("response exceeds the approved byte limit")
        self._response_hash.update(chunk)
        if self._streaming:
            self._event_buffer.extend(chunk)
            self._consume_complete_events()
            if len(self._event_buffer) > self._max_event_bytes:
                raise ProtocolError("SSE event exceeds the approved byte limit")
        else:
            self._body.extend(chunk)
        return chunk

    def finish(self, *, issued_utc_ns: int) -> ResponseEvidence:
        """Require one completed response and a clean HTTP message EOF."""
        if self._finished:
            raise ProtocolError("response EOF was already recorded")
        self._finished = True
        if issued_utc_ns <= 0:
            raise ProtocolError("response witness issue time is invalid")
        if self._streaming:
            if self._event_buffer:
                raise ProtocolError("SSE stream ended with an incomplete event")
            usage = self._completed_usage
        else:
            response = _parse_json_object(bytes(self._body))
            usage = self._usage_from_completed_response(response)
        if usage is None:
            raise ProtocolError("response did not contain exactly one completed event")
        return ResponseEvidence(
            case_id=self._case_id,
            status_code=self._status_code,
            response_sha256=self._response_hash.hexdigest(),
            input_tokens=usage[0],
            output_tokens=usage[1],
            total_tokens=usage[2],
            issued_utc_ns=issued_utc_ns,
            completed=True,
            clean_eof=True,
        )

    def _consume_complete_events(self) -> None:
        while True:
            delimiter, delimiter_size = _find_sse_delimiter(self._event_buffer)
            if delimiter < 0:
                return
            if delimiter > self._max_event_bytes:
                raise ProtocolError("SSE event exceeds the approved byte limit")
            frame = bytes(self._event_buffer[:delimiter])
            del self._event_buffer[: delimiter + delimiter_size]
            if frame:
                self._consume_event(frame)

    def _consume_event(self, frame: bytes) -> None:
        event_name, data_lines = _parse_sse_fields(frame)
        if event_name in FAILED_EVENTS:
            raise ProtocolError("provider reported a failed or incomplete response")
        if not data_lines:
            return
        data = "\n".join(data_lines)
        if data == "[DONE]":
            if self._completed_usage is None or self._done or event_name is not None:
                raise ProtocolError("SSE DONE marker is misplaced or duplicated")
            self._done = True
            return
        if self._completed_usage is not None or self._done:
            raise ProtocolError("SSE data arrived after the terminal completion event")
        response = _parse_json_object(data.encode("utf-8"))
        payload_type = response.get("type")
        if payload_type is not None and not isinstance(payload_type, str):
            raise ProtocolError("SSE payload type is invalid")
        if event_name is not None and payload_type is not None and event_name != payload_type:
            raise ProtocolError("SSE event type does not match its event name")
        kind = payload_type if payload_type is not None else event_name
        if kind in FAILED_EVENTS or "error" in response:
            raise ProtocolError("provider reported a failed or incomplete response")
        if kind != COMPLETED_EVENT:
            return
        if payload_type != COMPLETED_EVENT:
            raise ProtocolError("completed SSE payload lacks the terminal type")
        self._completed_usage = self._usage_from_completed_response(response)

    def _usage_from_completed_response(self, response: dict[str, object]) -> tuple[int, int, int]:
        if self._streaming:
            response_value = response.get("response")
            if not isinstance(response_value, dict):
                raise ProtocolError("completed SSE event lacks a response object")
            response = response_value
        if response.get("status") != "completed":
            raise ProtocolError("response status is not completed")
        usage = response.get("usage")
        input_tokens = _token_count(
            usage,
            "input_tokens",
            maximum=self._max_input_tokens,
        )
        output_tokens = _token_count(
            usage,
            "output_tokens",
            maximum=self._max_output_tokens,
        )
        total_tokens = _token_count(usage, "total_tokens", maximum=MAX_TOKEN_COUNT)
        if total_tokens != input_tokens + output_tokens:
            raise ProtocolError("response total_tokens does not match input and output")
        return input_tokens, output_tokens, total_tokens


def _find_sse_delimiter(buffer: bytearray) -> tuple[int, int]:
    candidates: list[tuple[int, int]] = []
    for delimiter in (b"\r\n\r\n", b"\n\n"):
        position = buffer.find(delimiter)
        if position >= 0:
            candidates.append((position, len(delimiter)))
    if not candidates:
        return -1, 0
    return min(candidates, key=lambda item: item[0])
