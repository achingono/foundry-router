"""Bootstrap remains idempotent after lost acknowledgments and day rollover."""

import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
from google_canary_quota import bootstrap

from foundry_router.ratelimit import QuotaStoreError
from tests.unit.test_table_quota import AtomicClient, Clock, settings


async def test_lost_ack_delayed_rerun_and_rollover_never_reseed():
    class LostMarkerAck(AtomicClient):
        async def try_batch_transaction(self, operations):
            if any(op.row_key == "canary-bootstrap-v1" for op in operations):
                self.fail_after_commit = True
            return await super().try_batch_transaction(operations)

    client, clock = LostMarkerAck(), Clock()
    config = settings()
    from foundry_router.state.quota import AzureTableRateLimitStore

    original = AzureTableRateLimitStore(client, now_fn=clock)
    await original.sync_from_settings(config)
    store = await bootstrap(
        client, config, counts={"project": 2}, history_sha256="a" * 64, now=clock()
    )
    snap = (await store.snapshot_quota_groups(["project"]))["project"]
    assert snap.rpd_used == 2
    clock.now += timedelta(seconds=90)
    store = await bootstrap(
        client, config, counts={"project": 2}, history_sha256="a" * 64, now=clock()
    )
    assert (await store.snapshot_quota_groups(["project"]))["project"].rpd_used == 2
    assert await store.try_reserve_estimate("new", "project", estimated_input_tokens=1)
    await store.finalize_request("new")
    clock.now += timedelta(days=1)
    store = await bootstrap(
        client, config, counts={"project": 2}, history_sha256="a" * 64, now=clock()
    )
    assert (await store.snapshot_quota_groups(["project"]))["project"].rpd_used == 0


async def test_existing_usage_and_mismatched_history_fail_closed():
    from foundry_router.state.quota import AzureTableRateLimitStore

    client, clock = AtomicClient(), Clock()
    config = settings()
    store = AzureTableRateLimitStore(client, now_fn=clock)
    await store.sync_from_settings(config)
    assert await store.try_reserve_estimate("existing", "project", estimated_input_tokens=1)
    with pytest.raises(QuotaStoreError):
        await bootstrap(client, config, counts={"project": 2}, history_sha256="a" * 64, now=clock())
    client = AtomicClient()
    await bootstrap(client, config, counts={"project": 2}, history_sha256="a" * 64, now=clock())
    with pytest.raises(QuotaStoreError):
        await bootstrap(client, config, counts={"project": 3}, history_sha256="a" * 64, now=clock())
