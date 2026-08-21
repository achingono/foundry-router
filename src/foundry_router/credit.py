"""Credit estimation, cycle math, and in-memory reservations."""

from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

DEFAULT_MAX_OUTPUT_TOKENS = 4096
CHARS_PER_TOKEN_DIVISOR = 3
MIN_SCORE_DENOMINATOR = 0.0001


class CreditState(StrEnum):
    """Credit suitability state for a backend candidate."""

    USABLE = "USABLE"
    CONSERVATION = "CONSERVATION"
    PROTECTED = "PROTECTED"
    INSUFFICIENT_CAPACITY = "INSUFFICIENT_CAPACITY"


@dataclass(frozen=True)
class CycleWindow:
    """UTC-aligned cycle boundaries for a backend."""

    current_cycle_start_utc: datetime
    next_reset_utc: datetime
    days_elapsed: int
    days_remaining: int


@dataclass(frozen=True)
class RequestEstimate:
    """Conservative local request estimate."""

    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


@dataclass(frozen=True)
class CreditAssessment:
    """Derived credit posture for candidate selection."""

    state: CreditState
    available_credit_usd: float
    projected_unused_credit_usd: float
    estimated_request_cost_usd: float
    cycle_allowance_usd: float


@dataclass
class _BackendCreditSnapshot:
    cycle_start_day: int
    cycle_allowance_usd: float
    estimated_remaining_usd: float
    cycle_start_utc: datetime
    reserved_inflight_usd: float = 0.0


@dataclass
class _Reservation:
    request_id: str
    backend_id: str
    estimated_cost_usd: float


def calculate_cycle_window(now_utc: datetime, cycle_start_day: int) -> CycleWindow:
    """Calculate cycle boundaries in UTC with month and leap-year handling."""
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=UTC)
    else:
        now_utc = now_utc.astimezone(UTC)

    if now_utc.day >= cycle_start_day:
        start_year = now_utc.year
        start_month = now_utc.month
    else:
        if now_utc.month == 1:
            start_year = now_utc.year - 1
            start_month = 12
        else:
            start_year = now_utc.year
            start_month = now_utc.month - 1

    start = datetime(start_year, start_month, cycle_start_day, tzinfo=UTC)

    if start_month == 12:
        next_start = datetime(start_year + 1, 1, cycle_start_day, tzinfo=UTC)
    else:
        next_start = datetime(start_year, start_month + 1, cycle_start_day, tzinfo=UTC)

    elapsed_seconds = max(0.0, (now_utc - start).total_seconds())
    days_elapsed = int(elapsed_seconds // 86400)
    days_remaining = max(1, math.ceil((next_start - now_utc).total_seconds() / 86400))
    return CycleWindow(
        current_cycle_start_utc=start,
        next_reset_utc=next_start,
        days_elapsed=days_elapsed,
        days_remaining=days_remaining,
    )


def estimate_request_cost(
    *,
    model: str,
    operation: str,
    body: dict[str, Any],
    pricing: dict[str, Any],
) -> RequestEstimate | None:
    """Estimate a request cost from configured pricing; missing pricing fails closed."""
    model_pricing = pricing.get(model)
    if model_pricing is None:
        return None

    input_price = float(getattr(model_pricing, "input_per_million", float("nan")))
    output_price = float(getattr(model_pricing, "output_per_million", float("nan")))
    if not _valid_non_negative_finite(input_price) or not _valid_non_negative_finite(output_price):
        return None

    input_tokens = 0
    output_tokens = 0
    if operation == "responses":
        input_tokens = _estimate_text_tokens(body.get("input"))
        max_output_tokens = body.get("max_output_tokens")
        if max_output_tokens is None:
            output_tokens = DEFAULT_MAX_OUTPUT_TOKENS
        elif isinstance(max_output_tokens, bool) or not isinstance(max_output_tokens, int):
            return None
        elif max_output_tokens < 0:
            return None
        else:
            output_tokens = max_output_tokens
    elif operation == "embeddings":
        input_tokens = _estimate_embeddings_tokens(body.get("input"))
    else:
        return None

    estimated_cost = ((input_tokens * input_price) + (output_tokens * output_price)) / 1_000_000
    if not _valid_non_negative_finite(estimated_cost):
        return None
    return RequestEstimate(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimated_cost,
    )


def estimate_response_usage_cost(
    response: Any, model: str, pricing: dict[str, Any]
) -> float | None:
    """Extract usage fields from non-streaming JSON responses when available."""
    model_pricing = pricing.get(model)
    if model_pricing is None:
        return None
    input_price = float(getattr(model_pricing, "input_per_million", float("nan")))
    output_price = float(getattr(model_pricing, "output_per_million", float("nan")))
    if not _valid_non_negative_finite(input_price) or not _valid_non_negative_finite(output_price):
        return None

    content_type = response.headers.get("content-type", "") if hasattr(response, "headers") else ""
    if "application/json" not in content_type.lower():
        return None
    payload: Any
    body = getattr(response, "body", None)
    if isinstance(body, bytes):
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
    else:
        return None
    if not isinstance(payload, dict):
        return None
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None

    input_tokens = _usage_int(usage, "input_tokens")
    output_tokens = _usage_int(usage, "output_tokens")
    if input_tokens is None:
        input_tokens = _usage_int(usage, "prompt_tokens")
    if output_tokens is None:
        output_tokens = _usage_int(usage, "completion_tokens")
    if input_tokens is None:
        total_tokens = _usage_int(usage, "total_tokens")
        if total_tokens is not None:
            input_tokens = total_tokens
    if input_tokens is None:
        return None
    if output_tokens is None:
        output_tokens = 0

    cost = ((input_tokens * input_price) + (output_tokens * output_price)) / 1_000_000
    return cost if _valid_non_negative_finite(cost) else None


def _usage_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _estimate_embeddings_tokens(value: Any) -> int:
    if isinstance(value, str):
        return _chars_to_tokens(value)
    if isinstance(value, list):
        total = 0
        for item in value:
            if not isinstance(item, str):
                return -1
            total += _chars_to_tokens(item)
        return total
    return -1


def _estimate_text_tokens(value: Any) -> int:
    if value is None:
        return 0
    total_chars = _walk_text_chars(value)
    return _chars_to_tokens_from_count(total_chars)


def _walk_text_chars(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return -1
    if isinstance(value, list):
        total = 0
        for item in value:
            chars = _walk_text_chars(item)
            if chars < 0:
                return -1
            total += chars
        return total
    if isinstance(value, dict):
        total = 0
        for item in value.values():
            chars = _walk_text_chars(item)
            if chars < 0:
                return -1
            total += chars
        return total
    return 0


def _chars_to_tokens(text: str) -> int:
    return _chars_to_tokens_from_count(len(text))


def _chars_to_tokens_from_count(count: int) -> int:
    if count < 0:
        return -1
    return math.ceil(count / CHARS_PER_TOKEN_DIVISOR)


def _valid_non_negative_finite(value: float) -> bool:
    return math.isfinite(value) and value >= 0.0


class InMemoryCreditStore:
    """Single-replica in-memory credit and reservation state."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._snapshots: dict[str, _BackendCreditSnapshot] = {}
        self._reservations: dict[str, _Reservation] = {}

    async def sync_from_settings(self, settings: Any) -> None:
        now = datetime.now(UTC)
        async with self._lock:
            for backend_id in settings.backends:
                allowance = settings.backend_cycle_allowance_usd.get(backend_id)
                remaining = settings.backend_initial_estimated_remaining_usd.get(backend_id)
                cycle_start_day = settings.backend_cycle_start_day.get(backend_id)
                if allowance is None or remaining is None or cycle_start_day is None:
                    continue
                if not _valid_non_negative_finite(allowance) or not _valid_non_negative_finite(
                    remaining
                ):
                    continue
                existing = self._snapshots.get(backend_id)
                if existing is None:
                    cycle = calculate_cycle_window(now, cycle_start_day)
                    self._snapshots[backend_id] = _BackendCreditSnapshot(
                        cycle_start_day=cycle_start_day,
                        cycle_allowance_usd=allowance,
                        estimated_remaining_usd=min(remaining, allowance),
                        cycle_start_utc=cycle.current_cycle_start_utc,
                    )
                else:
                    existing.cycle_start_day = cycle_start_day
                    existing.cycle_allowance_usd = allowance

    async def assess(
        self,
        backend_id: str,
        estimated_request_cost_usd: float,
        *,
        min_credit_reserve_usd: float,
        min_credit_reserve_percent: float,
        now_utc: datetime | None = None,
    ) -> CreditAssessment:
        now = now_utc or datetime.now(UTC)
        async with self._lock:
            snapshot = self._snapshots.get(backend_id)
            if snapshot is None:
                return CreditAssessment(
                    state=CreditState.INSUFFICIENT_CAPACITY,
                    available_credit_usd=0.0,
                    projected_unused_credit_usd=0.0,
                    estimated_request_cost_usd=estimated_request_cost_usd,
                    cycle_allowance_usd=0.0,
                )
            self._rollover_if_needed(snapshot, now)
            return self._assessment(
                snapshot,
                estimated_request_cost_usd,
                min_credit_reserve_usd,
                min_credit_reserve_percent,
                now,
            )

    async def try_assign_reservation(
        self,
        request_id: str,
        backend_id: str,
        estimated_request_cost_usd: float,
        *,
        min_credit_reserve_usd: float,
        min_credit_reserve_percent: float,
        now_utc: datetime | None = None,
    ) -> bool:
        now = now_utc or datetime.now(UTC)
        async with self._lock:
            snapshot = self._snapshots.get(backend_id)
            if snapshot is None:
                return False
            self._rollover_if_needed(snapshot, now)

            existing = self._reservations.get(request_id)
            if existing is not None and existing.backend_id == backend_id:
                return True

            assessment = self._assessment(
                snapshot,
                estimated_request_cost_usd,
                min_credit_reserve_usd,
                min_credit_reserve_percent,
                now,
            )
            if assessment.state not in {CreditState.USABLE, CreditState.CONSERVATION}:
                return False

            if existing is not None:
                self._release_locked(existing, charge_reserved=False, charged_cost_usd=None)

            snapshot.reserved_inflight_usd += estimated_request_cost_usd
            self._reservations[request_id] = _Reservation(
                request_id=request_id,
                backend_id=backend_id,
                estimated_cost_usd=estimated_request_cost_usd,
            )
            return True

    async def finalize_request(
        self,
        request_id: str,
        *,
        charge_reserved: bool,
        charged_cost_usd: float | None,
    ) -> None:
        async with self._lock:
            reservation = self._reservations.get(request_id)
            if reservation is None:
                return
            self._release_locked(
                reservation,
                charge_reserved=charge_reserved,
                charged_cost_usd=charged_cost_usd,
            )

    async def reset(self) -> None:
        async with self._lock:
            self._snapshots.clear()
            self._reservations.clear()

    def _release_locked(
        self,
        reservation: _Reservation,
        *,
        charge_reserved: bool,
        charged_cost_usd: float | None,
    ) -> None:
        snapshot = self._snapshots.get(reservation.backend_id)
        if snapshot is not None:
            snapshot.reserved_inflight_usd = max(
                0.0,
                snapshot.reserved_inflight_usd - reservation.estimated_cost_usd,
            )
            charge = 0.0
            if charged_cost_usd is not None and _valid_non_negative_finite(charged_cost_usd):
                charge = charged_cost_usd
            elif charge_reserved:
                charge = reservation.estimated_cost_usd
            snapshot.estimated_remaining_usd = max(0.0, snapshot.estimated_remaining_usd - charge)
        self._reservations.pop(reservation.request_id, None)

    def _rollover_if_needed(self, snapshot: _BackendCreditSnapshot, now_utc: datetime) -> None:
        cycle = calculate_cycle_window(now_utc, snapshot.cycle_start_day)
        if cycle.current_cycle_start_utc > snapshot.cycle_start_utc:
            snapshot.cycle_start_utc = cycle.current_cycle_start_utc
            snapshot.estimated_remaining_usd = snapshot.cycle_allowance_usd

    def _assessment(
        self,
        snapshot: _BackendCreditSnapshot,
        estimated_request_cost_usd: float,
        min_credit_reserve_usd: float,
        min_credit_reserve_percent: float,
        now_utc: datetime,
    ) -> CreditAssessment:
        cycle = calculate_cycle_window(now_utc, snapshot.cycle_start_day)
        safety_reserve = max(
            min_credit_reserve_usd,
            snapshot.cycle_allowance_usd * (min_credit_reserve_percent / 100.0),
        )
        available_credit = max(
            0.0,
            snapshot.estimated_remaining_usd - snapshot.reserved_inflight_usd - safety_reserve,
        )
        estimated_daily_burn = max(
            0.0,
            (snapshot.cycle_allowance_usd - snapshot.estimated_remaining_usd)
            / max(1, cycle.days_elapsed),
        )
        projected_unused = max(
            0.0,
            snapshot.estimated_remaining_usd - (estimated_daily_burn * cycle.days_remaining),
        )

        if available_credit <= 0:
            state = CreditState.PROTECTED
        elif estimated_request_cost_usd > available_credit:
            state = CreditState.INSUFFICIENT_CAPACITY
        elif cycle.days_remaining <= 3 and projected_unused > (snapshot.cycle_allowance_usd * 0.05):
            state = CreditState.CONSERVATION
        else:
            state = CreditState.USABLE

        return CreditAssessment(
            state=state,
            available_credit_usd=available_credit,
            projected_unused_credit_usd=projected_unused,
            estimated_request_cost_usd=estimated_request_cost_usd,
            cycle_allowance_usd=snapshot.cycle_allowance_usd,
        )


def score_credit_assessment(
    *,
    state: CreditState,
    is_health_active: bool,
    is_error_cooldown: bool,
    available_credit_usd: float,
    estimated_request_cost_usd: float,
    projected_unused_credit_usd: float,
    cycle_allowance_usd: float,
) -> float:
    """Compute ADR-006 composite score for candidate ranking."""
    availability = (
        1.0 if state == CreditState.USABLE else (0.5 if state == CreditState.CONSERVATION else 0.0)
    )
    quota_health = 1.0 if is_health_active else 0.0
    credit_health = min(
        1.0, available_credit_usd / max(estimated_request_cost_usd, MIN_SCORE_DENOMINATOR)
    )
    cycle_urgency = max(
        0.0,
        min(1.0, projected_unused_credit_usd / max(cycle_allowance_usd, MIN_SCORE_DENOMINATOR)),
    )
    error_health = 0.0 if is_error_cooldown else 1.0
    return (
        (0.3 * availability)
        + (0.2 * quota_health)
        + (0.2 * credit_health)
        + (0.2 * cycle_urgency)
        + (0.1 * error_health)
    )
