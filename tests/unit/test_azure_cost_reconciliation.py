"""Delayed billing evidence must never replenish concurrent credit spend."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from foundry_router.config import Settings
from foundry_router.config.cost_management import CostGroupConfig
from foundry_router.credit import InMemoryCreditStore, calculate_cycle_window
from foundry_router.reconciliation import ReconciliationLoop
from foundry_router.reconciliation.azure_cost import AzureCostManagementProvider
from foundry_router.reconciliation.cost_types import (
    CostCeiling,
    CostCeilingBatch,
    CostEvidenceError,
    cost_policy_fingerprint,
    downward_float,
)
from foundry_router.state import AzureTableCreditStore, TableEntityCreditStoreError
from tests.unit.test_state import FakeTableClient

SCOPE = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/test-rg"
RESOURCE = SCOPE + "/providers/Microsoft.CognitiveServices/accounts/test-account"
POLICY = {"min_credit_reserve_usd": 0, "min_credit_reserve_percent": 0}


def settings(**kwargs):
    return Settings(
        _env_file=None,
        backends_json=json.dumps(
            {
                "b": {
                    "endpoint": "https://example.openai.azure.com",
                    "credential": "test-only",
                    "deployment": "model",
                    "credit_group": "account",
                }
            }
        ),
        models_json='{"m":{"backends":{"b":1}}}',
        client_api_keys_json='["client"]',
        admin_api_keys_json='["admin"]',
        backend_cycle_start_day_json='{"account":1}',
        backend_cycle_allowance_usd_json='{"account":100}',
        backend_initial_estimated_remaining_usd_json='{"account":100}',
        reconciliation_provider="azure_cost_management",
        cost_management_groups_json=json.dumps(
            {"account": {"scope": SCOPE, "resource_ids": [RESOURCE]}}
        ),
        **kwargs,
    )


def batch(config, remaining=80, now=None):
    now = now or datetime.now(UTC)
    return CostCeilingBatch(
        (
            CostCeiling(
                "account",
                remaining,
                calculate_cycle_window(now, 1).current_cycle_start_utc,
                1,
                100,
                cost_policy_fingerprint(config, "account"),
            ),
        ),
        now,
    )


class Credential:
    def __init__(self):
        self.closed = False
        self.scopes = []

    async def get_token(self, scope):
        self.scopes.append(scope)
        return SimpleNamespace(token="synthetic-token")

    async def close(self):
        self.closed = True


def response(cost=20, next_link=None):
    return {
        "properties": {
            "columns": [
                {"name": "Currency", "type": "String"},
                {"name": "ResourceId", "type": "String"},
                {"name": "PreTaxCost", "type": "Number"},
            ],
            "rows": [["USD", RESOURCE.upper(), cost]],
            "nextLink": next_link,
        }
    }


@pytest.mark.parametrize("table", [False, True])
async def test_atomic_downward_only_inflight_and_settlement(table):
    config = settings()
    store = (
        AzureTableCreditStore(FakeTableClient(), retry_backoff_ms=0)
        if table
        else InMemoryCreditStore()
    )
    await store.sync_from_settings(config)
    assert await store.try_assign_reservation("pending", "b", 10, **POLICY)
    assert await store.apply_cost_ceilings(batch(config)) == 1
    live = (await store.live_snapshot(["b"], **POLICY))["b"]
    assert live.estimated_remaining_usd == 80 and live.reserved_inflight_usd == 10
    await store.finalize_request(
        "pending", backend_id="b", charge_reserved=True, charged_cost_usd=5
    )
    await store.apply_cost_ceilings(batch(config, 95))
    await store.apply_cost_ceilings(batch(config, 80))
    assert (await store.live_snapshot(["b"], **POLICY))["b"].estimated_remaining_usd == 75


@pytest.mark.parametrize("table", [False, True])
async def test_stale_mapping_cycle_and_allowance_rejected(table):
    config = settings()
    store = (
        AzureTableCreditStore(FakeTableClient(), retry_backoff_ms=0)
        if table
        else InMemoryCreditStore()
    )
    await store.sync_from_settings(config)
    old = batch(config, 1)
    config.cost_management_groups["account"] = CostGroupConfig(
        scope=SCOPE, resource_ids=(RESOURCE + "-new",)
    )
    assert await store.apply_cost_ceilings(old) == 0
    current = batch(config, 1)
    assert (
        await store.apply_cost_ceilings(
            replace(
                current,
                ceilings=(
                    replace(
                        current.ceilings[0],
                        cycle_start_utc=current.ceilings[0].cycle_start_utc - timedelta(days=1),
                    ),
                ),
            )
        )
        == 0
    )
    assert (
        await store.apply_cost_ceilings(
            replace(current, ceilings=(replace(current.ceilings[0], allowance_usd=101),))
        )
        == 0
    )
    assert (await store.live_snapshot(["b"], **POLICY))["b"].estimated_remaining_usd == 100


async def test_table_cas_conflict_recomputes_concurrent_debit():
    config = settings()
    client = FakeTableClient()
    first = AzureTableCreditStore(client, retry_backoff_ms=0)
    second = AzureTableCreditStore(client, retry_backoff_ms=0)
    await first.sync_from_settings(config)
    await second.sync_from_settings(config)
    assert await second.try_assign_reservation("spend", "b", 30, **POLICY)
    original = client.try_batch_transaction
    count = 0

    async def conflict(operations):
        nonlocal count
        count += 1
        if count == 1:
            client.try_batch_transaction = original
            await second.finalize_request(
                "spend", backend_id="b", charge_reserved=True, charged_cost_usd=30
            )
            client.try_batch_transaction = conflict
            return False
        return await original(operations)

    client.try_batch_transaction = conflict
    assert await first.apply_cost_ceilings(batch(config, 80)) == 1
    assert count == 2
    assert (await first.live_snapshot(["b"], **POLICY))["b"].estimated_remaining_usd == 70


async def test_table_failed_write_never_claims_applied():
    config = settings()
    client = FakeTableClient()
    store = AzureTableCreditStore(client, retry_backoff_ms=0)
    await store.sync_from_settings(config)

    async def fail(_operations):
        raise OSError("synthetic failure")

    client.try_batch_transaction = fail
    with pytest.raises(TableEntityCreditStoreError):
        await store.apply_cost_ceilings(batch(config))


async def test_exact_post_pagination_auth_and_conservative_decimal(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://invalid.example")
    calls = []
    next_link = (
        "https://management.azure.com"
        + SCOPE
        + "/providers/Microsoft.CostManagement/query?api-version=2025-03-01&$skiptoken=page2"
    )

    def handle(request):
        calls.append(request)
        return httpx.Response(
            200, json=response(0.1, next_link) if len(calls) == 1 else response(0.2)
        )

    credential = Credential()
    provider = AzureCostManagementProvider(
        credential=credential, transport=httpx.MockTransport(handle)
    )
    result = await provider.fetch_remaining_credit(settings())
    assert len(calls) == 2 and calls[0].method == "POST"
    assert calls[0].content == calls[1].content
    body = json.loads(calls[0].content)
    assert body["dataset"]["filter"]["dimensions"]["values"] == [RESOURCE]
    assert body["dataset"]["aggregation"]["totalCost"] == {"name": "PreTaxCost", "function": "Sum"}
    assert calls[0].headers["Authorization"] == "Bearer synthetic-token"
    assert credential.scopes == ["https://management.azure.com/.default"]
    assert Decimal(result.ceilings[0].remaining_usd) <= Decimal("99.7")
    await provider.close()
    assert credential.closed


@pytest.mark.parametrize(
    "mutation", ["currency", "resource", "empty", "columns", "nan", "negative", "huge", "body"]
)
async def test_invalid_cost_evidence_preserves_credit(mutation):
    data = response()
    if mutation == "currency":
        data["properties"]["rows"][0][0] = "EUR"
    elif mutation == "resource":
        data["properties"]["rows"][0][1] = RESOURCE + "-other"
    elif mutation == "empty":
        data["properties"]["rows"] = []
    elif mutation == "columns":
        data["properties"]["columns"][2]["type"] = "String"
    elif mutation == "nan":
        data["properties"]["rows"][0][2] = float("nan")
    elif mutation == "negative":
        data["properties"]["rows"][0][2] = -1
    elif mutation == "huge":
        data["properties"]["rows"][0][2] = 1e100
    elif mutation == "body":
        data = {}
    provider = AzureCostManagementProvider(
        credential=Credential(),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data)),
    )
    config = settings()
    store = InMemoryCreditStore()
    await store.sync_from_settings(config)
    loop = ReconciliationLoop(provider=provider, credit_store=store, settings=config)
    await loop.run_once()
    assert loop.status_snapshot()["consecutive_failures"] == 1
    assert (await store.live_snapshot(["b"], **POLICY))["b"].estimated_remaining_usd == 100
    await provider.close()


@pytest.mark.parametrize(
    "link",
    [
        "https://evil.example/query",
        "https://management.azure.com@evil.example/query",
        "https://management.azure.com"
        + SCOPE
        + "/providers/Microsoft.CostManagement/query?api-version=2021-10-01&$skiptoken=a",
        "https://management.azure.com"
        + SCOPE
        + "/providers/Microsoft.CostManagement/query?api-version=2025-03-01&key=a",
        "https://management.azure.com"
        + SCOPE
        + "/providers/Microsoft.CostManagement/query?api-version=2025-03-01&$skiptoken=a#fragment",
    ],
)
async def test_hostile_pagination_does_not_forward_token(link):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json=response(next_link=link))

    provider = AzureCostManagementProvider(
        credential=Credential(), transport=httpx.MockTransport(handle)
    )
    with pytest.raises(CostEvidenceError):
        await provider.fetch_remaining_credit(settings())
    assert len(calls) == 1
    await provider.close()


@pytest.mark.parametrize("status", [204, 301, 401, 403, 429, 500])
async def test_http_failure_single_attempt(status):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, headers={"Location": "https://evil.example"})

    provider = AzureCostManagementProvider(
        credential=Credential(), transport=httpx.MockTransport(handle)
    )
    with pytest.raises(CostEvidenceError):
        await provider.fetch_remaining_credit(settings())
    assert len(calls) == 1
    await provider.close()


async def test_deadline_and_cancellation(monkeypatch):
    import foundry_router.reconciliation.azure_cost as module

    monkeypatch.setattr(module, "REFRESH_SECONDS", 0.02)

    async def slow(_request):
        await asyncio.sleep(10)

    provider = AzureCostManagementProvider(
        credential=Credential(), transport=httpx.MockTransport(slow)
    )
    with pytest.raises(CostEvidenceError):
        await provider.fetch_remaining_credit(settings())
    task = asyncio.create_task(provider.fetch_remaining_credit(settings()))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await provider.close()


async def test_failed_billing_still_reaps():
    class Broken:
        async def fetch_remaining_credit(self, _settings):
            raise CostEvidenceError("synthetic")

    class Store:
        reaped = False

        async def reap_expired_reservations(self, **_kwargs):
            self.reaped = True
            return 1

    store = Store()
    loop = ReconciliationLoop(provider=Broken(), credit_store=store, settings=settings())
    await loop.run_once()
    assert store.reaped and loop.status_snapshot()["stale"]


@pytest.mark.parametrize(
    "scope",
    [SCOPE + "?key=x", SCOPE + "/../rg", SCOPE + "%2f", "https://evil.example", SCOPE + "\\bad"],
)
def test_unsafe_scopes_rejected(scope):
    with pytest.raises(ValidationError):
        CostGroupConfig(scope=scope, resource_ids=(RESOURCE,))


def test_decimal_overflow_and_upward_rounding():
    assert Decimal(downward_float(Decimal("0.1"))) <= Decimal("0.1")
    with pytest.raises(CostEvidenceError):
        downward_float(Decimal("1e999"))


def test_override_conflict_rejected():
    with pytest.raises(ValidationError):
        settings(reconciliation_overrides_usd_json='{"account":50}')


@pytest.mark.parametrize("bound", ["bytes", "rows", "pages", "repeat"])
async def test_finite_response_and_pagination_bounds(monkeypatch, bound):
    import foundry_router.reconciliation.azure_cost as module

    count = 0

    def handle(_request):
        nonlocal count
        count += 1
        if bound == "bytes":
            return httpx.Response(200, content=b" " * 65)
        data = response()
        if bound == "rows":
            data["properties"]["rows"] *= 3
        if bound in {"pages", "repeat"}:
            data["properties"]["nextLink"] = (
                "https://management.azure.com"
                + SCOPE
                + "/providers/Microsoft.CostManagement/query?api-version=2025-03-01&$skiptoken="
                + ("same" if bound == "repeat" else str(count))
            )
        return httpx.Response(200, json=data)

    monkeypatch.setattr(module, "MAX_PAGE_BYTES", 64 if bound == "bytes" else 1024 * 1024)
    monkeypatch.setattr(module, "MAX_ROWS", 2 if bound == "rows" else 10000)
    monkeypatch.setattr(module, "MAX_PAGES", 2 if bound == "pages" else 10)
    provider = AzureCostManagementProvider(
        credential=Credential(), transport=httpx.MockTransport(handle)
    )
    with pytest.raises(CostEvidenceError):
        await provider.fetch_remaining_credit(settings())
    assert count <= 2
    await provider.close()


async def test_loop_applies_typed_batch_and_sanitizes_status():
    provider = AzureCostManagementProvider(
        credential=Credential(),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response())),
    )
    config = settings()
    store = InMemoryCreditStore()
    await store.sync_from_settings(config)
    loop = ReconciliationLoop(provider=provider, credit_store=store, settings=config)
    await loop.run_once()
    status = loop.status_snapshot()
    assert (
        status["provider_kind"] == "azure_cost_management"
        and status["last_updated_credit_groups"] == 1
    )
    assert RESOURCE not in str(status) and "synthetic-token" not in str(status)
    assert (await store.live_snapshot(["b"], **POLICY))["b"].estimated_remaining_usd == 80
    await provider.close()
    with pytest.raises(CostEvidenceError):
        await provider.fetch_remaining_credit(config)


async def test_identity_deadline_before_dispatch(monkeypatch):
    import foundry_router.reconciliation.azure_cost as module

    monkeypatch.setattr(module, "REFRESH_SECONDS", 0.02)

    class SlowCredential(Credential):
        async def get_token(self, _scope):
            await asyncio.sleep(10)

    calls = []
    provider = AzureCostManagementProvider(
        credential=SlowCredential(),
        transport=httpx.MockTransport(calls.append),
    )
    with pytest.raises(CostEvidenceError):
        await provider.fetch_remaining_credit(settings())
    assert calls == []
    await provider.close()


async def test_lifespan_owned_provider_closed_after_startup_failure(monkeypatch):
    from foundry_router import main

    config = settings()
    provider = Credential()
    monkeypatch.setattr(main, "load_settings", lambda: config)
    monkeypatch.setattr(main, "get_backend_client", lambda: None)
    monkeypatch.setattr(main, "_build_cost_provider", lambda _: provider)

    async def fail(_self):
        raise RuntimeError("original-startup")

    monkeypatch.setattr(main.ReconciliationLoop, "start", fail)

    async def fail_close():
        raise OSError("secondary-close")

    monkeypatch.setattr(main, "close_backend_client", fail_close)
    with pytest.raises(RuntimeError, match="original-startup"):
        async with main.lifespan(main.app):
            pass
    assert provider.closed


async def test_cas_cycle_rollover_rejects_old_ceiling(monkeypatch):
    import foundry_router.state.table as module

    now = datetime(2026, 10, 31, 23, 59, 59, tzinfo=UTC)

    class Clock(datetime):
        current = datetime(2026, 10, 31, 23, 59, 59, tzinfo=UTC)

        @classmethod
        def now(cls, _tz):
            return cls.current

    monkeypatch.setattr(module, "datetime", Clock)
    client = FakeTableClient()
    store = AzureTableCreditStore(client, retry_backoff_ms=0)
    config = settings()
    await store.sync_from_settings(config)
    old = batch(config, 1, now)
    count = 0

    async def conflict(_operations):
        nonlocal count
        count += 1
        Clock.current = datetime(2026, 11, 1, tzinfo=UTC)
        return False

    client.try_batch_transaction = conflict
    assert await store.apply_cost_ceilings(old) == 0
    assert count == 1


@pytest.mark.parametrize(
    "case", ["unknown", "nonmetered", "out_of_scope", "overlap", "missing_policy", "invalid_json"]
)
def test_mapping_validation(case):
    config = settings()
    from foundry_router.config.cost_management import parse_cost_groups

    if case == "unknown":
        config.cost_management_groups_json = json.dumps(
            {"other": {"scope": SCOPE, "resource_ids": [RESOURCE]}}
        )
    elif case == "nonmetered":
        config.backends["b"].credit_metered = False
    elif case == "out_of_scope":
        config.cost_management_groups_json = json.dumps(
            {"account": {"scope": SCOPE + "-other", "resource_ids": [RESOURCE]}}
        )
    elif case == "overlap":
        config.backends["c"] = config.backends["b"].model_copy(update={"credit_group": "second"})
        config.backend_cycle_start_day["second"] = 1
        config.backend_cycle_allowance_usd["second"] = 100
        config.cost_management_groups_json = json.dumps(
            {name: {"scope": SCOPE, "resource_ids": [RESOURCE]} for name in ["account", "second"]}
        )
    elif case == "missing_policy":
        config.backend_cycle_allowance_usd = {}
    elif case == "invalid_json":
        config.cost_management_groups_json = "["
    with pytest.raises(ValueError):
        parse_cost_groups(config)


async def test_repeated_cancellation_waits_for_owned_cleanup():
    class SlowCredential(Credential):
        async def close(self):
            await asyncio.sleep(0.02)
            self.closed = True

    credential = SlowCredential()
    provider = AzureCostManagementProvider(
        credential=credential, transport=httpx.MockTransport(lambda _: httpx.Response(200))
    )
    task = asyncio.create_task(provider.close())
    await asyncio.sleep(0.001)
    task.cancel()
    await asyncio.sleep(0.001)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert credential.closed and provider._client_closed and provider._credential_closed
    assert provider._close_task.done()


async def test_client_close_failure_still_closes_identity_and_retryable(monkeypatch):
    credential = Credential()
    provider = AzureCostManagementProvider(
        credential=credential, transport=httpx.MockTransport(lambda _: httpx.Response(200))
    )
    original = provider._client.aclose
    calls = 0

    async def fail():
        nonlocal calls
        calls += 1
        raise OSError("secret-like synthetic error")

    monkeypatch.setattr(provider._client, "aclose", fail)
    with pytest.raises(CostEvidenceError, match="cost_cleanup_unavailable"):
        await provider.close()
    assert credential.closed and calls == 2 and not provider._client_closed
    monkeypatch.setattr(provider._client, "aclose", original)
    await provider.close()
    assert provider._client_closed


@pytest.mark.parametrize("name", ["production.ai", "équipe.ai"])
async def test_documented_resource_group_names_encoded(name):
    scope = SCOPE.rsplit("/", 1)[0] + "/" + name
    resource = scope + "/providers/Microsoft.CognitiveServices/accounts/test-account"
    config = settings()
    config.cost_management_groups["account"] = CostGroupConfig(
        scope=scope, resource_ids=(resource,)
    )
    calls = []

    def handle(request):
        calls.append(request)
        data = response()
        data["properties"]["rows"][0][1] = resource
        return httpx.Response(200, json=data)

    provider = AzureCostManagementProvider(
        credential=Credential(), transport=httpx.MockTransport(handle)
    )
    await provider.fetch_remaining_credit(config)
    assert calls[0].url.host == "management.azure.com"
    assert calls[0].url.path.startswith(scope)
    await provider.close()


async def test_blocked_table_read_crossing_cycle_rejects_ceiling(monkeypatch):
    import foundry_router.state.table as module

    class Clock(datetime):
        current = datetime(2026, 10, 31, 23, 59, 59, tzinfo=UTC)

        @classmethod
        def now(cls, _tz):
            return cls.current

    monkeypatch.setattr(module, "datetime", Clock)
    client = FakeTableClient()
    store = AzureTableCreditStore(client, retry_backoff_ms=0)
    config = settings()
    await store.sync_from_settings(config)
    old = batch(config, 1, Clock.current)
    original = client.get_entity

    async def blocked(*args, **kwargs):
        row = await original(*args, **kwargs)
        Clock.current = datetime(2026, 11, 1, tzinfo=UTC)
        return row

    client.get_entity = blocked
    assert await store.apply_cost_ceilings(old) == 0
    assert client.entities[("account", "balance")]["estimated_remaining_usd"] == 100


async def test_json_depth_before_recursive_decode():
    provider = AzureCostManagementProvider(
        credential=Credential(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=b"[" * 2000 + b"]" * 2000)
        ),
    )
    with pytest.raises(CostEvidenceError, match="cost_json_depth_bound"):
        await provider.fetch_remaining_credit(settings())
    await provider.close()
