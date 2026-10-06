"""Generated image configuration is finite and remains startup gated before integration."""

import json

import pytest
from pydantic import ValidationError

from foundry_router.config import BackendConfig, Settings
from foundry_router.config.google_features import GoogleFeatureProfile


def profile():
    return {
        "features": ["image_output"],
        "generated_output_tokens_bound": 2048,
        "image_output_price_ceiling_usd": 0.2,
        "image_output_input_token_pricing": True,
        "image_output_quota_via_rpm": True,
        "image_output_input_tpm_tokens": True,
        "image_output_ipm": 10,
        "native_thinking_disabled": True,
    }


@pytest.mark.parametrize(
    "field",
    [
        "generated_output_tokens_bound",
        "image_output_price_ceiling_usd",
        "image_output_input_token_pricing",
        "image_output_quota_via_rpm",
        "image_output_input_tpm_tokens",
        "image_output_ipm",
        "native_thinking_disabled",
    ],
)
def test_missing_dimension_fails_closed(field):
    data = profile()
    data.pop(field)
    with pytest.raises(ValidationError):
        GoogleFeatureProfile(**data)


def test_config_cannot_enable_unattached_runtime():
    backend = {
        "provider": "google_ai_studio",
        "api_surface": "native",
        "endpoint": "https://synthetic.example.test",
        "deployment": "configured",
        "credential": "synthetic",
        "credit_metered": False,
        "quota_group": "project",
        "google_features": {**profile(), "image_output_price_ceiling_usd": 0},
    }
    assert BackendConfig(**backend).google_features.generated_output_tokens_bound == 2048
    with pytest.raises(ValidationError, match="Generated image runtime is unavailable"):
        Settings(
            backends_json=json.dumps({"g": backend}),
            models_json='{"m":{"backends":{"g":1}}}',
            client_api_keys_json='["caller"]',
            admin_api_keys_json='["admin"]',
            pricing_json='{"m":{"input_per_million":0,"output_per_million":0,"image_output_per_image":0.2}}',
            quota_group_rate_limits_json='{"project":{"rpm":10,"tpm":100000}}',
        )
    with pytest.raises(ValidationError):
        BackendConfig(**{**backend, "api_surface": "openai_compat"})


def test_pool_pricing_and_shared_project_quota_prerequisites():
    from types import SimpleNamespace

    from foundry_router.config.google_output import validate_image_output_pools

    backend = BackendConfig(
        provider="google_ai_studio",
        api_surface="native",
        endpoint="https://synthetic.example.test",
        deployment="configured",
        credential="synthetic",
        quota_group="project",
        google_features=profile(),
        credit_metered=False,
    )
    settings = SimpleNamespace(
        backends={"g": backend},
        models={"m": SimpleNamespace(backends={"g": 1})},
        pricing={"m": SimpleNamespace(image_output_per_image=0.2)},
        quota_group_rate_limits={"project": {"rpm": 10, "tpm": 100000}},
        protected_emergency_fallback=False,
    )
    explicit = {"g": {"quota_group": "project"}}
    validate_image_output_pools(settings, explicit)
    for limits in ({"rpm": 11, "tpm": 100}, {"rpm": 10}, {"tpm": 100}):
        settings.quota_group_rate_limits = {"project": limits}
        with pytest.raises(ValueError, match="RPM"):
            validate_image_output_pools(settings, explicit)
    settings.quota_group_rate_limits = {"project": {"rpm": 10, "tpm": 100000}}
    with pytest.raises(ValueError, match="explicit"):
        validate_image_output_pools(settings, {"g": {}})
    settings.protected_emergency_fallback = True
    with pytest.raises(ValueError, match="emergency"):
        validate_image_output_pools(settings, explicit)
    settings.protected_emergency_fallback = False
    settings.pricing["m"].image_output_per_image = 0.1
    with pytest.raises(ValueError, match="price"):
        validate_image_output_pools(settings, explicit)
    settings.pricing["m"].image_output_per_image = 0.2
    settings.backends["other"] = backend.model_copy(update={"quota_group": "other"})
    with pytest.raises(ValueError, match="Shared"):
        validate_image_output_pools(settings, explicit)
    settings.backends["other"] = backend.model_copy(
        update={
            "credential": "distinct",
            "google_features": GoogleFeatureProfile(native_thinking_disabled=True),
        }
    )
    settings.models["m"].backends["other"] = 1
    with pytest.raises(ValueError, match="identical"):
        validate_image_output_pools(settings, explicit)
