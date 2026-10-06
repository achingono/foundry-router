"""Owned turn association, caller/backend pinning and immutable request snapshots."""

import base64
from dataclasses import replace

import pytest

from foundry_router.api.google_continuation import (
    prepare_continuation,
    seal_output_turn,
    unsigned_native_part,
)
from foundry_router.api.google_history import project_history
from foundry_router.api.google_state import (
    ProviderStateError,
    SealedTurn,
    StateBinding,
    StateCodec,
    framed_digest,
)

KEY = base64.urlsafe_b64encode(b"k" * 32)
BINDING = StateBinding("caller", "m", "g", "fixture", "native", "v1", "config", "context")


def fixture():
    codec = StateCodec({"one": KEY}, active="one")
    body = {
        "model": "m",
        "foundry_provider_state": {"version": 1},
        "input": [
            {"role": "user", "content": "fixture"},
            {
                "type": "function_call",
                "id": "fc_fixture",
                "call_id": "call_fixture",
                "name": "fixture",
                "arguments": "{}",
                "status": "completed",
            },
        ],
    }
    _, digests = project_history(body)
    turn = SealedTurn(
        "resp_fixture",
        1,
        ("fc_fixture",),
        digests[-1],
        (framed_digest("part", unsigned_native_part(body["input"][1])),),
        ("c2ln",),
    )
    token = codec.seal(BINDING, turn, now=1000)
    body["input"][1]["foundry_provider_state"] = {"version": 1, "token": token}
    body["input"].append(
        {"type": "function_call_output", "call_id": "call_fixture", "output": "fixture result"}
    )
    return codec, body


def test_prepare_backend_pin_single_decrypt_and_snapshot(monkeypatch):
    codec, body = fixture()
    original = codec.open_bound
    calls = []

    def open_bound(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(codec, "open_bound", open_bound)
    prepared = prepare_continuation(
        body, codec, {"other": replace(BINDING, backend="other"), "g": BINDING}, now=1000
    )
    assert prepared.backend == "g" and prepared.signature_input_tokens == 68 and calls == [1]
    prepared.validate(body)
    body["input"][-1]["output"] = "changed"
    with pytest.raises(ProviderStateError):
        prepared.validate(body)


@pytest.mark.parametrize(
    "change", ["text", "arguments", "identity", "missing", "reorder", "caller", "backend", "expiry"]
)
def test_invalid_bindings_or_history_reject_before_admission(change):
    codec, body = fixture()
    binding = BINDING
    now = 1000
    if change == "text":
        body["input"][0]["content"] = "changed"
    elif change == "arguments":
        body["input"][1]["arguments"] = "{ }"
    elif change == "identity":
        body["input"][1]["id"] = "changed"
    elif change == "missing":
        del body["input"][1]["foundry_provider_state"]
    elif change == "reorder":
        body["input"][:2] = reversed(body["input"][:2])
    elif change == "caller":
        binding = replace(binding, caller="other")
    elif change == "backend":
        binding = replace(binding, backend="other")
    elif change == "expiry":
        now = 1901
    with pytest.raises(ProviderStateError):
        prepare_continuation(body, codec, {"g": binding}, now=now)


def test_fresh_stateless_history_has_no_pin_and_bad_pool_rejects():
    codec, body = fixture()
    body["input"] = body["input"][:1]
    assert prepare_continuation(body, codec, {"g": BINDING}, now=1000) is None
    _, body = fixture()
    with pytest.raises(ProviderStateError):
        prepare_continuation(body, codec, {}, now=1000)


@pytest.mark.parametrize("arguments", ["[]", "invalid"])
def test_native_function_part_requires_bounded_object_arguments(arguments):
    with pytest.raises(ProviderStateError):
        unsigned_native_part(
            {
                "type": "function_call",
                "call_id": "call_fixture",
                "name": "fixture",
                "arguments": arguments,
            }
        )


def test_text_part_identity_and_unsupported_item_reject():
    assert unsigned_native_part(
        {"type": "message", "role": "assistant", "content": [{"text": "fixture"}]}
    ) == {"text": "fixture"}
    with pytest.raises(ProviderStateError):
        unsigned_native_part({"type": "function_call_output"})


def test_seal_output_and_replay_independent_request_ownership():

    codec, body = fixture()
    body["input"] = body["input"][:1]
    output = [
        {
            "type": "function_call",
            "id": "fc_new",
            "call_id": "call_new",
            "name": "fixture",
            "arguments": "{}",
            "status": "completed",
        }
    ]
    finalized = seal_output_turn(
        body,
        output,
        ("c2ln",),
        codec,
        BINDING,
        response_id="resp_new",
        now=1000,
        max_history_items=128,
        max_result_bytes=65536,
    )
    assert "foundry_provider_state" not in output[0]
    replay = {
        **body,
        "input": [
            *body["input"],
            *finalized,
            {"type": "function_call_output", "call_id": "call_new", "output": "fixture"},
        ],
    }
    assert prepare_continuation(replay, codec, {"g": BINDING}, now=1000).backend == "g"


@pytest.mark.parametrize("scenario", ["unsigned_call", "items", "bytes", "signature_count"])
def test_seal_replay_limits_fail_before_mutating_output(scenario):

    codec, body = fixture()
    body["input"] = body["input"][:1]
    output = [
        {
            "type": "function_call",
            "id": "fc_new",
            "call_id": "call_new",
            "name": "fixture",
            "arguments": "{}",
            "status": "completed",
        }
    ]
    signatures = (
        (None,)
        if scenario == "unsigned_call"
        else ()
        if scenario == "signature_count"
        else ("c2ln",)
    )
    with pytest.raises(ProviderStateError):
        seal_output_turn(
            body,
            output,
            signatures,
            codec,
            BINDING,
            response_id="resp_new",
            now=1000,
            max_history_items=2 if scenario == "items" else 128,
            max_result_bytes=400000 if scenario == "bytes" else 65536,
        )
    assert "foundry_provider_state" not in output[0]
