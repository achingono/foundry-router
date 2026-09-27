"""Unit tests for the in-memory quota/rate-limit state boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from foundry_router.ratelimit import InMemoryRateLimitStore


@pytest.mark.asyncio
async def test_naive_clock_datetime_is_rejected() -> None:
    store = InMemoryRateLimitStore(
        now_fn=lambda: datetime(2026, 9, 27, 12, 0),
    )

    with pytest.raises(ValueError, match="timezone-aware datetime"):
        await store.snapshot_quota_groups(["project-a"])


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
    store = InMemoryRateLimitStore(
        quota_limits={
            "project-a": {"rpm": 2, "tpm": 5000, "rpd": 10},
        },
        now_fn=lambda: now,
    )

    await store.record_estimate("project-a", request_count=1, estimated_input_tokens=2000)
    snapshot = await store.snapshot_quota_groups(["project-a"])

    assert snapshot["project-a"].rpm_used_60s == 1
    assert snapshot["project-a"].input_tpm_used_60s == 2000
    assert snapshot["project-a"].remaining_rpm == 1
    assert snapshot["project-a"].remaining_input_tpm == 3000
    assert snapshot["project-a"].remaining_rpd == 9
    assert snapshot["project-a"].exhausted is False

    now = now + timedelta(seconds=61)
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
