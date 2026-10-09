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

from typing import Any

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
        return request_context(body, self.profile)

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
