"""Strict typing fixture: generic hooks require no Google-specific methods."""

from dataclasses import dataclass, field
from typing import Any

from foundry_router.api.adapters.openai_compatible import (
    ChatRequestContext,
    OpenAICompatibleAdapter,
    OpenAICompatibleStreamDecoder,
)


@dataclass(frozen=True)
class TextContext:
    tools: dict[str, dict[str, Any]] = field(default_factory=dict)
    choice: Any = "auto"
    parallel: bool = False
    text_format: dict[str, Any] | None = None
    max_calls: int = 0
    max_argument_bytes: int = 0

    def validate_text(self, text: str, *, completed: bool, has_calls: bool) -> None:
        if has_calls or (completed and not text):
            raise ValueError("Text-only output required")


class TextDecoder(OpenAICompatibleStreamDecoder[TextContext]):
    provider_label = "Synthetic"

    def _translate_calls(self, raw: Any, *, completed: bool, refusal: bool) -> list[dict[str, Any]]:
        if raw:
            raise ValueError("Text-only output required")
        return []


class TextAdapter(OpenAICompatibleAdapter[TextContext]):
    provider_label = "Synthetic"
    stream_decoder_class = TextDecoder

    def request_context(self, body: dict[str, Any]) -> TextContext:
        return TextContext()

    def permits(self, body: dict[str, Any], context: TextContext) -> bool:
        return not any(
            key in body for key in ("tools", "text", "tool_choice", "parallel_tool_calls")
        )

    def build_messages(
        self, body: dict[str, Any], context: TextContext, *, deadline: float | None = None
    ) -> list[dict[str, Any]]:
        if not isinstance(body.get("input"), str):
            raise TypeError("Text-only input required")
        return [{"role": "user", "content": body["input"]}]

    def translate_calls(
        self, raw: Any, context: TextContext, *, completed: bool, refusal: bool
    ) -> list[dict[str, Any]]:
        if raw:
            raise ValueError("Text-only output required")
        return []


def accepts_common_context(context: ChatRequestContext) -> None:
    context.validate_text("synthetic", completed=True, has_calls=False)


accepts_common_context(TextContext())
