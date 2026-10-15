"""Bounded nonstream Anthropic Messages translation for OpenCode Zen."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from foundry_router.api.adapters.base import AdapterRejection, TranslatedSuccess
from foundry_router.api.adapters.compatible_text import CompatibleTextAdapter

if TYPE_CHECKING:
    from foundry_router.api.google_pdf import PreparedGoogleMedia

_MAX_TOKENS = 1_000_000_000
_MAX_BLOCKS = 128
_MAX_TEXT_BYTES = 4 * 1024 * 1024
_NULL_FIELDS = {"container", "diagnostics", "stop_details"}
_FIELDS = {
    "id",
    "type",
    "role",
    "model",
    "content",
    "stop_reason",
    "stop_sequence",
    "usage",
} | _NULL_FIELDS


def anthropic_usage(upstream: Any) -> tuple[int | None, int | None]:
    """Capture actual cache-inclusive tokens independently of message validity."""
    usage = upstream.get("usage") if isinstance(upstream, dict) else None
    if not isinstance(usage, dict):
        return None, None
    values = [
        usage.get("input_tokens"),
        usage.get("output_tokens"),
        usage.get("cache_creation_input_tokens", 0),
        usage.get("cache_read_input_tokens", 0),
    ]
    if any(type(value) is not int or not 0 <= value <= _MAX_TOKENS for value in values):
        return None, None
    return values[0] + values[2] + values[3], values[1]


class OpenCodeAnthropicAdapter(CompatibleTextAdapter):
    """Text-only Messages; streaming requires a separate implementation gate."""

    provider = "opencode_anthropic"
    provider_label = "OpenCode Anthropic"

    def supports_operation(self, operation: str) -> bool:
        return operation == "responses"

    def check_request(
        self,
        operation: str,
        body: dict[str, Any],
        *,
        deadline_monotonic: float | None = None,
        prepared_media: PreparedGoogleMedia | None = None,
    ) -> AdapterRejection | None:
        if operation != "responses" or body.get("stream") is True:
            return AdapterRejection(
                422,
                "unsupported_parameter",
                "OpenCode Anthropic supports non-streaming Responses only",
            )
        if body.get("temperature") is not None and body.get("top_p") is not None:
            return AdapterRejection(
                422, "unsupported_parameter", "Specify at most one sampling parameter"
            )
        temperature = body.get("temperature")
        if isinstance(temperature, (int, float)) and temperature > 1:
            return AdapterRejection(
                422, "unsupported_parameter", "Anthropic temperature must not exceed 1"
            )
        rejection = super().check_request(
            operation, body, deadline_monotonic=deadline_monotonic, prepared_media=prepared_media
        )
        if rejection:
            return rejection
        messages = self.build_messages(
            body, self.request_context(body), deadline=deadline_monotonic
        )
        if not any(message["role"] in {"user", "assistant"} for message in messages):
            return AdapterRejection(422, "unsupported_input", "Generation history is required")
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
        if self.check_request(operation, body, prepared_media=prepared_media):
            raise ValueError("Unsupported Anthropic request")
        messages = self.build_messages(body, self.request_context(body))
        system = [
            {"type": "text", "text": message["content"]}
            for message in messages
            if message["role"] in {"system", "developer"}
        ]
        out: dict[str, Any] = {
            "model": deployment,
            "messages": [
                {"role": message["role"], "content": [{"type": "text", "text": message["content"]}]}
                for message in messages
                if message["role"] in {"user", "assistant"}
            ],
            "max_tokens": body["max_output_tokens"]
            if type(body.get("max_output_tokens")) is int
            else default_output_tokens,
        }
        if system:
            out["system"] = system
        for key in ("temperature", "top_p"):
            if body.get(key) is not None:
                out[key] = body[key]
        return out

    def extract_usage(self, operation: str, upstream: Any) -> tuple[int | None, int | None]:
        _ = operation
        return anthropic_usage(upstream)

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
        _ = expected_input_count, expected_dimensions
        if (
            operation != "responses"
            or not isinstance(upstream, dict)
            or set(upstream) - _FIELDS
            or upstream.get("type") != "message"
            or upstream.get("role") != "assistant"
            or any(upstream.get(field) is not None for field in _NULL_FIELDS)
        ):
            raise ValueError("Invalid Anthropic message")
        input_tokens, output_tokens = anthropic_usage(upstream)
        if input_tokens is None:
            raise ValueError("Anthropic message lacks valid usage")
        blocks = upstream.get("content")
        if not isinstance(blocks, list) or len(blocks) > _MAX_BLOCKS:
            raise ValueError("Invalid Anthropic content")
        texts = []
        used = 0
        for block in blocks:
            if (
                not isinstance(block, dict)
                or set(block) - {"type", "text", "citations"}
                or block.get("type") != "text"
                or not isinstance(block.get("text"), str)
                or (
                    block.get("citations") is not None
                    and (not isinstance(block["citations"], list) or bool(block["citations"]))
                )
            ):
                raise ValueError("Unsupported Anthropic block")
            used += len(block["text"].encode())
            if used > _MAX_TEXT_BYTES:
                raise ValueError("Anthropic text exceeds bound")
            texts.append(block["text"])
        reason = upstream.get("stop_reason")
        reasons = {
            "end_turn": "stop",
            "stop_sequence": "stop",
            "max_tokens": "length",
            "refusal": "content_filter",
        }
        if not isinstance(reason, str) or reason not in reasons:
            raise ValueError("Unsupported Anthropic stop reason")
        message: dict[str, Any] = {"role": "assistant", "content": "".join(texts)}
        if reason == "refusal":
            message = {
                "role": "assistant",
                "content": None,
                "refusal": "The provider declined this request.",
            }
        translated = self._translate_responses_success(
            {
                "choices": [{"message": message, "finish_reason": reasons[reason]}],
                "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens},
            },
            logical_model=logical_model,
            context=self.request_context(request_body or {}),
        )
        translated.body["metadata"] = dict(metadata or {})
        return translated

    def create_stream_decoder(self, **kwargs: Any) -> Any:
        _ = kwargs
        raise ValueError("OpenCode Anthropic streaming is disabled")
