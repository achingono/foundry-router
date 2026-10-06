"""Azure pass-through adapter preserving existing wire contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from foundry_router.api.google_pdf import PreparedGoogleMedia

from foundry_router.api.adapters.base import (
    AdapterRejection,
    TranslatedError,
    TranslatedSuccess,
)


class AzureAdapter:
    """Identity conversion for Azure Foundry backends."""

    provider = "azure_foundry"

    def supports_operation(self, operation: str) -> bool:
        return operation in {"responses", "embeddings"}

    def check_request(
        self,
        operation: str,
        body: dict[str, Any],
        *,
        deadline_monotonic: float | None = None,
        prepared_media: PreparedGoogleMedia | None = None,
    ) -> AdapterRejection | None:
        # Azure is the native Responses surface; no first-release feature gate.
        _ = (operation, body, deadline_monotonic, prepared_media)
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
        _ = (default_output_tokens, prepared_media)
        out = dict(body)
        if operation == "responses":
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
            raise ValueError("Azure upstream payload must be a JSON object")
        return TranslatedSuccess(body=dict(upstream), input_tokens=None, output_tokens=None)

    def translate_error(self, status_code: int, upstream_body: bytes | None) -> TranslatedError:
        _ = upstream_body
        if status_code == 429:
            return TranslatedError(429, "rate_limit_exceeded", "Backend rate limit exceeded")
        if status_code >= 500:
            return TranslatedError(status_code, "upstream_error", "Backend request failed")
        return TranslatedError(status_code, "upstream_error", "Backend request failed")

    def extract_usage(self, operation: str, upstream: Any) -> tuple[int | None, int | None]:
        _ = (operation, upstream)
        return None, None

    def create_stream_decoder(
        self,
        *,
        logical_model: str,
        request_input: Any = None,
        metadata: dict[str, Any] | None = None,
        request_body: dict[str, Any] | None = None,
    ) -> Any:
        _ = (logical_model, request_input, metadata, request_body)
        raise NotImplementedError("Azure uses raw byte pass-through")


__all__ = ["AzureAdapter"]
