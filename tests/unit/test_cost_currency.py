"""Subscription currency and public daily rate conversion preserve USD estimate integrity."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from zoneinfo import ZoneInfo

import httpx
import pytest

from foundry_router.config.cost_management import parse_subscription_currencies
from foundry_router.credit import InMemoryCreditStore
from foundry_router.reconciliation.azure_cost import AzureCostManagementProvider
from foundry_router.reconciliation.cost_types import CostEvidenceError, cost_policy_fingerprint
from foundry_router.reconciliation.exchange_rate import (
    DailyExchangeRate,
    DailyExchangeRateClient,
    parse_daily_rate,
)
from tests.unit.test_azure_cost_reconciliation import POLICY, Credential, response, settings

SUBSCRIPTION = "00000000-0000-0000-0000-000000000000"


def rate_payload(day=None, value="1.4240"):
    day = day or datetime.now(UTC).astimezone(ZoneInfo("America/Toronto")).date().isoformat()
    return {
        "seriesDetail": {
            "FXUSDCAD": {
                "label": "USD/CAD",
                "description": "Daily average exchange rate of the US dollar in Canadian dollars.",
                "dimension": {"key": "d", "name": "Date"},
            }
        },
        "observations": [{"d": day, "FXUSDCAD": {"v": value}}],
    }


def cad_settings():
    return settings(cost_management_subscription_currencies_json=json.dumps({SUBSCRIPTION: "CAD"}))


def test_currency_resolution_and_fingerprint():
    usd, cad = settings(), cad_settings()
    assert cad.cost_management_subscription_currencies == {SUBSCRIPTION: "CAD"}
    assert cost_policy_fingerprint(usd, "account") != cost_policy_fingerprint(cad, "account")


@pytest.mark.parametrize(
    "raw",
    [
        "[]",
        '{"wrong":"CAD"}',
        json.dumps({SUBSCRIPTION: "EUR"}),
        json.dumps({SUBSCRIPTION: {"private": "CAD"}}),
        '{"00000000-0000-0000-0000-000000000000":"CAD","00000000-0000-0000-0000-000000000000":"USD"}',
    ],
)
def test_invalid_subscription_currency_map(raw):
    with pytest.raises(ValueError):
        parse_subscription_currencies(raw, settings().cost_management_groups)


@pytest.mark.parametrize(
    "value", ["0", "NaN", "Infinity", "-1", "0.09", "11", "1.1234567890123", 1.4]
)
def test_invalid_rate_values(value):
    data = rate_payload("2026-10-08", value)
    with pytest.raises(CostEvidenceError):
        parse_daily_rate(json.dumps(data).encode(), datetime(2026, 10, 8, 20, tzinfo=UTC))


def test_latest_weekend_rate_and_stale_future_duplicate():
    now = datetime(2026, 10, 11, 20, tzinfo=UTC)
    assert parse_daily_rate(
        json.dumps(rate_payload("2026-10-09")).encode(), now
    ).observation_date == date(2026, 10, 9)
    for day in ("2026-10-01", "2026-10-12"):
        with pytest.raises(CostEvidenceError):
            parse_daily_rate(json.dumps(rate_payload(day)).encode(), now)
    data = rate_payload("2026-10-09")
    data["observations"] *= 2
    with pytest.raises(CostEvidenceError):
        parse_daily_rate(json.dumps(data).encode(), now)


@pytest.mark.asyncio
async def test_cad_division_is_conservative_and_rate_transport_unauthenticated():
    config = cad_settings()
    requests = []

    def fx(request):
        requests.append(request)
        assert "authorization" not in request.headers and "api-key" not in request.headers
        return httpx.Response(200, json=rate_payload(value="1.3"))

    def billing(_request):
        data = response(cost=1)
        data["properties"]["rows"][0][0] = "CAD"
        return httpx.Response(200, json=data)

    provider = AzureCostManagementProvider(
        credential=Credential(),
        transport=httpx.MockTransport(billing),
        rate_transport=httpx.MockTransport(fx),
    )
    try:
        batch = await provider.fetch_remaining_credit(config)
        with localcontext() as context:
            context.prec = 2000
            exact = Decimal(100) - Decimal(1) / Decimal("1.3")
        assert Decimal(batch.ceilings[0].remaining_usd) <= exact
        assert batch.exchange_rate.cad_per_usd == Decimal("1.3") and len(requests) == 1
    finally:
        await provider.close()
    assert provider._rate_closed


@pytest.mark.asyncio
async def test_usd_only_has_zero_fx_egress_and_missing_cad_map_rejects():
    calls = []

    def billing(_request):
        data = response()
        data["properties"]["rows"][0][0] = "CAD"
        return httpx.Response(200, json=data)

    provider = AzureCostManagementProvider(
        credential=Credential(),
        transport=httpx.MockTransport(billing),
        rate_transport=httpx.MockTransport(calls.append),
    )
    try:
        with pytest.raises(CostEvidenceError):
            await provider.fetch_remaining_credit(settings())
        assert not calls
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_currency_change_invalidates_fetched_ceiling_application():
    config = cad_settings()

    def billing(_request):
        data = response()
        data["properties"]["rows"][0][0] = "CAD"
        return httpx.Response(200, json=data)

    provider = AzureCostManagementProvider(
        credential=Credential(),
        transport=httpx.MockTransport(billing),
        rate_transport=httpx.MockTransport(lambda _: httpx.Response(200, json=rate_payload())),
    )
    store = InMemoryCreditStore()
    await store.sync_from_settings(config)
    try:
        batch = await provider.fetch_remaining_credit(config)
        await store.sync_from_settings(settings())
        assert await store.apply_cost_ceilings(batch) == 0
        assert (await store.live_snapshot(["b"], **POLICY))["b"].estimated_remaining_usd == 100
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_rate_transport_deadline_and_cleanup(monkeypatch):
    from foundry_router.reconciliation import exchange_rate

    async def stalled(_request):
        await asyncio.sleep(1)

    monkeypatch.setattr(exchange_rate, "RATE_SECONDS", 0.02)
    client = DailyExchangeRateClient(transport=httpx.MockTransport(stalled))
    try:
        with pytest.raises(CostEvidenceError):
            await client.fetch(datetime.now(UTC))
    finally:
        await client.aclose()


def test_typed_rate_rejects_untrusted_metadata():
    with pytest.raises(CostEvidenceError):
        DailyExchangeRate(datetime.now(UTC).date(), Decimal("1.4"), source="private-state")


@pytest.mark.asyncio
async def test_policy_snapshot_precedes_fx_await():
    config = cad_settings()

    async def fx(_request):
        config.cost_management_subscription_currencies.clear()
        return httpx.Response(200, json=rate_payload())

    def billing(_request):
        data = response()
        data["properties"]["rows"][0][0] = "CAD"
        return httpx.Response(200, json=data)

    provider = AzureCostManagementProvider(
        credential=Credential(),
        transport=httpx.MockTransport(billing),
        rate_transport=httpx.MockTransport(fx),
    )
    try:
        batch = await provider.fetch_remaining_credit(config)
        store = InMemoryCreditStore()
        await store.sync_from_settings(config)
        assert await store.apply_cost_ceilings(batch) == 0
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_multiple_cad_groups_share_one_rate():
    from foundry_router.config.cost_management import CostGroupConfig

    config = cad_settings()
    original = config.cost_management_groups["account"]
    second = original.resource_ids[0] + "second"
    config.cost_management_groups["second"] = CostGroupConfig(
        scope=original.scope, resource_ids=(second,)
    )
    config.backend_cycle_start_day["second"] = 1
    config.backend_cycle_allowance_usd["second"] = 100
    fx_calls = []

    def fx(request):
        fx_calls.append(request)
        return httpx.Response(200, json=rate_payload())

    def billing(request):
        resource = json.loads(request.content)["dataset"]["filter"]["dimensions"]["values"][0]
        data = response()
        data["properties"]["rows"][0][0] = "CAD"
        data["properties"]["rows"][0][1] = resource
        return httpx.Response(200, json=data)

    provider = AzureCostManagementProvider(
        credential=Credential(),
        transport=httpx.MockTransport(billing),
        rate_transport=httpx.MockTransport(fx),
    )
    try:
        assert len((await provider.fetch_remaining_credit(config)).ceilings) == 2
        assert len(fx_calls) == 1
    finally:
        await provider.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload", [b"{" * 40, b"x" * 65537, b'{"observations":[],"observations":[]}']
)
async def test_rate_body_bounds_and_malformed_json(payload):
    client = DailyExchangeRateClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=payload))
    )
    try:
        with pytest.raises(CostEvidenceError):
            await client.fetch(datetime.now(UTC))
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_rate_redirect_rejected_without_billing_traffic():
    calls = []
    provider = AzureCostManagementProvider(
        credential=Credential(),
        transport=httpx.MockTransport(calls.append),
        rate_transport=httpx.MockTransport(
            lambda _: httpx.Response(302, headers={"location": "https://example.com"})
        ),
    )
    try:
        with pytest.raises(CostEvidenceError):
            await provider.fetch_remaining_credit(cad_settings())
        assert not calls and not provider._credential.scopes
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_rate_setup_failure_retains_provider_cleanup_owner(monkeypatch):
    from foundry_router.reconciliation import azure_cost

    def fail_setup(**_kwargs):
        raise OSError("private setup detail")

    provider = AzureCostManagementProvider(credential=Credential())
    monkeypatch.setattr(azure_cost, "DailyExchangeRateClient", fail_setup)
    try:
        with pytest.raises(OSError):
            await provider.fetch_remaining_credit(cad_settings())
    finally:
        await provider.close()
    assert provider._client.is_closed and provider._credential.closed
    assert provider._rate_closed


@pytest.mark.asyncio
async def test_currency_change_during_table_cas_rejects_old_ceiling():
    from foundry_router.state import AzureTableCreditStore
    from tests.unit.test_azure_cost_reconciliation import batch
    from tests.unit.test_state import FakeTableClient

    config = cad_settings()
    client = FakeTableClient()
    store = AzureTableCreditStore(client, retry_backoff_ms=0)
    other = AzureTableCreditStore(client, retry_backoff_ms=0)
    await store.sync_from_settings(config)
    await other.sync_from_settings(config)
    old = batch(config, 1)
    original = client.try_batch_transaction

    async def conflict(_operations):
        client.try_batch_transaction = original
        config.cost_management_subscription_currencies.clear()
        await other.sync_from_settings(settings())
        return False

    client.try_batch_transaction = conflict
    assert await store.apply_cost_ceilings(old) == 0
    assert (await store.live_snapshot(["b"], **POLICY))["b"].estimated_remaining_usd == 100
