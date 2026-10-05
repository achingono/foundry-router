"""Provider adapters owned by the API boundary."""

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

_ADAPTERS: dict[str, ProviderAdapter] = {
    "azure_foundry": AzureAdapter(),
    "google_ai_studio": GoogleAiStudioAdapter(),
}


def get_adapter(provider: str) -> ProviderAdapter:
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
