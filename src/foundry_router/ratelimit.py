"""Rate-limit / quota tracking for Google AI Studio quota groups."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable

from zoneinfo import ZoneInfo


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


class InMemoryRateLimitStore:
    """Single-replica in-memory quota limiter keyed by quota group."""

    def __init__(
        self,
        *,
        quota_limits: dict[str, dict[str, int]] | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._quota_limits = quota_limits or {}
        self._now_fn = now_fn or (lambda: datetime.now(UTC))
        self._lock = asyncio.Lock()
        self._usage: dict[str, deque[tuple[datetime, int, int]]] = {}
        self._daily_requests: dict[str, tuple[str, int]] = {}
        self._daily_tokens: dict[str, tuple[str, int]] = {}

    @property
    def quota_limits(self) -> dict[str, dict[str, int]]:
        return dict(self._quota_limits)

    async def record_estimate(
        self,
        quota_group: str,
        *,
        request_count: int,
        estimated_input_tokens: int,
    ) -> None:
        if request_count < 0 or estimated_input_tokens < 0:
            raise ValueError("Rate-limit reservations must be non-negative")

        async with self._lock:
            now = self._now()
            usage = self._prune_usage(quota_group, now - timedelta(seconds=60))
            usage.append((now, request_count, estimated_input_tokens))
            self._usage[quota_group] = usage

            pacific_date = self._pacific_date(now)
            current_requests = self._daily_requests.get(quota_group)
            current_tokens = self._daily_tokens.get(quota_group)
            if current_requests is None or current_requests[0] != pacific_date:
                self._daily_requests[quota_group] = (pacific_date, request_count)
            else:
                self._daily_requests[quota_group] = (
                    pacific_date,
                    current_requests[1] + request_count,
                )

            if current_tokens is None or current_tokens[0] != pacific_date:
                self._daily_tokens[quota_group] = (pacific_date, estimated_input_tokens)
            else:
                self._daily_tokens[quota_group] = (
                    pacific_date,
                    current_tokens[1] + estimated_input_tokens,
                )

    async def snapshot_quota_groups(self, quota_groups: list[str]) -> dict[str, QuotaGroupSnapshot]:
        snapshots: dict[str, QuotaGroupSnapshot] = {}

        async with self._lock:
            now = self._now()
            for quota_group in quota_groups:
                limits = self._quota_limits.get(quota_group, {})
                rpm_limit = int(limits.get("rpm", 0))
                tpm_limit = int(limits.get("tpm", 0))
                rpd_limit = int(limits.get("rpd", 0))

                window_start = now - timedelta(seconds=60)
                recent = self._prune_usage(quota_group, window_start)
                rpm_used = sum(item[1] for item in recent)
                token_used = sum(item[2] for item in recent)

                pacific_date = self._pacific_date(now)
                daily_requests = self._daily_requests.get(quota_group)
                daily_tokens = self._daily_tokens.get(quota_group)
                if daily_requests is not None and daily_requests[0] != pacific_date:
                    daily_requests = (pacific_date, 0)
                if daily_tokens is not None and daily_tokens[0] != pacific_date:
                    daily_tokens = (pacific_date, 0)

                daily_rpd = daily_requests[1] if daily_requests is not None else 0
                daily_tpm = daily_tokens[1] if daily_tokens is not None else 0

                remaining_rpm = max(0, rpm_limit - rpm_used)
                remaining_input_tpm = max(0, tpm_limit - token_used)
                remaining_rpd = max(0, rpd_limit - daily_rpd)
                exhausted = (
                    (rpm_limit > 0 and rpm_used >= rpm_limit)
                    or (tpm_limit > 0 and token_used >= tpm_limit)
                    or (rpd_limit > 0 and daily_rpd >= rpd_limit)
                )

                snapshots[quota_group] = QuotaGroupSnapshot(
                    quota_group=quota_group,
                    rpm_used_60s=rpm_used,
                    input_tpm_used_60s=token_used,
                    rpd_used=daily_rpd,
                    remaining_rpm=remaining_rpm,
                    remaining_input_tpm=remaining_input_tpm,
                    remaining_rpd=remaining_rpd,
                    exhausted=exhausted,
                )

        return snapshots

    def _prune_usage(
        self, quota_group: str, window_start: datetime
    ) -> deque[tuple[datetime, int, int]]:
        usage = self._usage.get(quota_group)
        if usage is None:
            return deque()

        while usage and usage[0][0] < window_start:
            usage.popleft()

        if usage:
            return usage
        else:
            self._usage.pop(quota_group, None)
            return deque()

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
            self._daily_tokens.clear()


__all__ = [
    "InMemoryRateLimitStore",
    "QuotaGroupSnapshot",
]
