"""Remaining Major regressions: failed sync, stale tracking and post-output charges."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from foundry_router.credit import InMemoryCreditStore
from foundry_router.forwarding import BackendRequestResult, stream_response
from foundry_router.reconciliation import ReconciliationLoop
from foundry_router.state import AzureTableCreditStore, TableEntityCreditStoreError
from tests.unit.test_shared_resource_credit import POLICY, run_route, shared_settings
from tests.unit.test_state import FakeTableClient


@pytest.mark.asyncio
async def test_failed_membership_initialization_stops_egress_and_same_settings_retries():
    from fastapi.responses import JSONResponse

    client = FakeTableClient()
    store = AzureTableCreditStore(client)
    await store.sync_from_settings(shared_settings())
    settings = shared_settings(("new-one", "new-two"))
    create = client.try_create_entity
    client.try_create_entity = AsyncMock(side_effect=TimeoutError("initialization failed"))
    execute = AsyncMock(return_value=BackendRequestResult(JSONResponse({}), False))
    for _ in range(2):
        response = await run_route(settings, store, execute)
        assert response.status_code == 503
        execute.assert_not_awaited()
        assert store._credit_aliases == {"a": "account", "b": "account"}
        assert not [key for key in client.entities if key[1].startswith("req-")]
    client.try_create_entity = create
    assert (await run_route(settings, store, execute)).status_code == 200
    execute.assert_awaited_once_with("a")
    assert store._credit_aliases == {"a": "new-one", "b": "new-two"}


@pytest.mark.asyncio
async def test_sdk_create_race_without_error_code_requires_confirmed_existing_row():
    from azure.core.exceptions import ResourceExistsError

    from foundry_router.state.azure import AzureTableEntityClient

    client = AzureTableEntityClient(
        endpoint="https://example.table.core.windows.net", table_name="credit"
    )
    client._client = SimpleNamespace(create_entity=AsyncMock(side_effect=ResourceExistsError()))
    client.get_entity = AsyncMock(return_value={"PartitionKey": "account", "RowKey": "balance"})
    assert not await client.try_create_entity({"PartitionKey": "account", "RowKey": "balance"})
    client.get_entity = AsyncMock(return_value=None)
    with pytest.raises(ResourceExistsError):
        await client.try_create_entity({"PartitionKey": "account", "RowKey": "balance"})


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["no-commit", "other-writer", "reaper-lost-ack", "finalized"])
async def test_periodic_ownership_retirement_restores_capacity(monkeypatch, outcome):
    from foundry_router.state import table

    monkeypatch.setattr(table, "MAX_TRACKED_RESERVATIONS", 1)
    client = FakeTableClient()
    store = AzureTableCreditStore(client)
    settings = shared_settings()
    await store.sync_from_settings(settings)
    original = client.try_batch_transaction
    if outcome == "no-commit":
        client.try_batch_transaction = AsyncMock(side_effect=TimeoutError("no actual commit"))
        with pytest.raises(TableEntityCreditStoreError):
            await store.try_assign_reservation("stale", "a", 4, **POLICY)
        assert "stale" in store._uncertain_ids
    else:
        assert await store.try_assign_reservation("stale", "a", 4, **POLICY)
    client.try_batch_transaction = original
    if outcome == "other-writer":
        other = AzureTableCreditStore(client)
        await other.sync_from_settings(settings)
        await other.reap_expired_reservations(1, datetime.now(UTC) + timedelta(seconds=1000))
    elif outcome == "reaper-lost-ack":

        async def commit_timeout(operations):
            assert await original(operations)
            raise TimeoutError("reaper committed acknowledgement lost")

        client.try_batch_transaction = commit_timeout
        await store.reap_expired_reservations(1, datetime.now(UTC) + timedelta(seconds=1000))
        client.try_batch_transaction = original
    elif outcome == "finalized":
        client.entities[("account", "req-stale")]["state"] = "finalized"
    assert store._reservation_owners == {"stale": "account"}
    # Provider outage must not prevent independent periodic ownership maintenance.
    provider = SimpleNamespace(fetch_remaining_credit=AsyncMock(side_effect=ConnectionError()))
    loop = ReconciliationLoop(provider=provider, credit_store=store, settings=settings)
    await loop.run_once()
    assert not store._reservation_owners
    assert not store._uncertain_ids
    assert await store.try_assign_reservation("new", "b", 1, **POLICY)


@pytest.mark.asyncio
async def test_ownership_retirement_preserves_live_ambiguous_and_incomplete_discovery(monkeypatch):
    from foundry_router.state import table

    monkeypatch.setattr(table, "MAX_TRACKED_RESERVATIONS", 1)
    client = FakeTableClient()
    store = AzureTableCreditStore(client)
    await store.sync_from_settings(shared_settings(("one", "two")))
    assert await store.try_assign_reservation("live", "a", 4, **POLICY)
    assert await store.reconcile_tracked_ownership() == 0
    original = client.get_entity

    async def incomplete(pk, rk):
        if pk == "two":
            raise TimeoutError("discovery incomplete")
        return await original(pk, rk)

    client.entities.pop(("one", "req-live"))
    client.get_entity = incomplete
    assert await store.reconcile_tracked_ownership() == 0
    assert store._reservation_owners == {"live": "one"}
    client.get_entity = original
    with pytest.raises(TableEntityCreditStoreError, match="capacity"):
        await store.try_assign_reservation("new", "b", 1, **POLICY)
    assert await store.reconcile_tracked_ownership() == 1
    assert await store.try_assign_reservation("new", "b", 1, **POLICY)
    row = dict(client.entities[("two", "req-new")])
    row["PartitionKey"] = "one"
    client.entities[("one", "req-new")] = row
    assert await store.reconcile_tracked_ownership() == 0
    assert store._reservation_owners == {"new": "two"}


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["memory", "table"])
@pytest.mark.parametrize("usage", [None, 2, 0])
async def test_post_output_http_error_known_usage_wins_else_full_reserve(kind, usage):
    store = InMemoryCreditStore() if kind == "memory" else AzureTableCreditStore(FakeTableClient())
    settings = shared_settings()
    await store.sync_from_settings(settings)
    assert await store.try_assign_reservation("stream", "a", 4, **POLICY)

    async def chunks():
        if usage is not None:
            yield f'data: {{"usage":{{"input_tokens":{usage},"output_tokens":0}}}}\n\n'.encode()
        raise httpx.ReadError("failure after meaningful output")

    quota = SimpleNamespace(finalize_request=AsyncMock())
    metrics = SimpleNamespace(observe_request=AsyncMock())
    close = AsyncMock()
    stream = stream_response(
        chunks(),
        b'data: {"delta":"output"}\n\n',
        SimpleNamespace(__aexit__=close),
        request_id="stream",
        backend_id="a",
        cooldown_seconds=1,
        model="m",
        pricing=settings.pricing,
        status_code=200,
        set_backend_cooldown=AsyncMock(),
        credit_store=store,
        rate_limit_store=quota,
        metrics_store=metrics,
    )
    output = b"".join([chunk async for chunk in stream])
    assert output.startswith(b'data: {"delta":"output"}\n\n')
    assert b'"type":"upstream_error"' in output
    live = (await store.live_snapshot(["account"], **POLICY))["account"]
    assert live.estimated_remaining_usd == (6 if usage is None else 10 - usage)
    assert live.reserved_inflight_usd == 0
    assert live.active_reservations == 0
    close.assert_awaited_once()
    quota.finalize_request.assert_awaited_once()
    assert metrics.observe_request.call_args.kwargs["status_code"] == 502
