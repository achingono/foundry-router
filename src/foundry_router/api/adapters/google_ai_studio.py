"""Google AI Studio compatibility adapter (Responses <-> Chat Completions).

Baseline: text Responses/embeddings. Default-off profiles extend this with unsigned
functions, bounded schemas and small PNG input. Unsupported fields fail
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

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from foundry_router.api.adapters.google_tools import (
    GoogleRequestContext,
    build_messages,
    request_context,
    requested_features,
    translate_calls,
)
from foundry_router.api.adapters.openai_compatible import (
    MAX_OPENAI_ASSEMBLED_TEXT_BYTES as MAX_GOOGLE_ASSEMBLED_TEXT_BYTES,
)
from foundry_router.api.adapters.openai_compatible import (
    MAX_OPENAI_EVENT_BYTES as MAX_GOOGLE_EVENT_BYTES,
)
from foundry_router.api.adapters.openai_compatible import (
    MAX_OPENAI_SSE_BUFFER_BYTES as MAX_GOOGLE_SSE_BUFFER_BYTES,
)
from foundry_router.api.adapters.openai_compatible import (
    OpenAICompatibleAdapter,
    OpenAICompatibleStreamDecoder,
)
from foundry_router.config.google_features import GoogleFeatureProfile

if TYPE_CHECKING:
    from foundry_router.api.adapters import TranslatedSuccess

MAX_STATELESS_SIGNATURE_BYTES = 65536
CONTROL_LIMIT = 32
DELETE_CODEPOINT = 127


def _stateless_signature_message(message: dict[str, Any], enabled: bool) -> dict[str, Any]:
    """Drop one bounded opaque signature only for the explicit stateless text policy."""
    if "extra_content" not in message or not enabled:
        return message
    extra = message["extra_content"]
    if extra is not None and extra != {}:
        if not isinstance(extra, dict) or set(extra) != {"google"}:
            raise ValueError("Unsupported Google signature wrapper")
        google = extra["google"]
        if not isinstance(google, dict) or set(google) != {"thought_signature"}:
            raise ValueError("Unsupported Google signature wrapper")
        signature = google["thought_signature"]
        if not isinstance(signature, str) or not signature:
            raise ValueError("Invalid Google signature")
        try:
            size = len(signature.encode())
        except UnicodeError as exc:
            raise ValueError("Invalid Google signature encoding") from exc
        if size > MAX_STATELESS_SIGNATURE_BYTES or any(
            ord(char) < CONTROL_LIMIT or ord(char) == DELETE_CODEPOINT for char in signature
        ):
            raise ValueError("Invalid bounded Google signature")
    return {key: value for key, value in message.items() if key != "extra_content"}


def normalize_google_usage(usage: dict[str, Any]) -> dict[str, Any]:
    """Account aggregate excess conservatively without asserting reasoning semantics."""
    prompt, completion, total = (
        usage.get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    )
    for value in (prompt, completion, total):
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("Google usage must contain non-negative integers")
    if prompt is not None and total is not None and total < prompt:
        raise ValueError("Google aggregate usage is below its prompt count")
    result = dict(usage)
    if prompt is not None and completion is not None and total is not None:
        if total < prompt + completion:
            raise ValueError("Google aggregate usage is below its explicit split")
        result["completion_tokens"] = total - prompt
    return result


class GoogleStreamDecoder(OpenAICompatibleStreamDecoder[GoogleRequestContext]):
    """Google call validation with the historical optional empty-profile context."""

    provider_label = "Google"

    def __init__(
        self,
        *,
        logical_model: str,
        metadata: dict[str, Any] | None = None,
        context: GoogleRequestContext | None = None,
    ) -> None:
        super().__init__(
            logical_model=logical_model,
            metadata=metadata,
            context=context or request_context({}, GoogleFeatureProfile()),
        )

    def normalize_delta(self, delta: dict[str, Any]) -> dict[str, Any]:
        return _stateless_signature_message(delta, self._context.stateless_signature_text)

    def _absorb_usage(self, usage: dict[str, Any]) -> None:
        normalized = normalize_google_usage(usage)
        prompt = normalized.get("prompt_tokens")
        completion = normalized.get("completion_tokens")
        previous = getattr(self, "_complete_usage_snapshot", None)
        if prompt is not None and completion is not None:
            if previous is not None and (prompt < previous[0] or completion < previous[1]):
                self._input_tokens = self._output_tokens = None
                raise ValueError("Google complete usage decreased")
            self._complete_usage_snapshot = (prompt, completion)
        self._input_tokens = prompt
        self._output_tokens = completion if prompt is not None else None

    def _translate_calls(self, raw: Any, *, completed: bool, refusal: bool) -> list[dict[str, Any]]:
        return translate_calls(raw, self._context, completed=completed, refusal=refusal)


class GoogleAiStudioAdapter(OpenAICompatibleAdapter[GoogleRequestContext]):
    """Google profile and validation hooks for the shared compatibility translator."""

    provider = "google_ai_studio"
    provider_label = "Google"
    stream_decoder_class = GoogleStreamDecoder

    def __init__(self, *, profile: object = None) -> None:
        self.profile = (
            profile if isinstance(profile, GoogleFeatureProfile) else GoogleFeatureProfile()
        )

    def request_context(self, body: dict[str, Any]) -> GoogleRequestContext:
        context = request_context(body, self.profile)
        eligible = (
            self.profile.continuation_policy == "disabled"
            and not requested_features(body, context)
            and not any(key in body for key in ("previous_response_id", "google_state", "text"))
            and body.get("store") is not True
        )
        return replace(context, stateless_signature_text=eligible)

    def normalize_message(
        self, message: dict[str, Any], context: GoogleRequestContext
    ) -> dict[str, Any]:
        return _stateless_signature_message(message, context.stateless_signature_text)

    def _translate_responses_success(
        self, upstream: Any, *, logical_model: str, context: GoogleRequestContext
    ) -> TranslatedSuccess:
        if isinstance(upstream, dict) and isinstance(upstream.get("usage"), dict):
            upstream = {**upstream, "usage": normalize_google_usage(upstream["usage"])}
        return super()._translate_responses_success(
            upstream, logical_model=logical_model, context=context
        )

    def extract_usage(self, operation: str, upstream: Any) -> tuple[int | None, int | None]:
        if (
            operation != "embeddings"
            and isinstance(upstream, dict)
            and isinstance(upstream.get("usage"), dict)
        ):
            try:
                upstream = {**upstream, "usage": normalize_google_usage(upstream["usage"])}
            except ValueError:
                return None, None
        return super().extract_usage(operation, upstream)

    def permits(self, body: dict[str, Any], context: GoogleRequestContext) -> bool:
        return self.profile.permits(requested_features(body, context))

    def build_messages(
        self,
        body: dict[str, Any],
        context: GoogleRequestContext,
        *,
        deadline: float | None = None,
    ) -> list[dict[str, Any]]:
        return build_messages(body, self.profile, context, deadline=deadline)

    def translate_calls(
        self, raw: Any, context: GoogleRequestContext, *, completed: bool, refusal: bool
    ) -> list[dict[str, Any]]:
        return translate_calls(raw, context, completed=completed, refusal=refusal)

    def create_stream_decoder(
        self,
        *,
        logical_model: str,
        request_input: Any = None,
        metadata: dict[str, Any] | None = None,
        request_body: dict[str, Any] | None = None,
    ) -> GoogleStreamDecoder:
        _ = request_input
        return GoogleStreamDecoder(
            logical_model=logical_model,
            metadata=metadata,
            context=self.request_context(request_body or {}),
        )


__all__ = [
    "MAX_GOOGLE_ASSEMBLED_TEXT_BYTES",
    "MAX_GOOGLE_EVENT_BYTES",
    "MAX_GOOGLE_SSE_BUFFER_BYTES",
    "GoogleAiStudioAdapter",
    "GoogleStreamDecoder",
]
