"""Real Table transactions, concurrent quota caps and UTF-16 storage boundaries."""

import asyncio
import uuid

import pytest

from foundry_router.ratelimit import QuotaStoreError
from foundry_router.state.quota import AzureTableRateLimitStore
from tests.integration.azurite_fixtures import AzuriteFixture, azurite_available
from tests.unit.test_table_quota import settings

pytestmark = pytest.mark.azurite


@pytest.fixture
async def quota_table():
    if not azurite_available():
        pytest.skip("Local Azurite Table endpoint unavailable")
    async with AzuriteFixture("rq" + uuid.uuid4().hex[:12]) as fixture:
        yield fixture


async def test_real_independent_clients_admission_caps_restart(quota_table):
    a, b = [
        AzureTableRateLimitStore(await quota_table.client(quota_table.table_names[0]))
        for _ in range(2)
    ]
    await a.sync_from_settings(settings())
    await b.sync_from_settings(settings())
    admitted = await asyncio.gather(
        *(
            store.try_reserve_estimate(f"attempt-{i}", "project", estimated_input_tokens=20)
            for i, store in enumerate([a, b] * 4)
        )
    )
    assert sum(admitted) == 4
    restarted = AzureTableRateLimitStore(await quota_table.client(quota_table.table_names[0]))
    await restarted.sync_from_settings(settings())
    snap = (await restarted.snapshot_quota_groups(["project"]))["project"]
    assert (snap.rpm_used_60s, snap.input_tpm_used_60s, snap.rpd_used) == (4, 80, 4)
    for i, success in enumerate(admitted):
        if success:
            await restarted.finalize_request(f"attempt-{i}", actual_input_tokens=10)
    assert (await a.snapshot_quota_groups(["project"]))["project"].input_tpm_used_60s == 40


async def test_real_utf16_property_bound_preserves_usage(quota_table):
    store = AzureTableRateLimitStore(await quota_table.client(quota_table.table_names[0]))
    config = settings(rpm=1000, tpm=10000, rpd=1000)
    await store.sync_from_settings(config)
    accepted = 0
    for i in range(256):
        try:
            admitted = await store.try_reserve_estimate(
                f"attempt-{i}-" + "界" * 35, "project", estimated_input_tokens=1
            )
        except QuotaStoreError:
            break
        if not admitted:
            break
        accepted += 1
    assert 0 < accepted < 256
    restarted = AzureTableRateLimitStore(await quota_table.client(quota_table.table_names[0]))
    await restarted.sync_from_settings(config)
    assert (await restarted.snapshot_quota_groups(["project"]))["project"].rpd_used == accepted
