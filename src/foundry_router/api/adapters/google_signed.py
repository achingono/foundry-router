"""Native signed mapping with complete-response Part association and owned state."""

from __future__ import annotations

import copy
import time
import uuid
from typing import TYPE_CHECKING, Any

from foundry_router.api.adapters.base import AdapterRejection, TranslatedSuccess
from foundry_router.api.adapters.google_native import GoogleNativeAdapter, native_usage
from foundry_router.api.adapters.google_signed_stream import GoogleSignedStreamDecoder
from foundry_router.api.google_continuation import (
    PreparedContinuation,
    seal_output_turn,
    unsigned_native_part,
)
from foundry_router.api.google_history import (
    STATE_FIELD,
    carrier_tokens,
    project_context,
    project_history,
)
from foundry_router.api.google_state import ProviderStateError

if TYPE_CHECKING:
    from foundry_router.api.google_pdf import PreparedGoogleMedia
    from foundry_router.api.google_sealing import SealContext
    from foundry_router.config.google_features import GoogleFeatureProfile


def _ordinary_body(body: dict[str, Any]) -> dict[str, Any]:
    projected, _ = project_history(body)
    return {
        **{key: value for key, value in body.items() if key != STATE_FIELD},
        "input": list(projected),
    }


class GoogleSignedAdapter(GoogleNativeAdapter):
    """Per-request adapter; construction requires API-owned sealing identity."""

    def __init__(
        self,
        *,
        profile: GoogleFeatureProfile,
        seal_context: SealContext,
        backend_id: str,
        prepared: PreparedContinuation | None,
    ) -> None:
        super().__init__(profile=profile)
        self.seal_context = seal_context
        self.backend_id = backend_id
        self.prepared = prepared
        self.ordinary = GoogleNativeAdapter(
            profile=profile.model_copy(
                update={
                    "continuation_policy": "unsigned",
                    "native_thinking_disabled": True,
                }
            )
        )

    def check_request(
        self,
        operation: str,
        body: dict[str, Any],
        *,
        deadline_monotonic: float | None = None,
        prepared_media: PreparedGoogleMedia | None = None,
    ) -> AdapterRejection | None:
        try:
            self.seal_context.validate(body)
            project_context(body, self.profile)
            tokens = carrier_tokens(body)
            if tokens and self.prepared is None:
                raise ProviderStateError("Invalid provider state")
            if self.prepared is not None:
                self.prepared.validate(body)
                if (
                    self.prepared.backend != self.backend_id
                    or self.prepared.signature_input_tokens
                    > (self.profile.signature_input_token_bound or 0)
                ):
                    raise ProviderStateError("Invalid provider state")
            return self.ordinary.check_request(
                operation,
                _ordinary_body(body),
                deadline_monotonic=deadline_monotonic,
                prepared_media=prepared_media,
            )
        except (ValueError, TypeError, KeyError):
            return AdapterRejection(422, "invalid_provider_state", "Invalid provider state")

    def build_upstream_body(
        self,
        operation: str,
        body: dict[str, Any],
        *,
        deployment: str,
        default_output_tokens: int,
        prepared_media: PreparedGoogleMedia | None = None,
    ) -> dict[str, Any]:
        if self.check_request(operation, body, prepared_media=prepared_media) is not None:
            raise ProviderStateError("Invalid provider state")
        upstream = self.ordinary.build_upstream_body(
            operation,
            _ordinary_body(body),
            deployment=deployment,
            default_output_tokens=default_output_tokens,
            prepared_media=prepared_media,
        )
        upstream["generationConfig"]["thinkingConfig"] = {
            "thinkingBudget": self.profile.native_thinking_budget,
        }
        # Replace merged model groups with the exact authenticated turn boundaries.
        if self.prepared is not None:
            projected, _ = project_history(body)
            turns = iter(self.prepared.turns)
            pending = next(turns, None)
            rebuilt = []
            for content in upstream["contents"]:
                if content["role"] != "model":
                    rebuilt.append(content)
                    continue
                remaining = len(content["parts"])
                while remaining:
                    if pending is None or len(pending.item_ids) > remaining:
                        raise ProviderStateError("Invalid provider state")
                    native_parts = []
                    for offset, signature in enumerate(pending.signatures):
                        part = unsigned_native_part(projected[pending.start + offset])
                        if signature is not None:
                            part["thoughtSignature"] = signature
                        native_parts.append(part)
                    rebuilt.append({"role": "model", "parts": native_parts})
                    remaining -= len(native_parts)
                    pending = next(turns, None)
            if pending is not None:
                raise ProviderStateError("Invalid provider state")
            upstream["contents"] = rebuilt
        return upstream

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
        if request_body is None or not isinstance(upstream, dict):
            raise ProviderStateError("Invalid provider state")
        self.seal_context.validate(request_body)
        input_tokens, output_tokens = native_usage(upstream)
        if "usageMetadata" in upstream and input_tokens is None:
            raise ProviderStateError("Invalid provider state")
        original_usage = upstream.get("usageMetadata", {})
        if isinstance(original_usage, dict) and original_usage.get("toolUsePromptTokenCount", 0):
            raise ProviderStateError("Invalid provider state")
        copied = copy.deepcopy(upstream)
        candidates = copied.get("candidates", [])
        if not isinstance(candidates, list) or len(candidates) > 1:
            raise ProviderStateError("Invalid provider state")
        candidate = candidates[0] if candidates else {}
        if not isinstance(candidate, dict):
            raise ProviderStateError("Invalid provider state")
        content = candidate.get("content", {})
        if not isinstance(content, dict):
            raise ProviderStateError("Invalid provider state")
        parts = content.get("parts", [])
        if not isinstance(parts, list) or len(parts) > 64:
            raise ProviderStateError("Invalid provider state")
        signatures = []
        for part in parts:
            if not isinstance(part, dict):
                raise ProviderStateError("Invalid provider state")
            if "thoughtSignature" in part and (
                not isinstance(part["thoughtSignature"], str) or not part["thoughtSignature"]
            ):
                raise ProviderStateError("Invalid provider state")
            signatures.append(part.pop("thoughtSignature", None))
        usage = copied.get("usageMetadata")
        if isinstance(usage, dict):
            usage["thoughtsTokenCount"] = 0
            usage["toolUsePromptTokenCount"] = 0
            if input_tokens is not None and output_tokens is not None:
                usage.update(
                    promptTokenCount=input_tokens,
                    candidatesTokenCount=output_tokens,
                    totalTokenCount=input_tokens + output_tokens,
                )
        translated = self.ordinary.translate_success(
            operation,
            copied,
            logical_model=logical_model,
            expected_input_count=expected_input_count,
            expected_dimensions=expected_dimensions,
            metadata=metadata,
            request_body=_ordinary_body(request_body),
        )
        if candidate.get("finishReason") != "STOP" or translated.body["status"] != "completed":
            # Truncated/refused turns never become replayable signed histories.
            return translated
        calls = {
            item["call_id"]: item
            for item in translated.body["output"]
            if item["type"] == "function_call"
        }
        output = []
        for part in parts:
            if set(part) == {"text"} and isinstance(part["text"], str) and part["text"].strip():
                output.append(
                    {
                        "type": "message",
                        "id": "msg_" + uuid.uuid4().hex[:24],
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {"type": "output_text", "text": part["text"], "annotations": []}
                        ],
                    }
                )
            elif set(part) == {"functionCall"}:
                output.append(calls[part["functionCall"]["id"]])
            else:
                raise ProviderStateError("Invalid provider state")
        if len(output) != len(parts):
            raise ProviderStateError("Invalid provider state")
        signature_tokens = sum(len(value) + 64 for value in signatures if isinstance(value, str))
        if signature_tokens + (self.prepared.signature_input_tokens if self.prepared else 0) > (
            self.profile.signature_input_token_bound or 0
        ):
            raise ProviderStateError("Invalid provider state")
        translated.body["output"] = seal_output_turn(
            request_body,
            output,
            tuple(signatures),
            self.seal_context.codec,
            self.seal_context.binding(self.backend_id),
            response_id=translated.body["id"],
            now=int(time.time()),
            max_history_items=self.profile.max_history_items,
            max_result_bytes=self.profile.max_result_bytes,
        )
        return TranslatedSuccess(translated.body, input_tokens, output_tokens)

    def create_stream_decoder(
        self,
        *,
        logical_model: str,
        request_input: Any = None,
        metadata: dict[str, Any] | None = None,
        request_body: dict[str, Any] | None = None,
    ) -> Any:
        _ = request_input, metadata
        if request_body is None:
            raise ProviderStateError("Invalid provider state")
        return GoogleSignedStreamDecoder(self, request_body, logical_model)
