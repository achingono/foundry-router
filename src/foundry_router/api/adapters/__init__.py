"""Provider adapters owned by the API boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from foundry_router.api.google_continuation import PreparedContinuation
    from foundry_router.api.google_sealing import SealContext

from foundry_router.api.adapters.azure import AzureAdapter
from foundry_router.api.adapters.base import (
    AdapterRejection,
    ProviderAdapter,
    TranslatedError,
    TranslatedSuccess,
)
from foundry_router.api.adapters.google_ai_studio import (
    GoogleAiStudioAdapter,
    GoogleStreamDecoder,
)
from foundry_router.api.adapters.google_audio_output import GoogleAudioOutputAdapter
from foundry_router.api.adapters.google_native import GoogleNativeAdapter
from foundry_router.config.google_features import GoogleFeatureProfile

_ADAPTERS: dict[str, ProviderAdapter] = {
    "azure_foundry": AzureAdapter(),
    "google_ai_studio": GoogleAiStudioAdapter(),
}


def get_adapter(
    provider: str,
    *,
    google_features: object = None,
    api_surface: str = "openai_compat",
    seal_context: SealContext | None = None,
    backend_id: str | None = None,
    prepared_continuation: PreparedContinuation | None = None,
) -> ProviderAdapter:
    if (
        isinstance(google_features, GoogleFeatureProfile)
        and "audio_output" in google_features.features
    ):
        if provider != "google_ai_studio" or api_surface != "native":
            raise ValueError("Generated audio requires Google native surface")
        return GoogleAudioOutputAdapter(profile=google_features)
    if (
        isinstance(google_features, GoogleFeatureProfile)
        and google_features.continuation_policy == "sealed_native"
    ):
        if (
            provider != "google_ai_studio"
            or api_surface != "native"
            or seal_context is None
            or backend_id is None
        ):
            raise ValueError("Signed native requests require owned sealing context")
        from foundry_router.api.adapters.google_signed import (  # noqa: PLC0415 -- avoid state/schema import cycle
            GoogleSignedAdapter,
        )

        return GoogleSignedAdapter(
            profile=google_features,
            seal_context=seal_context,
            backend_id=backend_id,
            prepared=prepared_continuation,
        )
    if api_surface == "native":
        if provider != "google_ai_studio":
            raise ValueError("Native surface requires Google")
        return GoogleNativeAdapter(profile=google_features)
    if provider == "google_ai_studio" and google_features is not None:
        return GoogleAiStudioAdapter(profile=google_features)
    try:
        return _ADAPTERS[provider]
    except KeyError as exc:
        raise ValueError(f"Unknown provider '{provider}'") from exc


__all__ = [
    "AdapterRejection",
    "AzureAdapter",
    "GoogleAiStudioAdapter",
    "GoogleStreamDecoder",
    "ProviderAdapter",
    "TranslatedError",
    "TranslatedSuccess",
    "get_adapter",
]
