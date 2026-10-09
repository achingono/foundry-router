"""Bounded text-only capability contract for configured compatible upstreams."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from foundry_router.api.adapters.openai_compatible import (
    OpenAICompatibleAdapter,
    OpenAICompatibleStreamDecoder,
)

MAX_HISTORY_ITEMS = 128
MAX_TEXT_BYTES = 256 * 1024
MAX_TEXT_PARTS = 128
_ROLES = frozenset({"system", "developer", "user", "assistant"})


@dataclass(frozen=True)
class TextRequestContext:
    """No tools, schemas or provider state; no inherited Google capability policy."""

    tools: dict[str, dict[str, Any]] = field(default_factory=dict)
    choice: Any = "auto"
    parallel: bool = False
    text_format: dict[str, Any] | None = None
    max_calls: int = 0
    max_argument_bytes: int = 0

    def validate_text(self, text: str, *, completed: bool, has_calls: bool) -> None:
        if has_calls or (completed and not text.strip()):
            raise ValueError("Compatible text response requires nonempty text without calls")


def _no_calls(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or raw:
        raise ValueError("Compatible text backends do not support function calls")
    return []


class CompatibleTextStreamDecoder(OpenAICompatibleStreamDecoder[TextRequestContext]):
    def _translate_calls(self, raw: Any, *, completed: bool, refusal: bool) -> list[dict[str, Any]]:
        _ = completed, refusal
        return _no_calls(raw)


class CompatibleTextAdapter(OpenAICompatibleAdapter[TextRequestContext]):
    """Fixed Chat Completions dialect with text histories and float embeddings."""

    stream_decoder_class = CompatibleTextStreamDecoder

    def request_context(self, body: dict[str, Any]) -> TextRequestContext:
        _ = body
        return TextRequestContext()

    def permits(self, body: dict[str, Any], context: TextRequestContext) -> bool:
        _ = context
        return not any(
            key in body for key in ("tools", "tool_choice", "parallel_tool_calls", "text")
        )

    def build_messages(
        self,
        body: dict[str, Any],
        context: TextRequestContext,
        *,
        deadline: float | None = None,
    ) -> list[dict[str, Any]]:
        _ = context
        used_bytes = 0

        def text(value: Any) -> str:
            nonlocal used_bytes
            if deadline is not None and time.monotonic() >= deadline:
                raise ValueError("Compatible text intake deadline exceeded")
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Compatible histories require nonempty text")
            used_bytes += len(value.encode())
            if used_bytes > MAX_TEXT_BYTES:
                raise ValueError("Compatible text history exceeds its byte bound")
            return value

        messages: list[dict[str, Any]] = []
        if body.get("instructions") is not None:
            messages.append({"role": "system", "content": text(body["instructions"])})
        inputs = body.get("input")
        if isinstance(inputs, str):
            messages.append({"role": "user", "content": text(inputs)})
            return messages
        if not isinstance(inputs, list) or not 1 <= len(inputs) <= MAX_HISTORY_ITEMS:
            raise ValueError("Compatible text history exceeds its item bound")
        for item in inputs:
            if (
                not isinstance(item, dict)
                or set(item) - {"type", "role", "content"}
                or item.get("type", "message") != "message"
                or item.get("role") not in _ROLES
            ):
                raise ValueError("Compatible histories require ordinary text messages")
            content = item.get("content")
            if isinstance(content, list):
                if not 1 <= len(content) <= MAX_TEXT_PARTS:
                    raise ValueError("Compatible text parts exceed their item bound")
                parts = []
                for part in content:
                    if (
                        not isinstance(part, dict)
                        or set(part) - {"type", "text"}
                        or part.get("type") not in {"input_text", "output_text", "text"}
                    ):
                        raise ValueError("Compatible histories do not support media or state")
                    parts.append(text(part.get("text")))
                content = "".join(parts)
            else:
                content = text(content)
            messages.append({"role": item["role"], "content": content})
        return messages

    def translate_calls(
        self, raw: Any, context: TextRequestContext, *, completed: bool, refusal: bool
    ) -> list[dict[str, Any]]:
        _ = context, completed, refusal
        return _no_calls(raw)
