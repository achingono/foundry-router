"""Unit tests for configuration module."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from foundry_router.config import (
    BackendConfig,
    ModelBackendPool,
    PricingConfig,
    load_settings,
)


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    load_settings.cache_clear()
    yield
    load_settings.cache_clear()


class TestBackendConfig:
    def test_valid_backend(self) -> None:
        config = BackendConfig(
            endpoint="https://example.openai.azure.com",
            credential="test-key",
            region="eastus",
            deployment="gpt-4",
        )
        assert str(config.endpoint) == "https://example.openai.azure.com/"
        assert config.credential == "test-key"

    def test_endpoint_requires_https(self) -> None:
        with pytest.raises(ValidationError):
            BackendConfig(endpoint="http://example.com", credential="key")

    def test_endpoint_validation(self) -> None:
        with pytest.raises(ValidationError):
            BackendConfig(endpoint="not-a-url", credential="key")

    def test_deployment_is_required(self) -> None:
        with pytest.raises(ValidationError):
            BackendConfig(endpoint="https://example.com", credential="key")

    def test_deployment_must_be_one_path_segment(self) -> None:
        with pytest.raises(ValidationError):
            BackendConfig(endpoint="https://example.com", credential="key", deployment="a/b")


class TestModelBackendPool:
    def test_valid_pool(self) -> None:
        pool = ModelBackendPool(backends={"backend_a": 1.0, "backend_b": 2.0})
        assert pool.backends == {"backend_a": 1.0, "backend_b": 2.0}

    def test_empty_pool_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelBackendPool(backends={})

    def test_negative_weight_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelBackendPool(backends={"backend_a": -1.0})

    def test_zero_weight_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelBackendPool(backends={"backend_a": 0.0})


class TestPricingConfig:
    def test_valid_pricing(self) -> None:
        pricing = PricingConfig(input_per_million=1.0, output_per_million=2.0)
        assert pricing.input_per_million == 1.0
        assert pricing.output_per_million == 2.0

    def test_zero_price_allowed(self) -> None:
        pricing = PricingConfig(input_per_million=0, output_per_million=0)
        assert pricing.input_per_million == 0
        assert pricing.output_per_million == 0


class TestSettings:
    def test_minimal_valid_config(self) -> None:
        backends = {
            "backend_a": {
                "endpoint": "https://backend-a.openai.azure.com",
                "credential": "key-a",
                "deployment": "gpt-4",
            }
        }
        models = {"gpt-4": {"backends": {"backend_a": 1.0}}}
        client_keys = ["client-key-1"]
        admin_keys = ["admin-key-1"]

        with patch.dict(
            os.environ,
            {
                "FOUNDRY_BACKENDS_JSON": json.dumps(backends),
                "FOUNDRY_MODELS_JSON": json.dumps(models),
                "FOUNDRY_CLIENT_API_KEYS_JSON": json.dumps(client_keys),
                "FOUNDRY_ADMIN_API_KEYS_JSON": json.dumps(admin_keys),
                "FOUNDRY_PRICING_JSON": "{}",
                "FOUNDRY_BACKEND_CYCLE_START_DAY_JSON": "{}",
            },
        ):
            settings = load_settings()

        assert "backend_a" in settings.backends
        assert "gpt-4" in settings.models
        assert settings.client_api_keys == ["client-key-1"]
        assert settings.admin_api_keys == ["admin-key-1"]

    def test_missing_backends_rejected(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "FOUNDRY_BACKENDS_JSON": "{}",
                    "FOUNDRY_MODELS_JSON": '{"gpt-4": {"backends": {"backend_a": 1.0}}}',
                    "FOUNDRY_CLIENT_API_KEYS_JSON": '["client-key"]',
                    "FOUNDRY_ADMIN_API_KEYS_JSON": '["admin-key"]',
                    "FOUNDRY_PRICING_JSON": "{}",
                    "FOUNDRY_BACKEND_CYCLE_START_DAY_JSON": "{}",
                },
            ),
            pytest.raises(ValueError, match="At least one backend must be configured"),
        ):
            load_settings()

    def test_missing_models_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FOUNDRY_BACKENDS_JSON": '{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key", "deployment": "gpt-4"}}',
                "FOUNDRY_MODELS_JSON": "{}",
                "FOUNDRY_CLIENT_API_KEYS_JSON": '["client-key"]',
                "FOUNDRY_ADMIN_API_KEYS_JSON": '["admin-key"]',
                "FOUNDRY_PRICING_JSON": "{}",
                "FOUNDRY_BACKEND_CYCLE_START_DAY_JSON": "{}",
            },
        ):
            with pytest.raises(ValueError, match="At least one model must be configured"):
                load_settings()

    def test_model_references_unknown_backend_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FOUNDRY_BACKENDS_JSON": '{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key", "deployment": "gpt-4"}}',
                "FOUNDRY_MODELS_JSON": '{"gpt-4": {"backends": {"backend_b": 1.0}}}',
                "FOUNDRY_CLIENT_API_KEYS_JSON": '["client-key"]',
                "FOUNDRY_ADMIN_API_KEYS_JSON": '["admin-key"]',
                "FOUNDRY_PRICING_JSON": "{}",
                "FOUNDRY_BACKEND_CYCLE_START_DAY_JSON": "{}",
            },
        ):
            with pytest.raises(ValueError, match="unknown backend"):
                load_settings()

    def test_empty_client_keys_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FOUNDRY_BACKENDS_JSON": '{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key", "deployment": "gpt-4"}}',
                "FOUNDRY_MODELS_JSON": '{"gpt-4": {"backends": {"backend_a": 1.0}}}',
                "FOUNDRY_CLIENT_API_KEYS_JSON": "[]",
                "FOUNDRY_ADMIN_API_KEYS_JSON": '["admin-key"]',
                "FOUNDRY_PRICING_JSON": "{}",
                "FOUNDRY_BACKEND_CYCLE_START_DAY_JSON": "{}",
            },
        ):
            with pytest.raises(ValueError, match="At least one client API key"):
                load_settings()

    def test_empty_admin_keys_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FOUNDRY_BACKENDS_JSON": '{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key", "deployment": "gpt-4"}}',
                "FOUNDRY_MODELS_JSON": '{"gpt-4": {"backends": {"backend_a": 1.0}}}',
                "FOUNDRY_CLIENT_API_KEYS_JSON": '["client-key"]',
                "FOUNDRY_ADMIN_API_KEYS_JSON": "[]",
                "FOUNDRY_PRICING_JSON": "{}",
                "FOUNDRY_BACKEND_CYCLE_START_DAY_JSON": "{}",
            },
        ):
            with pytest.raises(ValueError, match="At least one admin API key"):
                load_settings()

    def test_client_admin_keys_disjoint(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FOUNDRY_BACKENDS_JSON": '{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key", "deployment": "gpt-4"}}',
                "FOUNDRY_MODELS_JSON": '{"gpt-4": {"backends": {"backend_a": 1.0}}}',
                "FOUNDRY_CLIENT_API_KEYS_JSON": '["shared-key"]',
                "FOUNDRY_ADMIN_API_KEYS_JSON": '["shared-key"]',
                "FOUNDRY_PRICING_JSON": "{}",
                "FOUNDRY_BACKEND_CYCLE_START_DAY_JSON": "{}",
            },
        ):
            with pytest.raises(ValueError, match="disjoint"):
                load_settings()

    def test_cycle_start_day_validation(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FOUNDRY_BACKENDS_JSON": '{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key", "deployment": "gpt-4"}}',
                "FOUNDRY_MODELS_JSON": '{"gpt-4": {"backends": {"backend_a": 1.0}}}',
                "FOUNDRY_CLIENT_API_KEYS_JSON": '["client-key"]',
                "FOUNDRY_ADMIN_API_KEYS_JSON": '["admin-key"]',
                "FOUNDRY_PRICING_JSON": "{}",
                "FOUNDRY_BACKEND_CYCLE_START_DAY_JSON": '{"backend_a": 0}',
            },
        ):
            with pytest.raises(ValueError, match="must be 1-28"):
                load_settings()

        with patch.dict(
            os.environ,
            {
                "FOUNDRY_BACKENDS_JSON": '{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key", "deployment": "gpt-4"}}',
                "FOUNDRY_MODELS_JSON": '{"gpt-4": {"backends": {"backend_a": 1.0}}}',
                "FOUNDRY_CLIENT_API_KEYS_JSON": '["client-key"]',
                "FOUNDRY_ADMIN_API_KEYS_JSON": '["admin-key"]',
                "FOUNDRY_PRICING_JSON": "{}",
                "FOUNDRY_BACKEND_CYCLE_START_DAY_JSON": '{"backend_a": 29}',
            },
        ):
            with pytest.raises(ValueError, match="must be 1-28"):
                load_settings()

    def test_cycle_start_day_unknown_backend_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FOUNDRY_BACKENDS_JSON": '{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key", "deployment": "gpt-4"}}',
                "FOUNDRY_MODELS_JSON": '{"gpt-4": {"backends": {"backend_a": 1.0}}}',
                "FOUNDRY_CLIENT_API_KEYS_JSON": '["client-key"]',
                "FOUNDRY_ADMIN_API_KEYS_JSON": '["admin-key"]',
                "FOUNDRY_PRICING_JSON": "{}",
                "FOUNDRY_BACKEND_CYCLE_START_DAY_JSON": '{"backend_b": 15}',
            },
        ):
            with pytest.raises(ValueError, match="unknown backend"):
                load_settings()

    def test_reconciliation_override_unknown_backend_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FOUNDRY_BACKENDS_JSON": '{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key", "deployment": "gpt-4"}}',
                "FOUNDRY_MODELS_JSON": '{"gpt-4": {"backends": {"backend_a": 1.0}}}',
                "FOUNDRY_CLIENT_API_KEYS_JSON": '["client-key"]',
                "FOUNDRY_ADMIN_API_KEYS_JSON": '["admin-key"]',
                "FOUNDRY_PRICING_JSON": "{}",
                "FOUNDRY_BACKEND_CYCLE_START_DAY_JSON": "{}",
                "FOUNDRY_RECONCILIATION_OVERRIDES_USD_JSON": '{"backend_b": 12.5}',
            },
        ):
            with pytest.raises(ValueError, match="unknown backend"):
                load_settings()

    def test_get_allowed_hostnames(self) -> None:
        backends = {
            "backend_a": {
                "endpoint": "https://backend-a.openai.azure.com",
                "credential": "key-a",
                "deployment": "gpt-4",
            },
            "backend_b": {
                "endpoint": "https://backend-b.openai.azure.com",
                "credential": "key-b",
                "deployment": "gpt-4",
            },
        }
        with patch.dict(
            os.environ,
            {
                "FOUNDRY_BACKENDS_JSON": json.dumps(backends),
                "FOUNDRY_MODELS_JSON": '{"gpt-4": {"backends": {"backend_a": 1.0}}}',
                "FOUNDRY_CLIENT_API_KEYS_JSON": '["client-key"]',
                "FOUNDRY_ADMIN_API_KEYS_JSON": '["admin-key"]',
                "FOUNDRY_PRICING_JSON": "{}",
                "FOUNDRY_BACKEND_CYCLE_START_DAY_JSON": "{}",
            },
        ):
            settings = load_settings()
            hostnames = settings.get_allowed_hostnames()
            assert hostnames == {"backend-a.openai.azure.com", "backend-b.openai.azure.com"}

    def test_invalid_json_rejected(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "FOUNDRY_BACKENDS_JSON": "not valid json",
                    "FOUNDRY_MODELS_JSON": '{"gpt-4": {"backends": {"backend_a": 1.0}}}',
                    "FOUNDRY_CLIENT_API_KEYS_JSON": '["client-key"]',
                    "FOUNDRY_ADMIN_API_KEYS_JSON": '["admin-key"]',
                    "FOUNDRY_PRICING_JSON": "{}",
                    "FOUNDRY_BACKEND_CYCLE_START_DAY_JSON": "{}",
                },
            ),
            pytest.raises(ValueError, match="Invalid FOUNDRY_BACKENDS_JSON"),
        ):
            load_settings()
