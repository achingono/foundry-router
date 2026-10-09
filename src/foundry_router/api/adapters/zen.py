"""OpenCode Zen Responses validation and wire pass-through.

Zen serves its Responses-model rows over the OpenAI Responses wire shape.
This adapter validates the bounded stateless-text request contract and passes
the accepted body through with only the provider deployment substituted; it
never translates into the Chat Completions dialect. Broader Responses support
(tools, structured output, media, stored continuation) requires a separately
reviewed extension.
"""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING, Any

from foundry_router.api.adapters.base import (
    AdapterRejection,
    TranslatedError,
    TranslatedSuccess,
)

if TYPE_CHECKING:
    from foundry_router.api.google_pdf import PreparedGoogleMedia


_ALLOWED_TOP_LEVEL = frozenset(
    {
        "model",
        "input",
        "instructions",
        "metadata",
        "max_output_tokens",
        "temperature",
        "top_p",
        "stream",
        "store",
        "background",
    }
)
_FALSE_ONLY = frozenset({"store", "background"})
_ALLOWED_ROLES = frozenset({"system", "developer", "user", "assistant"})
_ALLOWED_PART_TYPES = frozenset({"input_text", "output_text", "text"})
_MAX_OUTPUT_TOKENS_MIN = 1
_MAX_OUTPUT_TOKENS_MAX = 128000
MAX_ZEN_HISTORY_ITEMS = 128
MAX_ZEN_TEXT_PARTS = 128
MAX_ZEN_TEXT_BYTES = 256 * 1024


def _rejection(message: str, code: str = "unsupported_parameter") -> AdapterRejection:
    return AdapterRejection(status_code=422, code=code, message=message)


class ZenAdapter:
    """Bounded stateless-text validation with Responses wire pass-through."""

    provider = "opencode_zen"

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
        _ = prepared_media
        if operation != "responses":
            return AdapterRejection(
                status_code=422,
                code="unsupported_operation",
                message=f"Unsupported operation '{operation}' for Zen backends",
            )
        for key in body:
            if key not in _ALLOWED_TOP_LEVEL:
                return _rejection(f"Unsupported field '{key}' for Zen backends")
        for key in _FALSE_ONLY:
            if body.get(key) is True:
                return _rejection(f"Unsupported field '{key}' for Zen backends")
        instructions = body.get("instructions")
        if instructions is not None and not isinstance(instructions, str):
            return _rejection("instructions must be a string")
        max_tokens = body.get("max_output_tokens")
        if max_tokens is not None and (
            isinstance(max_tokens, bool)
            or not isinstance(max_tokens, int)
            or not (_MAX_OUTPUT_TOKENS_MIN <= max_tokens <= _MAX_OUTPUT_TOKENS_MAX)
        ):
            return _rejection(
                "max_output_tokens must be an integer "
                f"{_MAX_OUTPUT_TOKENS_MIN}-{_MAX_OUTPUT_TOKENS_MAX}"
            )
        for key, low, high in (("temperature", 0.0, 2.0), ("top_p", 0.0, 1.0)):
            value = body.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return _rejection(f"{key} must be a number")
            if not math.isfinite(float(value)) or not (low <= float(value) <= high):
                return _rejection(f"{key} must be in range {low}-{high}")
        if "stream" in body and not isinstance(body["stream"], bool):
            return _rejection("stream must be a boolean")
        metadata = body.get("metadata")
        if metadata is not None:
            if not isinstance(metadata, dict):
                return _rejection("metadata must be an object")
            if len(metadata) > 16:
                return _rejection("metadata must have at most 16 entries")
            if any(
                not isinstance(key, str)
                or len(key) > 64
                or not isinstance(value, str)
                or len(value) > 512
                for key, value in metadata.items()
            ):
                return _rejection(
                    "metadata requires string keys up to 64 and values up to 512 characters"
                )
        try:
            self._check_input(body.get("input"), deadline=deadline_monotonic)
        except ValueError as exc:
            return AdapterRejection(422, "invalid_request", str(exc))
        return None

    def _check_input(self, value: Any, *, deadline: float | None) -> None:
        used = 0

        def text(part: Any) -> str:
            nonlocal used
            if deadline is not None and time.monotonic() >= deadline:
                raise ValueError("Zen text intake deadline exceeded")
            if not isinstance(part, str) or not part.strip():
                raise ValueError("Zen histories require nonempty text")
            used += len(part.encode())
            if used > MAX_ZEN_TEXT_BYTES:
                raise ValueError("Zen text history exceeds its byte bound")
            return part

        if isinstance(value, str):
            if not value.strip():
                raise ValueError("The 'input' field must be non-empty")
            text(value)
            return
        if not isinstance(value, list) or not 1 <= len(value) <= MAX_ZEN_HISTORY_ITEMS:
            raise ValueError("The 'input' field must be text")
        for item in value:
            if (
                not isinstance(item, dict)
                or set(item) - {"type", "role", "content"}
                or item.get("type", "message") != "message"
                or item.get("role") not in _ALLOWED_ROLES
            ):
                raise ValueError("Zen histories require ordinary text messages")
            content = item.get("content")
            if isinstance(content, list):
                if not 1 <= len(content) <= MAX_ZEN_TEXT_PARTS:
                    raise ValueError("Zen text parts exceed their item bound")
                for part in content:
                    if (
                        not isinstance(part, dict)
                        or set(part) - {"type", "text"}
                        or part.get("type") not in _ALLOWED_PART_TYPES
                    ):
                        raise ValueError("Zen histories do not support media or state")
                    text(part.get("text"))
            else:
                text(content)

    def build_upstream_body(
        self,
        operation: str,
        body: dict[str, Any],
        *,
        deployment: str,
        default_output_tokens: int,
        prepared_media: PreparedGoogleMedia | None = None,
    ) -> dict[str, Any]:
        _ = (default_output_tokens, prepared_media)
        if operation != "responses":
            raise ValueError("Zen backends support only the Responses operation")
        out = dict(body)
        out["model"] = deployment
        return out

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
        _ = (
            operation,
            logical_model,
            expected_input_count,
            expected_dimensions,
            metadata,
            request_body,
        )
        if not isinstance(upstream, dict):
            raise ValueError("Zen upstream payload must be a JSON object")
        input_tokens, output_tokens = self.extract_usage(operation, upstream)
        return TranslatedSuccess(
            body=dict(upstream), input_tokens=input_tokens, output_tokens=output_tokens
        )

    def translate_error(
        self, status_code: int, upstream_body: bytes | None
    ) -> TranslatedError:
        _ = upstream_body  # Never relay provider bodies.
        if status_code in (401, 403):
            return TranslatedError(
                502, "upstream_error", "Backend authentication failed; check server configuration"
            )
        if status_code == 429:
            return TranslatedError(429, "rate_limit_exceeded", "Backend rate limit exceeded")
        if status_code == 400:
            return TranslatedError(502, "upstream_error", "Backend rejected the request")
        if 500 <= status_code < 600:
            return TranslatedError(status_code, "upstream_error", "Backend request failed")
        return TranslatedError(status_code, "upstream_error", "Backend request failed")

    def extract_usage(self, operation: str, upstream: Any) -> tuple[int | None, int | None]:
        _ = operation
        usage = upstream.get("usage") if isinstance(upstream, dict) else None
        if not isinstance(usage, dict):
            return None, None
        prompt = usage.get("input_tokens")
        completion = usage.get("output_tokens")
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
    ) -> Any:
        _ = (logical_model, request_input, metadata, request_body)
        raise NotImplementedError("Zen uses raw byte pass-through")


__all__ = [
    "MAX_ZEN_HISTORY_ITEMS",
    "MAX_ZEN_TEXT_BYTES",
    "MAX_ZEN_TEXT_PARTS",
    "ZenAdapter",
]
