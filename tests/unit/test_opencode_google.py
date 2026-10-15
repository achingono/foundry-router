"""Native OpenCode configuration, raw-root safety and error adapter selection."""

import pytest
from pydantic import ValidationError

from foundry_router.api.adapters import get_adapter
from foundry_router.api.adapters.google_native import GoogleNativeAdapter
from foundry_router.config import BackendConfig

BASE = {
    "provider": "opencode_google",
    "api_surface": "native",
    "endpoint": "https://opencode.example.test/inference/v1",
    "credential": "synthetic-key",
    "deployment": "arbitrary-model.2",
    "google_features": {"native_thinking_level": "low", "thought_token_pricing": True},
}


@pytest.mark.parametrize("level", ["low", "minimal"])
def test_explicit_native_text_profile(level):
    config = BackendConfig.model_validate(
        {**BASE, "google_features": {"native_thinking_level": level, "thought_token_pricing": True}}
    )
    assert config.supported_operations == ["responses"]
    assert isinstance(
        get_adapter(config.provider, google_features=config.google_features), GoogleNativeAdapter
    )
    assert isinstance(get_adapter(config.provider), GoogleNativeAdapter)


@pytest.mark.parametrize(
    "delta",
    [
        {"api_surface": "openai_compat"},
        {"credit_metered": False},
        {"google_pre_output_failover": True},
        {"google_features": {}},
        {"google_features": {"native_thinking_level": "low"}},
        {"google_features": {"native_thinking_disabled": True}},
        {
            "google_features": {
                "native_thinking_level": "low",
                "thought_token_pricing": True,
                "max_images": 1,
            }
        },
        {"google_features": {"features": ["json_object"], "native_thinking_disabled": True}},
        {"supported_operations": ["responses", "embeddings"]},
    ],
)
def test_unsupported_contract_rejected(delta):
    with pytest.raises(ValidationError):
        BackendConfig.model_validate({**BASE, **delta})


@pytest.mark.parametrize(
    "deployment",
    [None, "x" * 513, ".", "..", "a/b", "a\\b", "a:b", "a%2fb", " white", "a?x", "é", "a\n"],
)
def test_model_path_injection_rejected(deployment):
    with pytest.raises(ValidationError):
        BackendConfig.model_validate({**BASE, "deployment": deployment})


@pytest.mark.parametrize(
    "suffix",
    [
        "/../v2",
        "//v2",
        "/%76%32",
        "/models",
        "/models/other",
        "/other:generateContent",
        "/responses",
        "/chat/completions",
        "/embeddings",
        "/messages",
        "?key=x",
        "#x",
    ],
)
def test_raw_root_injection_rejected(suffix):
    with pytest.raises(ValidationError):
        BackendConfig.model_validate({**BASE, "endpoint": BASE["endpoint"] + suffix})


def test_direct_adapter_rejects_feature_expansion():
    from foundry_router.config.google_features import GoogleFeatureProfile

    with pytest.raises(ValueError, match="text-only"):
        get_adapter(
            "opencode_google", google_features=GoogleFeatureProfile(features=("json_object",))
        )
