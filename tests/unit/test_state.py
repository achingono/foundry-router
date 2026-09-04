"""Tests for shared-state protocol adapters."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from foundry_router.health import BackendHealthState, HealthStore, InMemoryHealthStore
from foundry_router.state import AzureTableHealthStore, TableEntityWriteError

if TYPE_CHECKING:
    from collections.abc import Mapping


class FakeTableClient:
    def __init__(self) -> None:
        self.entities: dict[tuple[str, str], dict[str, object]] = {}
        self.upserted: list[dict[str, object]] = []
        self.reads_in_flight = 0
        self.max_reads_in_flight = 0
        self.read_count = 0
        self.fail_writes = False

    async def get_entity(self, partition_key: str, row_key: str) -> Mapping[str, object] | None:
        self.read_count += 1
        self.reads_in_flight += 1
        self.max_reads_in_flight = max(self.max_reads_in_flight, self.reads_in_flight)
        await asyncio.sleep(0)
        self.reads_in_flight -= 1
        entity = self.entities.get((partition_key, row_key))
        return None if entity is None else dict(entity)

    async def upsert_entity(self, entity: Mapping[str, object]) -> None:
        if self.fail_writes:
            raise TableEntityWriteError("write failed")
        saved = dict(entity)
        key = (str(saved["PartitionKey"]), str(saved["RowKey"]))
        self.entities[key] = saved
        self.upserted.append(saved)


def test_in_memory_health_store_conforms_to_protocol() -> None:
    assert isinstance(InMemoryHealthStore(), HealthStore)


def test_table_health_store_conforms_to_protocol() -> None:
    assert isinstance(AzureTableHealthStore(FakeTableClient()), HealthStore)


def test_table_health_store_preserves_disabled_state() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableHealthStore(client)
        await store.set_backend_active("backend-a")
        client.entities[("backend-a", "health")]["state"] = BackendHealthState.DISABLED.value

        await store.set_backend_cooldown(
            "backend-a", state=BackendHealthState.ERROR_COOLDOWN, cooldown_seconds=30.0
        )
        snapshot = await store.snapshot_backend_health(["backend-a"])

        assert snapshot["backend-a"].state == BackendHealthState.DISABLED

    asyncio.run(run())


def test_table_health_store_skips_redundant_active_write() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableHealthStore(client)
        await store.set_backend_active("backend-a")
        client.upserted.clear()

        await store.set_backend_active("backend-a")

        assert client.upserted == []

    asyncio.run(run())


def test_table_health_store_skips_redundant_active_read() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableHealthStore(client)
        await store.set_backend_active("backend-a")
        client.read_count = 0

        await store.set_backend_active("backend-a")

        assert client.read_count == 0
        assert len(client.upserted) == 1

    asyncio.run(run())


def test_table_health_store_expires_cooldown_and_reset_only_clears_cache() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableHealthStore(client)
        await store.set_backend_cooldown(
            "backend-a", state=BackendHealthState.QUOTA_COOLDOWN, cooldown_seconds=0.0
        )

        snapshot = await store.snapshot_backend_health(["backend-a", "backend-b"])
        assert snapshot["backend-a"].state == BackendHealthState.ACTIVE
        assert snapshot["backend-b"].state == BackendHealthState.ACTIVE
        assert client.entities[("backend-a", "health")]["state"] == BackendHealthState.ACTIVE.value

        await store.reset()
        assert client.entities != {}

    asyncio.run(run())


def test_table_health_store_does_not_shorten_newer_cooldown() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableHealthStore(client)
        await store.set_backend_cooldown(
            "backend-a", state=BackendHealthState.ERROR_COOLDOWN, cooldown_seconds=30.0
        )
        client.upserted.clear()

        await store.set_backend_cooldown(
            "backend-a", state=BackendHealthState.QUOTA_COOLDOWN, cooldown_seconds=1.0
        )

        assert client.upserted == []

    asyncio.run(run())


def test_table_health_store_parallelizes_health_reads() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableHealthStore(client, cache_ttl_seconds=0.0)

        await store.snapshot_backend_health(["backend-a", "backend-b", "backend-c"])

        assert client.max_reads_in_flight == 3

    asyncio.run(run())


def test_table_health_store_uses_short_lived_snapshot_cache() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableHealthStore(client, cache_ttl_seconds=30.0)
        await store.snapshot_backend_health(["backend-a"])
        client.entities[("backend-a", "health")] = {
            "PartitionKey": "backend-a",
            "RowKey": "health",
            "state": BackendHealthState.ERROR_COOLDOWN.value,
            "cooldown_until": 9_999_999_999.0,
        }

        snapshot = await store.snapshot_backend_health(["backend-a"])

        assert snapshot["backend-a"].state == BackendHealthState.ACTIVE

    asyncio.run(run())


def test_table_health_store_invalidates_cache_after_cooldown_write() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableHealthStore(client, cache_ttl_seconds=30.0)
        await store.snapshot_backend_health(["backend-a"])

        await store.set_backend_cooldown(
            "backend-a", state=BackendHealthState.QUOTA_COOLDOWN, cooldown_seconds=30.0
        )
        snapshot = await store.snapshot_backend_health(["backend-a"])

        assert snapshot["backend-a"].state == BackendHealthState.QUOTA_COOLDOWN

    asyncio.run(run())


def test_table_health_store_read_expiry_does_not_fail_when_cleanup_write_fails() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableHealthStore(client)
        await store.set_backend_cooldown(
            "backend-a", state=BackendHealthState.QUOTA_COOLDOWN, cooldown_seconds=0.0
        )
        client.fail_writes = True

        snapshot = await store.snapshot_backend_health(["backend-a"])

        assert snapshot["backend-a"].state == BackendHealthState.ACTIVE

    asyncio.run(run())


def test_table_health_store_recovers_non_finite_cooldown_timestamp() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableHealthStore(client)
        await store.set_backend_cooldown(
            "backend-a", state=BackendHealthState.ERROR_COOLDOWN, cooldown_seconds=30.0
        )
        for invalid_timestamp in (float("nan"), float("inf")):
            client.entities[("backend-a", "health")]["cooldown_until"] = invalid_timestamp
            snapshot = await store.snapshot_backend_health(["backend-a"])
            assert snapshot["backend-a"].state == BackendHealthState.ACTIVE

    asyncio.run(run())


def test_table_health_store_rejects_invalid_values() -> None:
    async def run() -> None:
        with pytest.raises(ValueError, match="cache_ttl_seconds"):
            AzureTableHealthStore(FakeTableClient(), cache_ttl_seconds=float("nan"))
        store = AzureTableHealthStore(FakeTableClient())
        with pytest.raises(ValueError, match="cooldown state"):
            await store.set_backend_cooldown(
                "backend-a", state=BackendHealthState.ACTIVE, cooldown_seconds=1.0
            )
        with pytest.raises(ValueError, match="cooldown state"):
            await store.set_backend_cooldown(
                "backend-a", state=BackendHealthState.ERROR_COOLDOWN, cooldown_seconds=float("inf")
            )

    asyncio.run(run())
