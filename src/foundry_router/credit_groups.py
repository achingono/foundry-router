"""Credit account namespace shared by settings and store adapters."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

MAX_PARTITION_KEY_BYTES = 1024
CONTROL_START = 32
EXTENDED_CONTROL_START = 127
EXTENDED_CONTROL_END = 159


class CreditStoreError(RuntimeError):
    """Credit ownership or persistence could not be confirmed."""


def validate_credit_group(value: str) -> str:
    """Validate an account ID usable as an Azure Table partition key."""
    if (
        not value
        or value != value.strip()
        or len(value.encode("utf-16-le")) > MAX_PARTITION_KEY_BYTES
        or any(
            char in "/\\#?"
            or ord(char) < CONTROL_START
            or EXTENDED_CONTROL_START <= ord(char) <= EXTENDED_CONTROL_END
            for char in value
        )
    ):
        raise ValueError("Credit group must be a safe nonblank Table partition key")
    return value


def credit_membership(settings: Any) -> dict[str, str]:
    """Support validated configs and existing mapping/object configuration stubs."""
    aliases: dict[str, str] = {}
    metering: dict[str, bool] = {}
    for backend_id, config in settings.backends.items():
        if isinstance(config, Mapping):
            group = config.get("credit_group")
            metered = config.get("credit_metered", True)
        else:
            group = getattr(config, "credit_group", None)
            metered = getattr(config, "credit_metered", True)
        group = validate_credit_group(backend_id if group is None else group)
        aliases[backend_id] = group
        if group in metering and metering[group] != metered:
            raise ValueError("Credit group cannot mix metered and non-metered backends")
        metering[group] = metered
    for group in aliases.values():
        if group in aliases and aliases[group] != group:
            raise ValueError("Credit group overlaps a backend alias mapped elsewhere")
    return aliases


def metered_credit_groups(settings: Any) -> set[str]:
    aliases = credit_membership(settings)
    return {
        aliases[backend_id]
        for backend_id, config in settings.backends.items()
        if (
            config.get("credit_metered", True)
            if isinstance(config, Mapping)
            else getattr(config, "credit_metered", True)
        )
    }


def resolve_credit_group(aliases: dict[str, str], identifier: str) -> str:
    """Resolve aliases exactly once; canonical IDs are never chained."""
    return aliases.get(identifier, identifier)


def normalize_reconciliation(
    aliases: dict[str, str], amounts: dict[str, float]
) -> dict[str, float]:
    """Prevalidate the whole update before writes; coalesce equal aliases."""
    normalized: dict[str, float] = {}
    for identifier, amount in amounts.items():
        group = resolve_credit_group(aliases, identifier)
        if isinstance(amount, bool):
            continue
        try:
            value = float(amount)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value) or value < 0:
            continue
        if group in normalized and normalized[group] != value:
            raise ValueError("Conflicting reconciliation amounts for one credit group")
        normalized[group] = value
    return normalized
