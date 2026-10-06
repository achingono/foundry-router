"""Secret-only signed continuation key configuration; capability remains default-off."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Mapping  # noqa: TC003 -- Pydantic resolves at runtime
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

MAX_KEY_CONFIG_BYTES = 4096
MAX_SIGNED_BACKENDS = 256
MAX_SIGNED_REQUEST_BYTES = 2 * 1024 * 1024
_KEY_BYTES = 32


def decode_state_key(value: SecretStr) -> bytes:
    """Require exactly one canonical spelling of a random 32-byte key."""
    try:
        wire = value.get_secret_value().encode("ascii")
        decoded = base64.b64decode(wire, altchars=b"-_", validate=True)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid provider-state key configuration") from exc
    if len(decoded) != _KEY_BYTES or base64.urlsafe_b64encode(decoded) != wire:
        raise ValueError("Invalid provider-state key configuration")
    return decoded


class GoogleStateKeys(BaseModel):
    """Validated keys are never represented in diagnostics or serialized settings."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)

    scope_key: SecretStr = Field(exclude=True, repr=False)
    keys: Mapping[str, SecretStr] = Field(min_length=1, max_length=3, exclude=True, repr=False)
    active: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    generation: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    ttl_seconds: int = Field(default=900, ge=60, le=3600, strict=True)

    @model_validator(mode="after")
    def validate_keys(self) -> GoogleStateKeys:
        if self.active not in self.keys or any(
            not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name) for name in self.keys
        ):
            raise ValueError("Invalid provider-state key configuration")
        decoded = [
            decode_state_key(self.scope_key),
            *(decode_state_key(key) for key in self.keys.values()),
        ]
        if len(set(decoded)) != len(decoded):
            raise ValueError("Provider-state keys must be distinct")
        object.__setattr__(self, "keys", MappingProxyType(dict(self.keys)))
        return self


def parse_state_keys(raw: str) -> GoogleStateKeys:
    """Bounded duplicate-free secret configuration with safe errors."""

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Invalid provider-state key configuration")
            result[key] = value
        return result

    try:
        size = len(raw.encode("utf-8"))
    except UnicodeError:
        raise ValueError("Invalid provider-state key configuration") from None
    if size > MAX_KEY_CONFIG_BYTES:
        raise ValueError("Invalid provider-state key configuration")

    def invalid_constant(value: str) -> None:
        _ = value
        raise ValueError("Invalid provider-state key configuration")

    try:
        value = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)
        return GoogleStateKeys.model_validate(value)
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("Invalid provider-state key configuration") from None
