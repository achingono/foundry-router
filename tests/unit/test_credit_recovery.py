"""Exact independent-review fault reproductions for credit recovery."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from foundry_router.credit import InMemoryCreditStore
from foundry_router.credit_groups import CreditStoreError
from foundry_router.forwarding import stream_response
from foundry_router.state import AzureTableCreditStore, TableEntityCreditStoreError
from tests.unit.test_shared_resource_credit import POLICY, run_route, shared_settings
from tests.unit.test_state import FakeTableClient


@pytest.fixture(params=["memory", "table"])
def store(request):
    if request.param == "memory":
        return InMemoryCreditStore()
    return AzureTableCreditStore(FakeTableClient(), retry_backoff_ms=0)


async def expire(store):
    if isinstance(store, InMemoryCreditStore):
        for reservation in store._reservations.values():
            reservation.created_at_monotonic -= 1000
        await store.assess("account", 0, reservation_max_age_seconds=1, **POLICY)
    else:
        await store.reap_expired_reservations(1, datetime.now(UTC) + timedelta(seconds=1000))


@pytest.mark.asyncio
async def test_expired_pending_full_reserve_and_explicit_release_zero(store):
    await store.sync_from_settings(shared_settings())
    assert await store.try_assign_reservation("expired", "a", 4, **POLICY)
    assert await store.try_assign_reservation("released", "b", 2, **POLICY)
    await store.finalize_request(
        "released", backend_id="b", charge_reserved=False, charged_cost_usd=None
    )
    await expire(store)
    await expire(store)
    await store.finalize_request(
        "expired", backend_id="a", charge_reserved=True, charged_cost_usd=4
    )
    live = (await store.live_snapshot(["account"], **POLICY))["account"]
    assert live.estimated_remaining_usd == 6
    assert live.active_reservations == 0
    assert live.reserved_inflight_usd == 0


@pytest.mark.asyncio
async def test_memory_failed_settlement_retains_actual_intent_then_expiry(monkeypatch):
    store = InMemoryCreditStore()
    await store.sync_from_settings(shared_settings())
    assert await store.try_assign_reservation("r", "a", 4, **POLICY)
    original = store._release_locked
    monkeypatch.setattr(
        store,
        "_release_locked",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(CreditStoreError()),
    )
    with pytest.raises(CreditStoreError):
        await store.finalize_request("r", charge_reserved=True, charged_cost_usd=2)
    monkeypatch.setattr(store, "_release_locked", original)
    await expire(store)
    assert (await store.live_snapshot(["account"], **POLICY))[
        "account"
    ].estimated_remaining_usd == 8


@pytest.mark.asyncio
@pytest.mark.parametrize("intent_failure", [False, True])
async def test_table_failed_settlement_restart_recovery_intent_or_full_reserve(intent_failure):
    client = FakeTableClient()
    store = AzureTableCreditStore(client, retry_backoff_ms=0)
    await store.sync_from_settings(shared_settings())
    assert await store.try_assign_reservation("r", "a", 4, **POLICY)
    original = client.try_batch_transaction

    async def fail(operations):
        if intent_failure or any(op.row_key == "balance" for op in operations):
            raise TimeoutError("settlement unavailable")
        return await original(operations)

    client.try_batch_transaction = fail
    with pytest.raises(TableEntityCreditStoreError):
        await store.finalize_request("r", backend_id="a", charge_reserved=True, charged_cost_usd=2)
    client.try_batch_transaction = original
    restarted = AzureTableCreditStore(client)
    await restarted.sync_from_settings(shared_settings())
    await expire(restarted)
    await expire(restarted)
    await restarted.finalize_request("r", charge_reserved=False, charged_cost_usd=None)
    balance = client.entities[("account", "balance")]
    assert balance["estimated_remaining_usd"] == (6 if intent_failure else 8)
    assert balance["reserved_inflight_usd"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["reserve", "settle", "reap"])
async def test_commit_then_timeout_is_never_double_debit_or_second_admission(operation):
    client = FakeTableClient()
    store = AzureTableCreditStore(client, retry_backoff_ms=0)
    settings = shared_settings(("one", "two")) if operation == "reserve" else shared_settings()
    await store.sync_from_settings(settings)
    original = client.try_batch_transaction
    if operation != "reserve":
        assert await store.try_assign_reservation("r", "a", 4, **POLICY)

    async def commit_timeout(operations):
        result = await original(operations)
        if result and any(op.row_key == "balance" for op in operations):
            raise TimeoutError("response lost after commit")
        return result

    client.try_batch_transaction = commit_timeout
    if operation == "reserve":
        execute = AsyncMock()
        response = await run_route(settings, store, execute)
        assert response.status_code == 503
        execute.assert_not_awaited()
        assert {pk for pk, rk in client.entities if rk.startswith("req-")} == {"one"}
        with pytest.raises(TableEntityCreditStoreError):
            await store.try_assign_reservation("r", "b", 1, **POLICY)
    elif operation == "settle":
        with pytest.raises(TableEntityCreditStoreError):
            await store.finalize_request(
                "r", backend_id="a", charge_reserved=True, charged_cost_usd=2
            )
    else:
        await expire(store)
    client.try_batch_transaction = original
    if operation == "reserve":
        await store.finalize_request(
            "r", backend_id="a", charge_reserved=False, charged_cost_usd=None
        )
    else:
        await store.finalize_request("r", charge_reserved=True, charged_cost_usd=2)
        await expire(store)
        assert client.entities[("account", "balance")]["estimated_remaining_usd"] == (
            8 if operation == "settle" else 6
        )


@pytest.mark.asyncio
async def test_legacy_pending_expiry_and_reaper_intent_race_fresh_etags():
    client = FakeTableClient()
    first = AzureTableCreditStore(client, retry_backoff_ms=0)
    await first.sync_from_settings(shared_settings())
    assert await first.try_assign_reservation("r", "a", 4, **POLICY)
    client.entities[("account", "req-r")]["created_at_utc"] -= 1000
    original = client.try_batch_transaction
    raced = False

    async def competing_intent(operations):
        nonlocal raced
        if not raced and any(op.operation == "Delete" for op in operations):
            raced = True
            row = dict(client.entities[("account", "req-r")])
            row["settlement_charge_usd"] = 2
            row["odata.etag"] = "new-intent-etag"
            client.entities[("account", "req-r")] = row
        return await original(operations)

    client.try_batch_transaction = competing_intent
    assert await first.reap_expired_reservations(1) == 1
    assert client.entities[("account", "balance")]["estimated_remaining_usd"] == 8
    assert raced


@pytest.mark.asyncio
@pytest.mark.parametrize("stub", ["object", "mapping"])
async def test_metering_flip_same_settings_pending_guard_and_old_discovery(store, stub):
    configs = {"a": {"credit_group": "account"}, "b": {"credit_group": "account"}}
    settings = SimpleNamespace(
        backends=configs
        if stub == "mapping"
        else {key: SimpleNamespace(**value) for key, value in configs.items()},
        backend_cycle_start_day={"account": 1},
        backend_cycle_allowance_usd={"account": 10},
        backend_initial_estimated_remaining_usd={"account": 10},
    )
    await store.sync_from_settings(settings)
    assert await store.try_assign_reservation("r", "a", 4, **POLICY)
    for config in settings.backends.values():
        if stub == "mapping":
            config["credit_metered"] = False
        else:
            config.credit_metered = False
    with pytest.raises(CreditStoreError, match="Drain"):
        await store.sync_from_settings(settings)
    assert store._credit_aliases == {"a": "account", "b": "account"}
    await store.finalize_request("r", charge_reserved=False, charged_cost_usd=None)
    await store.sync_from_settings(settings)
    assert not await store.try_assign_reservation("new", "a", 1, **POLICY)
    if isinstance(store, AzureTableCreditStore):
        assert "account" in store._configured_backend_ids


@pytest.mark.asyncio
async def test_sync_admission_interleaving_serializes_publish_and_guard():
    client = FakeTableClient()
    store = AzureTableCreditStore(client)
    await store.sync_from_settings(shared_settings())
    entered, proceed = asyncio.Event(), asyncio.Event()
    original = client.try_batch_transaction

    async def blocked(operations):
        entered.set()
        await proceed.wait()
        return await original(operations)

    client.try_batch_transaction = blocked
    admission = asyncio.create_task(store.try_assign_reservation("r", "a", 4, **POLICY))
    await entered.wait()
    sync = asyncio.create_task(store.sync_from_settings(shared_settings(("new-one", "new-two"))))
    await asyncio.sleep(0)
    assert not sync.done()
    proceed.set()
    assert await admission
    with pytest.raises(TableEntityCreditStoreError, match="Drain"):
        await sync
    assert store._credit_aliases == {"a": "account", "b": "account"}


@pytest.mark.asyncio
async def test_concurrent_same_id_cross_group_requires_release(store):
    await store.sync_from_settings(shared_settings(("one", "two")))
    results = await asyncio.gather(
        store.try_assign_reservation("r", "a", 4, **POLICY),
        store.try_assign_reservation("r", "b", 4, **POLICY),
        return_exceptions=True,
    )
    assert sum(result is True for result in results) == 1
    assert sum(isinstance(result, CreditStoreError) for result in results) == 1
    await store.finalize_request("r", charge_reserved=False, charged_cost_usd=None)
    assert await store.try_assign_reservation("r", "b", 4, **POLICY)


@pytest.mark.asyncio
async def test_ownership_limit_no_eviction_and_incomplete_discovery_not_absence(monkeypatch):
    from foundry_router.state import table

    monkeypatch.setattr(table, "MAX_TRACKED_RESERVATIONS", 1)
    client = FakeTableClient()
    store = AzureTableCreditStore(client)
    await store.sync_from_settings(shared_settings(("one", "two")))
    assert await store.try_assign_reservation("r", "a", 4, **POLICY)
    with pytest.raises(TableEntityCreditStoreError, match="capacity"):
        await store.try_assign_reservation("other", "b", 1, **POLICY)
    assert store._reservation_owners == {"r": "one"}
    original = client.get_entity

    async def incomplete(pk, rk):
        if pk == "two":
            raise TimeoutError()
        return await original(pk, rk)

    client.get_entity = incomplete
    with pytest.raises(TableEntityCreditStoreError):
        await store.finalize_request("unknown", charge_reserved=False, charged_cost_usd=None)
    with pytest.raises(TableEntityCreditStoreError):
        await store.try_assign_reservation("unknown", "a", 1, **POLICY)


@pytest.mark.asyncio
async def test_multiple_persisted_owners_are_ambiguous():
    client = FakeTableClient()
    stores = [AzureTableCreditStore(client) for _ in range(2)]
    settings = shared_settings(("one", "two"))
    await asyncio.gather(*(store.sync_from_settings(settings) for store in stores))
    assert await stores[0].try_assign_reservation("r", "a", 4, **POLICY)
    # Reproduce legacy/broken multi-writer ownership explicitly.
    row = dict(client.entities[("one", "req-r")])
    row["PartitionKey"] = "two"
    client.entities[("two", "req-r")] = row
    with pytest.raises(TableEntityCreditStoreError, match="Ambiguous"):
        await stores[1].finalize_request("r", charge_reserved=True, charged_cost_usd=2)


async def make_stream(store, close, *, timeout_seconds=0.1):
    async def chunks():
        yield b"data: [DONE]\n\n"

    quota = SimpleNamespace(finalize_request=AsyncMock())
    metrics = SimpleNamespace(observe_request=AsyncMock())
    stream = stream_response(
        chunks(),
        b'data: {"usage":{"input_tokens":2,"output_tokens":0}}\n\n',
        SimpleNamespace(__aexit__=close),
        request_id="r",
        backend_id="a",
        cooldown_seconds=1,
        model="m",
        pricing=shared_settings().pricing,
        status_code=200,
        set_backend_cooldown=AsyncMock(),
        credit_store=store,
        rate_limit_store=quota,
        metrics_store=metrics,
        cleanup_timeout_seconds=timeout_seconds,
    )

    async def consume():
        async for _ in stream:
            pass

    return consume, quota, metrics


@pytest.mark.asyncio
async def test_stream_context_close_error_still_settles_credit_quota_metrics(store):
    await store.sync_from_settings(shared_settings())
    assert await store.try_assign_reservation("r", "a", 4, **POLICY)
    consume, quota, metrics = await make_stream(
        store, AsyncMock(side_effect=ConnectionError("close"))
    )
    with pytest.raises(ConnectionError):
        await consume()
    assert (await store.live_snapshot(["account"], **POLICY))[
        "account"
    ].estimated_remaining_usd == 8
    quota.finalize_request.assert_awaited_once()
    metrics.observe_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_repeated_cancel_cannot_interrupt_financial_opportunity():
    entered, finish = asyncio.Event(), asyncio.Event()

    async def settle(*_args, **_kwargs):
        entered.set()
        await finish.wait()

    store = SimpleNamespace(finalize_request=AsyncMock(side_effect=settle))
    close = AsyncMock(side_effect=ConnectionError("close"))
    consume, quota, metrics = await make_stream(store, close, timeout_seconds=1)
    task = asyncio.create_task(consume())
    await entered.wait()
    for _ in range(3):
        task.cancel()
        await asyncio.sleep(0)
    assert not task.done()
    finish.set()
    with pytest.raises(ConnectionError):
        await task
    store.finalize_request.assert_awaited_once()
    quota.finalize_request.assert_awaited_once()
    metrics.observe_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_and_credit_timeouts_bounded_join_recovery_no_leaked_tasks(store):
    await store.sync_from_settings(shared_settings())
    assert await store.try_assign_reservation("r", "a", 4, **POLICY)
    original = store.finalize_request

    async def hang(*_args, **_kwargs):
        await asyncio.Event().wait()

    store.finalize_request = AsyncMock(side_effect=hang)
    consume, quota, metrics = await make_stream(
        store, AsyncMock(side_effect=hang), timeout_seconds=0.01
    )
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(consume(), timeout=1)
    quota.finalize_request.assert_awaited_once()
    metrics.observe_request.assert_awaited_once()
    store.finalize_request = original
    await expire(store)
    assert (await store.live_snapshot(["account"], **POLICY))[
        "account"
    ].estimated_remaining_usd == 6
    assert not [
        task
        for task in asyncio.all_tasks()
        if task is not asyncio.current_task() and not task.done()
    ]


@pytest.mark.asyncio
async def test_failed_sync_does_not_publish_new_aliases_or_hide_old_partitions():
    client = FakeTableClient()
    store = AzureTableCreditStore(client)
    await store.sync_from_settings(shared_settings())
    changed = shared_settings(("new-one", "new-two"))
    client.try_create_entity = AsyncMock(side_effect=TimeoutError())
    with pytest.raises(TableEntityCreditStoreError, match="incomplete"):
        await store.sync_from_settings(changed)
    assert store._credit_aliases == {"a": "account", "b": "account"}
    assert store._metered_groups == {"account"}
    assert store._configured_backend_ids == {"account", "new-one", "new-two"}


@pytest.mark.asyncio
async def test_intent_commit_then_timeout_survives_restart():
    client = FakeTableClient()
    store = AzureTableCreditStore(client)
    await store.sync_from_settings(shared_settings())
    assert await store.try_assign_reservation("r", "a", 4, **POLICY)
    original = client.try_batch_transaction

    async def commit_timeout(operations):
        result = await original(operations)
        if result:
            raise TimeoutError()
        return result

    client.try_batch_transaction = commit_timeout
    with pytest.raises(TableEntityCreditStoreError):
        await store.finalize_request("r", charge_reserved=True, charged_cost_usd=2)
    client.try_batch_transaction = original
    restarted = AzureTableCreditStore(client)
    await restarted.sync_from_settings(shared_settings())
    await expire(restarted)
    assert client.entities[("account", "balance")]["estimated_remaining_usd"] == 8


@pytest.mark.asyncio
async def test_repeated_cancellation_propagates_after_successful_cleanup():
    entered, finish = asyncio.Event(), asyncio.Event()

    async def close(*_args):
        entered.set()
        await finish.wait()

    store = SimpleNamespace(finalize_request=AsyncMock())
    consume, quota, metrics = await make_stream(store, close, timeout_seconds=1)
    task = asyncio.create_task(consume())
    await entered.wait()
    for _ in range(3):
        task.cancel()
        await asyncio.sleep(0)
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    store.finalize_request.assert_awaited_once()
    quota.finalize_request.assert_awaited_once()
    metrics.observe_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_noncooperative_close_bounded_join_and_no_eviction(monkeypatch):
    from foundry_router import cleanup

    release = asyncio.Event()

    async def stubborn_close(*_args):
        while not release.is_set():
            try:
                await release.wait()
            except asyncio.CancelledError:
                continue

    store = SimpleNamespace(finalize_request=AsyncMock())
    consume, quota, metrics = await make_stream(store, stubborn_close, timeout_seconds=0.01)
    try:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(consume(), 1)
        assert len(cleanup._active_cleanup_tasks) == 1
        monkeypatch.setattr(cleanup, "MAX_CLEANUP_TASKS", 1)
        with pytest.raises(RuntimeError, match="capacity"):
            await cleanup.protected_cleanup([AsyncMock()])
        assert len(cleanup._active_cleanup_tasks) == 1
        store.finalize_request.assert_awaited_once()
        quota.finalize_request.assert_awaited_once()
        metrics.observe_request.assert_awaited_once()
    finally:
        release.set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
    assert not cleanup._active_cleanup_tasks
