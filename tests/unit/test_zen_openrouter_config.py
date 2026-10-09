"""Unit tests for OpenCode Zen and OpenRouter backend configuration."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from foundry_router.config import BackendConfig


class TestZenBackendConfig:
    def test_valid_zen_backend_defaults_to_responses(self) -> None:
        config = BackendConfig(
            provider="opencode_zen",
            endpoint="https://opencode.ai/zen/v1",
            credential="synthetic-zen-key",
            deployment="gpt-5.4",
        )
        assert config.provider == "opencode_zen"
        assert config.supported_operations == ["responses"]

    @pytest.mark.parametrize(
        "endpoint",
        [
            "https://opencode.ai/zen/v1/responses",
            "https://opencode.ai/zen/v1/chat/completions",
            "https://opencode.ai/zen/v1/embeddings",
            "https://opencode.ai/zen/v1/messages",
            "https://opencode.ai/zen/v1/systemone",
        ],
    )
    def test_zen_operation_paths_rejected(self, endpoint: str) -> None:
        with pytest.raises(ValidationError, match="API root, not an operation path"):
            BackendConfig(
                provider="opencode_zen",
                endpoint=endpoint,
                credential="synthetic-zen-key",
                deployment="gpt-5.4",
            )

    @pytest.mark.parametrize(
        "endpoint",
        [
            "https://opencode.ai/zen/v1/../v1",
            "https://opencode.ai/zen/v1//responses-x",
            "https://opencode.ai/zen/%76%31",
        ],
    )
    def test_zen_unsafe_raw_paths_rejected(self, endpoint: str) -> None:
        with pytest.raises(ValidationError):
            BackendConfig(
                provider="opencode_zen",
                endpoint=endpoint,
                credential="synthetic-zen-key",
                deployment="gpt-5.4",
            )

    def test_zen_rejects_namespaced_deployment(self) -> None:
        with pytest.raises(ValidationError, match="single non-empty path segment"):
            BackendConfig(
                provider="opencode_zen",
                endpoint="https://opencode.ai/zen/v1",
                credential="synthetic-zen-key",
                deployment="org/model",
            )

    def test_zen_requires_deployment(self) -> None:
        with pytest.raises(ValidationError):
            BackendConfig(
                provider="opencode_zen",
                endpoint="https://opencode.ai/zen/v1",
                credential="synthetic-zen-key",
            )

    def test_zen_rejects_embeddings_operations(self) -> None:
        with pytest.raises(ValidationError, match="only the Responses operation"):
            BackendConfig(
                provider="opencode_zen",
                endpoint="https://opencode.ai/zen/v1",
                credential="synthetic-zen-key",
                deployment="gpt-5.4",
                supported_operations=["responses", "embeddings"],
            )

    def test_zen_rejects_native_surface(self) -> None:
        with pytest.raises(ValidationError, match="native or Google feature profiles"):
            BackendConfig(
                provider="opencode_zen",
                endpoint="https://opencode.ai/zen/v1",
                credential="synthetic-zen-key",
                deployment="gpt-5.4",
                api_surface="native",
            )

    def test_zen_rejects_oversized_deployment(self) -> None:
        with pytest.raises(ValidationError, match="bounded physical model identifier"):
            BackendConfig(
                provider="opencode_zen",
                endpoint="https://opencode.ai/zen/v1",
                credential="synthetic-zen-key",
                deployment="m" * 513,
            )


class TestOpenRouterBackendConfig:
    def test_valid_openrouter_backend_allows_namespaced_model(self) -> None:
        config = BackendConfig(
            provider="openrouter",
            endpoint="https://openrouter.ai/api/v1",
            credential="synthetic-openrouter-key",
            deployment="organization/model",
        )
        assert config.provider == "openrouter"
        assert config.supported_operations == ["responses"]

    def test_openrouter_explicit_embeddings_opt_in(self) -> None:
        config = BackendConfig(
            provider="openrouter",
            endpoint="https://openrouter.ai/api/v1",
            credential="synthetic-openrouter-key",
            deployment="organization/model",
            supported_operations=["responses", "embeddings"],
        )
        assert config.supported_operations == ["responses", "embeddings"]

    @pytest.mark.parametrize(
        "endpoint",
        [
            "https://openrouter.ai/api/v1/chat/completions",
            "https://openrouter.ai/api/v1/embeddings",
            "https://openrouter.ai/api/v1/responses",
        ],
    )
    def test_openrouter_operation_paths_rejected(self, endpoint: str) -> None:
        with pytest.raises(ValidationError, match="API root, not an operation path"):
            BackendConfig(
                provider="openrouter",
                endpoint=endpoint,
                credential="synthetic-openrouter-key",
                deployment="organization/model",
            )

    def test_openrouter_requires_deployment(self) -> None:
        with pytest.raises(ValidationError):
            BackendConfig(
                provider="openrouter",
                endpoint="https://openrouter.ai/api/v1",
                credential="synthetic-openrouter-key",
            )

    def test_openrouter_rejects_native_surface(self) -> None:
        with pytest.raises(ValidationError, match="native"):
            BackendConfig(
                provider="openrouter",
                endpoint="https://openrouter.ai/api/v1",
                credential="synthetic-openrouter-key",
                deployment="organization/model",
                api_surface="native",
            )

    def test_openrouter_rejects_non_https(self) -> None:
        with pytest.raises(ValidationError, match="HTTPS"):
            BackendConfig(
                provider="openrouter",
                endpoint="http://openrouter.ai/api/v1",
                credential="synthetic-openrouter-key",
                deployment="organization/model",
            )
