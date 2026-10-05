"""Provider adapter protocol for Responses/embeddings translation.

Adapters are pure transformations owned by ``api/``. They must not issue HTTP
requests, select backends, touch stores, handle retries, inject credentials, or
keep global conversation state. Per-request stream state lives in the decoder
object returned for a single upstream stream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class AdapterRejection:
    """Client-visible request rejection decided before any egress."""

    status_code: int
    code: str
    message: str


@dataclass(frozen=True)
class TranslatedSuccess:
    """Public body plus normalized usage extracted independently of output."""

    body: dict[str, Any]
    input_tokens: int | None
    output_tokens: int | None


@dataclass(frozen=True)
class TranslatedError:
    """Sanitized upstream failure mapped to a public error."""

    status_code: int
    code: str
    message: str


@runtime_checkable
class ProviderAdapter(Protocol):
    """Typed transport-neutral adapter boundary."""

    provider: str

    def supports_operation(self, operation: str) -> bool: ...

    def check_request(self, operation: str, body: dict[str, Any]) -> AdapterRejection | None: ...

    def build_upstream_body(
        self,
        operation: str,
        body: dict[str, Any],
        *,
        deployment: str,
        default_output_tokens: int,
    ) -> dict[str, Any]: ...

    def translate_success(
        self,
        operation: str,
        upstream: Any,
        *,
        logical_model: str,
        expected_input_count: int | None = None,
        expected_dimensions: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TranslatedSuccess: ...

    def translate_error(self, status_code: int, upstream_body: bytes | None) -> TranslatedError: ...

    def create_stream_decoder(
        self,
        *,
        logical_model: str,
        request_input: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any: ...


__all__ = [
    "AdapterRejection",
    "ProviderAdapter",
    "TranslatedError",
    "TranslatedSuccess",
]
