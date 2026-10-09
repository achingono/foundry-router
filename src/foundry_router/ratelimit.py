"""Rate-limit / quota tracking for Google AI Studio quota groups."""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from collections.abc import Callable


class QuotaStoreError(RuntimeError):
    """Shared quota ownership or usage could not be safely confirmed."""


def configured_quota_limits(settings: Any) -> dict[str, dict[str, int]]:
    """Use full shared limits for Table; retain local replica shares for memory."""
    limits = getattr(settings, "quota_group_rate_limits", {})
    if getattr(settings, "rate_limit_backend", "memory") == "table":
        return {group: dict(values) for group, values in limits.items()}
    return effective_quota_limits(limits, int(getattr(settings, "rate_limit_replica_share", 1)))


class AttemptQuotaStore:
    """Immutable forwarding view binding a logical request to one quota attempt."""

    def __init__(self, store: Any, attempt_id: str) -> None:
        self._store = store
        self._attempt_id = attempt_id

    async def finalize_request(
        self, request_id: str, *, actual_input_tokens: int | None = None
    ) -> None:
        _ = request_id
        await self._store.finalize_request(
            self._attempt_id, actual_input_tokens=actual_input_tokens
        )


@dataclass(frozen=True)
class QuotaGroupSnapshot:
    quota_group: str
    rpm_used_60s: int = 0
    input_tpm_used_60s: int = 0
    rpd_used: int = 0
    remaining_rpm: int = 0
    remaining_input_tpm: int = 0
    remaining_rpd: int = 0
    exhausted: bool = False
    retry_after_seconds: float | None = None
    configured_limits: tuple[str, ...] = ()


def effective_quota_limits(
    quota_limits: dict[str, dict[str, int]], replica_share: int
) -> dict[str, dict[str, int]]:
    """Derive the per-replica limits enforced by one replica (D6 option B).

    Each replica enforces ``floor(limit / share)`` on every dimension (RPM,
    input TPM, RPD) through a single contract used by startup sync, the routing
    comparison/re-sync and admin sync. Ordinary admissions across replicas can
    therefore never exceed the configured provider quota in aggregate; the only
    exemptions are the protected emergency fallback (explicit
    ``allow_over_limit``) and brief single-revision rollout overlap.
    """
    share = int(replica_share)
    if share <= 0:
        return {group: dict.fromkeys(limits, 0) for group, limits in quota_limits.items()}
    return {
        group: {dim: limit // share for dim, limit in limits.items()}
        for group, limits in quota_limits.items()
    }


def zero_share_dimensions(
    quota_limits: dict[str, dict[str, int]], replica_share: int
) -> list[tuple[str, str]]:
    """Return (group, dimension) pairs whose per-replica share floors to zero."""
    effective = effective_quota_limits(quota_limits, replica_share)
    return [
        (group, dim)
        for group, limits in effective.items()
        for dim, limit in limits.items()
        if limit <= 0
    ]


@dataclass
class _UsageRecord:
    request_id: str | None
    recorded_at_monotonic: float
    request_count: int
    input_tokens: int


@dataclass
class _QuotaReservation:
    quota_group: str
    usage: _UsageRecord
    pacific_date: str
    created_at_monotonic: float


@runtime_checkable
class RateLimitStore(Protocol):
    async def sync_from_settings(self, settings: Any) -> None: ...

    async def snapshot_quota_groups(
        self, quota_groups: list[str]
    ) -> dict[str, QuotaGroupSnapshot]: ...

    async def try_reserve_estimate(
        self,
        request_id: str,
        quota_group: str,
        *,
        estimated_input_tokens: int,
        reservation_max_age_seconds: float = 900.0,
        allow_over_limit: bool = False,
    ) -> bool: ...

    async def finalize_request(
        self, request_id: str, *, actual_input_tokens: int | None = None
    ) -> None: ...

    async def release_request(self, request_id: str) -> None: ...

    async def reset(self) -> None: ...


class InMemoryRateLimitStore:
    """Single-replica in-memory quota limiter keyed by quota group."""

    def __init__(
        self,
        *,
        quota_limits: dict[str, dict[str, int]] | None = None,
        now_fn: Callable[[], datetime] | None = None,
        monotonic_fn: Callable[[], float] | None = None,
        reservation_max_age_seconds: float = 900.0,
    ) -> None:
        self._quota_limits = quota_limits or {}
        self._now_fn = now_fn or (lambda: datetime.now(UTC))
        self._monotonic_fn = monotonic_fn or time.monotonic
        self._lock = asyncio.Lock()
        self._usage: dict[str, deque[_UsageRecord]] = {}
        self._daily_requests: dict[str, tuple[str, int]] = {}
        self._reservations: dict[str, _QuotaReservation] = {}
        self._reservation_max_age_seconds = reservation_max_age_seconds

    @property
    def quota_limits(self) -> dict[str, dict[str, int]]:
        return {group: dict(limits) for group, limits in self._quota_limits.items()}

    @property
    def reservation_max_age_seconds(self) -> float:
        return self._reservation_max_age_seconds

    async def sync_from_settings(self, settings: Any) -> None:
        raw_limits = {
            group: dict(group_limits)
            for group, group_limits in getattr(settings, "quota_group_rate_limits", {}).items()
        }
        share = int(getattr(settings, "rate_limit_replica_share", 1))
        async with self._lock:
            # D6 option B: each replica enforces its per-replica share locally.
            self._quota_limits = effective_quota_limits(raw_limits, share)
            self._reservation_max_age_seconds = float(
                getattr(settings, "reservation_max_age_seconds", 900.0)
            )

    async def record_estimate(
        self,
        quota_group: str,
        *,
        request_count: int,
        estimated_input_tokens: int,
    ) -> None:
        if (
            isinstance(request_count, bool)
            or not isinstance(request_count, int)
            or request_count < 0
            or isinstance(estimated_input_tokens, bool)
            or not isinstance(estimated_input_tokens, int)
            or estimated_input_tokens < 0
        ):
            raise ValueError("Rate-limit reservations must be non-negative")

        async with self._lock:
            now = self._now()
            monotonic_now = self._monotonic_fn()
            usage = self._prune_usage(quota_group, monotonic_now - 60.0)
            self._append_usage(
                quota_group,
                _UsageRecord(None, monotonic_now, request_count, estimated_input_tokens),
                usage,
            )

            pacific_date = self._pacific_date(now)
            current_requests = self._daily_requests.get(quota_group)
            if current_requests is None or current_requests[0] != pacific_date:
                self._daily_requests[quota_group] = (pacific_date, request_count)
            else:
                self._daily_requests[quota_group] = (
                    pacific_date,
                    current_requests[1] + request_count,
                )

    async def try_reserve_estimate(
        self,
        request_id: str,
        quota_group: str,
        *,
        estimated_input_tokens: int,
        reservation_max_age_seconds: float = 900.0,
        allow_over_limit: bool = False,
    ) -> bool:
        if not request_id:
            raise ValueError("Rate-limit reservation ID must not be empty")
        if (
            isinstance(estimated_input_tokens, bool)
            or not isinstance(estimated_input_tokens, int)
            or estimated_input_tokens < 0
        ):
            raise ValueError("Estimated input tokens must be non-negative")
        if reservation_max_age_seconds <= 0 or math.isnan(reservation_max_age_seconds):
            raise ValueError("Reservation max age must be positive")

        async with self._lock:
            now = self._now()
            monotonic_now = self._monotonic_fn()
            self._sweep_expired_reservations(reservation_max_age_seconds, monotonic_now)
            self._release_request_locked(request_id)

            limits = self._quota_limits.get(quota_group, {})
            if not limits:
                return True

            usage = self._prune_usage(quota_group, monotonic_now - 60.0)
            requests_used = sum(item.request_count for item in usage)
            tokens_used = sum(item.input_tokens for item in usage)
            daily = self._daily_requests.get(quota_group)
            pacific_date = self._pacific_date(now)
            daily_requests = daily[1] if daily is not None and daily[0] == pacific_date else 0

            rpm_limit = limits.get("rpm")
            tpm_limit = limits.get("tpm")
            rpd_limit = limits.get("rpd")
            if not allow_over_limit and (
                (rpm_limit is not None and requests_used + 1 > rpm_limit)
                or (tpm_limit is not None and tokens_used + estimated_input_tokens > tpm_limit)
                or (rpd_limit is not None and daily_requests + 1 > rpd_limit)
            ):
                return False

            record = _UsageRecord(request_id, monotonic_now, 1, estimated_input_tokens)
            self._append_usage(quota_group, record, usage)
            self._daily_requests[quota_group] = (pacific_date, daily_requests + 1)
            self._reservations[request_id] = _QuotaReservation(
                quota_group=quota_group,
                usage=record,
                pacific_date=pacific_date,
                created_at_monotonic=monotonic_now,
            )
            return True

    async def finalize_request(
        self, request_id: str, *, actual_input_tokens: int | None = None
    ) -> None:
        if actual_input_tokens is not None and actual_input_tokens < 0:
            raise ValueError("Actual input tokens must be non-negative")
        async with self._lock:
            reservation = self._reservations.pop(request_id, None)
            if reservation is not None and actual_input_tokens is not None:
                reservation.usage.input_tokens = actual_input_tokens

    async def release_request(self, request_id: str) -> None:
        async with self._lock:
            self._release_request_locked(request_id)

    async def snapshot_quota_groups(self, quota_groups: list[str]) -> dict[str, QuotaGroupSnapshot]:
        snapshots: dict[str, QuotaGroupSnapshot] = {}

        async with self._lock:
            now = self._now()
            monotonic_now = self._monotonic_fn()
            self._sweep_expired_reservations(self._reservation_max_age_seconds, monotonic_now)
            for quota_group in quota_groups:
                limits = self._quota_limits.get(quota_group, {})
                rpm_limit = int(limits.get("rpm", 0))
                tpm_limit = int(limits.get("tpm", 0))
                rpd_limit = int(limits.get("rpd", 0))

                window_start = monotonic_now - 60.0
                recent = self._prune_usage(quota_group, window_start)
                rpm_used = sum(item.request_count for item in recent)
                token_used = sum(item.input_tokens for item in recent)

                pacific_date = self._pacific_date(now)
                daily_requests = self._daily_requests.get(quota_group)
                if daily_requests is not None and daily_requests[0] != pacific_date:
                    daily_requests = (pacific_date, 0)

                daily_rpd = daily_requests[1] if daily_requests is not None else 0

                remaining_rpm = max(0, rpm_limit - rpm_used)
                remaining_input_tpm = max(0, tpm_limit - token_used)
                remaining_rpd = max(0, rpd_limit - daily_rpd)
                exhausted = (
                    (rpm_limit > 0 and rpm_used >= rpm_limit)
                    or (tpm_limit > 0 and token_used >= tpm_limit)
                    or (rpd_limit > 0 and daily_rpd >= rpd_limit)
                )
                reset_delays: list[float] = []
                if rpm_limit > 0 and rpm_used >= rpm_limit:
                    reset_delays.append(
                        self._seconds_until_under_limit(
                            recent, "request_count", rpm_limit, monotonic_now
                        )
                    )
                if tpm_limit > 0 and token_used >= tpm_limit:
                    reset_delays.append(
                        self._seconds_until_under_limit(
                            recent, "input_tokens", tpm_limit, monotonic_now
                        )
                    )
                if rpd_limit > 0 and daily_rpd >= rpd_limit:
                    reset_delays.append(self._seconds_until_pacific_midnight(now))

                snapshots[quota_group] = QuotaGroupSnapshot(
                    quota_group=quota_group,
                    rpm_used_60s=rpm_used,
                    input_tpm_used_60s=token_used,
                    rpd_used=daily_rpd,
                    remaining_rpm=remaining_rpm,
                    remaining_input_tpm=remaining_input_tpm,
                    remaining_rpd=remaining_rpd,
                    exhausted=exhausted,
                    retry_after_seconds=min(reset_delays) if reset_delays else None,
                    configured_limits=tuple(sorted(limits)),
                )

        return snapshots

    def _prune_usage(self, quota_group: str, window_start_monotonic: float) -> deque[_UsageRecord]:
        usage = self._usage.get(quota_group)
        if usage is None:
            return deque()

        while usage and usage[0].recorded_at_monotonic < window_start_monotonic:
            usage.popleft()

        if usage:
            return usage
        self._usage.pop(quota_group, None)
        return deque()

    def _append_usage(
        self,
        quota_group: str,
        record: _UsageRecord,
        usage: deque[_UsageRecord] | None = None,
    ) -> None:
        if usage is None:
            usage = self._usage.setdefault(quota_group, deque())
        usage.append(record)
        self._usage[quota_group] = usage

    @staticmethod
    def _seconds_until_under_limit(
        usage: deque[_UsageRecord], field: str, limit: int, now_monotonic: float
    ) -> float:
        """Compute when usage falls below the limit; the snapshot lock guards the deque."""
        current = sum(getattr(item, field) for item in usage)
        for item in usage:
            current -= getattr(item, field)
            if current < limit:
                return max(
                    0.0,
                    item.recorded_at_monotonic + 60.0 - now_monotonic,
                )
        return 60.0

    @staticmethod
    def _seconds_until_pacific_midnight(now: datetime) -> float:
        pacific = ZoneInfo("America/Los_Angeles")
        local_now = now.astimezone(pacific)
        next_midnight = datetime.combine(
            local_now.date() + timedelta(days=1), datetime.min.time(), tzinfo=pacific
        )
        return max(0.0, (next_midnight.astimezone(UTC) - now).total_seconds())

    def _release_request_locked(self, request_id: str) -> None:
        reservation = self._reservations.pop(request_id, None)
        if reservation is None:
            return

        usage = self._usage.get(reservation.quota_group)
        if usage is not None:
            with suppress(ValueError):
                usage.remove(reservation.usage)
            if not usage:
                self._usage.pop(reservation.quota_group, None)

        daily = self._daily_requests.get(reservation.quota_group)
        current_date = self._pacific_date(self._now())
        if daily is not None and daily[0] == current_date == reservation.pacific_date:
            remaining = daily[1] - reservation.usage.request_count
            if remaining > 0:
                self._daily_requests[reservation.quota_group] = (current_date, remaining)
            else:
                self._daily_requests.pop(reservation.quota_group, None)

    def _sweep_expired_reservations(
        self, reservation_max_age_seconds: float, now_monotonic: float
    ) -> None:
        if math.isinf(reservation_max_age_seconds):
            return
        expired_ids = [
            request_id
            for request_id, reservation in self._reservations.items()
            if now_monotonic - reservation.created_at_monotonic > reservation_max_age_seconds
        ]
        for request_id in expired_ids:
            self._release_request_locked(request_id)

    def _now(self) -> datetime:
        now = self._now_fn()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now_fn must return a timezone-aware datetime")
        return now

    @staticmethod
    def _pacific_date(value: datetime) -> str:
        return value.astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat()

    async def reset(self) -> None:
        async with self._lock:
            self._usage.clear()
            self._daily_requests.clear()
            self._reservations.clear()


__all__ = [
    "InMemoryRateLimitStore",
    "QuotaGroupSnapshot",
    "RateLimitStore",
    "effective_quota_limits",
    "zero_share_dimensions",
]
