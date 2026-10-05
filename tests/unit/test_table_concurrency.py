"""Phase 11: adapter multi-replica correctness (create-if-absent, recompute-on-conflict)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from foundry_router.state import AzureTableCreditStore, TableEntityCreditStoreError
from tests.unit.test_state import FakeTableClient


def _settings(allowance=100.0, remaining=100.0, day=1) -> SimpleNamespace:
    return SimpleNamespace(
        backends={"b1": SimpleNamespace()},
        backend_cycle_allowance_usd={"b1": allowance},
        backend_initial_estimated_remaining_usd={"b1": remaining},
        backend_cycle_start_day={"b1": day},
    )


def _live_sum(client: FakeTableClient) -> float:
    total = 0.0
    for (pk, rk), ent in client.entities.items():
        if pk == "b1" and rk.startswith("req-"):
            total += float(ent["estimated_cost_usd"])
    return total


@pytest.mark.asyncio
async def test_second_instance_start_preserves_reservations_and_spend() -> None:
    client = FakeTableClient()
    s1 = AzureTableCreditStore(client)
    await s1.sync_from_settings(_settings())
    assert await s1.try_assign_reservation(
        "req-a",
        "b1",
        10.0,
        min_credit_reserve_usd=0.0,
        min_credit_reserve_percent=0.0,
    )
    before = dict(client.entities[("b1", "balance")])

    s2 = AzureTableCreditStore(client)
    await s2.sync_from_settings(_settings())  # different settings object id
    after = client.entities[("b1", "balance")]
    assert after["reserved_inflight_usd"] == before["reserved_inflight_usd"] == 10.0
    assert after["estimated_remaining_usd"] == before["estimated_remaining_usd"]
    assert ("b1", "req-req-a") in client.entities


@pytest.mark.asyncio
async def test_failed_initial_sync_retries_same_settings_object() -> None:
    client = FakeTableClient()
    original_create = client.try_create_entity
    attempts = 0

    async def fail_once(entity):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("temporary storage outage")
        return await original_create(entity)

    client.try_create_entity = fail_once
    store = AzureTableCreditStore(client)
    settings = _settings()

    with pytest.raises(TableEntityCreditStoreError, match="incomplete"):
        await store.sync_from_settings(settings)
    assert ("b1", "balance") not in client.entities
    await store.sync_from_settings(settings)

    assert ("b1", "balance") in client.entities
    assert attempts == 2


@pytest.mark.asyncio
async def test_failed_config_merge_retries_same_settings_object() -> None:
    client = FakeTableClient()
    store = AzureTableCreditStore(client, max_retries=1)
    await store.sync_from_settings(_settings())
    attempts = 0

    async def conflict(_operations):
        nonlocal attempts
        attempts += 1
        return False

    client.try_batch_transaction = conflict
    changed_settings = _settings(allowance=200.0, remaining=200.0)
    for _ in range(2):
        with pytest.raises(TableEntityCreditStoreError, match="incomplete"):
            await store.sync_from_settings(changed_settings)

    assert attempts == 2
    assert client.entities[("b1", "balance")]["cycle_allowance_usd"] == 100.0


@pytest.mark.asyncio
async def test_config_drift_merge_preserves_live_credit() -> None:
    client = FakeTableClient()
    s1 = AzureTableCreditStore(client)
    await s1.sync_from_settings(_settings(allowance=100.0, remaining=100.0))
    assert await s1.try_assign_reservation(
        "req-a",
        "b1",
        10.0,
        min_credit_reserve_usd=0.0,
        min_credit_reserve_percent=0.0,
    )
    s2 = AzureTableCreditStore(client)
    await s2.sync_from_settings(_settings(allowance=200.0, remaining=200.0))
    balance = client.entities[("b1", "balance")]
    assert balance["cycle_allowance_usd"] == 200.0
    assert balance["reserved_inflight_usd"] == 10.0
    assert balance["estimated_remaining_usd"] == 100.0


@pytest.mark.asyncio
async def test_concurrent_reserves_across_instances_never_oversubscribe() -> None:
    client = FakeTableClient()
    s1 = AzureTableCreditStore(client, cache_ttl_seconds=60.0)
    s2 = AzureTableCreditStore(client, cache_ttl_seconds=60.0)
    await s1.sync_from_settings(_settings())
    await s2.sync_from_settings(_settings())

    assert await s1.try_assign_reservation(
        "req-a", "b1", 10.0, min_credit_reserve_usd=0.0, min_credit_reserve_percent=0.0
    )
    assert await s2.try_assign_reservation(
        "req-b", "b1", 20.0, min_credit_reserve_usd=0.0, min_credit_reserve_percent=0.0
    )
    balance = client.entities[("b1", "balance")]
    assert balance["reserved_inflight_usd"] == 30.0
    assert balance["reserved_inflight_usd"] == _live_sum(client)


@pytest.mark.asyncio
async def test_settle_recomputes_from_fresh_state_on_conflict() -> None:
    client = FakeTableClient()
    s1 = AzureTableCreditStore(client, cache_ttl_seconds=60.0)
    s2 = AzureTableCreditStore(client, cache_ttl_seconds=60.0)
    await s1.sync_from_settings(_settings())
    await s2.sync_from_settings(_settings())
    for req, cost in (("req-a", 10.0), ("req-b", 20.0)):
        store = s1 if req == "req-a" else s2
        assert await store.try_assign_reservation(
            req, "b1", cost, min_credit_reserve_usd=0.0, min_credit_reserve_percent=0.0
        )
    # Both settle concurrently; each retry recomputes from fresh storage reads.
    await s1.finalize_request("req-a", backend_id="b1", charge_reserved=True, charged_cost_usd=8.0)
    await s2.finalize_request("req-b", backend_id="b1", charge_reserved=True, charged_cost_usd=15.0)
    balance = client.entities[("b1", "balance")]
    assert balance["reserved_inflight_usd"] == 0.0
    assert balance["reserved_inflight_usd"] == _live_sum(client)
    assert balance["estimated_remaining_usd"] == pytest.approx(100.0 - 8.0 - 15.0)


@pytest.mark.asyncio
async def test_reaper_preserves_competing_reservation() -> None:
    client = FakeTableClient()
    store = AzureTableCreditStore(client, cache_ttl_seconds=60.0)
    await store.sync_from_settings(_settings())
    now = datetime.now(UTC).timestamp()
    # Old reservation (expired) + fresh reservation (live), same partition.
    client.entities[("b1", "req-old")] = {
        "PartitionKey": "b1",
        "RowKey": "req-old",
        "request_id": "old",
        "backend_id": "b1",
        "estimated_cost_usd": 5.0,
        "created_at_utc": now - 3600.0,
        "state": "pending",
        "odata.etag": "v1",
    }
    client.entities[("b1", "req-new")] = {
        "PartitionKey": "b1",
        "RowKey": "req-new",
        "request_id": "new",
        "backend_id": "b1",
        "estimated_cost_usd": 7.0,
        "created_at_utc": now,
        "state": "pending",
        "odata.etag": "v1",
    }
    balance = dict(client.entities[("b1", "balance")])
    balance["reserved_inflight_usd"] = 12.0
    client.entities[("b1", "balance")] = balance

    reaped = await store.reap_expired_reservations(900.0)
    assert reaped == 1
    assert ("b1", "req-old") not in client.entities
    assert ("b1", "req-new") in client.entities
    assert client.entities[("b1", "balance")]["reserved_inflight_usd"] == pytest.approx(7.0)


@pytest.mark.asyncio
async def test_reconcile_override_preserves_other_replica_reservation() -> None:
    client = FakeTableClient()
    s1 = AzureTableCreditStore(client, cache_ttl_seconds=60.0)
    await s1.sync_from_settings(_settings())
    assert await s1.try_assign_reservation(
        "req-a", "b1", 10.0, min_credit_reserve_usd=0.0, min_credit_reserve_percent=0.0
    )
    updated = await s1.apply_reconciled_remaining({"b1": 80.0})
    assert updated == 1
    balance = client.entities[("b1", "balance")]
    assert balance["estimated_remaining_usd"] == 80.0
    assert balance["reserved_inflight_usd"] == 10.0
