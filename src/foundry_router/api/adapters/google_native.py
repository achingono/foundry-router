"""Explicit native generateContent mapping, with stateless unsigned history only.

Transport/auth remains in backends. Native framing and usage are validated before
sharing the compatibility adapter's public Responses item/event construction.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any, TypeGuard, cast

if TYPE_CHECKING:
    from foundry_router.api.google_pdf import PreparedGoogleMedia

from foundry_router.api.adapters.base import AdapterRejection, TranslatedSuccess
from foundry_router.api.adapters.google_ai_studio import GoogleAiStudioAdapter, GoogleStreamDecoder
from foundry_router.api.adapters.google_image_request import (
    image_output_request,
    validate_image_output_request,
)
from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.api.adapters.google_tools import (
    build_messages,
    request_context,
    requested_features,
    validate_identity,
)

_BLOCKS = {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "OTHER"}
_FILTERS = {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}
_SAFE_REFUSAL = "The provider declined this request."
_MAX_TOKENS = 1000000000
_ENVELOPE_FIELDS = {"candidates", "usageMetadata", "promptFeedback", "modelVersion", "responseId"}


def _token(value: Any) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= _MAX_TOKENS


def native_usage(
    upstream: Any, *, strict: bool = False, accept_thoughts: bool = False
) -> tuple[int | None, int | None]:
    usage = upstream.get("usageMetadata") if isinstance(upstream, dict) else None
    if usage is None and (not isinstance(upstream, dict) or "usageMetadata" not in upstream):
        return None, None
    if not isinstance(usage, dict):
        if strict:
            raise ValueError("Native usage must be an object")
        return None, None
    prompt = usage.get("promptTokenCount")
    candidates = usage.get("candidatesTokenCount")
    thoughts = usage.get("thoughtsTokenCount", 0)
    tools = usage.get("toolUsePromptTokenCount", 0)
    cache = usage.get("cachedContentTokenCount", 0)
    total = usage.get("totalTokenCount")
    valid = (
        _token(prompt)
        and _token(candidates)
        and _token(thoughts)
        and _token(tools)
        and _token(cache)
        and cache <= prompt
        and (total is None or (_token(total) and total == prompt + candidates + thoughts))
    )
    if not valid:
        if strict:
            raise ValueError("Invalid native usage dimensions")
        return None, None
    if strict and (tools or (thoughts and not accept_thoughts)):
        raise ValueError("Native thinking or tool prompt usage is disabled")
    # Unexpected billed dimensions still retained through conversion failure.
    return cast("int", prompt) + cast("int", tools), cast("int", candidates) + cast("int", thoughts)


def _native_output(upstream: Any, *, drop_signatures: bool = False) -> dict[str, Any]:
    if not isinstance(upstream, dict) or "error" in upstream:
        raise ValueError("Invalid native response envelope")
    if set(upstream) - _ENVELOPE_FIELDS:
        raise ValueError("Unsupported native envelope or provider state")
    feedback = upstream.get("promptFeedback")
    if "promptFeedback" in upstream and (
        not isinstance(feedback, dict)
        or set(feedback) - {"blockReason", "blockReasonMessage", "safetyRatings"}
    ):
        raise ValueError("Unsupported native feedback or provider state")
    candidates = upstream.get("candidates", [])
    if not isinstance(candidates, list):
        raise ValueError("Invalid native candidates")
    if not candidates:
        feedback = upstream.get("promptFeedback")
        if isinstance(feedback, dict) and set(feedback) - {
            "blockReason",
            "blockReasonMessage",
            "safetyRatings",
        }:
            raise ValueError("Unsupported native feedback or provider state")
        if (
            isinstance(feedback, dict)
            and isinstance(feedback.get("blockReason"), str)
            and feedback["blockReason"] in _BLOCKS
        ):
            return {
                "content": None,
                "tool_calls": [],
                "refusal": _SAFE_REFUSAL,
                "finish_reason": "content_filter",
                "ordered_parts": [],
                "dropped_signatures": 0,
            }
        raise ValueError("Native response lacks candidate or block evidence")
    if len(candidates) != 1 or not isinstance(candidates[0], dict):
        raise ValueError("Native response requires one candidate")
    candidate = candidates[0]
    if set(candidate) - {
        "index",
        "content",
        "finishReason",
        "safetyRatings",
        "tokenCount",
        "avgLogprobs",
    }:
        raise ValueError("Unsupported native candidate or provider state")
    if candidate.get("index", 0) != 0:
        raise ValueError("Native candidate index must be zero")
    content = candidate.get("content", {"role": "model", "parts": []})
    if not isinstance(content, dict) or content.get("role", "model") != "model":
        raise ValueError("Invalid native output role")
    if set(content) - {"role", "parts"}:
        raise ValueError("Unsupported native content or provider state")
    parts = content.get("parts", [])
    if not isinstance(parts, list) or len(parts) > 64:
        raise ValueError("Native output parts exceed bound")
    text: list[str] = []
    calls: list[dict[str, Any]] = []
    ordered: list[dict[str, Any]] = []
    output_bytes = 0
    dropped_signatures = 0
    for part in parts:
        if not isinstance(part, dict):
            raise ValueError("Invalid native output part")
        if set(part) == {"text"} and isinstance(part["text"], str):
            text.append(part["text"])
            ordered.append({"content": part["text"]})
            output_bytes += len(part["text"].encode())
        elif (
            drop_signatures
            and set(part) == {"text", "thoughtSignature"}
            and isinstance(part["text"], str)
            and isinstance(part["thoughtSignature"], str)
            and part["thoughtSignature"]
        ):
            # Text-pilot decision (level profiles only): thought signatures are
            # dropped after usage capture. They are never persisted, replayed,
            # or forwarded, and their presence alone grants no history or tool
            # support. All other profiles keep rejecting signature state.
            text.append(part["text"])
            ordered.append({"content": part["text"]})
            output_bytes += len(part["text"].encode())
            dropped_signatures += 1
        elif set(part) == {"functionCall"}:
            function = part["functionCall"]
            if (
                not isinstance(function, dict)
                or set(function) != {"id", "name", "args"}
                or not isinstance(function["args"], dict)
            ):
                raise ValueError("Native function identity/arguments required")
            identity = validate_identity(function["id"])
            calls.append(
                {
                    "id": identity,
                    "type": "function",
                    "function": {
                        "name": function["name"],
                        "arguments": json.dumps(
                            function["args"],
                            ensure_ascii=False,
                            separators=(",", ":"),
                            allow_nan=False,
                        ),
                    },
                }
            )
            output_bytes += len(calls[-1]["function"]["arguments"].encode())
            ordered.append({"tool_calls": [calls[-1]]})
        else:
            # Reject thought/signature/media/unknown state before common translation.
            raise ValueError("Unsupported native output or provider state")
        if output_bytes > 4 * 1024 * 1024:
            raise ValueError("Native output exceeds aggregate byte bound")
    reason = candidate.get("finishReason")
    if reason is not None and not isinstance(reason, str):
        raise ValueError("Invalid native finish reason")
    finish = None
    refusal = None
    if reason == "STOP":
        finish = "tool_calls" if calls else "stop"
    elif reason == "MAX_TOKENS":
        finish = "length"
    elif reason in _FILTERS:
        finish = "content_filter"
        if not text and not calls:
            refusal = _SAFE_REFUSAL
    elif reason is not None:
        raise ValueError("Unsupported native finish reason")
    return {
        "content": "".join(text) or None,
        "tool_calls": calls,
        "refusal": refusal,
        "finish_reason": finish,
        "ordered_parts": ordered,
        "dropped_signatures": dropped_signatures,
    }


def _contents(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    contents: list[dict[str, Any]] = []
    system: list[dict[str, str]] = []
    call_names: dict[str, str] = {}
    for message in messages:
        role = message["role"]
        content = message.get("content")
        if role == "system":
            if contents:
                raise ValueError("Native system instructions must precede history")
            if not isinstance(content, str):
                raise ValueError("Native system instruction must be text")
            system.append({"text": content})
            continue
        parts: list[dict[str, Any]] = []
        native_role = "model" if role == "assistant" else "user"
        if role == "tool":
            identity = message["tool_call_id"]
            parts.append(
                {
                    "functionResponse": {
                        "id": identity,
                        "name": call_names[identity],
                        "response": {"output": content},
                    }
                }
            )
        else:
            message_parts: list[dict[str, Any]] = (
                [{"type": "text", "text": content}] if isinstance(content, str) else content or []
            )
            for part in message_parts:
                if part["type"] == "text":
                    parts.append({"text": part["text"]})
                else:
                    uri = (
                        part["file_data"]
                        if part["type"] == "inline_file"
                        else part["image_url"]["url"]
                    )
                    prefix, data = uri.split(",", 1)
                    native_part = {
                        "inlineData": {"mimeType": prefix[5:].split(";", 1)[0], "data": data}
                    }
                    if prefix == "data:video/avi;base64":
                        native_part["videoMetadata"] = {"fps": 1}
                    parts.append(native_part)
            for call in message.get("tool_calls", []):
                function = call["function"]
                call_names[call["id"]] = function["name"]
                parts.append(
                    {
                        "functionCall": {
                            "id": call["id"],
                            "name": function["name"],
                            "args": load_bounded_json(function["arguments"]),
                        }
                    }
                )
        if contents and contents[-1]["role"] == native_role:
            contents[-1]["parts"].extend(parts)
        else:
            contents.append({"role": native_role, "parts": parts})
    if not contents:
        raise ValueError("Native request requires generation history")
    return contents, system


def unsigned_ordinary_profile(profile: Any) -> Any:
    """Return the unsigned thinking-disabled delegate profile for sealed intake.

    Centralizes the two sealed-path constructions so a thinking level can never
    leak into the unsigned delegate (where the signed overwrite would silently
    clobber it). ``model_copy`` skips validators, hence the explicit assert.
    """
    ordinary = profile.model_copy(
        update={
            "continuation_policy": "unsigned",
            "native_thinking_disabled": True,
            "native_thinking_level": None,
        }
    )
    assert ordinary.native_thinking_level is None
    return ordinary


class GoogleNativeAdapter(GoogleAiStudioAdapter):
    """Native unsigned, thinking-disabled Responses subset, explicitly configured."""

    def supports_operation(self, operation: str) -> bool:
        return operation == "responses"

    def _generation_request(self, body: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        # The standard image tool is a generation modality, never a function declaration.
        image = image_output_request(body)
        if image:
            validate_image_output_request(body)
            bound = self.profile.generated_output_tokens_bound
            if (
                "image_output" not in self.profile.features
                or type(body.get("max_output_tokens", bound)) is not int
                or body.get("max_output_tokens", bound) != bound
            ):
                raise ValueError("Generated image capability or output bound is unavailable")
            return {key: value for key, value in body.items() if key != "tools"}, True
        return body, False

    def check_request(
        self,
        operation: str,
        body: dict[str, Any],
        *,
        deadline_monotonic: float | None = None,
        prepared_media: PreparedGoogleMedia | None = None,
    ) -> AdapterRejection | None:
        if not self.supports_operation(operation):
            return AdapterRejection(422, "unsupported_parameter", "Native capability is disabled")
        level = self.profile.native_thinking_level
        if level is None:
            if not self.profile.native_thinking_disabled:
                return AdapterRejection(
                    422, "unsupported_parameter", "Native capability is disabled"
                )
        elif (
            self.profile.native_thinking_disabled or self.profile.native_thinking_budget is not None
        ):
            return AdapterRejection(422, "unsupported_parameter", "Native capability is disabled")
        try:
            body, image = self._generation_request(body)
        except ValueError:
            return AdapterRejection(
                422, "unsupported_parameter", "Invalid image generation request"
            )
        rejection = self._check_responses_request(body)
        if rejection:
            return rejection
        try:
            context = request_context(body, self.profile)
            features = requested_features(body, context) | ({"image_output"} if image else set())
            if not self.profile.permits(features):
                return AdapterRejection(
                    422, "unsupported_input", "Native feature combination disabled"
                )
            _contents(
                build_messages(
                    body,
                    self.profile,
                    context,
                    deadline=deadline_monotonic,
                    preserve_assistant_order=True,
                    prepared_media=prepared_media,
                )
            )
        except (ValueError, KeyError):
            return AdapterRejection(422, "unsupported_input", "Invalid native stateless history")
        return None

    def build_upstream_body(
        self,
        operation: str,
        body: dict[str, Any],
        *,
        deployment: str,
        default_output_tokens: int,
        prepared_media: PreparedGoogleMedia | None = None,
    ) -> dict[str, Any]:
        _ = deployment
        body, image = self._generation_request(body)
        level = self.profile.native_thinking_level
        thinking_ok = (
            self.profile.native_thinking_disabled
            if level is None
            else not self.profile.native_thinking_disabled
            and self.profile.native_thinking_budget is None
        )
        if (
            not self.supports_operation(operation)
            or not thinking_ok
            or self._check_responses_request(body)
        ):
            raise ValueError("Native request is unsupported")
        context = request_context(body, self.profile)
        features = requested_features(body, context) | ({"image_output"} if image else set())
        if not self.profile.permits(features):
            raise ValueError("Native feature combination disabled")
        contents, system = _contents(
            build_messages(
                body,
                self.profile,
                context,
                preserve_assistant_order=True,
                prepared_media=prepared_media,
            )
        )
        if level is None:
            thinking_config: dict[str, Any] = {"thinkingBudget": 0}
        else:
            thinking_config = {"thinkingLevel": level}
        generation: dict[str, Any] = {
            "maxOutputTokens": body.get(
                "max_output_tokens",
                self.profile.generated_output_tokens_bound if image else default_output_tokens,
            ),
            "candidateCount": 1,
            "thinkingConfig": thinking_config,
            "responseModalities": ["TEXT"],
        }
        if image:
            generation["responseModalities"] = ["TEXT", "IMAGE"]
            generation["imageConfig"] = {"aspectRatio": "1:1", "imageSize": "1K"}
        for public, native in (("temperature", "temperature"), ("top_p", "topP")):
            if public in body:
                generation[native] = body[public]
        if context.text_format is not None:
            generation["responseMimeType"] = "application/json"
            if context.text_format["type"] == "json_schema":
                generation["responseJsonSchema"] = context.text_format["schema"]
        upstream: dict[str, Any] = {"contents": contents, "generationConfig": generation}
        if system:
            upstream["systemInstruction"] = {"parts": system}
        if context.tools:
            upstream["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": tool["name"],
                            "parametersJsonSchema": tool["parameters"],
                            **(
                                {"description": tool["description"]}
                                if "description" in tool
                                else {}
                            ),
                        }
                        for tool in context.tools.values()
                    ]
                }
            ]
            choice = context.choice
            mode = (
                "ANY"
                if choice == "required" or isinstance(choice, dict)
                else "NONE"
                if choice == "none"
                else "AUTO"
            )
            config: dict[str, Any] = {"mode": mode}
            if isinstance(choice, dict):
                config["allowedFunctionNames"] = [choice["name"]]
            upstream["toolConfig"] = {"functionCallingConfig": config}
        return upstream

    def extract_usage(self, operation: str, upstream: Any) -> tuple[int | None, int | None]:
        _ = operation
        return native_usage(upstream)

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
        if operation != "responses":
            raise ValueError("Native supports only Responses")
        _ = (expected_input_count, expected_dimensions)
        input_tokens, output_tokens = native_usage(
            upstream,
            strict=True,
            accept_thoughts=self.profile.native_thinking_level is not None,
        )
        result = _native_output(
            upstream,
            drop_signatures=self.profile.native_thinking_level is not None,
        )
        if result["finish_reason"] is None:
            raise ValueError("Native response requires finish evidence")
        translated = self._translate_responses_success(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            **{key: result[key] for key in ("content", "tool_calls", "refusal")},
                        },
                        "finish_reason": result["finish_reason"],
                    }
                ],
                **(
                    {"usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens}}
                    if input_tokens is not None
                    else {}
                ),
            },
            logical_model=logical_model,
            context=request_context(request_body or {}, self.profile),
        )
        translated.body["metadata"] = dict(metadata or {})
        context = request_context(request_body or {}, self.profile)
        translated.body.update(
            {
                "parallel_tool_calls": context.parallel,
                "tool_choice": context.choice,
                "tools": list(context.tools.values()),
            }
        )
        if result["ordered_parts"]:
            calls = {
                item["call_id"]: item
                for item in translated.body["output"]
                if item["type"] == "function_call"
            }
            output: list[dict[str, Any]] = []
            for part in result["ordered_parts"]:
                if "tool_calls" in part:
                    output.append(calls[part["tool_calls"][0]["id"]])
                elif part["content"]:
                    if output and output[-1]["type"] == "message":
                        output[-1]["content"][0]["text"] += part["content"]
                    else:
                        output.append(
                            {
                                "type": "message",
                                "id": f"msg_{uuid.uuid4().hex[:24]}",
                                "role": "assistant",
                                "status": translated.body["status"],
                                "content": [
                                    {
                                        "type": "output_text",
                                        "text": part["content"],
                                        "annotations": [],
                                    }
                                ],
                            }
                        )
            translated.body["output"] = output
        return translated

    def create_stream_decoder(
        self,
        *,
        logical_model: str,
        request_input: Any = None,
        metadata: dict[str, Any] | None = None,
        request_body: dict[str, Any] | None = None,
    ) -> GoogleNativeStreamDecoder:
        _ = request_input
        return GoogleNativeStreamDecoder(
            logical_model=logical_model,
            metadata=metadata,
            context=request_context(request_body or {}, self.profile),
            accept_thoughts=self.profile.native_thinking_level is not None,
        )


class GoogleNativeStreamDecoder(GoogleStreamDecoder):
    """Native SSE terminates only at clean EOF with validated finish evidence."""

    usage_invalid = False

    def __init__(self, *args: Any, accept_thoughts: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._accept_thoughts = accept_thoughts

    def _archive_message(self) -> list[bytes]:
        if self._message_index is None:
            return []
        if len(self._archived_messages) >= 64:
            raise ValueError("Native message segments exceed bound")
        text = "".join(self._text_parts)
        part = {"type": "output_text", "text": text, "annotations": []}
        item = {
            "type": "message",
            "id": self._item_id,
            "role": "assistant",
            "status": "incomplete",
            "content": [part],
        }
        index = self._message_index
        events = [
            self._sse(
                {
                    "type": kind,
                    "sequence_number": self._next_sequence(),
                    "output_index": index,
                    **fields,
                }
            )
            for kind, fields in (
                (
                    "response.output_text.done",
                    {"item_id": self._item_id, "content_index": 0, "text": text},
                ),
                (
                    "response.content_part.done",
                    {"item_id": self._item_id, "content_index": 0, "part": part},
                ),
            )
        ]
        self._archived_messages.append((index, item))
        self._message_index = None
        self._text_parts = []
        self._item_id = f"msg_{uuid.uuid4().hex[:24]}"
        return events

    @property
    def usage(self) -> tuple[int | None, int | None]:
        return (None, None) if self.usage_invalid else super().usage

    def _absorb_calls(self, calls: Any) -> None:
        super()._absorb_calls(calls)
        for call in calls:
            fragment = self._call_fragments[call["index"]]
            self._context.validate_arguments(fragment["name"], fragment["arguments"])
            fragment["ready"] = True

    def _handle_provider_event(self, raw: bytes) -> list[bytes]:
        data = b"\n".join(
            line[5:].lstrip() for line in raw.splitlines() if line.startswith(b"data:")
        )
        if not data.strip():
            return []
        try:
            payload = load_bounded_json(data.decode(), max_bytes=262144)
        except ValueError:
            self.usage_invalid = True
            raise
        known = native_usage(payload)
        if known[0] is not None and known[1] is not None:
            if any(
                previous is not None and current is not None and current < previous
                for previous, current in zip(self.usage, known, strict=True)
            ):
                self.usage_invalid = True
                raise ValueError("Native cumulative usage decreased")
            self._input_tokens, self._output_tokens = known
        try:
            native_usage(payload, strict=True, accept_thoughts=self._accept_thoughts)
        except ValueError:
            if isinstance(payload, dict) and "usageMetadata" in payload and known == (None, None):
                self.usage_invalid = True
            raise
        if not isinstance(payload, dict):
            raise ValueError("Invalid native SSE envelope")
        if set(payload) - _ENVELOPE_FIELDS:
            raise ValueError("Unsupported native envelope or provider state")
        if "candidates" not in payload and "promptFeedback" not in payload:
            if "usageMetadata" in payload:
                return []
            raise ValueError("Native SSE envelope lacks content")
        result = _native_output(payload, drop_signatures=self._accept_thoughts)
        if self._finish_reason is not None:
            raise ValueError("Native content arrived after finish")
        events: list[bytes] = []
        for part in result["ordered_parts"]:
            delta = part
            if "tool_calls" in delta:
                events.extend(self._archive_message())
                delta = {
                    "tool_calls": [{"index": len(self._call_fragments), **delta["tool_calls"][0]}]
                }
            events.extend(
                self._handle_payload({"choices": [{"delta": delta, "finish_reason": None}]})
            )
        finish = result["finish_reason"]
        if finish == "stop" and self._call_fragments:
            finish = "tool_calls"
        events.extend(
            self._handle_payload(
                {"choices": [{"delta": {"refusal": result["refusal"]}, "finish_reason": finish}]}
            )
        )
        return events

    def finish(self) -> list[bytes]:
        if self._buffer or not self._validated or self._finish_reason is None:
            raise ValueError("Native stream ended without clean finish evidence")
        return self._terminal_events()
