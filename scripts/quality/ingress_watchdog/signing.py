"""Domain-separated Ed25519 signatures with explicit signer roles."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from cryptography.exceptions import InvalidSignature

from .errors import AuthorizationError, ProtocolError
from .schema import canonical_json, parse_canonical_json, require_exact_keys

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

_SIGNATURE_DOMAIN: Final[bytes] = b"foundry-watchdog/"
MAX_KEY_ID_LENGTH: Final[int] = 128
ED25519_SIGNATURE_LENGTH: Final[int] = 64


class KeyRole(StrEnum):
    REVIEWER = "reviewer"
    BUDGET_AUTHORITY = "budget-authority"
    FINANCIAL_VERIFIER = "financial-verifier"
    SUPERVISOR = "supervisor"
    GATEWAY = "gateway"
    OPERATOR = "operator"


@dataclass(frozen=True, slots=True)
class VerificationKey:
    key_id: str
    role: KeyRole
    public_key: Ed25519PublicKey


def _signing_bytes(kind: str, payload_bytes: bytes) -> bytes:
    if not kind or not kind.isascii() or "/" in kind:
        raise ProtocolError("invalid signed-object kind")
    return _SIGNATURE_DOMAIN + kind.encode("ascii") + b"/v1\0" + payload_bytes


def sign_object(
    kind: str,
    payload: dict[str, object],
    *,
    key_id: str,
    private_key: Ed25519PrivateKey,
) -> bytes:
    """Sign a canonical payload; caller must provision keys outside the runner."""
    if not key_id or not key_id.isascii() or len(key_id) > MAX_KEY_ID_LENGTH:
        raise ProtocolError("invalid signing key ID")
    payload_bytes = canonical_json(payload)
    signature = private_key.sign(_signing_bytes(kind, payload_bytes))
    return canonical_json(
        {
            "kind": kind,
            "key_id": key_id,
            "payload": payload,
            "signature": base64.b64encode(signature).decode("ascii"),
        }
    )


def verify_object(
    encoded: bytes,
    *,
    expected_kind: str,
    expected_role: KeyRole,
    keyring: dict[str, VerificationKey],
    expected_key_id: str | None = None,
) -> dict[str, object]:
    """Verify canonical bytes, key identity, signer role, and signature."""
    envelope = require_exact_keys(
        parse_canonical_json(encoded),
        {"kind", "key_id", "payload", "signature"},
        label="signed envelope",
    )
    kind = envelope["kind"]
    key_id = envelope["key_id"]
    payload = envelope["payload"]
    signature_text = envelope["signature"]
    if not isinstance(kind, str) or kind != expected_kind:
        raise AuthorizationError("signed object kind is not authorized")
    if not isinstance(key_id, str):
        raise ProtocolError("signed object key ID must be a string")
    if expected_key_id is not None and key_id != expected_key_id:
        raise AuthorizationError("signed object key ID is not the packet-bound signer")
    if not isinstance(payload, dict):
        raise ProtocolError("signed payload must be an object")
    if not isinstance(signature_text, str):
        raise ProtocolError("signature must be a string")
    key = keyring.get(key_id)
    if key is None or key.role is not expected_role:
        raise AuthorizationError("signing key is unknown or has the wrong role")
    try:
        signature = base64.b64decode(signature_text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ProtocolError("signature is not valid base64") from exc
    if len(signature) != ED25519_SIGNATURE_LENGTH:
        raise ProtocolError("signature has an invalid length")
    try:
        key.public_key.verify(
            signature,
            _signing_bytes(kind, canonical_json(payload)),
        )
    except InvalidSignature as exc:
        raise AuthorizationError("signature verification failed") from exc
    return payload
