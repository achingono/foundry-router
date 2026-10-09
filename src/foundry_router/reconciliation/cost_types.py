"""Cycle-bound billing ceilings, separate from replacement balance snapshots."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from foundry_router.config.cost_management import billing_currency

if TYPE_CHECKING:
    from foundry_router.reconciliation.exchange_rate import DailyExchangeRate

MAX_CYCLE_START_DAY = 28


class CostEvidenceError(RuntimeError):
    """Cost evidence was unavailable, malformed or incomplete."""


def cost_policy_fingerprint(settings: Any, group: str) -> str | None:
    """Bind exact active billing membership and numeric cycle policy."""
    config = getattr(settings, "cost_management_groups", {}).get(group)
    if (
        config is None
        or getattr(settings, "reconciliation_provider", "static") != "azure_cost_management"
    ):
        return None
    payload = [
        group,
        config.scope.casefold(),
        sorted(value.casefold() for value in config.resource_ids),
        settings.backend_cycle_start_day.get(group),
        settings.backend_cycle_allowance_usd.get(group),
        billing_currency(settings, config),
    ]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def downward_float(value: Decimal) -> float:
    """Use the greatest representable float no larger than a decimal ceiling."""
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise CostEvidenceError("invalid_cost_ceiling")
    if Decimal(result) > value:
        result = math.nextafter(result, -math.inf)
    return result


@dataclass(frozen=True)
class CostCeiling:
    """An immutable ceiling bound to the policy that produced its evidence."""

    credit_group: str
    remaining_usd: float
    cycle_start_utc: datetime
    cycle_start_day: int
    allowance_usd: float
    policy_fingerprint: str

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.remaining_usd)
            or self.remaining_usd < 0
            or not math.isfinite(self.allowance_usd)
            or self.allowance_usd < 0
            or self.remaining_usd > self.allowance_usd
            or self.cycle_start_utc.tzinfo != UTC
            or not 1 <= self.cycle_start_day <= MAX_CYCLE_START_DAY
        ):
            raise CostEvidenceError("invalid_cost_ceiling")

    def matches(self, settings: Any, balance: Any) -> bool:
        return (
            self.policy_fingerprint == cost_policy_fingerprint(settings, self.credit_group)
            and self.cycle_start_utc == balance.cycle_start_utc
            and self.cycle_start_day == balance.cycle_start_day
            and self.allowance_usd == balance.cycle_allowance_usd
        )


@dataclass(frozen=True)
class CostCeilingBatch:
    """Complete fetch; apply groups independently without replacing balances."""

    ceilings: tuple[CostCeiling, ...]
    fetched_at_utc: datetime
    exchange_rate: DailyExchangeRate | None = None

    def __post_init__(self) -> None:
        if len({ceiling.credit_group for ceiling in self.ceilings}) != len(self.ceilings):
            raise CostEvidenceError("duplicate_cost_groups")
