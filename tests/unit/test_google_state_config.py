"""Secret continuation key readiness and safe configuration diagnostics."""

import base64

import pytest
from pydantic import ValidationError

from foundry_router.config.google_state import GoogleStateKeys, decode_state_key

SCOPE = base64.urlsafe_b64encode(b"scope-key-fixture-32-bytes-padding"[:32]).decode()
KEY = base64.urlsafe_b64encode(b"envelope-fixture-32-bytes-padding"[:32]).decode()


def config(**changes):
    return GoogleStateKeys(
        scope_key=SCOPE, keys={"current": KEY}, active="current", generation="fixture-v1", **changes
    )


def test_secret_keys_excluded_from_representation_and_serialization():
    keys = config()
    assert len(decode_state_key(keys.scope_key)) == 32
    assert keys.model_dump() == {
        "active": "current",
        "generation": "fixture-v1",
        "ttl_seconds": 900,
    }
    assert SCOPE not in repr(keys) and KEY not in repr(keys)


@pytest.mark.parametrize(
    "changes",
    [
        {"scope_key": KEY},
        {"scope_key": "SECRET-INVALID"},
        {"keys": {"a": KEY, "b": KEY}, "active": "a"},
        {"keys": {}},
        {"keys": {"bad.key": KEY}, "active": "bad.key"},
        {"active": "absent"},
        {"generation": ""},
        {"ttl_seconds": True},
        {"keys": {str(i): KEY for i in range(4)}},
        {"extra": "SECRET-INVALID"},
    ],
)
def test_invalid_configuration_is_safe(changes):
    supplied = {
        "scope_key": SCOPE,
        "keys": {"current": KEY},
        "active": "current",
        "generation": "fixture",
    }
    with pytest.raises(ValidationError) as error:
        GoogleStateKeys(**{**supplied, **changes})
    assert SCOPE not in str(error.value) and KEY not in str(error.value)
    assert "SECRET-INVALID" not in str(error.value)


@pytest.mark.parametrize("key", [KEY + "!!", KEY + "====", " " + KEY, "é", "AA=="])
def test_key_aliases_and_short_unicode_keys_reject(key):
    with pytest.raises(ValidationError):
        GoogleStateKeys(
            scope_key=SCOPE, keys={"current": key}, active="current", generation="fixture"
        )


def test_settings_secret_configuration_enables_no_profile():
    from foundry_router.config import Settings

    settings = Settings(
        backends_json='{"g":{"provider":"google_ai_studio","endpoint":"https://fixture.example.test","credential":"fixture","deployment":"fixture","credit_metered":false}}',
        models_json='{"m":{"backends":{"g":1}}}',
        client_api_keys_json='["fixture-client"]',
        admin_api_keys_json='["fixture-admin"]',
        google_state_keys_json='{"scope_key":"'
        + SCOPE
        + '","keys":{"current":"'
        + KEY
        + '"},"active":"current","generation":"fixture"}',
    )
    assert settings.google_state_keys.active == "current"
    assert settings.backends["g"].google_features.continuation_policy == "disabled"
    assert "google_state_keys_json" not in settings.model_dump()
    assert SCOPE not in repr(settings) and KEY not in repr(settings)


@pytest.mark.parametrize("raw", ['{"scope_key":"SECRET-INVALID"}', "SECRET-INVALID" * 1000])
def test_settings_key_error_never_contains_raw_secret(raw):
    from foundry_router.config import Settings

    with pytest.raises(ValidationError) as error:
        Settings(google_state_keys_json=raw)
    assert "SECRET-INVALID" not in str(error.value)


def test_key_ring_is_owned_and_immutable():
    supplied = {"current": KEY}
    keys = GoogleStateKeys(scope_key=SCOPE, keys=supplied, active="current", generation="fixture")
    supplied["current"] = SCOPE
    assert keys.keys["current"].get_secret_value() == KEY
    with pytest.raises(TypeError):
        keys.keys["current"] = keys.scope_key


@pytest.mark.parametrize(
    "raw", ['{"active":"wrong","active":"current"}', '{"keys":{"current":"a","current":"b"}}']
)
def test_duplicate_secret_configuration_keys_reject(raw):
    from foundry_router.config.google_state import parse_state_keys

    with pytest.raises(ValueError, match="^Invalid provider-state key configuration$"):
        parse_state_keys(raw)


def test_signed_profile_requires_explicit_bounds_and_runtime_stays_disabled():
    from foundry_router.config import Settings
    from foundry_router.config.google_features import GoogleFeatureProfile

    with pytest.raises(ValidationError):
        GoogleFeatureProfile(features=("function_tools",), continuation_policy="sealed_native")
    profile = GoogleFeatureProfile(
        features=("function_tools",),
        continuation_policy="sealed_native",
        native_thinking_budget=0,
        thought_token_pricing=True,
        signature_input_token_bound=100000,
    )
    import json

    with pytest.raises(ValidationError, match="runtime integration"):
        Settings(
            backends_json=json.dumps(
                {
                    "g": {
                        "provider": "google_ai_studio",
                        "api_surface": "native",
                        "endpoint": "https://fixture.example.test",
                        "credential": "fixture",
                        "deployment": "fixture",
                        "credit_metered": False,
                        "google_features": profile.model_dump(),
                    }
                }
            ),
            models_json='{"m":{"backends":{"g":1},"continuation_policy":"bound_history_required"}}',
            client_api_keys_json='["client"]',
            admin_api_keys_json='["admin"]',
            google_state_keys_json=json.dumps(
                {
                    "scope_key": SCOPE,
                    "keys": {"current": KEY},
                    "active": "current",
                    "generation": "fixture",
                }
            ),
        )
