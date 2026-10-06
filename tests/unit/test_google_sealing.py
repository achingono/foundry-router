"""Configuration identity binds provider keys, routing, quotas and output contracts."""

import base64
import json

import pytest

from foundry_router.api.google_sealing import backend_fingerprint, build_seal_context
from foundry_router.config import Settings


def settings():
    return Settings(
        backends_json='{"g":{"provider":"google_ai_studio","api_surface":"native","endpoint":"https://fixture.example.test","credential":"fixture","deployment":"fixture","credit_metered":false,"google_features":{"native_thinking_disabled":true}}}',
        models_json='{"m":{"backends":{"g":1}}}',
        client_api_keys_json='["client"]',
        admin_api_keys_json='["admin"]',
        google_state_keys_json=json.dumps(
            {
                "scope_key": base64.urlsafe_b64encode(b"s" * 32).decode(),
                "keys": {"current": base64.urlsafe_b64encode(b"k" * 32).decode()},
                "active": "current",
                "generation": "fixture",
            }
        ),
    )


def test_owned_context_and_hidden_key_representation():
    configured = settings()
    context = build_seal_context(
        configured,
        "m",
        {"model": "m", "input": [{"role": "user", "content": "fixture"}]},
        caller_scope="caller",
    )
    assert context.binding("g").backend == "g" and context.binding("g").caller == "caller"
    assert context.key_configuration is configured.google_state_keys
    assert "fixture" not in repr(context)


@pytest.mark.parametrize(
    "field,value",
    [
        ("credential", "rotated"),
        ("deployment", "other"),
        ("endpoint", "https://other.example.test"),
        ("quota_group", "other"),
        ("credit_group", "other"),
    ],
)
def test_backend_configuration_changes_break_binding(field, value):
    configured = settings()
    before = backend_fingerprint(configured, "g", "m")
    setattr(configured.backends["g"], field, value)
    assert backend_fingerprint(configured, "g", "m") != before


def test_quota_and_profile_changes_break_binding():
    configured = settings()
    before = backend_fingerprint(configured, "g", "m")
    configured.quota_group_rate_limits = {"g": {"tpm": 1000}}
    assert backend_fingerprint(configured, "g", "m") != before
    configured = settings()
    configured.backends["g"].google_features = configured.backends["g"].google_features.model_copy(
        update={"max_history_items": 64}
    )
    assert backend_fingerprint(configured, "g", "m") != before


def test_missing_keys_fail_safely():
    configured = settings()
    configured.google_state_keys = None
    with pytest.raises(ValueError, match="unavailable"):
        backend_fingerprint(configured, "g", "m")
    with pytest.raises(ValueError, match="unavailable"):
        build_seal_context(configured, "m", {"input": []}, caller_scope="caller")


def test_shared_context_serialized_once_and_profile_mismatch_rejects(monkeypatch):
    import foundry_router.api.google_sealing as sealing

    configured = settings()
    configured.backends["h"] = configured.backends["g"].model_copy(update={"credential": "other"})
    configured.models["m"].backends["h"] = 1
    original = sealing.project_context
    visits = []

    def project(*args):
        visits.append(1)
        return original(*args)

    monkeypatch.setattr(sealing, "project_context", project)
    context = build_seal_context(
        configured, "m", {"model": "m", "input": []}, caller_scope="caller"
    )
    assert visits == [1] and context.binding("g").context == context.binding("h").context
    configured.backends["h"].google_features = configured.backends["h"].google_features.model_copy(
        update={"max_history_items": 64}
    )
    with pytest.raises(ValueError, match="common feature"):
        build_seal_context(configured, "m", {"model": "m", "input": []}, caller_scope="caller")


def test_signed_pool_work_is_bounded():
    configured = settings()
    for index in range(256):
        name = f"fixture_{index}"
        configured.backends[name] = configured.backends["g"]
        configured.models["m"].backends[name] = 1
    with pytest.raises(ValueError, match="common feature"):
        build_seal_context(configured, "m", {"model": "m", "input": []}, caller_scope="caller")
