"""Shared account capacity, ownership and failure-boundary regressions."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from foundry_router.api.common import api_error, finalize_non_streaming_credit
from foundry_router.api.routes.admin import build_router as admin_router
from foundry_router.api.routes.health import build_router as health_router
from foundry_router.auth import verify_admin_auth
from foundry_router.config import BackendConfig, Settings
from foundry_router.credit import CreditAssessmentContext, CreditReservePolicy, InMemoryCreditStore
from foundry_router.credit_groups import CreditStoreError, credit_membership
from foundry_router.forwarding import BackendRequestResult, stream_response
from foundry_router.health import InMemoryHealthStore
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.reconciliation import ReconciliationLoop, StaticSettingsReconciliationProvider
from foundry_router.routing import execute_with_single_failover, select_candidate_backend
from foundry_router.state import AzureTableCreditStore, TableEntityCreditStoreError
from tests.unit.test_state import FakeTableClient


def shared_settings(groups=("account", "account")):
    backends = {
        name: {
            "endpoint": "https://example.openai.azure.com",
            "credential": "test-only",
            "deployment": f"model-{name}",
            "credit_group": group,
        }
        for name, group in zip(("a", "b"), groups, strict=True)
    }
    canonical = set(groups)
    return Settings(
        _env_file=None,
        backends_json=json.dumps(backends),
        models_json=json.dumps(
            {"m": {"backends": {"a": 2, "b": 1}}, "other": {"backends": {"b": 1}}}
        ),
        client_api_keys_json='["client-test"]',
        admin_api_keys_json='["admin-test"]',
        pricing_json='{"m":{"input_per_million":1000000,"output_per_million":0},'
        '"other":{"input_per_million":1000000,"output_per_million":0}}',
        backend_cycle_start_day_json=json.dumps(dict.fromkeys(canonical, 1)),
        backend_cycle_allowance_usd_json=json.dumps(dict.fromkeys(canonical, 10)),
        backend_initial_estimated_remaining_usd_json=json.dumps(dict.fromkeys(canonical, 10)),
        min_credit_reserve_usd=0,
        min_credit_reserve_percent=0,
    )


@pytest.fixture(params=["memory", "table"])
def store(request):
    if request.param == "memory":
        return InMemoryCreditStore()
    return AzureTableCreditStore(FakeTableClient(), retry_backoff_ms=0)


POLICY = {"min_credit_reserve_usd": 0, "min_credit_reserve_percent": 0}


@pytest.mark.asyncio
async def test_combined_capacity_usage_and_context_scalar_aliases(store):
    settings = shared_settings()
    await store.sync_from_settings(settings)
    context = CreditAssessmentContext(CreditReservePolicy(0, 0))
    assert await store.try_assign_with_context("first", "a", 6, context)
    assert not await store.try_assign_reservation("second", "b", 5, **POLICY)
    assert (await store.assess_with_context("b", 1, context)).available_credit_usd == 4
    assert (await store.assess("account", 1, **POLICY)).available_credit_usd == 4
    await store.finalize_request("first", backend_id="b", charge_reserved=True, charged_cost_usd=3)
    live = await store.live_snapshot(["a", "b", "account"], **POLICY)
    assert all(snapshot.estimated_remaining_usd == 7 for snapshot in live.values())
    assert all(snapshot.active_reservations == 0 for snapshot in live.values())


@pytest.mark.asyncio
async def test_reconciliation_coalesces_and_rejects_before_any_write(store):
    await store.sync_from_settings(shared_settings())
    assert await store.apply_reconciled_remaining({"a": 7, "b": 7, "account": 7}) == 1
    with pytest.raises(ValueError, match="Conflicting"):
        await store.apply_reconciled_remaining({"account": 8, "b": 9})
    assert (await store.live_snapshot(["account"], **POLICY))[
        "account"
    ].estimated_remaining_usd == 7


@pytest.mark.asyncio
async def test_membership_mutation_guard_same_settings_retry_and_captured_owner(store):
    settings = shared_settings()
    await store.sync_from_settings(settings)
    assert await store.try_assign_reservation("r", "a", 4, **POLICY)
    settings.backends["a"].credit_group = "new-account"
    for _ in range(2):
        with pytest.raises(CreditStoreError, match="Drain"):
            await store.sync_from_settings(settings)
    await store.finalize_request("r", backend_id="a", charge_reserved=True, charged_cost_usd=2)
    assert (await store.live_snapshot(["account"], **POLICY))[
        "account"
    ].estimated_remaining_usd == 8
    settings.backend_cycle_start_day["new-account"] = 1
    settings.backend_cycle_allowance_usd["new-account"] = 10
    settings.backend_initial_estimated_remaining_usd["new-account"] = 10
    await store.sync_from_settings(settings)


@pytest.mark.parametrize(
    "bad", ["", " account", "account ", "a/b", "a\\b", "a#b", "a?b", "a\n", "a\x7f", "x" * 513]
)
def test_unsafe_credit_group_rejected(bad):
    with pytest.raises(ValueError):
        BackendConfig(
            endpoint="https://example.org", credential="test", deployment="m", credit_group=bad
        )


def test_namespace_collisions_and_mixed_metering():
    with pytest.raises(ValueError, match="overlaps"):
        shared_settings(("b", "account"))
    settings = shared_settings()
    settings.backends["b"].credit_metered = False
    with pytest.raises(ValueError, match="mix"):
        credit_membership(settings)
    with pytest.raises(ValueError, match="unknown"):
        Settings(**{**settings.model_dump(), "backend_cycle_start_day_json": '{"a":1}'})


@pytest.mark.asyncio
async def test_legacy_config_stubs_default_groups_and_non_metered(store):
    settings = SimpleNamespace(
        backends={"a": {}, "b": SimpleNamespace(credit_metered=False)},
        backend_cycle_start_day={"a": 1},
        backend_cycle_allowance_usd={"a": 10},
        backend_initial_estimated_remaining_usd={"a": 10},
    )
    await store.sync_from_settings(settings)
    assert await store.try_assign_reservation("r", "a", 2, **POLICY)
    assert not await store.try_assign_reservation("free", "b", 2, **POLICY)
    await store.finalize_request("r", charge_reserved=False, charged_cost_usd=None)
    assert (await store.assess("a", 1, **POLICY)).available_credit_usd == 10


@pytest.mark.asyncio
async def test_table_concurrent_cross_model_capacity_and_restart():
    client = FakeTableClient()
    stores = [AzureTableCreditStore(client, retry_backoff_ms=0) for _ in range(2)]
    await asyncio.gather(*(s.sync_from_settings(shared_settings()) for s in stores))
    assigned = await asyncio.gather(
        *(
            s.try_assign_reservation(str(i), backend, 6, **POLICY)
            for i, (s, backend) in enumerate(zip(stores, ("a", "b"), strict=True))
        )
    )
    assert sum(assigned) == 1
    assert {pk for pk, _ in client.entities} == {"account"}
    winner = str(assigned.index(True))
    restarted = AzureTableCreditStore(client, retry_backoff_ms=0)
    await restarted.sync_from_settings(shared_settings())
    assert await restarted.try_assign_reservation(winner, "b", 6, **POLICY)
    await restarted.finalize_request(
        winner, backend_id="b", charge_reserved=True, charged_cost_usd=2
    )
    assert client.entities[("account", "balance")]["estimated_remaining_usd"] == 8


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["conflict", "exception", "missing", "malformed"])
async def test_table_finalize_typed_failures_preserve_pending(failure):
    client = FakeTableClient()
    store = AzureTableCreditStore(client, retry_backoff_ms=0)
    await store.sync_from_settings(shared_settings())
    assert await store.try_assign_reservation("r", "a", 3, **POLICY)
    if failure == "conflict":
        client.try_batch_transaction = AsyncMock(return_value=False)
    elif failure == "exception":
        client.try_batch_transaction = AsyncMock(side_effect=ConnectionError())
    elif failure == "missing":
        client.entities.pop(("account", "balance"))
    else:
        client.entities[("account", "req-r")]["estimated_cost_usd"] = "broken"
    with pytest.raises(TableEntityCreditStoreError):
        await store.finalize_request(
            "r", backend_id="a", charge_reserved=False, charged_cost_usd=None
        )
    assert ("account", "req-r") in client.entities


@pytest.mark.asyncio
async def test_legacy_table_partition_is_ownership_even_when_property_differs():
    client = FakeTableClient()
    store = AzureTableCreditStore(client)
    await store.sync_from_settings(shared_settings())
    assert await store.try_assign_reservation("r", "a", 3, **POLICY)
    client.entities[("account", "req-r")]["backend_id"] = "legacy-backend"
    await store.finalize_request("r", backend_id="b", charge_reserved=True, charged_cost_usd=1)
    assert client.entities[("account", "balance")]["estimated_remaining_usd"] == 9


async def run_route(settings, store, execute, quota=None):
    async def finalize(**kwargs):
        return await finalize_non_streaming_credit(
            **kwargs, credit_store=store, rate_limit_store=quota
        )

    return await execute_with_single_failover(
        settings,
        "m",
        operation="responses",
        body={"input": "abc", "max_output_tokens": 0},
        request_id="r",
        execute_backend=execute,
        health_store=InMemoryHealthStore(),
        credit_store=store,
        metrics_store=InMemoryMetricsStore(),
        logger=SimpleNamespace(info=lambda *_a, **_k: None),
        api_error=api_error,
        finalize_non_streaming_credit=finalize,
        rate_limit_store=quota,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("groups", [("account", "account"), ("one", "two")])
async def test_failover_release_before_second_egress(store, groups):
    settings = shared_settings(groups)
    calls = []

    async def execute(backend):
        calls.append(backend)
        live = await store.live_snapshot(list(set(groups)), **POLICY)
        assert sum(snapshot.active_reservations for snapshot in live.values()) == 1
        return BackendRequestResult(
            JSONResponse(
                {"usage": {"input_tokens": 1, "output_tokens": 0}},
                status_code=503 if backend == "a" else 200,
            ),
            backend == "a",
        )

    assert (await run_route(settings, store, execute)).status_code == 200
    assert calls == ["a", "b"]


@pytest.mark.asyncio
async def test_failed_release_hard_stops_selection_and_egress(store):
    store.finalize_request = AsyncMock(side_effect=CreditStoreError("failed release"))
    execute = AsyncMock(return_value=BackendRequestResult(JSONResponse({}, status_code=503), True))
    response = await run_route(shared_settings(), store, execute)
    assert response.status_code == 503
    assert json.loads(response.body)["error"]["type"] == "credit_store_unavailable"
    assert execute.await_count == store.finalize_request.await_count == 1


@pytest.mark.asyncio
async def test_failed_settlement_never_free_releases_and_quota_cleanup_runs(store):
    store.finalize_request = AsyncMock(side_effect=CreditStoreError("failed settlement"))
    quota = SimpleNamespace(release_request=AsyncMock(), finalize_request=AsyncMock())
    execute = AsyncMock(return_value=BackendRequestResult(JSONResponse({}), False))
    assert (await run_route(shared_settings(), store, execute, quota)).status_code == 503
    assert store.finalize_request.await_count == 1
    assert store.finalize_request.call_args.kwargs["charge_reserved"] is True
    quota.finalize_request.assert_awaited_once()
    quota.release_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_quota_failure_release_stops_second_selection(store):
    settings = shared_settings()
    settings.quota_group_rate_limits = {"a": {"rpm": 100}, "b": {"rpm": 100}}
    store.finalize_request = AsyncMock(side_effect=CreditStoreError())
    quota = SimpleNamespace(
        snapshot_quota_groups=AsyncMock(return_value={}),
        try_reserve_estimate=AsyncMock(return_value=False),
    )
    with pytest.raises(CreditStoreError):
        await select_candidate_backend(
            settings,
            "m",
            operation="responses",
            body={"input": "abc"},
            request_id="r",
            health_store=InMemoryHealthStore(),
            credit_store=store,
            logger=SimpleNamespace(info=lambda *_a, **_k: None),
            rate_limit_store=quota,
        )
    assert quota.try_reserve_estimate.await_count == 1


@pytest.mark.asyncio
async def test_cancellation_releases_shared_reservation(store):
    async def execute(_backend):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await run_route(shared_settings(), store, execute)
    assert (await store.live_snapshot(["account"], **POLICY))["account"].active_reservations == 0


@pytest.mark.asyncio
async def test_stream_settlement_failure_still_closes_quota_and_metrics():
    async def chunks():
        yield b"data: [DONE]\n\n"

    credit = SimpleNamespace(finalize_request=AsyncMock(side_effect=CreditStoreError()))
    quota = SimpleNamespace(finalize_request=AsyncMock())
    metrics = SimpleNamespace(observe_request=AsyncMock())
    context = SimpleNamespace(__aexit__=AsyncMock())
    stream = stream_response(
        chunks(),
        b'data: {"usage":{"input_tokens":2,"output_tokens":0}}\n\n',
        context,
        request_id="r",
        backend_id="a",
        cooldown_seconds=1,
        model="m",
        pricing=shared_settings().pricing,
        status_code=200,
        set_backend_cooldown=AsyncMock(),
        credit_store=credit,
        rate_limit_store=quota,
        metrics_store=metrics,
    )
    with pytest.raises(CreditStoreError):
        async for _ in stream:
            pass
    context.__aexit__.assert_awaited_once()
    quota.finalize_request.assert_awaited_once_with("r", actual_input_tokens=2)
    metrics.observe_request.assert_awaited_once()
    assert credit.finalize_request.await_count == 1


@pytest.mark.asyncio
async def test_readiness_admin_and_canonical_group_metric(store):
    settings = shared_settings()
    app = FastAPI()
    app.dependency_overrides[verify_admin_auth] = lambda: None
    app.include_router(health_router(load_settings_fn=lambda: settings))
    app.include_router(
        admin_router(
            load_settings_fn=lambda: settings,
            health_store=InMemoryHealthStore(),
            credit_store=store,
            metrics_store=InMemoryMetricsStore(),
            reconciliation_status_snapshot=dict,
        )
    )
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        assert (await client.get("/health/ready")).status_code == 200
        status = (await client.get("/admin/status")).json()
        assert list(status["credit_groups"]) == ["account"]
        assert all(backend["credit_group"] == "account" for backend in status["backends"].values())
        metrics = (await client.get("/metrics")).text
        assert (
            metrics.count('foundry_router_credit_group_available_usd{credit_group="account"}') == 1
        )
        assert 'foundry_router_credit_available_usd{backend="a"}' in metrics
        assert 'foundry_router_credit_available_usd{backend="b"}' in metrics
        settings.backend_cycle_start_day.clear()
        assert (await client.get("/health/ready")).status_code == 503


@pytest.mark.asyncio
async def test_six_model_twelve_backend_two_account_topology(store):
    base = shared_settings().model_dump()
    backends = {}
    models = {}
    for index in range(6):
        pool = {}
        for resource in ("one", "two"):
            backend = f"{resource}-model-{index}"
            backends[backend] = {
                "endpoint": "https://example.openai.azure.com",
                "credential": "test-only",
                "deployment": f"model-{index}",
                "credit_group": resource,
            }
            pool[backend] = 1
        models[f"model-{index}"] = {"backends": pool}
    settings = Settings(
        **{
            **base,
            "backends_json": json.dumps(backends),
            "models_json": json.dumps(models),
            "pricing_json": json.dumps(
                {model: {"input_per_million": 1, "output_per_million": 1} for model in models}
            ),
            "backend_cycle_start_day_json": '{"one":1,"two":1}',
            "backend_cycle_allowance_usd_json": '{"one":10,"two":10}',
            "backend_initial_estimated_remaining_usd_json": '{"one":10,"two":10}',
        }
    )
    await store.sync_from_settings(settings)
    accepted = await asyncio.gather(
        *(
            store.try_assign_reservation(f"r-{index}", f"one-model-{index}", 3, **POLICY)
            for index in range(6)
        )
    )
    assert sum(accepted) == 3
    live = await store.live_snapshot(["one", "two"], **POLICY)
    assert live["one"].reserved_inflight_usd == 9
    assert live["two"].available_credit_usd == 10


@pytest.mark.asyncio
async def test_reconciliation_status_counts_unique_accounts(store):
    settings = shared_settings()
    await store.sync_from_settings(settings)
    settings.reconciliation_overrides_usd = {"account": 8}
    loop = ReconciliationLoop(
        provider=StaticSettingsReconciliationProvider(), credit_store=store, settings=settings
    )
    await loop.run_once()
    assert loop.status_snapshot()["last_updated_credit_groups"] == 1
    assert loop.status_snapshot()["last_updated_backends"] == 1


@pytest.mark.asyncio
async def test_table_readiness_probes_unique_routable_metered_accounts(monkeypatch):
    from foundry_router import main

    settings = shared_settings()
    settings.backends["unused"] = BackendConfig(
        endpoint="https://example.org", credential="test", deployment="m", credit_group="unused"
    )
    settings.backends["free"] = BackendConfig(
        endpoint="https://example.org", credential="test", deployment="m", credit_metered=False
    )
    health = SimpleNamespace(
        _table_name=settings.table_health_name, probe_reachable=AsyncMock(return_value=True)
    )
    credit = SimpleNamespace(
        _table_name=settings.table_credit_name, probe_reachable=AsyncMock(return_value=True)
    )
    monkeypatch.setattr(main, "_table_clients", (health, credit))
    monkeypatch.setattr(main, "_state_probe_cache", {})
    assert await main._probe_state_stores(settings)
    credit.probe_reachable.assert_awaited_once_with(
        "account", "balance", timeout_seconds=5, require_entity=True
    )
    health.probe_reachable.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_cancel_settles_captured_usage_and_shared_owner(store):
    settings = shared_settings()
    await store.sync_from_settings(settings)
    assert await store.try_assign_reservation("r", "a", 4, **POLICY)

    async def chunks():
        raise asyncio.CancelledError()
        yield b""  # pragma: no cover

    context = SimpleNamespace(__aexit__=AsyncMock())
    quota = SimpleNamespace(finalize_request=AsyncMock())
    metrics = SimpleNamespace(observe_request=AsyncMock())
    stream = stream_response(
        chunks(),
        b'data: {"usage":{"input_tokens":2,"output_tokens":0}}\n\n',
        context,
        request_id="r",
        backend_id="b",
        cooldown_seconds=1,
        model="m",
        pricing=settings.pricing,
        status_code=200,
        set_backend_cooldown=AsyncMock(),
        credit_store=store,
        rate_limit_store=quota,
        metrics_store=metrics,
    )
    with pytest.raises(asyncio.CancelledError):
        async for _ in stream:
            pass
    live = (await store.live_snapshot(["account"], **POLICY))["account"]
    assert live.estimated_remaining_usd == 8
    assert live.active_reservations == 0
    quota.finalize_request.assert_awaited_once_with("r", actual_input_tokens=2)
    metrics.observe_request.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ConnectionError, asyncio.CancelledError])
async def test_quota_admission_exception_releases_shared_credit(store, error):
    settings = shared_settings()
    settings.quota_group_rate_limits = {"a": {"rpm": 100}}
    quota = SimpleNamespace(
        snapshot_quota_groups=AsyncMock(return_value={}),
        try_reserve_estimate=AsyncMock(side_effect=error()),
        release_request=AsyncMock(),
    )
    with pytest.raises(error):
        await select_candidate_backend(
            settings,
            "m",
            operation="responses",
            body={"input": "abc"},
            request_id="r",
            health_store=InMemoryHealthStore(),
            credit_store=store,
            logger=SimpleNamespace(info=lambda *_a, **_k: None),
            rate_limit_store=quota,
        )
    assert (await store.live_snapshot(["account"], **POLICY))["account"].active_reservations == 0
    quota.release_request.assert_awaited_once_with("r")


@pytest.mark.asyncio
async def test_table_live_change_guard_observes_other_writer_and_retry():
    client = FakeTableClient()
    first = AzureTableCreditStore(client)
    second = AzureTableCreditStore(client)
    settings = shared_settings()
    await first.sync_from_settings(settings)
    await second.sync_from_settings(settings)
    assert await first.try_assign_reservation("r", "a", 3, **POLICY)
    changed = shared_settings(("new-one", "new-two"))
    for _ in range(2):
        with pytest.raises(TableEntityCreditStoreError, match="Drain"):
            await second.sync_from_settings(changed)
    await first.finalize_request("r", backend_id="b", charge_reserved=False, charged_cost_usd=None)
    await second.sync_from_settings(changed)
    assert await second.try_assign_reservation("new", "a", 2, **POLICY)


@pytest.mark.asyncio
async def test_table_reconciliation_failure_marks_attempt_failed():
    client = FakeTableClient()
    store = AzureTableCreditStore(client, max_retries=1)
    settings = shared_settings()
    await store.sync_from_settings(settings)
    settings.reconciliation_overrides_usd = {"account": 8}
    client.try_batch_transaction = AsyncMock(return_value=False)
    loop = ReconciliationLoop(
        provider=StaticSettingsReconciliationProvider(), credit_store=store, settings=settings
    )
    await loop.run_once()
    assert loop.status_snapshot()["last_error"] == "TableEntityCreditStoreError"
    assert loop.status_snapshot()["last_updated_credit_groups"] == 0
    assert loop.status_snapshot()["consecutive_failures"] == 1


@pytest.mark.asyncio
async def test_confirmed_finalized_and_absent_table_reservations_are_idempotent():
    client = FakeTableClient()
    store = AzureTableCreditStore(client)
    await store.sync_from_settings(shared_settings())
    assert await store.try_assign_reservation("r", "a", 2, **POLICY)
    client.entities[("account", "req-r")]["state"] = "finalized"
    before = dict(client.entities[("account", "balance")])
    await store.finalize_request("r", backend_id="b", charge_reserved=True, charged_cost_usd=2)
    await store.finalize_request("absent", backend_id="a", charge_reserved=True, charged_cost_usd=2)
    assert client.entities[("account", "balance")] == before


@pytest.mark.asyncio
async def test_missing_group_sync_retries_same_settings_after_completion(store):
    settings = shared_settings()
    remaining = settings.backend_initial_estimated_remaining_usd.pop("account")
    if isinstance(store, AzureTableCreditStore):
        with pytest.raises(TableEntityCreditStoreError, match="incomplete"):
            await store.sync_from_settings(settings)
    else:
        await store.sync_from_settings(settings)
    assert not await store.try_assign_reservation("r", "a", 2, **POLICY)
    settings.backend_initial_estimated_remaining_usd["account"] = remaining
    await store.sync_from_settings(settings)
    assert await store.try_assign_reservation("r", "b", 2, **POLICY)
