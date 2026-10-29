"""Production discrepancy regressions: actual ledger visibility and safe cache settlement."""

import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Response
from pydantic import ValidationError

from foundry_router.config import PricingConfig
from foundry_router.credit import InMemoryCreditStore, estimate_response_usage_cost
from foundry_router.credit_groups import CreditStoreError
from foundry_router.forwarding import stream_response
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.state import AzureTableCreditStore, TableEntityCreditStoreError
from tests.unit.test_credit_recovery import expire
from tests.unit.test_shared_resource_credit import POLICY, shared_settings
from tests.unit.test_state import FakeTableClient


@pytest.fixture(params=["memory", "table"])
def store(request):
    if request.param == "memory":
        return InMemoryCreditStore()
    return AzureTableCreditStore(FakeTableClient(), retry_backoff_ms=0)


def priced_response(usage, cached_price=0.2):
    response = Response(content=json.dumps({"usage": usage}), media_type="application/json")
    pricing = {
        "m": PricingConfig(
            input_per_million=2, output_per_million=10, cached_input_per_million=cached_price
        )
    }
    return estimate_response_usage_cost(response, "m", pricing)


@pytest.mark.parametrize(
    "count_key,details_key",
    [
        ("input_tokens", "input_tokens_details"),
        ("prompt_tokens", "prompt_tokens_details"),
    ],
)
def test_cached_subset_is_discounted_without_changing_public_usage(count_key, details_key):
    usage = {count_key: 1000, details_key: {"cached_tokens": 800}, "output_tokens": 20}
    assert priced_response(usage) == pytest.approx(0.00076)
    assert priced_response(usage, cached_price=None) == pytest.approx(0.0022)
    assert priced_response(usage, cached_price=0) == pytest.approx(0.0006)


@pytest.mark.parametrize(
    "details",
    [
        None,
        [],
        {},
        {"cached_tokens": True},
        {"cached_tokens": -1},
        {"cached_tokens": 1001},
        {"cached_tokens": "800"},
        {"cached_tokens": 800.5},
    ],
)
def test_malformed_cache_details_never_discount_known_input(details):
    assert priced_response(
        {"input_tokens": 1000, "input_tokens_details": details, "output_tokens": 20}
    ) == pytest.approx(0.0022)


def test_ambiguous_aliases_and_total_only_usage_never_discount():
    assert priced_response(
        {
            "input_tokens": 1000,
            "input_tokens_details": {"cached_tokens": 800},
            "prompt_tokens": 900,
            "prompt_tokens_details": {"cached_tokens": 800},
            "output_tokens": 20,
        }
    ) == pytest.approx(0.0022)
    assert priced_response(
        {"total_tokens": 1000, "input_tokens_details": {"cached_tokens": 800}, "output_tokens": 20}
    ) == pytest.approx(0.0022)


@pytest.mark.parametrize("price", [True, -0.1, 2.1, float("nan"), float("inf")])
def test_invalid_cached_prices_fail_configuration(price):
    with pytest.raises(ValidationError):
        PricingConfig(input_per_million=2, output_per_million=10, cached_input_per_million=price)


@pytest.mark.asyncio
async def test_shared_ledger_settlement_recovery_and_release_are_exactly_once(store):
    await store.sync_from_settings(shared_settings())
    for request, backend, amount in [("usage", "a", 4), ("released", "b", 2), ("expired", "a", 3)]:
        assert await store.try_assign_reservation(request, backend, amount, **POLICY)
    await store.finalize_request("usage", backend_id="a", charge_reserved=True, charged_cost_usd=2)
    await store.finalize_request("usage", backend_id="a", charge_reserved=True, charged_cost_usd=2)
    await store.finalize_request(
        "released", backend_id="b", charge_reserved=False, charged_cost_usd=None
    )
    await expire(store)
    await expire(store)
    await store.finalize_request(
        "expired", backend_id="a", charge_reserved=True, charged_cost_usd=3
    )
    snapshots = await store.live_snapshot(["a", "b", "account"], **POLICY)
    for snapshot in snapshots.values():
        assert snapshot.estimated_remaining_usd == 5
        assert snapshot.debited_usd_total == 5
        assert snapshot.recovered_debit_usd_total == 3
        assert snapshot.active_reservations == 0
    if isinstance(store, AzureTableCreditStore):
        restarted = AzureTableCreditStore(store._client)
        await restarted.sync_from_settings(shared_settings())
        after = (await restarted.live_snapshot(["account"], **POLICY))["account"]
        assert after.debited_usd_total == 5
        assert after.recovered_debit_usd_total == 3


@pytest.mark.asyncio
async def test_counters_preserved_through_admission_reconciliation_config_and_rollover(store):
    settings = shared_settings()
    await store.sync_from_settings(settings)
    assert await store.try_assign_reservation("first", "a", 4, **POLICY)
    await store.finalize_request("first", charge_reserved=True, charged_cost_usd=2)
    assert await store.try_assign_reservation("second", "b", 1, **POLICY)
    await store.finalize_request("second", charge_reserved=False, charged_cost_usd=None)
    await store.apply_reconciled_remaining({"account": 6})
    changed = shared_settings()
    changed.backend_cycle_allowance_usd["account"] = 12
    await store.sync_from_settings(changed)
    after = (await store.live_snapshot(["account"], **POLICY))["account"]
    assert after.debited_usd_total == 2
    assert after.estimated_remaining_usd == 6
    future = after.next_reset_utc + timedelta(days=1)
    rolled = (await store.live_snapshot(["account"], now_utc=future, **POLICY))["account"]
    assert rolled.estimated_remaining_usd == 12
    assert rolled.debited_usd_total == 2


@pytest.mark.asyncio
async def test_debit_is_actual_clamped_reduction_not_unbounded_usage_charge(store):
    await store.sync_from_settings(shared_settings())
    assert await store.try_assign_reservation("r", "a", 4, **POLICY)
    await store.finalize_request("r", charge_reserved=True, charged_cost_usd=20)
    after = (await store.live_snapshot(["account"], **POLICY))["account"]
    assert after.estimated_remaining_usd == 0
    assert after.debited_usd_total == 10


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal", [False, True])
async def test_stream_missing_usage_or_cached_terminal_preserves_bytes_and_ledger(store, terminal):
    await store.sync_from_settings(shared_settings())
    assert await store.try_assign_reservation("r", "a", 4, **POLICY)
    first = b'data: {"type":"response.output_text.delta","delta":"synthetic"}\n\n'
    event = b'data: {"type":"response.completed","response":{"usage":{"input_tokens":1000,"input_tokens_details":{"cached_tokens":800},"output_tokens":20}}}\r\n\r\n'
    pieces = [event[:37], event[37:]] if terminal else []

    async def chunks():
        for piece in pieces:
            yield piece

    metrics = InMemoryMetricsStore()
    actual = [
        chunk
        async for chunk in stream_response(
            chunks(),
            first,
            SimpleNamespace(__aexit__=AsyncMock()),
            request_id="r",
            backend_id="a",
            cooldown_seconds=1,
            model="m",
            pricing={
                "m": PricingConfig(
                    input_per_million=2, output_per_million=10, cached_input_per_million=0.2
                )
            },
            status_code=200,
            set_backend_cooldown=AsyncMock(),
            credit_store=store,
            metrics_store=metrics,
        )
    ]
    assert actual == [first, *pieces]
    after = (await store.live_snapshot(["account"], **POLICY))["account"]
    debit = 0.00076 if terminal else 4
    assert after.estimated_remaining_usd == pytest.approx(10 - debit)
    assert after.debited_usd_total == pytest.approx(debit)
    assert after.active_reservations == 0
    rendered = await metrics.render_prometheus(
        backend_health_states={},
        backend_available_credit_usd={},
        credit_group_debits={"account": (after.debited_usd_total, after.recovered_debit_usd_total)},
    )
    assert (
        f'foundry_router_credit_group_debited_usd_total{{credit_group="account"}} {debit:.9f}'
        in rendered
    )


@pytest.mark.asyncio
async def test_table_conflict_and_commit_then_timeout_do_not_duplicate_debits():
    client = FakeTableClient()
    store = AzureTableCreditStore(client, retry_backoff_ms=0)
    await store.sync_from_settings(shared_settings())
    assert await store.try_assign_reservation("r", "a", 4, **POLICY)
    original = client.try_batch_transaction
    attempts = 0

    async def ambiguous(ops):
        nonlocal attempts
        if any(op.row_key == "balance" for op in ops):
            attempts += 1
            if attempts == 1:
                return False
            assert await original(ops)
            raise TimeoutError("commit acknowledgement lost")
        return await original(ops)

    client.try_batch_transaction = ambiguous
    with pytest.raises(TableEntityCreditStoreError):
        await store.finalize_request("r", charge_reserved=True, charged_cost_usd=2)
    client.try_batch_transaction = original
    await store.finalize_request("r", charge_reserved=True, charged_cost_usd=2)
    after = (await store.live_snapshot(["account"], **POLICY))["account"]
    assert after.debited_usd_total == 2
    assert after.estimated_remaining_usd == 8


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [None, True, "1", -1, float("inf"), float("nan")])
async def test_table_missing_legacy_fields_default_but_invalid_present_fields_fail_closed(bad):
    client = FakeTableClient()
    store = AzureTableCreditStore(client)
    await store.sync_from_settings(shared_settings())
    entity = client.entities[("account", "balance")]
    entity.pop("debited_usd_total")
    entity.pop("recovered_debit_usd_total")
    restarted = AzureTableCreditStore(client)
    await restarted.sync_from_settings(shared_settings())
    assert (await restarted.live_snapshot(["account"], **POLICY))["account"].debited_usd_total == 0
    entity["debited_usd_total"] = bad
    with pytest.raises(TableEntityCreditStoreError):
        await AzureTableCreditStore(client).sync_from_settings(shared_settings())


@pytest.mark.asyncio
async def test_memory_counter_overflow_leaves_balance_and_reservation_intact():
    store = InMemoryCreditStore()
    await store.sync_from_settings(shared_settings())
    assert await store.try_assign_reservation("r", "a", 4, **POLICY)
    state = store._snapshots["account"]
    state.estimated_remaining_usd = 1e308
    state.debited_usd_total = 1e308
    with pytest.raises(CreditStoreError):
        await store.finalize_request("r", charge_reserved=True, charged_cost_usd=1e308)
    assert state.estimated_remaining_usd == 1e308
    assert state.debited_usd_total == 1e308
    assert state.reserved_inflight_usd == 4
    assert "r" in store._reservations
