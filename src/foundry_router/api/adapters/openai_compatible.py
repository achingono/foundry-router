"""Provider-neutral Responses/embeddings and Chat Completions translation.

Provider subclasses own capability, message and call validation. This module performs
no HTTP requests, routing, retries, credential handling or global conversation storage.
"""

from __future__ import annotations

import json
import math
import time
import uuid
from typing import TYPE_CHECKING, Any, Protocol

from foundry_router.api.adapters.base import AdapterRejection, TranslatedError, TranslatedSuccess

if TYPE_CHECKING:
    from foundry_router.api.google_pdf import PreparedGoogleMedia


class ChatRequestContext(Protocol):
    """Read-only common context; provider-specific argument validation stays private."""

    @property
    def tools(self) -> dict[str, dict[str, Any]]: ...

    @property
    def choice(self) -> Any: ...

    @property
    def parallel(self) -> bool: ...

    @property
    def text_format(self) -> dict[str, Any] | None: ...

    @property
    def max_calls(self) -> int: ...

    @property
    def max_argument_bytes(self) -> int: ...

    def validate_text(self, text: str, *, completed: bool, has_calls: bool) -> None: ...


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
        "tools",
        "tool_choice",
        "parallel_tool_calls",
        "text",
    }
)
_ALLOWED_ROLES = frozenset({"system", "developer", "user", "assistant"})
_ALLOWED_PART_TYPES = frozenset({"input_text", "output_text", "text"})
_ALLOWED_FINISH_REASONS = frozenset({"stop", "length", "content_filter"})
_MAX_OUTPUT_TOKENS_MIN = 1
_MAX_OUTPUT_TOKENS_MAX = 128000

MAX_OPENAI_EVENT_BYTES = 256 * 1024
MAX_OPENAI_ASSEMBLED_TEXT_BYTES = 4 * 1024 * 1024
MAX_OPENAI_SSE_BUFFER_BYTES = 1024 * 1024


def _rejection(message: str, code: str = "unsupported_parameter") -> AdapterRejection:
    return AdapterRejection(status_code=422, code=code, message=message)


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _extract_text(content: Any, *, provider_label: str = "OpenAI-compatible") -> str:
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
                    raise ValueError(f"{provider_label} message content parts must carry text")
                texts.append(part_text)
            else:
                raise ValueError(f"{provider_label} message content parts must be text")
        return "".join(texts)
    raise ValueError(f"{provider_label} message content must be text")


class OpenAICompatibleStreamDecoder[ContextT: ChatRequestContext]:
    """Bounded incremental Chat Completions SSE to Responses SSE translation."""

    provider_label = "OpenAI-compatible"

    def __init__(
        self,
        *,
        logical_model: str,
        metadata: dict[str, Any] | None = None,
        context: ContextT,
    ) -> None:
        self._context = context
        self._call_fragments: dict[int, dict[str, Any]] = {}
        self._calls: list[dict[str, Any]] = []
        self._calls_emitted = False
        self._call_ids: dict[int, str] = {}
        self._sent_arguments: dict[int, int] = {}
        self._public_call_indices: dict[int, int] = {}
        self._message_index: int | None = None
        self._archived_messages: list[tuple[int, dict[str, Any]]] = []
        self._next_output_index = 0
        self._refusal_parts: list[str] = []
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

    def _translate_calls(self, raw: Any, *, completed: bool, refusal: bool) -> list[dict[str, Any]]:
        """Require provider validation for assembled calls, including empty calls."""
        raise NotImplementedError

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
            "parallel_tool_calls": self._context.parallel,
            "tool_choice": self._context.choice,
            "tools": list(self._context.tools.values()),
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
        ]

    def _open_message(self, *, refusal: bool = False) -> list[bytes]:
        if self._message_index is not None:
            return []
        self._message_index = self._next_output_index
        self._next_output_index += 1
        return [
            self._sse(
                {
                    "type": "response.output_item.added",
                    "sequence_number": self._next_sequence(),
                    "output_index": self._message_index,
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
                    "output_index": self._message_index,
                    "content_index": 0,
                    "part": (
                        {"type": "refusal", "refusal": ""}
                        if refusal
                        else {"type": "output_text", "text": "", "annotations": []}
                    ),
                }
            ),
        ]

    def feed(self, chunk: bytes) -> list[bytes]:
        """Consume raw upstream bytes; return downstream Responses events."""
        if self._terminal_sent:
            return []
        if len(self._buffer) + len(chunk) > MAX_OPENAI_SSE_BUFFER_BYTES:
            raise ValueError(f"{self.provider_label} stream framing exceeds bound")
        self._buffer.extend(chunk)
        out: list[bytes] = []
        while True:
            event, rest = _split_sse_event(bytes(self._buffer))
            if event is None:
                break
            self._buffer = bytearray(rest)
            if len(event) > MAX_OPENAI_EVENT_BYTES:
                raise ValueError(f"{self.provider_label} stream event exceeds bound")
            events = self._handle_provider_event(event)
            out.extend(events)
        return out

    def finish(self) -> list[bytes]:
        """Close the stream; EOF without terminator is a truncation failure."""
        if self._terminal_sent:
            return []
        if not self._validated:
            raise ValueError(f"{self.provider_label} stream ended before any translatable event")
        if not self._saw_done:
            raise ValueError(f"{self.provider_label} stream truncated before [DONE]")
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
            raise ValueError(f"Malformed {self.provider_label} stream event") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"Malformed {self.provider_label} stream event")
        return self._handle_payload(payload)

    def _handle_payload(self, payload: dict[str, Any]) -> list[bytes]:
        """Shared validated text/call event construction; transport framing stays separate."""
        if "error" in payload:
            # Provider text may contain secrets or client content; never echo it.
            raise ValueError(f"{self.provider_label} stream reported an upstream failure")
        usage = payload.get("usage")
        if usage is not None and not isinstance(usage, dict):
            raise ValueError(f"{self.provider_label} stream usage must be an object")
        choices = payload.get("choices", [])
        if not isinstance(choices, list):
            raise ValueError(f"Malformed {self.provider_label} stream event")
        # Known usage survives output conversion errors in the same chunk.
        if isinstance(usage, dict):
            self._absorb_usage(usage)
        if not choices:
            # Usage-only chunk: validate usage, retain it, emit no downstream event yet.
            usage = payload.get("usage")
            if isinstance(usage, dict):
                self._absorb_usage(usage)
            return []
        if len(choices) != 1:
            raise ValueError(f"{self.provider_label} stream must carry a single choice")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise ValueError(f"Malformed {self.provider_label} stream event")
        delta = choice.get("delta", {})
        if not isinstance(delta, dict):
            raise ValueError(f"Malformed {self.provider_label} stream event")
        if set(delta) - {"role", "content", "tool_calls", "refusal"}:
            raise ValueError(f"Unsupported {self.provider_label} delta or provider state")
        raw_calls = delta.get("tool_calls")
        if raw_calls is not None:
            self._absorb_calls(raw_calls)
        content = delta.get("content")
        refusal = delta.get("refusal")
        if refusal is not None and not isinstance(refusal, str):
            raise ValueError(f"Malformed {self.provider_label} refusal")
        if refusal and (content or raw_calls or self._text_parts or self._call_fragments):
            raise ValueError(f"{self.provider_label} refusal cannot mix with generated output")
        if self._refusal_parts and (content or raw_calls):
            raise ValueError(f"{self.provider_label} generated output cannot follow a refusal")
        finish_reason = choice.get("finish_reason")
        if finish_reason is not None and finish_reason not in _ALLOWED_FINISH_REASONS | {
            "tool_calls"
        }:
            raise ValueError(f"Unsupported {self.provider_label} finish reason '{finish_reason}'")
        if self._finish_reason is not None and (
            content or raw_calls or refusal or finish_reason is not None
        ):
            raise ValueError(f"{self.provider_label} output arrived after its finish reason")
        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, str):
                    text += part
                elif isinstance(part, dict):
                    if part.get("type", "text") not in ("text", None) or set(part) - {
                        "type",
                        "text",
                    }:
                        raise ValueError(
                            f"Unsupported {self.provider_label} text part or provider state"
                        )
                    part_text = part.get("text", "")
                    if not isinstance(part_text, str):
                        raise ValueError(f"Malformed {self.provider_label} stream event")
                    text += part_text
                else:
                    raise ValueError(f"Malformed {self.provider_label} stream event")
        elif content is not None:
            raise ValueError(f"Malformed {self.provider_label} stream event")
        # Validate the envelope before absorbing usage or committing downstream.
        usage = payload.get("usage")
        if isinstance(usage, dict):
            self._absorb_usage(usage)
        if finish_reason is not None:
            self._finish_reason = finish_reason
        out: list[bytes] = []
        ready_call = any(
            fragment["id"]
            and fragment["name"] in self._context.tools
            and (fragment.get("ready") or finish_reason is not None)
            for fragment in self._call_fragments.values()
        )
        if not self._validated:
            if not text and not refusal and not ready_call and finish_reason is None:
                return []
            self._validated = True
            out.extend(self._header_events())
            self._header_sent = True
        if text or refusal:
            out.extend(self._open_message(refusal=bool(refusal)))
        elif finish_reason is not None and not self._call_fragments and self._message_index is None:
            out.extend(self._open_message())
        out.extend(self._flush_call_deltas(force=finish_reason is not None))
        if refusal:
            self._assembled += len(refusal.encode())
            if self._assembled > MAX_OPENAI_ASSEMBLED_TEXT_BYTES:
                raise ValueError(f"{self.provider_label} refusal exceeds bound")
            self._refusal_parts.append(refusal)
            out.append(
                self._sse(
                    {
                        "type": "response.refusal.delta",
                        "sequence_number": self._next_sequence(),
                        "item_id": self._item_id,
                        "output_index": self._message_index,
                        "content_index": 0,
                        "delta": refusal,
                    }
                )
            )
        if text:
            if self._assembled + len(text.encode()) > MAX_OPENAI_ASSEMBLED_TEXT_BYTES:
                raise ValueError(f"{self.provider_label} stream output exceeds bound")
            self._assembled += len(text.encode())
            self._text_parts.append(text)
            out.append(
                self._sse(
                    {
                        "type": "response.output_text.delta",
                        "sequence_number": self._next_sequence(),
                        "item_id": self._item_id,
                        "output_index": self._message_index,
                        "content_index": 0,
                        "delta": text,
                    }
                )
            )
        return out

    def _absorb_calls(self, calls: Any) -> None:
        if not self._context.tools or not isinstance(calls, list):
            raise ValueError(f"Unsupported {self.provider_label} tool deltas")
        for call in calls:
            if not isinstance(call, dict) or set(call) - {"index", "id", "type", "function"}:
                raise ValueError(f"Unsupported {self.provider_label} call or provider state")
            index = call.get("index")
            if (
                isinstance(index, bool)
                or not isinstance(index, int)
                or not 0 <= index < self._context.max_calls
            ):
                raise ValueError(f"{self.provider_label} call index exceeds its bound")
            if call.get("type", "function") != "function":
                raise ValueError(f"Unsupported {self.provider_label} tool type")
            fragment = self._call_fragments.setdefault(
                index, {"id": "", "name": "", "arguments": ""}
            )
            function = call.get("function", {})
            if not isinstance(function, dict) or set(function) - {"name", "arguments"}:
                raise ValueError(f"Unsupported {self.provider_label} function or provider state")
            if index in self._call_ids and (call.get("id") or function.get("name")):
                raise ValueError(
                    f"{self.provider_label} call identity changed after downstream output"
                )
            fragment["ready"] = fragment.get("ready", False) or (
                "arguments" in function and not call.get("id") and not function.get("name")
            )
            for key, value in (
                ("id", call.get("id")),
                ("name", function.get("name")),
                ("arguments", function.get("arguments")),
            ):
                if value is None:
                    continue
                if not isinstance(value, str):
                    raise ValueError(f"{self.provider_label} call fragments must be strings")
                fragment[key] += value
                bound = self._context.max_argument_bytes if key == "arguments" else 256
                if len(fragment[key].encode()) > bound:
                    raise ValueError(f"{self.provider_label} call fragments exceed their bound")
                self._assembled += len(value.encode())
                if self._assembled > MAX_OPENAI_ASSEMBLED_TEXT_BYTES:
                    raise ValueError(f"{self.provider_label} stream output exceeds bound")

    def _flush_call_deltas(self, *, force: bool) -> list[bytes]:
        events: list[bytes] = []
        for index in sorted(self._call_fragments):
            fragment = self._call_fragments[index]
            if not force and not fragment.get("ready"):
                continue
            if not fragment["id"] or fragment["name"] not in self._context.tools:
                if force:
                    raise ValueError(f"Incomplete {self.provider_label} function identity")
                continue
            if index not in self._call_ids:
                item = {
                    "type": "function_call",
                    "id": f"fc_{uuid.uuid4().hex[:24]}",
                    "call_id": fragment["id"],
                    "name": fragment["name"],
                    "arguments": "",
                    "status": "in_progress",
                }
                self._call_ids[index] = item["id"]
                self._public_call_indices[index] = self._next_output_index
                self._next_output_index += 1
                self._sent_arguments[index] = 0
                events.append(
                    self._sse(
                        {
                            "type": "response.output_item.added",
                            "sequence_number": self._next_sequence(),
                            "output_index": self._public_call_indices[index],
                            "item": item,
                        }
                    )
                )
            arguments = fragment["arguments"]
            sent = self._sent_arguments[index]
            if len(arguments) > sent:
                events.append(
                    self._sse(
                        {
                            "type": "response.function_call_arguments.delta",
                            "sequence_number": self._next_sequence(),
                            "output_index": self._public_call_indices[index],
                            "item_id": self._call_ids[index],
                            "delta": arguments[sent:],
                        }
                    )
                )
                self._sent_arguments[index] = len(arguments)
        return events

    def _call_events(self, *, completed: bool) -> list[bytes]:
        if self._calls_emitted:
            return []
        indices = sorted(self._call_fragments)
        if indices != list(range(len(indices))):
            raise ValueError(f"{self.provider_label} call indices must be contiguous")
        raw = [
            {
                "id": self._call_fragments[index]["id"],
                "type": "function",
                "function": {
                    "name": self._call_fragments[index]["name"],
                    "arguments": self._call_fragments[index]["arguments"],
                },
            }
            for index in indices
        ]
        self._calls = self._translate_calls(
            raw, completed=completed, refusal=bool(self._refusal_parts)
        )
        events: list[bytes] = []
        events.extend(self._flush_call_deltas(force=True))
        for provider_index, call in enumerate(self._calls):
            index = self._public_call_indices[provider_index]
            call["id"] = self._call_ids[provider_index]
            if completed:
                events.append(
                    self._sse(
                        {
                            "type": "response.function_call_arguments.done",
                            "sequence_number": self._next_sequence(),
                            "item_id": call["id"],
                            "output_index": index,
                            "arguments": call["arguments"],
                            "name": call["name"],
                        }
                    )
                )
            events.append(
                self._sse(
                    {
                        "type": "response.output_item.done",
                        "sequence_number": self._next_sequence(),
                        "output_index": index,
                        "item": call,
                    }
                )
            )
        self._calls_emitted = True
        return events

    def _absorb_usage(self, usage: dict[str, Any]) -> None:
        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")
        for value in (prompt, completion):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(
                    f"{self.provider_label} stream usage must be non-negative integers"
                )
        if prompt is not None:
            self._input_tokens = prompt
        if completion is not None:
            self._output_tokens = completion

    def _terminal_events(self) -> list[bytes]:
        if self._terminal_sent:
            return []
        if self._finish_reason is None:
            # Never present a stream without terminal evidence as successful completion.
            raise ValueError(f"{self.provider_label} stream ended without a finish reason")
        full_text = "".join(self._text_parts)
        validation_text = (
            "".join(item["content"][0]["text"] for _, item in self._archived_messages) + full_text
        )
        reason = self._finish_reason
        completed = reason in {"stop", "tool_calls"}
        call_events = self._call_events(completed=completed)
        if reason == "tool_calls" and not self._calls:
            raise ValueError(f"{self.provider_label} tool finish must carry calls")
        if not self._refusal_parts:
            self._context.validate_text(
                validation_text, completed=completed, has_calls=bool(self._calls)
            )
        self._terminal_sent = True
        if completed:
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
        content_part = (
            {"type": "refusal", "refusal": "".join(self._refusal_parts)}
            if self._refusal_parts
            else {"type": "output_text", "text": full_text, "annotations": []}
        )
        output: list[tuple[int, dict[str, Any]]] = [
            (index, {**item, "status": status}) for index, item in self._archived_messages
        ]
        events = list(call_events)
        events.extend(
            self._sse(
                {
                    "type": "response.output_item.done",
                    "sequence_number": self._next_sequence(),
                    "output_index": index,
                    "item": item,
                }
            )
            for index, item in output
        )
        if self._message_index is not None:
            output_item = {
                "type": "message",
                "id": self._item_id,
                "role": "assistant",
                "status": status,
                "content": [content_part],
            }
            output.append((self._message_index, output_item))
            events.extend(
                [
                    self._sse(
                        {
                            "type": "response.refusal.done"
                            if self._refusal_parts
                            else "response.output_text.done",
                            "sequence_number": self._next_sequence(),
                            "item_id": self._item_id,
                            "output_index": self._message_index,
                            "content_index": 0,
                            **(
                                {"refusal": content_part["refusal"]}
                                if self._refusal_parts
                                else {"text": full_text}
                            ),
                        }
                    ),
                    self._sse(
                        {
                            "type": "response.content_part.done",
                            "sequence_number": self._next_sequence(),
                            "item_id": self._item_id,
                            "output_index": self._message_index,
                            "content_index": 0,
                            "part": content_part,
                        }
                    ),
                    self._sse(
                        {
                            "type": "response.output_item.done",
                            "sequence_number": self._next_sequence(),
                            "output_index": self._message_index,
                            "item": output_item,
                        }
                    ),
                ]
            )
        for provider_index, call in enumerate(self._calls):
            output.append((self._public_call_indices[provider_index], call))
        terminal_response: dict[str, Any] = {
            "parallel_tool_calls": self._context.parallel,
            "tool_choice": self._context.choice,
            "tools": list(self._context.tools.values()),
            "metadata": dict(self._metadata),
            "id": self._response_id,
            "object": "response",
            "created_at": self._created_at,
            "model": self._logical_model,
            "status": status,
            "output": [item for _index, item in sorted(output, key=lambda pair: pair[0])],
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
            "parallel_tool_calls": self._context.parallel,
            "tool_choice": self._context.choice,
            "tools": list(self._context.tools.values()),
            "metadata": dict(self._metadata),
            "id": self._response_id,
            "object": "response",
            "created_at": self._created_at,
            "model": self._logical_model,
            "status": "failed",
            "output": (
                [
                    {
                        "type": "message",
                        "id": self._item_id,
                        "role": "assistant",
                        "status": "incomplete",
                        "content": (
                            [{"type": "refusal", "refusal": "".join(self._refusal_parts)}]
                            if self._refusal_parts
                            else [{"type": "output_text", "text": full_text, "annotations": []}]
                        ),
                    }
                ]
                if self._message_index is not None
                else []
            ),
            "error": {"message": message, "type": "upstream_error"},
        }
        for index, item_id in self._call_ids.items():
            fragment = self._call_fragments[index]
            failed_response["output"].append(
                {
                    "type": "function_call",
                    "id": item_id,
                    "call_id": fragment["id"],
                    "name": fragment["name"],
                    "arguments": fragment["arguments"],
                    "status": "incomplete",
                }
            )
        indexed_output = [
            (index, {**item, "status": "incomplete"}) for index, item in self._archived_messages
        ]
        for item in failed_response["output"]:
            output_index = (
                self._message_index
                if item["type"] == "message"
                else next(
                    self._public_call_indices[key]
                    for key, value in self._call_ids.items()
                    if value == item["id"]
                )
            )
            if output_index is not None:
                indexed_output.append((output_index, item))
        failed_response["output"] = [
            item for _, item in sorted(indexed_output, key=lambda pair: pair[0])
        ]
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


class OpenAICompatibleAdapter[ContextT: ChatRequestContext]:
    """Responses/embeddings translation with explicit provider capability hooks."""

    provider = "openai_compatible"
    provider_label = "OpenAI-compatible"
    stream_decoder_class: type[OpenAICompatibleStreamDecoder[ContextT]] = (
        OpenAICompatibleStreamDecoder
    )

    def request_context(self, body: dict[str, Any]) -> ContextT:
        """Return the provider-owned request validation context."""
        raise NotImplementedError

    def permits(self, body: dict[str, Any], context: ContextT) -> bool:
        """Check the exact provider feature combination before message assembly."""
        raise NotImplementedError

    def build_messages(
        self, body: dict[str, Any], context: ContextT, *, deadline: float | None = None
    ) -> list[dict[str, Any]]:
        """Build validated provider messages without transport or global state."""
        raise NotImplementedError

    def translate_calls(
        self, raw: Any, context: ContextT, *, completed: bool, refusal: bool
    ) -> list[dict[str, Any]]:
        """Validate and translate provider calls; no permissive default."""
        raise NotImplementedError

    def supports_operation(self, operation: str) -> bool:
        # Operation allow-list is enforced by BackendConfig.supported_operations;
        # the adapter additionally gates per-operation validation.
        return operation in {"responses", "embeddings", "chat/completions"}

    # -- request validation -------------------------------------------------
    def check_request(
        self,
        operation: str,
        body: dict[str, Any],
        *,
        deadline_monotonic: float | None = None,
        prepared_media: PreparedGoogleMedia | None = None,
    ) -> AdapterRejection | None:
        _ = prepared_media
        if operation == "embeddings":
            return self._check_embeddings_request(body)
        if operation in {"responses", "chat/completions"}:
            return self._check_feature_request(body, deadline=deadline_monotonic)
        return _rejection(f"Unsupported operation '{operation}'", "unsupported_operation")

    def _check_feature_request(
        self, body: dict[str, Any], *, deadline: float | None = None
    ) -> AdapterRejection | None:
        rejection = self._check_responses_request(body)
        if rejection is not None:
            return rejection
        try:
            context = self.request_context(body)
            if not self.permits(body, context):
                return _rejection("Request feature combination is not enabled for this backend")
            self.build_messages(body, context, deadline=deadline)
        except (ValueError, TypeError, RecursionError):
            return _rejection(
                f"Invalid or unsupported {self.provider_label} tools, schema, media or history"
            )
        return None

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
                    return _rejection(
                        f"Unsupported field '{key}' for {self.provider_label} backends"
                    )
                return _rejection(f"Unsupported field '{key}' for {self.provider_label} backends")
        if "previous_response_id" in body:
            return _rejection(
                f"previous_response_id is not supported for {self.provider_label} backends"
            )
        conversation = body.get("conversation")
        if isinstance(conversation, dict) and conversation:
            return _rejection(
                f"Stored conversations are not supported for {self.provider_label} backends"
            )
        if isinstance(conversation, str) and conversation.strip():
            return _rejection(
                f"Stored conversations are not supported for {self.provider_label} backends"
            )
        if body.get("store") is True:
            return _rejection(
                f"Stored responses are not supported for {self.provider_label} backends"
            )
        if body.get("background") is True:
            return _rejection(
                f"Background responses are not supported for {self.provider_label} backends"
            )
        include = body.get("include")
        if include is not None and include != []:
            return _rejection(
                f"Extended response includes are not supported for {self.provider_label} backends"
            )
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
            # Detailed history/media validation belongs to the bounded feature helper.
            for item in input_value:
                if isinstance(item, dict) and item.get("type", "message") == "message":
                    content = item.get("content")
                    if content in ("", [], None) or (
                        isinstance(content, str) and not content.strip()
                    ):
                        return AdapterRejection(
                            422, "invalid_request", "Message content must be non-empty"
                        )
                    if isinstance(content, list) and any(
                        (isinstance(part, str) and not part.strip())
                        or (
                            isinstance(part, dict)
                            and part.get("type", "input_text") in _ALLOWED_PART_TYPES
                            and isinstance(part.get("text"), str)
                            and not part["text"].strip()
                        )
                        for part in content
                    ):
                        return AdapterRejection(
                            422, "invalid_request", "Message content must be non-empty"
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
        prepared_media: PreparedGoogleMedia | None = None,
    ) -> dict[str, Any]:
        _ = prepared_media
        if operation == "embeddings":
            out: dict[str, Any] = {"model": deployment, "input": body["input"]}
            if body.get("dimensions") is not None:
                out["dimensions"] = body["dimensions"]
            out["encoding_format"] = "float"
            return out
        context = self.request_context(body)
        if not self.permits(body, context):
            raise ValueError(f"{self.provider_label} request features are disabled")
        messages = self.build_messages(body, context)
        upstream: dict[str, Any] = {"model": deployment, "messages": messages}
        if context.tools:
            upstream["tools"] = [
                {
                    "type": "function",
                    "function": {key: value for key, value in tool.items() if key != "type"},
                }
                for tool in context.tools.values()
            ]
            choice = context.choice
            upstream["tool_choice"] = (
                {"type": "function", "function": {"name": choice["name"]}}
                if isinstance(choice, dict)
                else choice
            )
            upstream["parallel_tool_calls"] = context.parallel
        if context.text_format is not None:
            fmt = context.text_format
            upstream["response_format"] = (
                {
                    "type": "json_schema",
                    "json_schema": {key: value for key, value in fmt.items() if key != "type"},
                }
                if fmt["type"] == "json_schema"
                else {"type": "json_object"}
            )
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
        request_body: dict[str, Any] | None = None,
    ) -> TranslatedSuccess:
        if operation == "embeddings":
            return self._translate_embeddings_success(
                upstream,
                logical_model=logical_model,
                expected_input_count=expected_input_count,
                expected_dimensions=expected_dimensions,
            )
        context = self.request_context(request_body or {})
        translated = self._translate_responses_success(
            upstream, logical_model=logical_model, context=context
        )
        translated.body["metadata"] = dict(metadata or {})
        translated.body.update(
            {
                "parallel_tool_calls": context.parallel,
                "tool_choice": context.choice,
                "tools": list(context.tools.values()),
            }
        )
        return translated

    def _translate_responses_success(
        self, upstream: Any, *, logical_model: str, context: ContextT
    ) -> TranslatedSuccess:
        if not isinstance(upstream, dict):
            raise ValueError(f"{self.provider_label} success body must be a JSON object")
        choices = upstream.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError(f"{self.provider_label} success must carry exactly one choice")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise ValueError(f"{self.provider_label} choice must be an object")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise ValueError(f"{self.provider_label} choice must carry an assistant message")
        if message.get("role", "assistant") != "assistant":
            raise ValueError(f"{self.provider_label} message role must be assistant")
        if set(message) - {"role", "content", "tool_calls", "refusal"}:
            raise ValueError(f"Unsupported {self.provider_label} output or provider state")
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
                    raise ValueError(f"{self.provider_label} message content parts must be text")
                part_type = part.get("type", "text")
                if part_type not in ("text", None) or set(part) - {"type", "text"}:
                    raise ValueError(f"{self.provider_label} message content must be text")
                part_text = part.get("text")
                if not isinstance(part_text, str):
                    raise ValueError(f"{self.provider_label} message content parts must carry text")
            text = _extract_text(content, provider_label=self.provider_label)
        else:
            raise ValueError(f"{self.provider_label} message content must be text")
        finish_reason = choice.get("finish_reason")
        if finish_reason not in _ALLOWED_FINISH_REASONS | {"tool_calls"}:
            raise ValueError(f"Unsupported {self.provider_label} finish reason '{finish_reason}'")
        completed = finish_reason in {"stop", "tool_calls"}
        refusal = message.get("refusal")
        calls = self.translate_calls(
            message.get("tool_calls", []), context, completed=completed, refusal=bool(refusal)
        )
        if finish_reason == "tool_calls" and not calls:
            raise ValueError(f"{self.provider_label} tool finish must carry calls")
        refusal = message.get("refusal")
        if refusal is not None and not isinstance(refusal, str):
            raise ValueError(f"{self.provider_label} refusal must be text")
        if not refusal:
            context.validate_text(text, completed=completed, has_calls=bool(calls))
        usage = upstream.get("usage")
        input_tokens: int | None = None
        output_tokens: int | None = None
        total_tokens: int | None = None
        if usage is not None:
            if not isinstance(usage, dict):
                raise ValueError(f"{self.provider_label} usage must be an object")
            prompt = usage.get("prompt_tokens")
            completion = usage.get("completion_tokens")
            total = usage.get("total_tokens")
            for value in (prompt, completion, total):
                if value is not None and (
                    isinstance(value, bool) or not isinstance(value, int) or value < 0
                ):
                    raise ValueError(
                        f"{self.provider_label} usage tokens must be non-negative integers"
                    )
            if prompt is None:
                raise ValueError(f"{self.provider_label} usage must report prompt_tokens")
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
        if completed:
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
            "content": (
                [{"type": "refusal", "refusal": refusal}]
                if refusal
                else [{"type": "output_text", "text": text, "annotations": []}]
            ),
        }
        public: dict[str, Any] = {
            "id": response_id,
            "object": "response",
            "created_at": created_at,
            "model": logical_model,
            "status": status,
            "output": ([output_item] if text or refusal or not calls else []) + calls,
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
            raise ValueError(f"{self.provider_label} embeddings body must be a JSON object")
        data = upstream.get("data")
        if not isinstance(data, list) or not data:
            raise ValueError(f"{self.provider_label} embeddings must return a non-empty data list")
        if expected_input_count is not None and len(data) != expected_input_count:
            raise ValueError(
                f"{self.provider_label} embeddings count must match the request input count"
            )
        vectors: list[list[float]] = []
        for index, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError(f"{self.provider_label} embedding items must be objects")
            if item.get("index") != index:
                raise ValueError(f"{self.provider_label} embedding indexes must match input order")
            embedding = item.get("embedding")
            if not isinstance(embedding, list) or not embedding:
                raise ValueError(
                    f"{self.provider_label} embedding vectors must be non-empty arrays"
                )
            values: list[float] = []
            for value in embedding:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(
                        f"{self.provider_label} embedding values must be finite numbers"
                    )
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError(
                        f"{self.provider_label} embedding values must be finite numbers"
                    )
                values.append(number)
            vectors.append(values)
        dimensions = len(vectors[0])
        if expected_dimensions is not None and dimensions != expected_dimensions:
            raise ValueError(
                f"{self.provider_label} embedding dimensions must match the requested dimensions"
            )
        if any(len(vector) != dimensions for vector in vectors):
            raise ValueError(f"{self.provider_label} embedding vectors must share dimensions")
        usage = upstream.get("usage")
        input_tokens: int | None = None
        if usage is not None:
            if not isinstance(usage, dict):
                raise ValueError(f"{self.provider_label} embeddings usage must be an object")
            prompt = usage.get("prompt_tokens")
            if prompt is not None and (
                isinstance(prompt, bool) or not isinstance(prompt, int) or prompt < 0
            ):
                raise ValueError(
                    f"{self.provider_label} embeddings usage must be a non-negative integer"
                )
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

    def extract_usage(self, operation: str, upstream: Any) -> tuple[int | None, int | None]:
        usage = upstream.get("usage") if isinstance(upstream, dict) else None
        if not isinstance(usage, dict):
            return None, None
        prompt = usage.get("prompt_tokens")
        completion = 0 if operation == "embeddings" else usage.get("completion_tokens")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (prompt, completion)
        ):
            return None, None
        return prompt, completion

    def create_stream_decoder(
        self,
        *,
        logical_model: str,
        request_input: Any = None,
        metadata: dict[str, Any] | None = None,
        request_body: dict[str, Any] | None = None,
    ) -> OpenAICompatibleStreamDecoder[ContextT]:
        _ = request_input
        return self.stream_decoder_class(
            logical_model=logical_model,
            metadata=metadata,
            context=self.request_context(request_body or {}),
        )


def _split_sse_event(buffer: bytes) -> tuple[bytes | None, bytes]:
    boundaries = [(buffer.find(d), d) for d in (b"\r\n\r\n", b"\n\n")]
    found = [(i, d) for i, d in boundaries if i >= 0]
    if found:
        index, delimiter = min(found)
        return buffer[:index], buffer[index + len(delimiter) :]
    return None, buffer


__all__ = [
    "MAX_OPENAI_ASSEMBLED_TEXT_BYTES",
    "MAX_OPENAI_EVENT_BYTES",
    "MAX_OPENAI_SSE_BUFFER_BYTES",
    "ChatRequestContext",
    "OpenAICompatibleAdapter",
    "OpenAICompatibleStreamDecoder",
]
