"""Per-credit-group reserve policy configuration and parsing."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

MAX_GROUP_RESERVES_JSON_BYTES = 64 * 1024
MAX_GROUP_RESERVE_ENTRIES = 1024
MAX_RESERVE_PERCENT = 100

VARIABLE = "FOUNDRY_CREDIT_GROUP_RESERVES_JSON"
USD_FIELD = "min_credit_reserve_usd"
PERCENT_FIELD = "min_credit_reserve_percent"


@dataclass(frozen=True)
class GroupReservePolicy:
    """Immutable effective reserve pair for one canonical metered credit group."""

    min_credit_reserve_usd: float
    min_credit_reserve_percent: float


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"{VARIABLE} must not contain duplicate keys")
        result[key] = value
    return result


def _check_number(value: object, *, percent: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{VARIABLE} reserve values must be numbers")
    amount = float(value)
    if not math.isfinite(amount) or amount < 0:
        raise ValueError(f"{VARIABLE} reserve values must be finite and non-negative")
    if percent and amount > MAX_RESERVE_PERCENT:
        raise ValueError(f"{VARIABLE} reserve percent must not exceed {MAX_RESERVE_PERCENT}")
    return amount


def parse_group_reserves(
    raw: str,
    metered_groups: set[str],
    non_metered_groups: set[str],
) -> dict[str, GroupReservePolicy]:
    """Parse and validate the group-keyed reserve override map.

    Groups absent from the map inherit app-wide settings; only canonical
    metered credit-group IDs are accepted as keys. Errors never echo input.
    """
    if not isinstance(raw, str):
        raise TypeError(f"{VARIABLE} must be a JSON object")
    if len(raw.encode("utf-8")) > MAX_GROUP_RESERVES_JSON_BYTES:
        raise ValueError(f"{VARIABLE} exceeds {MAX_GROUP_RESERVES_JSON_BYTES} bytes")
    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicates)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid {VARIABLE}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise TypeError(f"{VARIABLE} must be a JSON object")
    if len(value) > MAX_GROUP_RESERVE_ENTRIES:
        raise ValueError(f"{VARIABLE} must not exceed {MAX_GROUP_RESERVE_ENTRIES} entries")
    policies: dict[str, GroupReservePolicy] = {}
    for group, entry in value.items():
        if group in non_metered_groups:
            raise ValueError(f"{VARIABLE} must not target a non-metered credit group")
        if group not in metered_groups:
            raise ValueError(f"{VARIABLE} targets an unknown credit group")
        if not isinstance(entry, dict):
            raise TypeError(f"{VARIABLE} entries must be JSON objects")
        if set(entry) != {USD_FIELD, PERCENT_FIELD}:
            raise ValueError(f"{VARIABLE} entries must contain exactly the reserve pair")
        policies[group] = GroupReservePolicy(
            min_credit_reserve_usd=_check_number(entry[USD_FIELD], percent=False),
            min_credit_reserve_percent=_check_number(entry[PERCENT_FIELD], percent=True),
        )
    return policies
