"""Foundry specialization of the bounded Anthropic Messages text adapter."""

from dataclasses import dataclass

from foundry_router.api.adapters.compatible_text import MAX_TEXT_BYTES
from foundry_router.api.adapters.opencode_anthropic import OpenCodeAnthropicAdapter


@dataclass(frozen=True)
class AzureAnthropicAdapter(OpenCodeAnthropicAdapter):
    """Foundry transport is owned by backends; translation stays provider-neutral."""

    provider = "azure_anthropic"
    provider_label = "Foundry Anthropic"

    request_text_budget: int = MAX_TEXT_BYTES

    def __post_init__(self) -> None:
        if (
            type(self.request_text_budget) is not int
            or not 1 <= self.request_text_budget <= 1024**3
        ):
            raise ValueError("Invalid Azure request text budget")
