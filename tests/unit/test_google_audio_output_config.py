"""Finite audio-output profile has explicit model thinking, price, voice and quota gates."""

import json

import pytest
from pydantic import ValidationError

from foundry_router.api.adapters.google_audio_request import validate_audio_output_request
from foundry_router.config import BackendConfig, Settings
from foundry_router.config.google_features import GoogleFeatureProfile


def profile():
    return {
        "features": ["audio_output"],
        "generated_output_tokens_bound": 2048,
        "audio_output_voices": ["Kore"],
        "audio_output_thinking_policy": "omit",
        "audio_output_thinking_affirmed": True,
        "audio_output_price_ceiling_usd_per_second": 0.01,
        "audio_output_input_token_pricing": True,
        "audio_output_quota_via_rpm": True,
        "audio_output_input_tpm_tokens": True,
        "audio_output_rpm": 10,
    }


@pytest.mark.parametrize(
    "field",
    [
        "generated_output_tokens_bound",
        "audio_output_voices",
        "audio_output_thinking_policy",
        "audio_output_thinking_affirmed",
        "audio_output_price_ceiling_usd_per_second",
        "audio_output_input_token_pricing",
        "audio_output_quota_via_rpm",
        "audio_output_input_tpm_tokens",
        "audio_output_rpm",
    ],
)
def test_missing_dimension_never_enables_audio(field):
    data = profile()
    data.pop(field)
    with pytest.raises(ValidationError):
        GoogleFeatureProfile(**data)


@pytest.mark.parametrize(
    "voices", [["voice_stored"], ["voicekey_replica"], ["Kore", "Kore"], ["PRIVATE VOICE"]]
)
def test_stored_replicated_duplicate_or_invalid_voices_reject(voices):
    with pytest.raises(ValidationError):
        GoogleFeatureProfile(**{**profile(), "audio_output_voices": voices})


def test_startup_gate_and_native_only_profile():
    backend = {
        "provider": "google_ai_studio",
        "api_surface": "native",
        "endpoint": "https://synthetic.example.test",
        "deployment": "configured",
        "credential": "synthetic",
        "credit_metered": False,
        "google_features": {**profile(), "audio_output_price_ceiling_usd_per_second": 0},
        "quota_group": "project",
    }
    assert BackendConfig(**backend).google_features.audio_output_thinking_policy == "omit"
    with pytest.raises(ValidationError, match="Generated audio runtime is unavailable"):
        Settings(
            backends_json=json.dumps({"g": backend}),
            models_json='{"m":{"backends":{"g":1}}}',
            client_api_keys_json='["caller"]',
            admin_api_keys_json='["admin"]',
            quota_group_rate_limits_json='{"project":{"rpm":10,"tpm":100000}}',
        )
    with pytest.raises(ValidationError):
        BackendConfig(**{**backend, "api_surface": "openai_compat"})


@pytest.mark.parametrize(
    "patch",
    [
        {"input": "x" * 4097},
        {"instructions": "x" * 1025},
        {"stream": True},
        {"store": None},
        {"tools": []},
        {"max_output_tokens": 1024},
        {"foundry_audio_generation": {"version": True, "format": "wav", "voice": "Kore"}},
        {"foundry_audio_generation": {"version": 1, "format": "wav", "voice": "voice_stored"}},
    ],
)
def test_request_contract_bounds_and_no_unreviewed_controls(patch):
    config = GoogleFeatureProfile(**profile())
    body = {
        "input": "fixture",
        "foundry_audio_generation": {"version": 1, "format": "wav", "voice": "Kore"},
    }
    assert validate_audio_output_request(body, config) == "Kore"
    with pytest.raises(ValueError):
        validate_audio_output_request({**body, **patch}, config)


def test_audio_pool_explicit_project_dimensions_and_price():
    from types import SimpleNamespace

    from foundry_router.config.google_audio_output import validate_audio_output_pools

    backend = BackendConfig(
        provider="google_ai_studio",
        api_surface="native",
        endpoint="https://synthetic.example.test",
        deployment="configured",
        credential="synthetic",
        quota_group="project",
        google_features=profile(),
    )
    settings = SimpleNamespace(
        backends={"g": backend},
        models={"m": SimpleNamespace(backends={"g": 1})},
        pricing={"m": SimpleNamespace(audio_output_per_second=0.01)},
        quota_group_rate_limits={"project": {"rpm": 10, "tpm": 1000}},
        protected_emergency_fallback=False,
    )
    explicit = {"g": {"quota_group": "project"}}
    validate_audio_output_pools(settings, explicit)
    with pytest.raises(ValueError, match="explicit"):
        validate_audio_output_pools(settings, {"g": {}})
    for limits in ({"rpm": 11, "tpm": 100}, {"rpm": 10}, {"tpm": 100}):
        settings.quota_group_rate_limits = {"project": limits}
        with pytest.raises(ValueError, match="RPM"):
            validate_audio_output_pools(settings, explicit)
    settings.quota_group_rate_limits = {"project": {"rpm": 10, "tpm": 1000}}
    settings.pricing["m"].audio_output_per_second = 0.02
    with pytest.raises(ValueError, match="price"):
        validate_audio_output_pools(settings, explicit)
    settings.pricing["m"].audio_output_per_second = 0.01
    settings.protected_emergency_fallback = True
    with pytest.raises(ValueError, match="emergency"):
        validate_audio_output_pools(settings, explicit)
