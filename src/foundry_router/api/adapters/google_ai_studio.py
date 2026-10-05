"""Google AI Studio compatibility adapter (Responses <-> Chat Completions).

First-release subset: text Responses, stateless text history, instructions,
streaming, usage normalization, and text embeddings. Unsupported fields fail
explicitly before any egress.

Vendor basis (verified 2026-10-05 against public docs):
- Base path ``https://generativelanguage.googleapis.com/v1beta/openai/`` with
  ``chat/completions`` and ``embeddings`` operations.
- Documented OpenAI-compat auth is ``Authorization: Bearer <GEMINI_API_KEY>``.
  The native ``x-goog-api-key`` header 400s on the compat surface in forum
  reports, so the backend client sends Bearer and strips both inbound.
- Token limit uses ``max_completion_tokens`` (``max_tokens`` legacy accepted
  upstream by OpenAI semantics; we send the former).
- Streaming usage requires ``stream_options: {"include_usage": true}``;
  usage arrives in a final chunk (possibly choices-empty) before ``[DONE]``.
- Chat finish reasons handled: ``stop`` (completed), ``length`` (incomplete
  max_output_tokens), ``content_filter`` (incomplete content_filter).
  Unknown reasons and malformed envelopes are sanitized protocol failures.
"""

from __future__ import annotations

import json
import math
import time
import uuid
from typing import Any

from foundry_router.api.adapters.base import (
    AdapterRejection,
    TranslatedError,
    TranslatedSuccess,
)

_ALLOWED_TOP_LEVEL = frozenset(
    {
        "model",
        "input",
        "instructions",
        "max_output_tokens",
        "temperature",
        "top_p",
        "stream",
        "store",
        "background",
        "include",
        "metadata",
    }
)
_ALLOWED_ROLES = frozenset({"system", "developer", "user", "assistant"})
_ALLOWED_PART_TYPES = frozenset({"input_text", "output_text", "text"})
_ALLOWED_FINISH_REASONS = frozenset({"stop", "length", "content_filter"})
_MAX_OUTPUT_TOKENS_MIN = 1
_MAX_OUTPUT_TOKENS_MAX = 128000

MAX_GOOGLE_EVENT_BYTES = 256 * 1024
MAX_GOOGLE_ASSEMBLED_TEXT_BYTES = 4 * 1024 * 1024
MAX_GOOGLE_SSE_BUFFER_BYTES = 1024 * 1024


def _rejection(message: str, code: str = "unsupported_parameter") -> AdapterRejection:
    return AdapterRejection(status_code=422, code=code, message=message)


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_text_parts(content: Any) -> str | None:
    """Return rejection message if content is not supported text, else None."""
    if isinstance(content, str):
        return None if content.strip() else "Message content text must not be empty"
    if isinstance(content, list):
        if not content:
            return "Content array must not be empty"
        for part in content:
            if isinstance(part, str):
                if not part.strip():
                    return "Text content parts must carry non-empty text"
                continue
            if not isinstance(part, dict):
                return "Content parts must be text strings or objects"
            part_type = part.get("type", "input_text")
            if part_type not in _ALLOWED_PART_TYPES:
                return f"Unsupported content type '{part_type}'"
            text = part.get("text")
            if not isinstance(text, str):
                return "Text content parts must carry a string 'text' field"
            if not text.strip():
                return "Text content parts must carry non-empty text"
            extra = set(part.keys()) - {"type", "text"}
            if extra:
                return f"Unsupported content part field '{sorted(extra)[0]}'"
        return None
    return "Content must be a string or array of text parts"


def _extract_text(content: Any) -> str:
    """Extract concatenated text from validated text content.

    Raises ValueError (never TypeError) for malformed shapes so callers can
    normalize every malformed envelope into the sanitized protocol failure.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for part in content:
            if isinstance(part, str):
                texts.append(part)
            elif isinstance(part, dict):
                part_text = part.get("text", "")
                if not isinstance(part_text, str):
                    raise ValueError("Google message content parts must carry text")
                texts.append(part_text)
            else:
                raise ValueError("Google message content parts must be text")
        return "".join(texts)
    raise ValueError("Google message content must be text")


class GoogleAiStudioAdapter:
    """Compatibility translation for Google's OpenAI-compatible surface."""

    provider = "google_ai_studio"

    def supports_operation(self, operation: str) -> bool:
        # Operation allow-list is enforced by BackendConfig.supported_operations;
        # the adapter additionally gates per-operation validation.
        return operation in {"responses", "embeddings", "chat/completions"}

    # -- request validation -------------------------------------------------
    def check_request(self, operation: str, body: dict[str, Any]) -> AdapterRejection | None:
        if operation == "embeddings":
            return self._check_embeddings_request(body)
        if operation in {"responses", "chat/completions"}:
            return self._check_responses_request(body)
        return _rejection(f"Unsupported operation '{operation}'", "unsupported_operation")

    def _check_responses_request(self, body: dict[str, Any]) -> AdapterRejection | None:
        for key in body:
            if key not in _ALLOWED_TOP_LEVEL:
                if key in {
                    "tools",
                    "tool_choice",
                    "previous_response_id",
                    "conversation",
                    "text",
                    "reasoning",
                    "stream_options",
                }:
                    return _rejection(f"Unsupported field '{key}' for Google backends")
                return _rejection(f"Unsupported field '{key}' for Google backends")
        if "previous_response_id" in body:
            return _rejection("previous_response_id is not supported for Google backends")
        conversation = body.get("conversation")
        if isinstance(conversation, dict) and conversation:
            return _rejection("Stored conversations are not supported for Google backends")
        if isinstance(conversation, str) and conversation.strip():
            return _rejection("Stored conversations are not supported for Google backends")
        if body.get("store") is True:
            return _rejection("Stored responses are not supported for Google backends")
        if body.get("background") is True:
            return _rejection("Background responses are not supported for Google backends")
        include = body.get("include")
        if include is not None and include != []:
            return _rejection("Extended response includes are not supported for Google backends")
        if "instructions" in body and body["instructions"] is not None:
            if not isinstance(body["instructions"], str):
                return _rejection("instructions must be a string")
        max_tokens = body.get("max_output_tokens")
        if max_tokens is not None:
            if (
                isinstance(max_tokens, bool)
                or not isinstance(max_tokens, int)
                or not (_MAX_OUTPUT_TOKENS_MIN <= max_tokens <= _MAX_OUTPUT_TOKENS_MAX)
            ):
                return _rejection(
                    "max_output_tokens must be an integer "
                    f"{_MAX_OUTPUT_TOKENS_MIN}-{_MAX_OUTPUT_TOKENS_MAX}"
                )
        for key in ("temperature", "top_p"):
            if key in body and body[key] is not None:
                value = body[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    return _rejection(f"{key} must be a number")
                if not math.isfinite(float(value)):
                    return _rejection(f"{key} must be finite")
                if key == "temperature" and not (0.0 <= float(value) <= 2.0):
                    return _rejection("temperature must be in range 0-2")
                if key == "top_p" and not (0.0 <= float(value) <= 1.0):
                    return _rejection("top_p must be in range 0-1")
        if "stream" in body and not isinstance(body["stream"], bool):
            return _rejection("stream must be a boolean")
        if "metadata" in body and body["metadata"] is not None:
            if not isinstance(body["metadata"], dict):
                return _rejection("metadata must be an object")
            if len(body["metadata"]) > 16:
                return _rejection("metadata must have at most 16 entries")
            if any(
                not isinstance(key, str)
                or len(key) > 64
                or not isinstance(value, str)
                or len(value) > 512
                for key, value in body["metadata"].items()
            ):
                return _rejection(
                    "metadata requires string keys up to 64 and values up to 512 characters"
                )
        input_value = body.get("input")
        if input_value is None:
            return AdapterRejection(422, "invalid_request", "The 'input' field is required")
        if isinstance(input_value, str):
            if not input_value.strip():
                return AdapterRejection(
                    422, "invalid_request", "The 'input' field must be non-empty"
                )
            return None
        if isinstance(input_value, list):
            if not input_value:
                return AdapterRejection(
                    422, "invalid_request", "The 'input' field must be non-empty"
                )
            for item in input_value:
                if not isinstance(item, dict):
                    return _rejection("Input messages must be objects", "unsupported_input")
                role = item.get("role")
                if role not in _ALLOWED_ROLES:
                    return _rejection(f"Unsupported input role '{role}'", "unsupported_input")
                if "content" not in item:
                    return AdapterRejection(422, "invalid_request", "Input messages need 'content'")
                err = _validate_text_parts(item["content"])
                if err is not None:
                    if "empty" in err:
                        return AdapterRejection(422, "invalid_request", err)
                    return _rejection(err, "unsupported_input")
                if not _extract_text(item["content"]).strip():
                    return AdapterRejection(
                        422, "invalid_request", "Message content must be non-empty"
                    )
                extra = set(item.keys()) - {"role", "content", "type"}
                # Reject tool-call items and other message shapes explicitly.
                if item.get("type") not in (None, "message"):
                    return _rejection("Only text messages are supported", "unsupported_input")
                if extra - {"role", "content", "type"}:
                    return _rejection(
                        f"Unsupported input field '{sorted(extra)[0]}'", "unsupported_input"
                    )
            return None
        return AdapterRejection(422, "invalid_request", "The 'input' field must be text")

    def _check_embeddings_request(self, body: dict[str, Any]) -> AdapterRejection | None:
        allowed = {"model", "input", "dimensions", "encoding_format"}
        for key in body:
            if key not in allowed:
                return _rejection(f"Unsupported embeddings field '{key}'")
        input_value = body.get("input")
        if isinstance(input_value, str):
            if not input_value.strip():
                return AdapterRejection(
                    422, "invalid_request", "Embeddings input must be non-empty"
                )
        elif isinstance(input_value, list):
            if not input_value or any(
                not isinstance(item, str) or not item.strip() for item in input_value
            ):
                return AdapterRejection(
                    422, "invalid_request", "Embeddings input array must be non-empty strings"
                )
        else:
            return AdapterRejection(422, "invalid_request", "Embeddings input must be text")
        if "encoding_format" in body and body["encoding_format"] not in (None, "float"):
            return _rejection("Only float embeddings encoding is supported")
        dimensions = body.get("dimensions")
        if dimensions is not None and (
            isinstance(dimensions, bool) or not isinstance(dimensions, int) or dimensions <= 0
        ):
            return _rejection("dimensions must be a positive integer")
        return None

    # -- upstream request building ------------------------------------------
    def build_upstream_body(
        self,
        operation: str,
        body: dict[str, Any],
        *,
        deployment: str,
        default_output_tokens: int,
    ) -> dict[str, Any]:
        if operation == "embeddings":
            out: dict[str, Any] = {"model": deployment, "input": body["input"]}
            if body.get("dimensions") is not None:
                out["dimensions"] = body["dimensions"]
            out["encoding_format"] = "float"
            return out
        messages: list[dict[str, Any]] = []
        instructions = body.get("instructions")
        if isinstance(instructions, str) and instructions.strip():
            messages.append({"role": "system", "content": instructions})
        input_value = body.get("input")
        if isinstance(input_value, str):
            messages.append({"role": "user", "content": input_value})
        elif isinstance(input_value, list):
            for item in input_value:
                role = item["role"]
                mapped_role = "system" if role == "developer" else role
                content = item["content"]
                if isinstance(content, str):
                    messages.append({"role": mapped_role, "content": content})
                elif mapped_role == "system":
                    messages.append({"role": mapped_role, "content": _extract_text(content)})
                else:
                    parts = []
                    for part in content:
                        if isinstance(part, str):
                            parts.append({"type": "text", "text": part})
                        else:
                            parts.append({"type": "text", "text": str(part.get("text", ""))})
                    messages.append({"role": mapped_role, "content": parts})
        upstream: dict[str, Any] = {"model": deployment, "messages": messages}
        max_tokens = body.get("max_output_tokens")
        upstream["max_completion_tokens"] = (
            max_tokens if isinstance(max_tokens, int) else int(default_output_tokens)
        )
        for key in ("temperature", "top_p"):
            if body.get(key) is not None:
                upstream[key] = body[key]
        if body.get("stream") is True:
            upstream["stream"] = True
            upstream["stream_options"] = {"include_usage": True}
        return upstream

    # -- success translation --------------------------------------------------
    def translate_success(
        self,
        operation: str,
        upstream: Any,
        *,
        logical_model: str,
        expected_input_count: int | None = None,
        expected_dimensions: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TranslatedSuccess:
        if operation == "embeddings":
            return self._translate_embeddings_success(
                upstream,
                logical_model=logical_model,
                expected_input_count=expected_input_count,
                expected_dimensions=expected_dimensions,
            )
        translated = self._translate_responses_success(upstream, logical_model=logical_model)
        translated.body["metadata"] = dict(metadata or {})
        return translated

    def _translate_responses_success(
        self, upstream: Any, *, logical_model: str
    ) -> TranslatedSuccess:
        if not isinstance(upstream, dict):
            raise ValueError("Google success body must be a JSON object")
        choices = upstream.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError("Google success must carry exactly one choice")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise ValueError("Google choice must be an object")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("Google choice must carry an assistant message")
        if message.get("role", "assistant") != "assistant":
            raise ValueError("Google message role must be assistant")
        if message.get("tool_calls"):
            raise ValueError("Google tool calls are not supported in this release")
        content = message.get("content")
        # Validate the shape before extraction: anything that is not None, a
        # string, or a list is malformed (e.g. numeric content), as is any
        # list part that is not a string or a text dict.
        if content is None:
            text = ""
        elif isinstance(content, str):
            text = content
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, str):
                    continue
                if not isinstance(part, dict):
                    raise ValueError("Google message content parts must be text")
                part_type = part.get("type", "text")
                if part_type not in ("text", None) and "text" not in part:
                    raise ValueError("Google message content must be text")
                part_text = part.get("text")
                if not isinstance(part_text, str):
                    raise ValueError("Google message content parts must carry text")
            text = _extract_text(content)
        else:
            raise ValueError("Google message content must be text")
        finish_reason = choice.get("finish_reason")
        if finish_reason not in _ALLOWED_FINISH_REASONS:
            raise ValueError(f"Unsupported Google finish reason '{finish_reason}'")
        usage = upstream.get("usage")
        input_tokens: int | None = None
        output_tokens: int | None = None
        total_tokens: int | None = None
        if usage is not None:
            if not isinstance(usage, dict):
                raise ValueError("Google usage must be an object")
            prompt = usage.get("prompt_tokens")
            completion = usage.get("completion_tokens")
            total = usage.get("total_tokens")
            for value in (prompt, completion, total):
                if value is not None and (
                    isinstance(value, bool) or not isinstance(value, int) or value < 0
                ):
                    raise ValueError("Google usage tokens must be non-negative integers")
            if prompt is None:
                raise ValueError("Google usage must report prompt_tokens")
            # Never fabricate zero output: incomplete usage omits the public
            # usage block so settlement retains conservative estimates.
            if completion is None:
                input_tokens = prompt
                output_tokens = None
                total_tokens = None
            else:
                input_tokens = prompt
                output_tokens = completion
                total_tokens = total if total is not None else prompt + completion
        response_id = f"resp_{uuid.uuid4().hex[:24]}"
        message_id = f"msg_{uuid.uuid4().hex[:24]}"
        created_at = int(time.time())
        if finish_reason == "stop":
            status = "completed"
            item_status: str | None = None
            incomplete_details: dict[str, Any] | None = None
            error: dict[str, Any] | None = None
        elif finish_reason == "length":
            status = "incomplete"
            item_status = "incomplete"
            incomplete_details = {"reason": "max_output_tokens"}
            error = None
        else:  # content_filter
            status = "incomplete"
            item_status = "incomplete"
            incomplete_details = {"reason": "content_filter"}
            error = None
        output_item: dict[str, Any] = {
            "type": "message",
            "id": message_id,
            "role": "assistant",
            "status": item_status or "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        }
        public: dict[str, Any] = {
            "id": response_id,
            "object": "response",
            "created_at": created_at,
            "model": logical_model,
            "status": status,
            "output": [output_item],
            "error": error,
            "incomplete_details": incomplete_details,
            "usage": (
                {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                }
                if input_tokens is not None and output_tokens is not None
                else None
            ),
        }
        return TranslatedSuccess(
            body=public, input_tokens=input_tokens, output_tokens=output_tokens
        )

    def _translate_embeddings_success(
        self,
        upstream: Any,
        *,
        logical_model: str,
        expected_input_count: int | None = None,
        expected_dimensions: int | None = None,
    ) -> TranslatedSuccess:
        if not isinstance(upstream, dict):
            raise ValueError("Google embeddings body must be a JSON object")
        data = upstream.get("data")
        if not isinstance(data, list) or not data:
            raise ValueError("Google embeddings must return a non-empty data list")
        if expected_input_count is not None and len(data) != expected_input_count:
            raise ValueError("Google embeddings count must match the request input count")
        vectors: list[list[float]] = []
        for index, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError("Google embedding items must be objects")
            if item.get("index") != index:
                raise ValueError("Google embedding indexes must match input order")
            embedding = item.get("embedding")
            if not isinstance(embedding, list) or not embedding:
                raise ValueError("Google embedding vectors must be non-empty arrays")
            values: list[float] = []
            for value in embedding:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError("Google embedding values must be finite numbers")
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError("Google embedding values must be finite numbers")
                values.append(number)
            vectors.append(values)
        dimensions = len(vectors[0])
        if expected_dimensions is not None and dimensions != expected_dimensions:
            raise ValueError("Google embedding dimensions must match the requested dimensions")
        if any(len(vector) != dimensions for vector in vectors):
            raise ValueError("Google embedding vectors must share dimensions")
        usage = upstream.get("usage")
        input_tokens: int | None = None
        if usage is not None:
            if not isinstance(usage, dict):
                raise ValueError("Google embeddings usage must be an object")
            prompt = usage.get("prompt_tokens")
            if prompt is not None and (
                isinstance(prompt, bool) or not isinstance(prompt, int) or prompt < 0
            ):
                raise ValueError("Google embeddings usage must be a non-negative integer")
            input_tokens = prompt
        public = {
            "object": "list",
            "data": [
                {
                    "object": "embedding",
                    "index": index,
                    "embedding": vector,
                    "model": logical_model,
                }
                for index, vector in enumerate(vectors)
            ],
            "model": logical_model,
            "usage": (
                {
                    "prompt_tokens": input_tokens,
                    "total_tokens": input_tokens,
                }
                if input_tokens is not None
                else None
            ),
        }
        return TranslatedSuccess(body=public, input_tokens=input_tokens, output_tokens=0)

    def translate_error(self, status_code: int, upstream_body: bytes | None) -> TranslatedError:
        _ = upstream_body  # Never relay provider bodies.
        if status_code in (401, 403):
            return TranslatedError(
                502, "upstream_error", "Backend authentication failed; check server configuration"
            )
        if status_code == 429:
            return TranslatedError(429, "rate_limit_exceeded", "Backend rate limit exceeded")
        if status_code == 400:
            return TranslatedError(502, "upstream_error", "Backend rejected the translated request")
        if 500 <= status_code < 600:
            return TranslatedError(status_code, "upstream_error", "Backend request failed")
        return TranslatedError(status_code, "upstream_error", "Backend request failed")

    def create_stream_decoder(
        self,
        *,
        logical_model: str,
        request_input: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> GoogleStreamDecoder:
        _ = request_input
        return GoogleStreamDecoder(logical_model=logical_model, metadata=metadata)


class GoogleStreamDecoder:
    """Incremental Google SSE -> Responses SSE translator with bounded state."""

    def __init__(self, *, logical_model: str, metadata: dict[str, Any] | None = None) -> None:
        self._metadata = dict(metadata or {})
        self._logical_model = logical_model
        self._response_id = f"resp_{uuid.uuid4().hex[:24]}"
        self._item_id = f"msg_{uuid.uuid4().hex[:24]}"
        self._created_at = int(time.time())
        self._buffer = bytearray()
        self._assembled = 0
        self._text_parts: list[str] = []
        self._sequence = 0
        self._header_sent = False
        self._terminal_sent = False
        self._finish_reason: str | None = None
        self._input_tokens: int | None = None
        self._output_tokens: int | None = None
        self._saw_done = False
        self._validated = False

    @property
    def validated(self) -> bool:
        return self._validated

    @property
    def usage(self) -> tuple[int | None, int | None]:
        return self._input_tokens, self._output_tokens

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def _sse(self, payload: dict[str, Any]) -> bytes:
        return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n".encode()

    def _header_events(self) -> list[bytes]:
        base_response = {
            "metadata": dict(self._metadata),
            "id": self._response_id,
            "object": "response",
            "created_at": self._created_at,
            "model": self._logical_model,
            "status": "in_progress",
            "output": [],
        }
        return [
            self._sse(
                {
                    "type": "response.created",
                    "sequence_number": self._next_sequence(),
                    "response": dict(base_response),
                }
            ),
            self._sse(
                {
                    "type": "response.in_progress",
                    "sequence_number": self._next_sequence(),
                    "response": dict(base_response),
                }
            ),
            self._sse(
                {
                    "type": "response.output_item.added",
                    "sequence_number": self._next_sequence(),
                    "output_index": 0,
                    "item": {
                        "type": "message",
                        "id": self._item_id,
                        "role": "assistant",
                        "status": "in_progress",
                        "content": [],
                    },
                }
            ),
            self._sse(
                {
                    "type": "response.content_part.added",
                    "sequence_number": self._next_sequence(),
                    "item_id": self._item_id,
                    "output_index": 0,
                    "content_index": 0,
                    "part": {"type": "output_text", "text": "", "annotations": []},
                }
            ),
        ]

    def feed(self, chunk: bytes) -> list[bytes]:
        """Consume raw upstream bytes; return downstream Responses events."""
        if self._terminal_sent:
            return []
        if len(self._buffer) + len(chunk) > MAX_GOOGLE_SSE_BUFFER_BYTES:
            raise ValueError("Google stream framing exceeds bound")
        self._buffer.extend(chunk)
        out: list[bytes] = []
        while True:
            event, rest = _split_sse_event(bytes(self._buffer))
            if event is None:
                break
            self._buffer = bytearray(rest)
            if len(event) > MAX_GOOGLE_EVENT_BYTES:
                raise ValueError("Google stream event exceeds bound")
            events = self._handle_provider_event(event)
            out.extend(events)
        return out

    def finish(self) -> list[bytes]:
        """Close the stream; EOF without terminator is a truncation failure."""
        if self._terminal_sent:
            return []
        if not self._validated:
            raise ValueError("Google stream ended before any translatable event")
        if not self._saw_done:
            raise ValueError("Google stream truncated before [DONE]")
        return self._terminal_events()

    def _handle_provider_event(self, raw: bytes) -> list[bytes]:
        lines = raw.splitlines()
        data_lines = [
            line[5:].lstrip()
            for line in (raw_line.strip() for raw_line in lines)
            if line.startswith(b"data:")
        ]
        # Comments/keepalives carry no data lines.
        if not data_lines:
            return []
        data = b"\n".join(data_lines).strip()
        if not data:
            return []
        if data == b"[DONE]":
            if self._terminal_sent:
                return []
            self._saw_done = True
            return self._terminal_events()
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Malformed Google stream event") from exc
        if not isinstance(payload, dict):
            raise ValueError("Malformed Google stream event")
        if "error" in payload:
            # Provider text may contain secrets or client content; never echo it.
            raise ValueError("Google stream reported an upstream failure")
        usage = payload.get("usage")
        if usage is not None and not isinstance(usage, dict):
            raise ValueError("Google stream usage must be an object")
        choices = payload.get("choices", [])
        if not isinstance(choices, list):
            raise ValueError("Malformed Google stream event")
        if not choices:
            # Usage-only chunk: validate usage, retain it, emit no downstream event yet.
            usage = payload.get("usage")
            if isinstance(usage, dict):
                self._absorb_usage(usage)
            return []
        if len(choices) != 1:
            raise ValueError("Google stream must carry a single choice")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise ValueError("Malformed Google stream event")
        delta = choice.get("delta", {})
        if not isinstance(delta, dict):
            raise ValueError("Malformed Google stream event")
        if delta.get("tool_calls"):
            raise ValueError("Google tool calls are not supported in this release")
        content = delta.get("content")
        finish_reason = choice.get("finish_reason")
        if finish_reason is not None and finish_reason not in _ALLOWED_FINISH_REASONS:
            raise ValueError(f"Unsupported Google finish reason '{finish_reason}'")
        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, str):
                    text += part
                elif isinstance(part, dict):
                    part_text = part.get("text", "")
                    if not isinstance(part_text, str):
                        raise ValueError("Malformed Google stream event")
                    text += part_text
                else:
                    raise ValueError("Malformed Google stream event")
        elif content is not None:
            raise ValueError("Malformed Google stream event")
        # Validate the envelope before absorbing usage or committing downstream.
        usage = payload.get("usage")
        if isinstance(usage, dict):
            self._absorb_usage(usage)
        if finish_reason is not None:
            self._finish_reason = finish_reason
        out: list[bytes] = []
        if not self._validated:
            if not text and finish_reason is None:
                # Role-only/empty deltas do not commit the downstream stream.
                return []
            # First translatable provider event commits the downstream stream.
            self._validated = True
            out.extend(self._header_events())
            self._header_sent = True
        if text:
            if self._assembled + len(text.encode()) > MAX_GOOGLE_ASSEMBLED_TEXT_BYTES:
                raise ValueError("Google stream output exceeds bound")
            self._assembled += len(text.encode())
            self._text_parts.append(text)
            out.append(
                self._sse(
                    {
                        "type": "response.output_text.delta",
                        "sequence_number": self._next_sequence(),
                        "item_id": self._item_id,
                        "output_index": 0,
                        "content_index": 0,
                        "delta": text,
                    }
                )
            )
        return out

    def _absorb_usage(self, usage: dict[str, Any]) -> None:
        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")
        for value in (prompt, completion):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError("Google stream usage must be non-negative integers")
        if prompt is not None:
            self._input_tokens = prompt
        if completion is not None:
            self._output_tokens = completion

    def _terminal_events(self) -> list[bytes]:
        if self._terminal_sent:
            return []
        if self._finish_reason is None:
            # Never present a stream without terminal evidence as successful completion.
            raise ValueError("Google stream ended without a finish reason")
        self._terminal_sent = True
        full_text = "".join(self._text_parts)
        reason = self._finish_reason
        if reason == "stop":
            status = "completed"
            terminal_type = "response.completed"
        elif reason == "length":
            status = "incomplete"
            terminal_type = "response.incomplete"
        else:  # content_filter
            status = "incomplete"
            terminal_type = "response.incomplete"
        usage: dict[str, Any] | None = None
        if self._input_tokens is not None and self._output_tokens is not None:
            usage = {
                "input_tokens": self._input_tokens,
                "output_tokens": self._output_tokens,
                "total_tokens": self._input_tokens + self._output_tokens,
            }
        events = [
            self._sse(
                {
                    "type": "response.output_text.done",
                    "sequence_number": self._next_sequence(),
                    "item_id": self._item_id,
                    "output_index": 0,
                    "content_index": 0,
                    "text": full_text,
                }
            ),
            self._sse(
                {
                    "type": "response.content_part.done",
                    "sequence_number": self._next_sequence(),
                    "item_id": self._item_id,
                    "output_index": 0,
                    "content_index": 0,
                    "part": {"type": "output_text", "text": full_text, "annotations": []},
                }
            ),
            self._sse(
                {
                    "type": "response.output_item.done",
                    "sequence_number": self._next_sequence(),
                    "output_index": 0,
                    "item": {
                        "type": "message",
                        "id": self._item_id,
                        "role": "assistant",
                        "status": status,
                        "content": [{"type": "output_text", "text": full_text, "annotations": []}],
                    },
                }
            ),
        ]
        terminal_response: dict[str, Any] = {
            "metadata": dict(self._metadata),
            "id": self._response_id,
            "object": "response",
            "created_at": self._created_at,
            "model": self._logical_model,
            "status": status,
            "output": [
                {
                    "type": "message",
                    "id": self._item_id,
                    "role": "assistant",
                    "status": status,
                    "content": [{"type": "output_text", "text": full_text, "annotations": []}],
                }
            ],
        }
        if usage is not None:
            terminal_response["usage"] = usage
        if terminal_type == "response.incomplete":
            terminal_response["incomplete_details"] = {
                "reason": "max_output_tokens" if reason == "length" else "content_filter"
            }
        events.append(
            self._sse(
                {
                    "type": terminal_type,
                    "sequence_number": self._next_sequence(),
                    "response": terminal_response,
                }
            )
        )
        return events

    def build_failure(self, message: str) -> list[bytes]:
        """Emit a schema-valid terminal ``response.failed`` event.

        Preserves the decoder's response identity and monotonically increasing
        sequence numbers. Exactly one terminal event is ever emitted: a second
        call after any terminal outcome returns no events.
        """
        if self._terminal_sent:
            return []
        self._terminal_sent = True
        full_text = "".join(self._text_parts)
        failed_response: dict[str, Any] = {
            "metadata": dict(self._metadata),
            "id": self._response_id,
            "object": "response",
            "created_at": self._created_at,
            "model": self._logical_model,
            "status": "failed",
            "output": [
                {
                    "type": "message",
                    "id": self._item_id,
                    "role": "assistant",
                    "status": "failed",
                    "content": [{"type": "output_text", "text": full_text, "annotations": []}],
                }
            ],
            "error": {"message": message, "type": "upstream_error"},
        }
        if self._input_tokens is not None and self._output_tokens is not None:
            failed_response["usage"] = {
                "input_tokens": self._input_tokens,
                "output_tokens": self._output_tokens,
                "total_tokens": self._input_tokens + self._output_tokens,
            }
        return [
            self._sse(
                {
                    "type": "response.failed",
                    "sequence_number": self._next_sequence(),
                    "response": failed_response,
                }
            )
        ]


def _split_sse_event(buffer: bytes) -> tuple[bytes | None, bytes]:
    boundaries = [(buffer.find(d), d) for d in (b"\r\n\r\n", b"\n\n")]
    found = [(i, d) for i, d in boundaries if i >= 0]
    if found:
        index, delimiter = min(found)
        return buffer[:index], buffer[index + len(delimiter) :]
    return None, buffer


__all__ = [
    "MAX_GOOGLE_ASSEMBLED_TEXT_BYTES",
    "MAX_GOOGLE_EVENT_BYTES",
    "MAX_GOOGLE_SSE_BUFFER_BYTES",
    "GoogleAiStudioAdapter",
    "GoogleStreamDecoder",
]
