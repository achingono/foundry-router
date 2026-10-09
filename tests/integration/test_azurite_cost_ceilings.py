"""Actual Table ceiling concurrency and restart, using synthetic local accounts."""

from __future__ import annotations

import asyncio

import pytest

from foundry_router.state import AzureTableCreditStore
from tests.integration.azurite_fixtures import AzuriteFixture, azurite_available, unique_table_names
from tests.unit.test_azure_cost_reconciliation import POLICY, batch, settings

pytestmark = [
    pytest.mark.azurite,
    pytest.mark.skipif(not azurite_available(), reason="Azurite unavailable"),
]


async def test_billing_ceiling_concurrency_and_restart():
    async with AzuriteFixture(*unique_table_names()) as fixture:
        config = settings()
        first = AzureTableCreditStore(
            await fixture.client(fixture.credit_table), retry_backoff_ms=0
        )
        second = AzureTableCreditStore(
            await fixture.client(fixture.credit_table), retry_backoff_ms=0
        )
        await first.sync_from_settings(config)
        await second.sync_from_settings(config)
        assert await first.try_assign_reservation("pending", "b", 10, **POLICY)
        await asyncio.gather(
            first.apply_cost_ceilings(batch(config, 80)),
            second.apply_cost_ceilings(batch(config, 70)),
        )
        live = (await second.live_snapshot(["b"], **POLICY))["b"]
        assert live.estimated_remaining_usd == 70 and live.reserved_inflight_usd == 10
        await first.finalize_request(
            "pending", backend_id="b", charge_reserved=True, charged_cost_usd=5
        )
        restarted = AzureTableCreditStore(
            await fixture.client(fixture.credit_table), retry_backoff_ms=0
        )
        await restarted.sync_from_settings(config)
        await restarted.apply_cost_ceilings(batch(config, 95))
        live = (await restarted.live_snapshot(["b"], **POLICY))["b"]
        assert live.estimated_remaining_usd == 65 and live.reserved_inflight_usd == 0
