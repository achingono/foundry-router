"""Unit tests for the in-memory quota/rate-limit state boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from foundry_router.health import BackendHealthState, InMemoryHealthStore
from foundry_router.ratelimit import InMemoryRateLimitStore


@pytest.mark.asyncio
async def test_naive_clock_datetime_is_rejected() -> None:
    store = InMemoryRateLimitStore(
        now_fn=lambda: datetime(2026, 9, 27, 12, 0, tzinfo=UTC).replace(tzinfo=None),
    )

    with pytest.raises(ValueError, match="timezone-aware datetime"):
        await store.snapshot_quota_groups(["project-a"])


@pytest.mark.asyncio
async def test_reservations_share_budget_and_reconcile_actual_tokens() -> None:
    store = InMemoryRateLimitStore(
        quota_limits={"project-a": {"rpm": 2, "tpm": 100, "rpd": 2}},
        now_fn=lambda: datetime(2026, 9, 27, 12, 0, tzinfo=UTC),
    )

    assert await store.try_reserve_estimate("request-1", "project-a", estimated_input_tokens=70)
    assert not await store.try_reserve_estimate("request-2", "project-a", estimated_input_tokens=31)

    await store.finalize_request("request-1", actual_input_tokens=40)
    assert await store.try_reserve_estimate("request-2", "project-a", estimated_input_tokens=60)
    snapshot = await store.snapshot_quota_groups(["project-a"])

    assert snapshot["project-a"].rpm_used_60s == 2
    assert snapshot["project-a"].input_tpm_used_60s == 100
    assert snapshot["project-a"].rpd_used == 2


@pytest.mark.asyncio
async def test_reservation_transfer_releases_previous_group_on_failover() -> None:
    store = InMemoryRateLimitStore(
        quota_limits={
            "project-a": {"rpm": 1, "tpm": 100, "rpd": 1},
            "project-b": {"rpm": 1, "tpm": 100, "rpd": 1},
        },
        now_fn=lambda: datetime(2026, 9, 27, 12, 0, tzinfo=UTC),
    )

    assert await store.try_reserve_estimate("request-1", "project-a", estimated_input_tokens=20)
    assert await store.try_reserve_estimate("request-1", "project-b", estimated_input_tokens=30)
    snapshots = await store.snapshot_quota_groups(["project-a", "project-b"])

    assert snapshots["project-a"].rpm_used_60s == 0
    assert snapshots["project-a"].rpd_used == 0
    assert snapshots["project-b"].rpm_used_60s == 1
    assert snapshots["project-b"].rpd_used == 1


@pytest.mark.asyncio
async def test_exhausted_minute_budget_reports_earliest_reset() -> None:
    now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    monotonic_now = 10.0
    store = InMemoryRateLimitStore(
        quota_limits={"project-a": {"rpm": 1}},
        now_fn=lambda: now,
        monotonic_fn=lambda: monotonic_now,
    )

    assert await store.try_reserve_estimate("request-1", "project-a", estimated_input_tokens=0)
    now = datetime(2026, 9, 27, 12, 0, 30, tzinfo=UTC)
    monotonic_now = 40.0
    snapshot = await store.snapshot_quota_groups(["project-a"])

    assert snapshot["project-a"].exhausted is True
    assert snapshot["project-a"].retry_after_seconds == pytest.approx(30)


@pytest.mark.asyncio
async def test_expired_reservation_is_reaped_without_consuming_daily_quota() -> None:
    monotonic_now = 0.0
    store = InMemoryRateLimitStore(
        quota_limits={"project-a": {"rpm": 1, "rpd": 1}},
        now_fn=lambda: datetime(2026, 9, 27, 12, 0, tzinfo=UTC),
        monotonic_fn=lambda: monotonic_now,
        reservation_max_age_seconds=5.0,
    )

    assert await store.try_reserve_estimate("request-1", "project-a", estimated_input_tokens=1)
    monotonic_now = 6.0
    snapshot = await store.snapshot_quota_groups(["project-a"])

    assert snapshot["project-a"].rpm_used_60s == 0
    assert snapshot["project-a"].rpd_used == 0


@pytest.mark.asyncio
async def test_unconfigured_limits_do_not_exhaust_quota_group() -> None:
    store = InMemoryRateLimitStore(
        quota_limits={"project-a": {}},
        now_fn=lambda: datetime(2026, 9, 27, 12, 0, tzinfo=UTC),
    )

    await store.record_estimate("project-a", request_count=1, estimated_input_tokens=1)
    snapshot = await store.snapshot_quota_groups(["project-a"])

    assert snapshot["project-a"].exhausted is False
    assert snapshot["project-a"].remaining_rpm == 0
    assert snapshot["project-a"].remaining_input_tpm == 0
    assert snapshot["project-a"].remaining_rpd == 0


@pytest.mark.asyncio
async def test_trailing_60s_window_tracks_rpm_and_tpm_usage() -> None:
    now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    monotonic_now = 0.0
    store = InMemoryRateLimitStore(
        quota_limits={
            "project-a": {"rpm": 2, "tpm": 5000, "rpd": 10},
        },
        now_fn=lambda: now,
        monotonic_fn=lambda: monotonic_now,
    )

    await store.record_estimate("project-a", request_count=1, estimated_input_tokens=2000)
    snapshot = await store.snapshot_quota_groups(["project-a"])

    assert snapshot["project-a"].rpm_used_60s == 1
    assert snapshot["project-a"].input_tpm_used_60s == 2000
    assert snapshot["project-a"].remaining_rpm == 1
    assert snapshot["project-a"].remaining_input_tpm == 3000
    assert snapshot["project-a"].remaining_rpd == 9
    assert snapshot["project-a"].exhausted is False

    now = now + timedelta(hours=1)
    snapshot = await store.snapshot_quota_groups(["project-a"])
    assert snapshot["project-a"].rpm_used_60s == 1

    monotonic_now += 61.0
    snapshot = await store.snapshot_quota_groups(["project-a"])
    assert snapshot["project-a"].rpm_used_60s == 0
    assert snapshot["project-a"].input_tpm_used_60s == 0


@pytest.mark.asyncio
async def test_rpd_reset_uses_midnight_pacific_boundary() -> None:
    now = datetime(2026, 9, 27, 7, 30, tzinfo=UTC)
    store = InMemoryRateLimitStore(
        quota_limits={
            "project-a": {"rpm": 100, "tpm": 1000000, "rpd": 2},
        },
        now_fn=lambda: now,
    )

    await store.record_estimate("project-a", request_count=1, estimated_input_tokens=1)
    await store.record_estimate("project-a", request_count=1, estimated_input_tokens=1)

    now = datetime(2026, 9, 28, 7, 0, tzinfo=UTC)
    snapshot = await store.snapshot_quota_groups(["project-a"])
    assert snapshot["project-a"].remaining_rpd == 2

    now = datetime(2026, 9, 28, 8, 0, tzinfo=UTC)
    snapshot = await store.snapshot_quota_groups(["project-a"])
    assert snapshot["project-a"].rpd_used == 0


@pytest.mark.asyncio
async def test_rpd_reset_and_retry_delay_honor_dst_transition() -> None:
    now = datetime(2026, 11, 1, 6, 30, tzinfo=UTC)
    store = InMemoryRateLimitStore(
        quota_limits={"project-a": {"rpd": 1}},
        now_fn=lambda: now,
    )

    await store.record_estimate("project-a", request_count=1, estimated_input_tokens=0)
    snapshot = await store.snapshot_quota_groups(["project-a"])
    assert snapshot["project-a"].retry_after_seconds == pytest.approx(1800)

    now = datetime(2026, 11, 1, 7, 0, tzinfo=UTC)
    snapshot = await store.snapshot_quota_groups(["project-a"])
    assert snapshot["project-a"].rpd_used == 0
    assert snapshot["project-a"].exhausted is False


@pytest.mark.asyncio
async def test_pacific_rpd_reset_expires_quota_cooldown(monkeypatch) -> None:
    now = datetime(2026, 11, 1, 6, 30, tzinfo=UTC)
    monotonic_now = 100.0
    rate_store = InMemoryRateLimitStore(
        quota_limits={"project-a": {"rpd": 1}},
        now_fn=lambda: now,
        monotonic_fn=lambda: monotonic_now,
    )
    await rate_store.record_estimate("project-a", request_count=1, estimated_input_tokens=0)
    quota = await rate_store.snapshot_quota_groups(["project-a"])
    health_store = InMemoryHealthStore()
    monkeypatch.setattr("foundry_router.health.time.monotonic", lambda: monotonic_now)

    await health_store.set_backend_cooldown(
        "key-a",
        state=BackendHealthState.QUOTA_COOLDOWN,
        cooldown_seconds=quota["project-a"].retry_after_seconds or 0.0,
    )
    cooldown = await health_store.snapshot_backend_health(["key-a"])
    assert cooldown["key-a"].state == BackendHealthState.QUOTA_COOLDOWN

    now = datetime(2026, 11, 1, 7, 0, tzinfo=UTC)
    monotonic_now += quota["project-a"].retry_after_seconds or 0.0
    reset_quota = await rate_store.snapshot_quota_groups(["project-a"])
    reset_health = await health_store.snapshot_backend_health(["key-a"])

    assert reset_quota["project-a"].rpd_used == 0
    assert reset_health["key-a"].state == BackendHealthState.ACTIVE
