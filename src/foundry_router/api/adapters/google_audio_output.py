"""Gated native audio request and versioned WAV result projection."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from foundry_router.api.adapters.base import AdapterRejection, TranslatedSuccess
from foundry_router.api.adapters.google_ai_studio import GoogleAiStudioAdapter
from foundry_router.api.adapters.google_audio_request import (
    AUDIO_OUTPUT_FIELD,
    AUDIO_REQUEST_FIELD,
    validate_audio_output_request,
)
from foundry_router.api.adapters.google_native import _native_output, native_usage
from foundry_router.api.adapters.google_tools import request_context
from foundry_router.api.google_output_wav import MAX_OUTPUT_WAV_BYTES, decode_output_wav

if TYPE_CHECKING:
    from foundry_router.api.google_pdf import PreparedGoogleMedia


class GoogleAudioOutputAdapter(GoogleAiStudioAdapter):
    """Explicit audio-only adapter; ordinary native thinking policy stays unchanged."""

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
        _ = deadline_monotonic
        if not self.supports_operation(operation) or prepared_media is not None:
            return AdapterRejection(
                422, "unsupported_input", "Unsupported generated audio operation"
            )
        try:
            validate_audio_output_request(body, self.profile)
        except ValueError:
            return AdapterRejection(422, "unsupported_input", "Invalid generated audio request")
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
        _ = deployment, default_output_tokens
        if self.check_request(operation, body, prepared_media=prepared_media):
            raise ValueError("Invalid generated audio request")
        voice = validate_audio_output_request(body, self.profile)
        generation: dict[str, Any] = {
            "candidateCount": 1,
            "maxOutputTokens": self.profile.generated_output_tokens_bound,
            "responseModalities": ["AUDIO"],
            "responseFormat": {
                "audio": {"mimeType": "AUDIO_WAV", "delivery": "INLINE", "sampleRate": 24000}
            },
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        }
        if self.profile.audio_output_thinking_policy == "disable_zero":
            generation["thinkingConfig"] = {"thinkingBudget": 0}
        elif self.profile.audio_output_thinking_policy != "omit":
            raise ValueError("Generated audio thinking policy unavailable")
        result: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": body["input"]}]}],
            "generationConfig": generation,
        }
        if "instructions" in body:
            result["systemInstruction"] = {"parts": [{"text": body["instructions"]}]}
        return result

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
        _ = expected_input_count, expected_dimensions
        if operation != "responses" or not isinstance(upstream, dict):
            raise ValueError("Invalid generated audio envelope")
        body = request_body or {}
        validate_audio_output_request(body, self.profile)
        inputs, outputs = native_usage(upstream, strict=True)
        usage = upstream.get("usageMetadata", {})
        sanitized = dict(upstream)
        candidates = upstream.get("candidates", [])
        encoded = None
        if (
            isinstance(candidates, list)
            and len(candidates) == 1
            and isinstance(candidates[0], dict)
        ):
            candidate = candidates[0]
            content = candidate.get("content", {"role": "model", "parts": []})
            if not isinstance(content, dict):
                raise ValueError("Invalid generated audio content")
            parts = content.get("parts", [])
            if not isinstance(parts, list) or len(parts) > 1:
                raise ValueError("Generated audio requires one artifact")
            if parts:
                part = parts[0]
                if not isinstance(part, dict) or set(part) != {"inlineData"}:
                    raise ValueError("Unsupported generated audio output or state")
                media = part["inlineData"]
                if (
                    not isinstance(media, dict)
                    or set(media) != {"mimeType", "data"}
                    or media["mimeType"] != "audio/wav"
                    or not isinstance(media["data"], str)
                    or not media["data"]
                    or len(media["data"]) > 4 * ((MAX_OUTPUT_WAV_BYTES + 2) // 3)
                ):
                    raise ValueError("Unsupported generated audio media")
                encoded = media["data"]
            sanitized["candidates"] = [{**candidate, "content": {**content, "parts": []}}]
        result = _native_output(sanitized)
        if result["finish_reason"] is None:
            raise ValueError("Generated audio requires finish evidence")
        finish = (
            candidates[0].get("finishReason")
            if isinstance(candidates, list) and len(candidates) == 1
            else None
        )
        if encoded is not None and finish not in {"STOP", "MAX_TOKENS"}:
            raise ValueError("Blocked generated audio cannot carry an artifact")
        # Entire envelope/state preflight precedes canonical decode/container inspection.
        if encoded is not None:
            decode_output_wav(encoded)
        if finish == "STOP" and encoded is None:
            raise ValueError("Generated audio STOP requires an artifact")
        translated = self._translate_responses_success(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [],
                            "refusal": result["refusal"],
                        },
                        "finish_reason": result["finish_reason"],
                    }
                ],
                **(
                    {"usage": {"prompt_tokens": inputs, "completion_tokens": outputs}}
                    if inputs is not None
                    else {}
                ),
            },
            logical_model=logical_model,
            context=request_context({}, self.profile),
        )
        translated.body["metadata"] = dict(metadata or {})
        translated.body.update({"parallel_tool_calls": False, "tool_choice": "auto", "tools": []})
        if inputs is not None:
            translated.body["usage"].update(
                {
                    "input_tokens_details": {
                        "cached_tokens": usage.get("cachedContentTokenCount", 0)
                    },
                    "output_tokens_details": {"reasoning_tokens": 0},
                }
            )
        if finish in {"STOP", "MAX_TOKENS"}:
            translated.body["output"] = []
        if finish == "STOP":
            translated.body[AUDIO_OUTPUT_FIELD] = {
                "version": 1,
                "id": f"aud_{uuid.uuid4().hex}",
                "format": "wav",
                "media_type": "audio/wav",
                "sample_rate_hz": 24000,
                "channels": 1,
                "sample_width_bits": 16,
                "data": encoded,
            }
        translated.body[AUDIO_REQUEST_FIELD] = dict(body[AUDIO_REQUEST_FIELD])
        return translated

    def create_stream_decoder(self, **_kwargs: Any) -> Any:
        raise ValueError("Generated audio streaming is unsupported")
