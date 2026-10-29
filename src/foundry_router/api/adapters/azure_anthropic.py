"""Foundry specialization of the bounded Anthropic Messages text adapter."""

from foundry_router.api.adapters.opencode_anthropic import OpenCodeAnthropicAdapter


class AzureAnthropicAdapter(OpenCodeAnthropicAdapter):
    """Foundry transport is owned by backends; translation stays provider-neutral."""

    provider = "azure_anthropic"
    provider_label = "Foundry Anthropic"
