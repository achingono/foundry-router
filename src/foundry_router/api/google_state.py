"""Bounded sealed provider-state primitives; no secret lookup or conversation cache."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from foundry_router.api.adapters.google_schema import load_bounded_json

MAX_TOKEN_BYTES = 131072
MAX_TURN_CARRIER_BYTES = 262144
MAX_INPUT_CARRIER_BYTES = 524288
_KEY_ID = re.compile(r"[A-Za-z0-9_-]{1,32}")
_HEX_DIGEST = re.compile(r"[0-9a-f]{64}")


class ProviderStateError(ValueError):
    """Safe failure that never embeds keys, ciphertext or provider state."""


def _reject() -> None:
    raise ProviderStateError("Invalid provider state")


def _string_keys(value: Any, budget: list[int], *, depth: int = 0) -> None:
    budget[0] -= 1
    if depth > 32 or budget[0] < 0:
        _reject()
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            _reject()
        for item in value.values():
            _string_keys(item, budget, depth=depth + 1)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _string_keys(item, budget, depth=depth + 1)


def canonical_wire_bytes(value: Any, *, max_bytes: int = 2097152) -> bytes:
    """Encode an already validated JSON value without a duplicate parsing pass."""
    try:
        _string_keys(value, [16384])
        wire = json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
        encoded = wire.encode("utf-8")
        if len(encoded) > max_bytes:
            _reject()
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise ProviderStateError("Invalid provider state") from exc
    return encoded


def canonical_bytes(value: Any, *, max_bytes: int = 2097152) -> bytes:
    """One bounded, duplicate-free canonical JSON representation."""
    encoded = canonical_wire_bytes(value, max_bytes=max_bytes)
    try:
        load_bounded_json(encoded.decode("utf-8"), max_bytes=max_bytes)
    except ValueError as exc:
        raise ProviderStateError("Invalid provider state") from exc
    return encoded


def framed_digest(domain: str, value: Any, *, max_bytes: int = 2097152) -> str:
    if domain not in {"context", "part"}:
        _reject()
    wire = canonical_bytes(value, max_bytes=max_bytes)
    digest = hashlib.sha256(f"foundry-{domain}-v1\0".encode("ascii"))
    digest.update(len(wire).to_bytes(8, "big"))
    digest.update(wire)
    return digest.hexdigest()


def history_digests(items: list[dict[str, Any]]) -> tuple[str, ...]:
    """Hash each item once; snapshots identify exact prefix boundaries."""
    if not 1 <= len(items) <= 256:
        _reject()
    digest = hashlib.sha256(b"foundry-history-v1\0")
    total = 0
    result = []
    for item in items:
        wire = canonical_bytes(item)
        total += len(wire) + 8
        if total > 2097152:
            _reject()
        digest.update(len(wire).to_bytes(8, "big"))
        digest.update(wire)
        result.append(digest.copy().hexdigest())
    return tuple(result)


def credential_scope(key: bytes, credential: str, *, domain: str) -> str:
    if (
        not isinstance(key, bytes)
        or len(key) != 32
        or domain not in {"caller", "backend"}
        or not isinstance(credential, str)
        or not credential
    ):
        _reject()
    try:
        raw = credential.encode("utf-8")
    except UnicodeError as exc:
        raise ProviderStateError("Invalid provider state") from exc
    return hmac.new(key, domain.encode("ascii") + b"\0" + raw, hashlib.sha256).hexdigest()


@dataclass(frozen=True, repr=False)
class StateBinding:
    """Trusted API-owned binding; validated configuration constructs these facts."""

    caller: str
    model: str
    backend: str
    deployment: str
    surface: str
    generation: str
    configuration: str
    context: str

    def public_facts(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True, repr=False)
class SealedTurn:
    response_id: str
    start: int
    item_ids: tuple[str, ...]
    history: str
    parts: tuple[str, ...]
    signatures: tuple[str | None, ...]


def _valid_turn(turn: SealedTurn) -> bool:
    if (
        not isinstance(turn, SealedTurn)
        or not isinstance(turn.item_ids, tuple)
        or not isinstance(turn.parts, tuple)
        or not isinstance(turn.signatures, tuple)
        or not isinstance(turn.response_id, str)
        or not 1 <= len(turn.response_id) <= 128
        or type(turn.start) is not int
        or not 0 <= turn.start < 256
        or not 1 <= len(turn.item_ids) <= 64
        or turn.start + len(turn.item_ids) > 256
        or len(turn.parts) != len(turn.item_ids)
        or len(turn.signatures) != len(turn.item_ids)
        or not isinstance(turn.history, str)
        or not _HEX_DIGEST.fullmatch(turn.history)
        or any(not isinstance(value, str) or not 1 <= len(value) <= 128 for value in turn.item_ids)
        or len(set(turn.item_ids)) != len(turn.item_ids)
        or any(
            not isinstance(value, str) or not _HEX_DIGEST.fullmatch(value) for value in turn.parts
        )
    ):
        return False
    total = 0
    for signature in turn.signatures:
        if signature is None:
            continue
        if not isinstance(signature, str) or len(signature) > 21848:
            return False
        try:
            raw = base64.b64decode(signature, validate=True)
        except ValueError:
            return False
        if not 1 <= len(raw) <= 16384 or base64.b64encode(raw).decode("ascii") != signature:
            return False
        total += len(raw)
    return total <= 65536


class StateCodec:
    """Owned key ring with bounded rotation and authenticated explicit expiry."""

    def __init__(self, keys: dict[str, bytes], *, active: str, ttl: int = 900) -> None:
        if (
            not 1 <= len(keys) <= 3
            or active not in keys
            or type(ttl) is not int
            or not 60 <= ttl <= 3600
            or any(not isinstance(name, str) or not _KEY_ID.fullmatch(name) for name in keys)
        ):
            _reject()
        try:
            decoded_keys = []
            for value in keys.values():
                if not isinstance(value, bytes):
                    _reject()
                decoded = base64.b64decode(value, altchars=b"-_", validate=True)
                if len(decoded) != 32 or base64.urlsafe_b64encode(decoded) != value:
                    _reject()
                decoded_keys.append(decoded)
            if len(set(decoded_keys)) != len(decoded_keys):
                _reject()
            self._keys = {name: Fernet(value) for name, value in keys.items()}
        except (ValueError, TypeError) as exc:
            raise ProviderStateError("Invalid provider state key configuration") from exc
        self._active = active
        self._ttl = ttl

    def seal(self, binding: StateBinding, turn: SealedTurn, *, now: int) -> str:
        if type(now) is not int or not 0 <= now <= 253402300799 or not _valid_turn(turn):
            _reject()
        payload = {
            "version": 1,
            "key_id": self._active,
            "issued_at": now,
            "expiry": now + self._ttl,
            "binding": binding.public_facts(),
            "turn": {name: getattr(turn, name) for name in turn.__dataclass_fields__},
        }
        raw = canonical_bytes(payload, max_bytes=MAX_TOKEN_BYTES)
        token = (
            self._active + "." + self._keys[self._active].encrypt_at_time(raw, now).decode("ascii")
        )
        if len(token) > min(MAX_TOKEN_BYTES, MAX_TURN_CARRIER_BYTES // len(turn.item_ids)):
            _reject()
        return token

    def open(self, token: str, binding: StateBinding, *, now: int) -> SealedTurn:
        return self.open_bound(token, {binding.backend: binding}, now=now)[1]

    def open_bound(
        self, token: str, bindings: dict[str, StateBinding], *, now: int
    ) -> tuple[str, SealedTurn]:
        if not 1 <= len(bindings) <= 256:
            _reject()
        if (
            not isinstance(token, str)
            or len(token) > MAX_TOKEN_BYTES
            or type(now) is not int
            or now < 0
        ):
            _reject()
        try:
            key_id, ciphertext = token.split(".")
            encoded = ciphertext.encode("ascii")
            decoded = base64.b64decode(encoded, altchars=b"-_", validate=True)
            if base64.urlsafe_b64encode(decoded) != encoded or key_id not in self._keys:
                _reject()
            raw = self._keys[key_id].decrypt_at_time(encoded, ttl=self._ttl, current_time=now)
            payload = load_bounded_json(raw.decode("utf-8"), max_bytes=MAX_TOKEN_BYTES)
        except (ValueError, UnicodeError, InvalidToken) as exc:
            raise ProviderStateError("Invalid provider state") from exc
        if not isinstance(payload, dict) or set(payload) != {
            "version",
            "key_id",
            "issued_at",
            "expiry",
            "binding",
            "turn",
        }:
            _reject()
        issued, expiry = payload["issued_at"], payload["expiry"]
        if (
            type(payload["version"]) is not int
            or payload["version"] != 1
            or payload["key_id"] != key_id
            or type(issued) is not int
            or type(expiry) is not int
            or not 60 <= expiry - issued <= 3600
            or issued != int.from_bytes(decoded[1:9], "big")
            or issued > now + 60
            or expiry < now
            or not isinstance(payload["turn"], dict)
            or set(payload["turn"]) != set(SealedTurn.__dataclass_fields__)
        ):
            _reject()
        matches = [
            name
            for name, binding in bindings.items()
            if payload["binding"] == binding.public_facts()
        ]
        if len(matches) != 1:
            _reject()
        values = payload["turn"]
        if any(not isinstance(values[name], list) for name in ("item_ids", "parts", "signatures")):
            _reject()
        turn = SealedTurn(
            response_id=values["response_id"],
            start=values["start"],
            item_ids=tuple(values["item_ids"]),
            history=values["history"],
            parts=tuple(values["parts"]),
            signatures=tuple(values["signatures"]),
        )
        if not _valid_turn(turn) or len(token) * len(turn.item_ids) > MAX_TURN_CARRIER_BYTES:
            _reject()
        return matches[0], turn


def check_state_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("Provider state preparation exceeded its deadline")
