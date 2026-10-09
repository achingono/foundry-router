"""Durable quota admission across independent clients and failure boundaries."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from foundry_router.ratelimit import QuotaStoreError
from foundry_router.state.quota import AzureTableRateLimitStore
from tests.unit.test_state import FakeTableClient


class AtomicClient(FakeTableClient):
    def __init__(self):
        super().__init__()
        self.version = 0
        self.fail_after_commit = False

    async def try_batch_transaction(self, operations):
        result = await super().try_batch_transaction(operations)
        if result:
            self.version += 1
            for op in operations:
                self.entities[(op.partition_key, op.row_key)]["odata.etag"] = f"q{self.version}"
            if self.fail_after_commit:
                self.fail_after_commit = False
                raise TimeoutError("acknowledgement lost")
        return result


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 8, 18, tzinfo=UTC)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def settings(rpm=4, tpm=100, rpd=10, age=900):
    return SimpleNamespace(
        quota_group_rate_limits={"project": {"rpm": rpm, "tpm": tpm, "rpd": rpd}},
        reservation_max_age_seconds=age,
        backends={"a": SimpleNamespace(quota_group="project")},
    )


async def setup(count=2, config=None):
    client, clock = AtomicClient(), Clock()
    stores = [AzureTableRateLimitStore(client, now_fn=clock) for _ in range(count)]
    for store in stores:
        await store.sync_from_settings(config or settings())
    return client, clock, stores


async def test_independent_admission_atomic_caps_and_restart():
    client, clock, stores = await setup()
    results = await asyncio.gather(
        *(
            stores[i % 2].try_reserve_estimate(f"attempt-{i}", "project", estimated_input_tokens=20)
            for i in range(8)
        )
    )
    assert sum(results) == 4
    restarted = AzureTableRateLimitStore(client, now_fn=clock)
    await restarted.sync_from_settings(settings())
    snap = (await restarted.snapshot_quota_groups(["project"]))["project"]
    assert (snap.rpm_used_60s, snap.input_tpm_used_60s, snap.rpd_used) == (4, 80, 4)
    await restarted.reset()
    assert not await restarted.try_reserve_estimate("new", "project", estimated_input_tokens=1)


async def test_cross_writer_finalize_release_and_no_double_refund():
    _, _, (a, b) = await setup()
    assert await a.try_reserve_estimate("one", "project", estimated_input_tokens=50)
    assert await a.try_reserve_estimate("two", "project", estimated_input_tokens=40)
    await b.finalize_request("one", actual_input_tokens=10)
    await a.release_request("one")  # finalized usage is never free-released
    await b.release_request("two")
    await b.release_request("two")
    snap = (await a.snapshot_quota_groups(["project"]))["project"]
    assert (snap.rpm_used_60s, snap.input_tpm_used_60s, snap.rpd_used) == (1, 10, 1)


@pytest.mark.parametrize("operation", ["admit", "finalize", "release"])
async def test_commit_then_timeout_recovery(operation):
    client, _, (a, b) = await setup()
    if operation != "admit":
        assert await a.try_reserve_estimate("one", "project", estimated_input_tokens=50)
    client.fail_after_commit = True
    with pytest.raises(QuotaStoreError):
        if operation == "admit":
            await a.try_reserve_estimate("one", "project", estimated_input_tokens=50)
        elif operation == "finalize":
            await a.finalize_request("one", actual_input_tokens=10)
        else:
            await a.release_request("one")
    if operation == "admit":
        with pytest.raises(QuotaStoreError):
            await a.try_reserve_estimate("one", "project", estimated_input_tokens=50)
        await b.finalize_request("one")
    elif operation == "finalize":
        await b.finalize_request("one", actual_input_tokens=10)
    else:
        await b.release_request("one")
    snap = (await b.snapshot_quota_groups(["project"]))["project"]
    expected = (
        (0, 0, 0) if operation == "release" else (1, 10 if operation == "finalize" else 50, 1)
    )
    assert (snap.rpm_used_60s, snap.input_tpm_used_60s, snap.rpd_used) == expected


async def test_expiry_retains_daily_and_estimate_without_refund():
    _, clock, (a, b) = await setup(config=settings(age=90))
    assert await a.try_reserve_estimate(
        "one", "project", estimated_input_tokens=50, reservation_max_age_seconds=90
    )
    clock.advance(91)
    await b.release_request("one")
    snap = (await b.snapshot_quota_groups(["project"]))["project"]
    assert (snap.rpm_used_60s, snap.input_tpm_used_60s, snap.rpd_used) == (0, 0, 1)


async def test_midnight_uncertainty_and_safe_daily_rollover():
    _, clock, (a, b) = await setup(config=settings(rpd=1))
    clock.now = datetime(2026, 10, 9, 6, 59, 50, tzinfo=UTC)
    assert await a.try_reserve_estimate("old", "project", estimated_input_tokens=1)
    clock.advance(7)
    assert not await b.try_reserve_estimate("ambiguous", "project", estimated_input_tokens=1)
    clock.advance(7)
    assert not await b.try_reserve_estimate("ambiguous-after", "project", estimated_input_tokens=1)
    clock.advance(2)
    assert await b.try_reserve_estimate("new", "project", estimated_input_tokens=1)
    assert not await a.try_reserve_estimate("extra", "project", estimated_input_tokens=1)
    await a.release_request("old")
    snap = (await b.snapshot_quota_groups(["project"]))["project"]
    assert snap.rpd_used == 1


async def test_policy_change_requires_old_policy_expiry_and_full_day():
    client, clock, (a, b) = await setup()
    assert await a.try_reserve_estimate("one", "project", estimated_input_tokens=5)
    changed = AzureTableRateLimitStore(client, now_fn=clock)
    with pytest.raises(QuotaStoreError):
        await changed.sync_from_settings(settings(age=10))
    clock.advance(20)
    with pytest.raises(QuotaStoreError):
        await changed.sync_from_settings(settings(age=10))
    assert (await b.snapshot_quota_groups(["project"]))["project"].rpd_used == 1
    clock.advance(86400)
    await changed.sync_from_settings(settings(age=10))
    assert (await changed.snapshot_quota_groups(["project"]))["project"].rpd_used == 0


async def test_clock_regression_and_missing_etag_fail_closed():
    client, clock, (a, _) = await setup()
    clock.advance(-1)
    with pytest.raises(QuotaStoreError):
        await a.try_reserve_estimate("one", "project", estimated_input_tokens=1)
    clock.advance(2)
    for entity in client.entities.values():
        entity.pop("odata.etag")
    with pytest.raises(QuotaStoreError):
        await a.snapshot_quota_groups(["project"])


async def test_record_and_utf16_capacity_keep_existing_state():
    client, clock, (store,) = await setup(count=1, config=settings(rpm=1000, tpm=10000, rpd=1000))
    accepted = 0
    for i in range(256):
        try:
            result = await store.try_reserve_estimate(
                f"attempt-{i}-" + "界" * 35, "project", estimated_input_tokens=1
            )
        except QuotaStoreError:
            break
        if not result:
            break
        accepted += 1
    assert 0 < accepted < 256  # Actual UTF-16 bound, not merely record count.
    raw = next(iter(client.entities.values()))["state"]
    assert len(raw.encode("utf-16-le")) <= 48 * 1024
    restarted = AzureTableRateLimitStore(client, now_fn=clock)
    await restarted.sync_from_settings(settings(rpm=1000, tpm=10000, rpd=1000))
    assert (await restarted.snapshot_quota_groups(["project"]))["project"].rpd_used == accepted


async def test_conflict_exhaustion_and_outage_are_not_capacity_rejection():
    client, _, (a, b) = await setup()
    client.batch_etag_conflicts.update(client.entities)
    with pytest.raises(QuotaStoreError):
        await a.try_reserve_estimate("uncertain", "project", estimated_input_tokens=10)
    assert a._owners == {"uncertain": "project"}
    client.batch_etag_conflicts.clear()
    await b.release_request("uncertain")
    assert (await b.snapshot_quota_groups(["project"]))["project"].rpd_used == 0
    client.fail_batch = True
    with pytest.raises(QuotaStoreError):
        await a.snapshot_quota_groups(["project"])


async def test_initialization_commit_then_timeout_never_resets_existing_usage():
    client, clock, (a,) = await setup(count=1)
    assert await a.try_reserve_estimate("one", "project", estimated_input_tokens=10)
    b = AzureTableRateLimitStore(client, now_fn=clock)
    client.fail_after_commit = True
    with pytest.raises(QuotaStoreError):
        await b.sync_from_settings(settings())
    await b.sync_from_settings(settings())
    assert (await b.snapshot_quota_groups(["project"]))["project"].rpd_used == 1


@pytest.mark.parametrize(
    "at", [datetime(2026, 3, 8, 10, tzinfo=UTC), datetime(2026, 11, 1, 9, tzinfo=UTC)]
)
async def test_dst_transition_keeps_same_pacific_day_count(at):
    client, clock = AtomicClient(), Clock()
    clock.now = at - timedelta(seconds=10)
    a, b = [AzureTableRateLimitStore(client, now_fn=clock) for _ in range(2)]
    await a.sync_from_settings(settings(rpd=1))
    await b.sync_from_settings(settings(rpd=1))
    assert await a.try_reserve_estimate("one", "project", estimated_input_tokens=1)
    clock.advance(20)
    assert not await b.try_reserve_estimate("two", "project", estimated_input_tokens=1)
    assert (await b.snapshot_quota_groups(["project"]))["project"].rpd_used == 1


async def test_cross_writer_and_expiry_retire_over_4096_local_owners():
    _, clock, (a, b) = await setup(config=settings(rpm=10000, tpm=10000, rpd=10000, age=90))
    for i in range(4100):
        assert await a.try_reserve_estimate(
            f"attempt-{i}", "project", estimated_input_tokens=1, reservation_max_age_seconds=90
        )
        if i % 2:
            await b.release_request(f"attempt-{i}")
        else:
            clock.advance(91)
    assert len(a._owners) <= 1


@pytest.mark.parametrize("cancel", [False, True])
async def test_possible_azure_dispatch_failure_retains_quota_and_credit(cancel):
    from functools import partial
    from unittest.mock import AsyncMock, MagicMock

    from foundry_router.api.common import api_error, finalize_non_streaming_credit
    from foundry_router.config import Settings
    from foundry_router.credit import InMemoryCreditStore
    from foundry_router.health import InMemoryHealthStore
    from foundry_router.routing import execute_with_single_failover
    from tests.integration.test_compatible_provider_integration import settings as provider_settings

    config = provider_settings(metered=True)
    backends = json.loads(config.backends_json)
    backends["a"]["provider"] = "azure_foundry"
    backends["a"]["deployment"] = "azure-model"
    config = Settings(
        **{
            **config.model_dump(),
            "backends_json": json.dumps(backends),
            "rate_limit_backend": "table",
            "table_endpoint": "https://synthetic.table.test",
        }
    )
    rate = AzureTableRateLimitStore(AtomicClient())
    await rate.sync_from_settings(config)
    credit = InMemoryCreditStore()
    entered = asyncio.Event()
    calls = []

    async def dispatch(backend, **_kwargs):
        calls.append(backend)
        entered.set()
        if cancel:
            await asyncio.Event().wait()
        raise RuntimeError("after possible dispatch")

    task = asyncio.create_task(
        execute_with_single_failover(
            config,
            "logical",
            operation="responses",
            body={"model": "logical", "input": "hi", "max_output_tokens": 8},
            request_id="logical-request",
            execute_backend=dispatch,
            health_store=InMemoryHealthStore(),
            credit_store=credit,
            rate_limit_store=rate,
            metrics_store=SimpleNamespace(observe_request=AsyncMock()),
            logger=MagicMock(),
            api_error=api_error,
            finalize_non_streaming_credit=partial(
                finalize_non_streaming_credit, credit_store=credit, rate_limit_store=rate
            ),
        )
    )
    await entered.wait()
    if cancel:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
        await task
    assert calls == ["a"]
    snapshot = (await rate.snapshot_quota_groups(["a"]))["a"]
    assert (snapshot.rpm_used_60s, snapshot.input_tpm_used_60s, snapshot.rpd_used) == (1, 1, 1)
    live = (
        await credit.live_snapshot(["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0)
    )["a"]
    assert live.estimated_remaining_usd == pytest.approx(991)
    assert live.active_reservations == 0


@pytest.mark.parametrize("deadline_expires", [False, True])
async def test_post_admission_exclusion_cancellation_releases_attempt(deadline_expires):
    import time
    from unittest.mock import MagicMock

    from foundry_router.config import Settings
    from foundry_router.credit import InMemoryCreditStore
    from foundry_router.health import InMemoryHealthStore
    from foundry_router.routing import select_candidate_backend
    from tests.integration.test_compatible_provider_integration import settings as provider_settings

    config = provider_settings(metered=True)
    config = Settings(
        **{
            **config.model_dump(),
            "rate_limit_backend": "table",
            "table_endpoint": "https://synthetic.table.test",
        }
    )
    rate, credit = AzureTableRateLimitStore(AtomicClient()), InMemoryCreditStore()
    await rate.sync_from_settings(config)
    entered = asyncio.Event()

    from foundry_router.routing.exclusion import CombinationExclusionStore

    class Exclusion(CombinationExclusionStore):
        async def snapshot_combinations(self, *_args, **_kwargs):
            return {}

        async def admit(self, *_args, **_kwargs):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(
        select_candidate_backend(
            config,
            "logical",
            operation="responses",
            body={"input": "hi", "max_output_tokens": 8},
            request_id="logical-request",
            health_store=InMemoryHealthStore(),
            credit_store=credit,
            rate_limit_store=rate,
            logger=MagicMock(),
            exclusion_store=Exclusion(),
            intake_deadline_monotonic=time.monotonic() + 0.05 if deadline_expires else None,
        )
    )
    await asyncio.wait_for(entered.wait(), 1)
    if deadline_expires:
        result = await asyncio.wait_for(task, 1)
        assert result.feature_rejection.status_code == 408
    else:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    snap = (await rate.snapshot_quota_groups(["a"]))["a"]
    assert (snap.rpm_used_60s, snap.input_tpm_used_60s, snap.rpd_used) == (0, 0, 0)
    assert rate._owners == {}
    assert (
        await credit.live_snapshot(["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0)
    )["a"].estimated_remaining_usd == 1000


def test_table_quota_config_and_identity_store_factory(monkeypatch):
    from foundry_router.config import Settings
    from foundry_router.main import build_stores
    from tests.integration.test_compatible_provider_integration import settings as provider_settings

    base = provider_settings().model_dump()
    valid = {
        **base,
        "rate_limit_backend": "table",
        "table_endpoint": "https://synthetic.table.test",
    }
    for overrides in (
        {"table_endpoint": ""},
        {"reservation_max_age_seconds": 3601},
        {"table_quota_name": "routercredit"},
        {"quota_group_rate_limits_json": "{}"},
    ):
        with pytest.raises(ValueError):
            Settings(**{**valid, **overrides})
    config = Settings(**{**valid, "rate_limit_replica_share": 1000})
    created = []

    class Client:
        def __init__(self, **kwargs):
            created.append(kwargs)

    monkeypatch.setattr("foundry_router.state.azure.AzureTableEntityClient", Client)
    _health, _credit, rate, clients = build_stores(config)
    assert isinstance(rate, AzureTableRateLimitStore)
    assert len(clients) == 1
    assert created[0]["table_name"] == "routerquota"
    from foundry_router.ratelimit import configured_quota_limits

    assert configured_quota_limits(config) == config.quota_group_rate_limits
