"""Logical model alias configuration and one-hop resolution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

MAX_ALIAS_JSON_BYTES = 256 * 1024
MAX_ALIAS_ENTRIES = 1024
MAX_ALIAS_NAME_BYTES = 256
_CONTROL_BELOW = 32
_CONTROL_EXTENDED_START = 127
_CONTROL_EXTENDED_END = 159


@dataclass(frozen=True)
class ModelAliasResolution:
    """Immutable identity context for a single request."""

    requested_model: str
    resolved_model: str
    is_alias: bool


def _has_control_characters(value: str) -> bool:
    for char in value:
        code = ord(char)
        if code < _CONTROL_BELOW or _CONTROL_EXTENDED_START <= code <= _CONTROL_EXTENDED_END:
            return True
    return False


def _validate_alias_token(value: str, *, label: str) -> None:
    if not isinstance(value, str):
        raise TypeError("FOUNDRY_MODEL_ALIASES_JSON must map strings to strings")
    if not value.strip():
        raise ValueError(f"FOUNDRY_MODEL_ALIASES_JSON {label} must be a non-empty string")
    if value != value.strip():
        raise ValueError(
            f"FOUNDRY_MODEL_ALIASES_JSON {label} '{value}' must not have surrounding whitespace"
        )
    if _has_control_characters(value):
        raise ValueError(
            f"FOUNDRY_MODEL_ALIASES_JSON {label} '{value}' must not contain control characters"
        )
    if len(value.encode("utf-8")) > MAX_ALIAS_NAME_BYTES:
        raise ValueError(
            f"FOUNDRY_MODEL_ALIASES_JSON {label} '{value}' exceeds "
            f"{MAX_ALIAS_NAME_BYTES} UTF-8 bytes"
        )


def _load_alias_object(raw: str) -> dict[str, Any]:
    """Parse raw JSON with duplicate-key rejection."""

    def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(
                    f"FOUNDRY_MODEL_ALIASES_JSON must not contain duplicate key '{key}'"
                )
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicates)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid FOUNDRY_MODEL_ALIASES_JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise TypeError("FOUNDRY_MODEL_ALIASES_JSON must be a JSON object")
    if len(value) > MAX_ALIAS_ENTRIES:
        raise ValueError(f"FOUNDRY_MODEL_ALIASES_JSON must not exceed {MAX_ALIAS_ENTRIES} entries")
    return value


def _validate_alias_entries(value: dict[str, Any], canonical: set[str]) -> dict[str, str]:
    """Validate entry shapes and one-hop canonical targets."""
    aliases: dict[str, str] = {}
    for alias, target in value.items():
        if not isinstance(alias, str) or not isinstance(target, str):
            raise TypeError("FOUNDRY_MODEL_ALIASES_JSON must map strings to strings")
        _validate_alias_token(alias, label="alias")
        _validate_alias_token(target, label="target")
        if alias in canonical:
            raise ValueError(f"Model alias '{alias}' collides with a canonical model ID")
        if alias == target:
            raise ValueError(f"Model alias '{alias}' must not reference itself")
        aliases[alias] = target
    for alias, target in aliases.items():
        if target in aliases:
            raise ValueError(
                f"Model alias '{alias}' must target a canonical model, not another alias '{target}'"
            )
        if target not in canonical:
            raise ValueError(f"Model alias '{alias}' targets unknown model '{target}'")
    return aliases


def parse_model_aliases(raw: str, canonical_models: Collection[str]) -> dict[str, str]:
    """Parse and validate an explicit one-hop alias map.

    ``canonical_models`` is the set of loaded ``FOUNDRY_MODELS_JSON`` keys.
    Validation rejects duplicate keys, non-string values, blank/whitespace/
    control-character names, oversized entries, collisions with canonical IDs,
    self references, alias-to-alias targets (chains/cycles) and missing targets.
    """
    if not isinstance(raw, str):
        raise TypeError("FOUNDRY_MODEL_ALIASES_JSON must be a JSON object")
    if len(raw.encode("utf-8")) > MAX_ALIAS_JSON_BYTES:
        raise ValueError("FOUNDRY_MODEL_ALIASES_JSON exceeds 256 KiB")
    value = _load_alias_object(raw)
    return _validate_alias_entries(value, set(canonical_models))


def resolve_model_alias(requested: str, aliases: Mapping[str, str]) -> ModelAliasResolution:
    """Resolve exactly once; unconfigured names are not aliases."""
    target = aliases.get(requested)
    if target is None:
        return ModelAliasResolution(
            requested_model=requested, resolved_model=requested, is_alias=False
        )
    return ModelAliasResolution(requested_model=requested, resolved_model=target, is_alias=True)


def canonical_request_copy(body: dict[str, Any], resolved_model: str) -> dict[str, Any]:
    """Return a shallow copy with only top-level ``model`` replaced."""
    if body.get("model") == resolved_model:
        return body
    out = dict(body)
    out["model"] = resolved_model
    return out


def catalog_model_names(canonical_names: Iterable[str], aliases: Mapping[str, str]) -> list[str]:
    """Preserve canonical ordering, then append aliases deterministically."""
    names = list(canonical_names)
    seen = set(names)
    for alias in sorted(aliases):
        if alias not in seen:
            names.append(alias)
            seen.add(alias)
    return names


__all__ = [
    "MAX_ALIAS_ENTRIES",
    "MAX_ALIAS_JSON_BYTES",
    "MAX_ALIAS_NAME_BYTES",
    "ModelAliasResolution",
    "canonical_request_copy",
    "catalog_model_names",
    "parse_model_aliases",
    "resolve_model_alias",
]
