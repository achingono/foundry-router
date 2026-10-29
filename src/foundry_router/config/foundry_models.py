"""Pool prerequisites for explicit Foundry text and generated-image providers."""

from __future__ import annotations

from typing import Any


def validate_foundry_model_pools(settings: Any) -> None:
    for model, pool in settings.models.items():
        providers = {settings.backends[name].provider for name in pool.backends}
        if "azure_anthropic" in providers and pool.streaming_enabled:
            raise ValueError("Foundry Anthropic pools require streaming_enabled=false")
        if "azure_mai" not in providers:
            continue
        price = settings.pricing.get(model)
        if (
            providers != {"azure_mai"}
            or pool.streaming_enabled
            or pool.continuation_policy != "unsigned"
            or price is None
            or price.image_output_per_image is None
            or price.image_output_per_image <= 0
            or price.input_per_million != 0
            or price.output_per_million != 0
            or price.cached_input_per_million is not None
        ):
            raise ValueError(
                "MAI requires an image-only nonstream pool and a positive per-image ceiling"
            )
