"""Provider state cryptographic bindings, rotation, expiry and framing contracts."""

import base64
import hashlib
import json
from dataclasses import replace

import pytest
from cryptography.fernet import Fernet

from foundry_router.api.google_state import (
    ProviderStateError,
    SealedTurn,
    StateBinding,
    StateCodec,
    canonical_bytes,
    credential_scope,
    framed_digest,
    history_digests,
)

KEY = base64.urlsafe_b64encode(b"k" * 32)
SECOND = base64.urlsafe_b64encode(b"s" * 32)
BINDING = StateBinding(
    "caller", "model", "backend", "deployment", "native", "v1", "config", "context"
)
TURN = SealedTurn("resp_fixture", 1, ("fc_fixture",), "a" * 64, ("b" * 64,), ("c2lnbmF0dXJl",))


def test_round_trip_restart_rotation_and_repeated_open():
    token = StateCodec({"old": KEY}, active="old").seal(BINDING, TURN, now=1000)
    for _ in range(2):
        assert (
            StateCodec({"old": KEY, "new": SECOND}, active="new").open(token, BINDING, now=1100)
            == TURN
        )
    assert "signature" not in token and "caller" not in token
    with pytest.raises(ProviderStateError):
        StateCodec({"new": SECOND}, active="new").open(token, BINDING, now=1100)


@pytest.mark.parametrize("field", StateBinding.__dataclass_fields__)
def test_every_binding_field_is_authenticated(field):
    codec = StateCodec({"one": KEY}, active="one")
    token = codec.seal(BINDING, TURN, now=1000)
    with pytest.raises(ProviderStateError):
        codec.open(token, replace(BINDING, **{field: "changed"}), now=1000)


@pytest.mark.parametrize("now", [939, 1901, -1, True])
def test_expiry_and_future_issuance_fail_closed(now):
    codec = StateCodec({"one": KEY}, active="one")
    token = codec.seal(BINDING, TURN, now=1000)
    with pytest.raises(ProviderStateError):
        codec.open(token, BINDING, now=now)


def test_rotation_cannot_extend_minted_expiry_and_shorter_ttl_restricts():
    token = StateCodec({"one": KEY}, active="one", ttl=60).seal(BINDING, TURN, now=1000)
    with pytest.raises(ProviderStateError):
        StateCodec({"one": KEY}, active="one", ttl=3600).open(token, BINDING, now=1061)
    token = StateCodec({"one": KEY}, active="one", ttl=3600).seal(BINDING, TURN, now=1000)
    with pytest.raises(ProviderStateError):
        StateCodec({"one": KEY}, active="one", ttl=60).open(token, BINDING, now=1061)


@pytest.mark.parametrize("token", ["", "bad", "a.b.c", "one.%%%", "one." + "x" * 131072])
def test_invalid_wrapper_is_safe(token):
    with pytest.raises(ProviderStateError, match="^Invalid provider state$"):
        StateCodec({"one": KEY}, active="one").open(token, BINDING, now=1000)


def test_ciphertext_tampering_and_authenticated_payload_validation():
    codec = StateCodec({"one": KEY}, active="one")
    token = codec.seal(BINDING, TURN, now=1000)
    with pytest.raises(ProviderStateError):
        codec.open(token[:-8] + "AAAAAA==", BINDING, now=1000)
    raw = json.loads(Fernet(KEY).decrypt(token.split(".")[1]))
    for changes in (
        {"version": True},
        {"key_id": "other"},
        {"expiry": True},
        {"issued_at": 999},
        {"extra": 1},
        {"turn": {}},
        {"turn": {**raw["turn"], "parts": 1}},
    ):
        altered = (
            "one."
            + Fernet(KEY).encrypt_at_time(json.dumps({**raw, **changes}).encode(), 1000).decode()
        )
        with pytest.raises(ProviderStateError):
            codec.open(altered, BINDING, now=1000)


@pytest.mark.parametrize(
    "changes",
    [
        {"start": True},
        {"history": None},
        {"parts": ("invalid",)},
        {"signatures": ("%%%",)},
        {"signatures": ("",)},
        {"item_ids": ("a", "a")},
        {"item_ids": ({"bad": 1},)},
        {"response_id": ""},
        {"signatures": (base64.b64encode(b"x" * 16385).decode(),)},
    ],
)
def test_invalid_turns_cannot_be_minted(changes):
    with pytest.raises(ProviderStateError):
        StateCodec({"one": KEY}, active="one").seal(BINDING, replace(TURN, **changes), now=1000)


def test_repeated_carrier_and_signature_aggregate_limits():
    turn = replace(
        TURN,
        item_ids=tuple(f"item_{i}" for i in range(64)),
        parts=("b" * 64,) * 64,
        signatures=(None,) * 60 + (base64.b64encode(b"x" * 16384).decode(),) * 4,
    )
    with pytest.raises(ProviderStateError):
        StateCodec({"one": KEY}, active="one").seal(BINDING, turn, now=1000)
    with pytest.raises(ProviderStateError):
        StateCodec({"one": KEY}, active="one").seal(
            BINDING,
            replace(turn, signatures=(None,) * 59 + (base64.b64encode(b"x" * 16384).decode(),) * 5),
            now=1000,
        )


@pytest.mark.parametrize(
    "keys,active,ttl",
    [
        ({}, "one", 900),
        ({"one": KEY}, "missing", 900),
        ({"one": KEY, "two": KEY}, "one", 900),
        ({"bad.key": KEY}, "bad.key", 900),
        ({"one": b"invalid"}, "one", 900),
        ({"one": KEY}, "one", True),
        ({"one": KEY}, "one", 59),
    ],
)
def test_invalid_key_configuration(keys, active, ttl):
    with pytest.raises(ProviderStateError):
        StateCodec(keys, active=active, ttl=ttl)


def test_canonical_framing_vectors_preserve_order_and_nested_reserved_keys():
    items = [{"content": "é", "nested": {"foundry_provider_state": "inert"}}, {"call": "{}"}]
    digest = hashlib.sha256(b"foundry-history-v1\0")
    expected = []
    for item in items:
        wire = json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        digest.update(len(wire).to_bytes(8, "big") + wire)
        expected.append(digest.hexdigest())
    assert history_digests(items) == tuple(expected)
    assert history_digests(items)[-1] != history_digests(list(reversed(items)))[-1]
    assert framed_digest("part", items[0]) != framed_digest("context", items[0])
    assert canonical_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


@pytest.mark.parametrize("value", [float("nan"), object(), "\ud800", {"x": [[[[]]]]}])
def test_invalid_or_oversized_canonical_values(value):
    with pytest.raises(ProviderStateError):
        canonical_bytes(value, max_bytes=1)


def test_history_and_scope_limits_domain_separation():
    for items in ([], [{}] * 257, [{"x": "a" * 2097152}]):
        with pytest.raises(ProviderStateError):
            history_digests(items)
    assert credential_scope(b"k" * 32, "fixture", domain="caller") != credential_scope(
        b"k" * 32, "fixture", domain="backend"
    )
    for key, credential, domain in (
        (b"short", "fixture", "caller"),
        (b"k" * 32, "", "caller"),
        (b"k" * 32, "fixture", "other"),
    ):
        with pytest.raises(ProviderStateError):
            credential_scope(key, credential, domain=domain)
    with pytest.raises(ProviderStateError):
        framed_digest("other", {})


@pytest.mark.parametrize("field", SealedTurn.__dataclass_fields__)
@pytest.mark.parametrize("value", [None, True, 1, {}, [None]])
def test_authenticated_malformed_turn_fields_fail_safely(field, value):
    if (field == "start" and type(value) is int and value == 1) or (
        field == "signatures" and value == [None]
    ):
        return
    codec = StateCodec({"one": KEY}, active="one")
    token = codec.seal(BINDING, TURN, now=1000)
    payload = json.loads(Fernet(KEY).decrypt(token.split(".")[1]))
    payload["turn"][field] = value
    invalid = "one." + Fernet(KEY).encrypt_at_time(json.dumps(payload).encode(), 1000).decode()
    with pytest.raises(ProviderStateError):
        codec.open(invalid, BINDING, now=1000)


@pytest.mark.parametrize("value", [[{}], [[]]])
def test_authenticated_nonhashable_item_ids_fail_safely(value):
    codec = StateCodec({"one": KEY}, active="one")
    token = codec.seal(BINDING, TURN, now=1000)
    payload = json.loads(Fernet(KEY).decrypt(token.split(".")[1]))
    payload["turn"]["item_ids"] = value
    invalid = "one." + Fernet(KEY).encrypt_at_time(json.dumps(payload).encode(), 1000).decode()
    with pytest.raises(ProviderStateError):
        codec.open(invalid, BINDING, now=1000)


@pytest.mark.parametrize("key", [KEY + b"!!", KEY + b"====", b" " + KEY, None, [], "text"])
def test_key_aliases_and_malformed_key_values_reject(key):
    with pytest.raises(ProviderStateError):
        StateCodec({"one": key}, active="one")


def test_nonstring_keys_unicode_credentials_and_unbounded_time_reject():
    with pytest.raises(ProviderStateError):
        StateCodec({1: KEY}, active=1)
    with pytest.raises(ProviderStateError):
        canonical_bytes({1: "a"})
    with pytest.raises(ProviderStateError):
        credential_scope(b"k" * 32, "\ud800", domain="caller")
    with pytest.raises(ProviderStateError):
        StateCodec({"one": KEY}, active="one").seal(BINDING, TURN, now=2**64)


def test_turn_position_and_count_share_history_bound():
    codec = StateCodec({"one": KEY}, active="one")
    with pytest.raises(ProviderStateError):
        codec.seal(
            BINDING,
            replace(
                TURN,
                start=255,
                item_ids=("a", "b"),
                parts=("a" * 64, "b" * 64),
                signatures=(None, None),
            ),
            now=1000,
        )
    assert (
        codec.open(codec.seal(BINDING, replace(TURN, start=255), now=1000), BINDING, now=1000).start
        == 255
    )


@pytest.mark.parametrize(
    "value", [{"b": "😀", "a": [1, True, None]}, {"a": {"parsed_arguments": "exact"}}, []]
)
def test_owned_wire_encoding_matches_full_canonical_validation(value):
    from foundry_router.api.google_state import canonical_bytes, canonical_wire_bytes

    assert canonical_wire_bytes(value) == canonical_bytes(value)


@pytest.mark.parametrize("value", [{1: "x"}, {"x": float("nan")}, {"x": "\ud800"}])
def test_owned_wire_encoding_rejects_unsafe_values(value):
    from foundry_router.api.google_state import canonical_wire_bytes

    with pytest.raises(ValueError):
        canonical_wire_bytes(value)


def test_owned_wire_encoding_enforces_exact_size():
    from foundry_router.api.google_state import canonical_wire_bytes

    assert canonical_wire_bytes("x", max_bytes=3) == b'"x"'
    with pytest.raises(ValueError):
        canonical_wire_bytes("xx", max_bytes=3)
