"""Phase 11: Azurite-backed integration tests for distributed state wiring.

These tests run against the local Azurite emulator (table service on port 10002).
They are marked with @pytest.mark.azurite and run in a dedicated CI job.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from foundry_router.health import BackendHealthState
from foundry_router.state import (
    AzureTableCreditStore,
    AzureTableHealthStore,
    TableEntityCreditStoreError,
    _TransactionEntity,
)
from tests.integration.azurite_fixtures import AzuriteFixture, azurite_available, unique_table_names
from tests.unit.test_shared_resource_credit import POLICY, shared_settings

pytestmark = pytest.mark.azurite


@pytest.mark.asyncio
async def test_failed_membership_sync_blocks_egress_then_same_settings_recovers(
    azurite: AzuriteFixture,
) -> None:
    from unittest.mock import AsyncMock

    from fastapi.responses import JSONResponse

    from foundry_router.forwarding import BackendRequestResult
    from tests.unit.test_shared_resource_credit import run_route

    client = await azurite.client(azurite.credit_table)
    store = AzureTableCreditStore(client)
    await store.sync_from_settings(shared_settings())
    changed = shared_settings(("new-one", "new-two"))
    original = client.try_create_entity
    client.try_create_entity = AsyncMock(side_effect=TimeoutError())
    execute = AsyncMock(return_value=BackendRequestResult(JSONResponse({}), False))
    assert (await run_route(changed, store, execute)).status_code == 503
    execute.assert_not_awaited()
    assert store._credit_aliases == {"a": "account", "b": "account"}
    client.try_create_entity = original
    assert (await run_route(changed, store, execute)).status_code == 200
    execute.assert_awaited_once()
    assert execute.await_args.args == ("a",)
    assert execute.await_args.kwargs["reservation_deadline_monotonic"] > 0


@pytest.mark.asyncio
async def test_real_other_writer_and_lost_ack_retire_bounded_ownership(
    azurite: AzuriteFixture, monkeypatch
) -> None:
    from foundry_router.state import table

    monkeypatch.setattr(table, "MAX_TRACKED_RESERVATIONS", 1)
    first_client = await azurite.client(azurite.credit_table)
    second_client = await azurite.client(azurite.credit_table)
    first = AzureTableCreditStore(first_client)
    second = AzureTableCreditStore(second_client)
    settings = shared_settings()
    await first.sync_from_settings(settings)
    await second.sync_from_settings(settings)
    future = datetime.now(UTC) + timedelta(seconds=1000)
    assert await first.try_assign_reservation("other", "a", 2, **POLICY)
    assert await second.reap_expired_reservations(1, future) == 1
    assert first._reservation_owners == {"other": "account"}
    assert await first.reconcile_tracked_ownership() == 1
    assert await first.try_assign_reservation("lost", "b", 2, **POLICY)
    original = first_client.try_batch_transaction

    async def committed(operations):
        assert await original(operations)
        raise TimeoutError("lost reaper acknowledgement")

    first_client.try_batch_transaction = committed
    await first.reap_expired_reservations(1, future)
    assert first._reservation_owners == {"lost": "account"}
    first_client.try_batch_transaction = original
    assert await first.reconcile_tracked_ownership() == 1
    assert await first.try_assign_reservation("new", "a", 1, **POLICY)


@pytest.mark.asyncio
async def test_real_post_output_failure_without_usage_debits_full_reserve(
    azurite: AzuriteFixture,
) -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import httpx

    from foundry_router.forwarding import stream_response

    client = await azurite.client(azurite.credit_table)
    store = AzureTableCreditStore(client)
    settings = shared_settings()
    await store.sync_from_settings(settings)
    assert await store.try_assign_reservation("stream", "a", 4, **POLICY)

    async def chunks():
        raise httpx.ReadError("post-output failure without terminal usage")
        yield b""  # pragma: no cover

    stream = stream_response(
        chunks(),
        b'data: {"delta":"output"}\n\n',
        SimpleNamespace(__aexit__=AsyncMock()),
        request_id="stream",
        backend_id="a",
        cooldown_seconds=1,
        model="m",
        pricing=settings.pricing,
        status_code=200,
        set_backend_cooldown=AsyncMock(),
        credit_store=store,
        metrics_store=SimpleNamespace(observe_request=AsyncMock()),
    )
    output = b"".join([chunk async for chunk in stream])
    assert b"upstream_error" in output
    balance = await client.get_entity("account", "balance")
    assert balance is not None
    assert balance["estimated_remaining_usd"] == 6
    assert balance["reserved_inflight_usd"] == 0
    assert await client.get_entity("account", "req-stream") is None


@pytest.mark.asyncio
async def test_cross_model_shared_account_contention_settlement_restart(
    azurite: AzuriteFixture,
) -> None:
    clients = [await azurite.client(azurite.credit_table) for _ in range(2)]
    stores = [AzureTableCreditStore(client, retry_backoff_ms=1) for client in clients]
    await asyncio.gather(*(store.sync_from_settings(shared_settings()) for store in stores))
    accepted = await asyncio.gather(
        stores[0].try_assign_reservation("cross-a", "a", 6, **POLICY),
        stores[1].try_assign_reservation("cross-b", "b", 6, **POLICY),
    )
    assert sum(accepted) == 1
    balance = await clients[0].get_entity("account", "balance")
    assert balance is not None and balance["reserved_inflight_usd"] == 6
    assert await clients[0].get_entity("a", "balance") is None
    assert await clients[0].get_entity("b", "balance") is None
    restarted = AzureTableCreditStore(clients[1])
    await restarted.sync_from_settings(shared_settings())
    request_id = "cross-a" if accepted[0] else "cross-b"
    await restarted.finalize_request(
        request_id, backend_id="b", charge_reserved=True, charged_cost_usd=2
    )
    assert await restarted.apply_reconciled_remaining({"a": 7, "b": 7, "account": 7}) == 1
    balance = await clients[0].get_entity("account", "balance")
    assert balance is not None
    assert balance["reserved_inflight_usd"] == 0
    assert balance["estimated_remaining_usd"] == 7


@pytest.mark.asyncio
async def test_recovery_retains_intent_and_retries_reservation_etag_conflict(
    azurite: AzuriteFixture,
) -> None:
    client = await azurite.client(azurite.credit_table)
    competing = await azurite.client(azurite.credit_table)
    store = AzureTableCreditStore(client, retry_backoff_ms=1)
    await store.sync_from_settings(shared_settings())
    assert await store.try_assign_reservation("recover", "a", 4, **POLICY)
    original = client.try_batch_transaction

    async def fail_balance(operations):
        if any(op.row_key == "balance" for op in operations):
            raise TimeoutError("balance settlement unavailable")
        return await original(operations)

    client.try_batch_transaction = fail_balance
    with pytest.raises(TableEntityCreditStoreError):
        await store.finalize_request(
            "recover", backend_id="a", charge_reserved=True, charged_cost_usd=2
        )
    client.try_batch_transaction = original
    restarted = AzureTableCreditStore(client, retry_backoff_ms=1)
    await restarted.sync_from_settings(shared_settings())
    raced = False

    async def reservation_race(operations):
        nonlocal raced
        if not raced and any(op.operation == "Delete" for op in operations):
            raced = True
            row = await competing.get_entity("account", "req-recover")
            assert row is not None
            changed = dict(row)
            changed["settlement_charge_usd"] = 3
            assert await competing.try_batch_transaction(
                [_TransactionEntity("account", "req-recover", "Update", changed, row["odata.etag"])]
            )
        return await original(operations)

    client.try_batch_transaction = reservation_race
    future = datetime.now(UTC) + timedelta(seconds=1000)
    assert await restarted.reap_expired_reservations(1, future) == 1
    await restarted.finalize_request("recover", charge_reserved=True, charged_cost_usd=2)
    assert await restarted.reap_expired_reservations(1, future) == 0
    balance = await client.get_entity("account", "balance")
    assert balance is not None
    assert balance["estimated_remaining_usd"] == 7
    assert balance["reserved_inflight_usd"] == 0
    assert raced


@pytest.mark.asyncio
async def test_real_transaction_commit_then_timeout_admission_stops_egress(
    azurite: AzuriteFixture,
) -> None:
    from unittest.mock import AsyncMock

    from tests.unit.test_shared_resource_credit import run_route

    client = await azurite.client(azurite.credit_table)
    store = AzureTableCreditStore(client)
    settings = shared_settings(("one", "two"))
    await store.sync_from_settings(settings)
    original = client.try_batch_transaction

    async def commit_timeout(operations):
        result = await original(operations)
        if result:
            raise TimeoutError("committed acknowledgement lost")
        return result

    client.try_batch_transaction = commit_timeout
    execute = AsyncMock()
    assert (await run_route(settings, store, execute)).status_code == 503
    execute.assert_not_awaited()
    assert await client.get_entity("one", "req-r") is not None
    assert await client.get_entity("two", "req-r") is None
    client.try_batch_transaction = original
    await store.finalize_request("r", backend_id="a", charge_reserved=False, charged_cost_usd=None)
    assert await client.get_entity("one", "req-r") is None


@pytest.fixture(scope="session", autouse=True)
def require_azurite() -> None:
    if not azurite_available():
        pytest.skip("Azurite table service not available on localhost:10002")


@pytest.fixture
async def azurite() -> AzuriteFixture:
    async with AzuriteFixture(*unique_table_names()) as fixture:
        yield fixture


@pytest.mark.asyncio
async def test_two_instances_shared_credit(azurite: AzuriteFixture) -> None:
    """Two app instances sharing one Table store issue concurrent reservations."""
    credit_client1 = await azurite.client(azurite.credit_table)
    credit_client2 = await azurite.client(azurite.credit_table)

    store1 = AzureTableCreditStore(credit_client1)
    store2 = AzureTableCreditStore(credit_client2)

    await store1.sync_from_settings(
        type(
            "Settings",
            (),
            {
                "backends": {"b1": type("B", (), {})()},
                "backend_cycle_allowance_usd": {"b1": 100.0},
                "backend_initial_estimated_remaining_usd": {"b1": 100.0},
                "backend_cycle_start_day": {"b1": 1},
            },
        )
    )
    await store2.sync_from_settings(
        type(
            "Settings",
            (),
            {
                "backends": {"b1": type("B", (), {})()},
                "backend_cycle_allowance_usd": {"b1": 100.0},
                "backend_initial_estimated_remaining_usd": {"b1": 100.0},
                "backend_cycle_start_day": {"b1": 1},
            },
        )
    )

    # Both instances reserve concurrently
    accepted = await asyncio.gather(
        store1.try_assign_reservation(
            "req-a", "b1", 10.0, min_credit_reserve_usd=0.0, min_credit_reserve_percent=0.0
        ),
        store2.try_assign_reservation(
            "req-b", "b1", 20.0, min_credit_reserve_usd=0.0, min_credit_reserve_percent=0.0
        ),
    )
    assert all(accepted)

    # Total reserved inflight should be 30
    balance = await credit_client1.get_entity("b1", "balance")
    assert balance is not None
    assert balance["reserved_inflight_usd"] == 30.0


@pytest.mark.asyncio
async def test_concurrent_reservations_respect_credit_reserve(azurite: AzuriteFixture) -> None:
    client1 = await azurite.client(azurite.credit_table)
    client2 = await azurite.client(azurite.credit_table)
    store1 = AzureTableCreditStore(client1)
    store2 = AzureTableCreditStore(client2)
    settings = type(
        "Settings",
        (),
        {
            "backends": {"b1": type("B", (), {})()},
            "backend_cycle_allowance_usd": {"b1": 100.0},
            "backend_initial_estimated_remaining_usd": {"b1": 100.0},
            "backend_cycle_start_day": {"b1": 1},
        },
    )
    await store1.sync_from_settings(settings)
    await store2.sync_from_settings(settings)

    accepted = await asyncio.gather(
        store1.try_assign_reservation(
            "req-a",
            "b1",
            60.0,
            min_credit_reserve_usd=10.0,
            min_credit_reserve_percent=0.0,
        ),
        store2.try_assign_reservation(
            "req-b",
            "b1",
            60.0,
            min_credit_reserve_usd=10.0,
            min_credit_reserve_percent=0.0,
        ),
    )
    balance = await client1.get_entity("b1", "balance")
    reservations = await client1.query_entities("b1", "req-")
    assert sum(accepted) == 1
    assert balance is not None
    assert balance["reserved_inflight_usd"] == sum(
        entity["estimated_cost_usd"] for entity in reservations
    )
    assert balance["reserved_inflight_usd"] <= 90.0


@pytest.mark.asyncio
async def test_second_instance_start_does_not_reset_shared_credit(azurite: AzuriteFixture) -> None:
    """A second instance starting against a populated store leaves reservations and spend unchanged."""
    credit_client = await azurite.client(azurite.credit_table)

    store1 = AzureTableCreditStore(credit_client)
    await store1.sync_from_settings(
        type(
            "Settings",
            (),
            {
                "backends": {"b1": type("B", (), {})()},
                "backend_cycle_allowance_usd": {"b1": 100.0},
                "backend_initial_estimated_remaining_usd": {"b1": 100.0},
                "backend_cycle_start_day": {"b1": 1},
            },
        )
    )

    assert await store1.try_assign_reservation(
        "req-a", "b1", 10.0, min_credit_reserve_usd=0.0, min_credit_reserve_percent=0.0
    )

    # Second instance starts
    store2 = AzureTableCreditStore(credit_client)
    await store2.sync_from_settings(
        type(
            "Settings",
            (),
            {
                "backends": {"b1": type("B", (), {})()},
                "backend_cycle_allowance_usd": {"b1": 100.0},
                "backend_initial_estimated_remaining_usd": {"b1": 100.0},
                "backend_cycle_start_day": {"b1": 1},
            },
        )
    )

    balance = await credit_client.get_entity("b1", "balance")
    assert balance is not None
    assert balance["reserved_inflight_usd"] == 10.0
    assert balance["estimated_remaining_usd"] == 100.0


@pytest.mark.asyncio
async def test_concurrent_reapers(azurite: AzuriteFixture) -> None:
    """Concurrent reapers on two instances don't double-count or lose updates."""
    credit_client1 = await azurite.client(azurite.credit_table)
    credit_client2 = await azurite.client(azurite.credit_table)

    store1 = AzureTableCreditStore(credit_client1)
    store2 = AzureTableCreditStore(credit_client2)

    await store1.sync_from_settings(
        type(
            "Settings",
            (),
            {
                "backends": {"b1": type("B", (), {})()},
                "backend_cycle_allowance_usd": {"b1": 100.0},
                "backend_initial_estimated_remaining_usd": {"b1": 100.0},
                "backend_cycle_start_day": {"b1": 1},
            },
        )
    )
    await store2.sync_from_settings(
        type(
            "Settings",
            (),
            {
                "backends": {"b1": type("B", (), {})()},
                "backend_cycle_allowance_usd": {"b1": 100.0},
                "backend_initial_estimated_remaining_usd": {"b1": 100.0},
                "backend_cycle_start_day": {"b1": 1},
            },
        )
    )

    # Create an old and a new reservation
    import time

    now = time.time()
    # Manually insert into table (RowKey = req-{request_id})
    await credit_client1.upsert_entity(
        {
            "PartitionKey": "b1",
            "RowKey": "req-old",
            "request_id": "old",
            "backend_id": "b1",
            "estimated_cost_usd": 10.0,
            "created_at_utc": now - 3600,
            "state": "pending",
        }
    )
    await credit_client1.upsert_entity(
        {
            "PartitionKey": "b1",
            "RowKey": "req-new",
            "request_id": "new",
            "backend_id": "b1",
            "estimated_cost_usd": 5.0,
            "created_at_utc": now,
            "state": "pending",
        }
    )

    # Update balance to reflect both
    balance = await credit_client1.get_entity("b1", "balance")
    balance["reserved_inflight_usd"] = 15.0
    await credit_client1.upsert_entity(balance)

    # Both reapers run concurrently
    reaped1, reaped2 = await asyncio.gather(
        store1.reap_expired_reservations(900.0),
        store2.reap_expired_reservations(900.0),
    )

    # Only one should reap the old reservation
    assert (reaped1 + reaped2) == 1

    balance = await credit_client1.get_entity("b1", "balance")
    assert balance is not None
    assert balance["reserved_inflight_usd"] == 5.0  # Only new remains


@pytest.mark.asyncio
async def test_fail_closed_when_storage_is_unreachable(azurite: AzuriteFixture) -> None:
    """Request path fails closed when the Table SDK reports an outage."""
    credit_client = await azurite.client(azurite.credit_table)

    store = AzureTableCreditStore(credit_client)
    await store.sync_from_settings(
        type(
            "Settings",
            (),
            {
                "backends": {"b1": type("B", (), {})()},
                "backend_cycle_allowance_usd": {"b1": 100.0},
                "backend_initial_estimated_remaining_usd": {"b1": 100.0},
                "backend_cycle_start_day": {"b1": 1},
            },
        )
    )

    # Reserve succeeds
    assert await store.try_assign_reservation(
        "req-a", "b1", 10.0, min_credit_reserve_usd=0.0, min_credit_reserve_percent=0.0
    )

    class UnavailableClient:
        async def get_entity(self, **kwargs):
            raise ConnectionError("simulated Table Storage outage")

    sdk_client = credit_client._client
    credit_client._client = UnavailableClient()
    try:
        with pytest.raises(TableEntityCreditStoreError):
            await store.try_assign_reservation(
                "req-b", "b1", 10.0, min_credit_reserve_usd=0.0, min_credit_reserve_percent=0.0
            )
        assert not await credit_client.probe_reachable("b1", "balance")
        with pytest.raises(TableEntityCreditStoreError):
            await store.finalize_request(
                "req-a", backend_id="b1", charge_reserved=True, charged_cost_usd=None
            )
    finally:
        credit_client._client = sdk_client


@pytest.mark.asyncio
async def test_readiness_probe_detects_missing_table(azurite: AzuriteFixture) -> None:
    """Readiness probe returns false for missing table."""
    credit_client = await azurite.client(azurite.credit_table)
    health_client = await azurite.client(azurite.health_table)

    # Credit table exists, health table exists - both should be reachable
    assert await credit_client.probe_reachable("b1", "balance")
    assert await health_client.probe_reachable("b1", "health")

    # Create a client for a non-existent table
    from foundry_router.state.azure import AzureTableEntityClient
    from tests.integration.azurite_fixtures import (
        azurite_credential,
        azurite_endpoint,
        unique_table_names,
    )

    missing_client = AzureTableEntityClient(
        endpoint=azurite_endpoint(),
        table_name=unique_table_names()[0],
        credential=azurite_credential(),
        request_timeout_seconds=2.0,
        allow_http_for_testing=True,
    )
    reachable = await missing_client.probe_reachable("b1", "balance")
    assert reachable is False
    await missing_client.close()


@pytest.mark.asyncio
async def test_etag_conflict_retry_preserves_other_updates(azurite: AzuriteFixture) -> None:
    """ETag conflicts cause retry with fresh state, preserving other replica's update."""
    credit_client1 = await azurite.client(azurite.credit_table)
    credit_client2 = await azurite.client(azurite.credit_table)

    store1 = AzureTableCreditStore(credit_client1)
    store2 = AzureTableCreditStore(credit_client2)

    await store1.sync_from_settings(
        type(
            "Settings",
            (),
            {
                "backends": {"b1": type("B", (), {})()},
                "backend_cycle_allowance_usd": {"b1": 100.0},
                "backend_initial_estimated_remaining_usd": {"b1": 100.0},
                "backend_cycle_start_day": {"b1": 1},
            },
        )
    )
    await store2.sync_from_settings(
        type(
            "Settings",
            (),
            {
                "backends": {"b1": type("B", (), {})()},
                "backend_cycle_allowance_usd": {"b1": 100.0},
                "backend_initial_estimated_remaining_usd": {"b1": 100.0},
                "backend_cycle_start_day": {"b1": 1},
            },
        )
    )

    accepted = await asyncio.gather(
        store1.try_assign_reservation(
            "req-a", "b1", 10.0, min_credit_reserve_usd=0.0, min_credit_reserve_percent=0.0
        ),
        store2.try_assign_reservation(
            "req-b", "b1", 20.0, min_credit_reserve_usd=0.0, min_credit_reserve_percent=0.0
        ),
    )
    assert all(accepted)

    await asyncio.gather(
        store1.finalize_request(
            "req-a", backend_id="b1", charge_reserved=True, charged_cost_usd=8.0
        ),
        store2.finalize_request(
            "req-b", backend_id="b1", charge_reserved=True, charged_cost_usd=15.0
        ),
    )

    balance = await credit_client1.get_entity("b1", "balance")
    assert balance is not None
    assert balance["reserved_inflight_usd"] == 0.0
    assert balance["estimated_remaining_usd"] == pytest.approx(100.0 - 8.0 - 15.0, abs=0.01)


@pytest.mark.asyncio
async def test_health_store_timestamped_snapshots(azurite: AzuriteFixture) -> None:
    """Health store uses timestamped upserts with last-write-wins semantics."""
    health_client = await azurite.client(azurite.health_table)

    store = AzureTableHealthStore(health_client)
    await store.set_backend_active("b1")
    snap = await store.snapshot_backend_health(["b1"])
    assert snap["b1"].state.value == "ACTIVE"

    # Cooldown
    await store.set_backend_cooldown(
        "b1", state=BackendHealthState.QUOTA_COOLDOWN, cooldown_seconds=30.0
    )
    snap = await store.snapshot_backend_health(["b1"])
    assert snap["b1"].state.value == "QUOTA_COOLDOWN"
    assert snap["b1"].cooldown_remaining_seconds > 0


__all__ = [
    "test_concurrent_reapers",
    "test_concurrent_reservations_respect_credit_reserve",
    "test_etag_conflict_retry_preserves_other_updates",
    "test_fail_closed_when_storage_is_unreachable",
    "test_health_store_timestamped_snapshots",
    "test_readiness_probe_detects_missing_table",
    "test_second_instance_start_does_not_reset_shared_credit",
    "test_two_instances_shared_credit",
]
