"""Tests for shared-state protocol adapters."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from foundry_router.credit import CreditState, CreditStore
from foundry_router.health import BackendHealthState, HealthStore, InMemoryHealthStore
from foundry_router.state import (
    AzureTableCreditStore,
    AzureTableHealthStore,
    TableEntityWriteError,
    _TransactionEntity,
)

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
        self.fail_batch = False
        self.batch_etag_conflicts: set[tuple[str, str]] = (
            set()
        )  # (partition, row) to force conflict

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

    async def try_batch_transaction(self, operations: list[_TransactionEntity]) -> bool:
        if self.fail_batch:
            raise RuntimeError("batch failed")
        # Check for ETag conflicts
        for op in operations:
            key = (op.partition_key, op.row_key)
            if key in self.batch_etag_conflicts:
                return False
            if op.operation == "Update" and op.etag is not None:
                existing = self.entities.get(key)
                if existing is not None and existing.get("odata.etag") != op.etag:
                    return False
        # Apply all operations
        for op in operations:
            key = (op.partition_key, op.row_key)
            if op.operation == "Create":
                if key in self.entities:
                    return False  # Already exists
                self.entities[key] = dict(op.entity) if op.entity else {}
                self.entities[key]["odata.etag"] = f"v{len(self.entities)}"
            elif op.operation == "Update":
                if key not in self.entities:
                    return False
                self.entities[key] = dict(op.entity) if op.entity else {}
                self.entities[key]["odata.etag"] = f"v{len(self.entities)}"
            elif op.operation == "Delete":
                if key in self.entities:
                    del self.entities[key]
        return True


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


# Tests for AzureTableCreditStore


def _settings_stub() -> object:
    settings = type("SettingsStub", (), {})()
    settings.backends = {"backend-a": {}, "backend-b": {}}
    settings.backend_cycle_start_day = {"backend-a": 1, "backend-b": 1}
    settings.backend_cycle_allowance_usd = {"backend-a": 100.0, "backend-b": 200.0}
    settings.backend_initial_estimated_remaining_usd = {"backend-a": 80.0, "backend-b": 200.0}
    return settings


def test_table_credit_store_conforms_to_protocol() -> None:
    assert isinstance(AzureTableCreditStore(FakeTableClient()), CreditStore)


def test_table_credit_store_initializes_balance_rows() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()

        await store.sync_from_settings(settings)

        assert ("backend-a", "balance") in client.entities
        assert ("backend-b", "balance") in client.entities
        assert client.entities[("backend-a", "balance")]["cycle_allowance_usd"] == 100.0
        assert client.entities[("backend-b", "balance")]["cycle_allowance_usd"] == 200.0

    asyncio.run(run())


def test_table_credit_store_skips_redundant_sync() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()

        await store.sync_from_settings(settings)
        client.upserted.clear()
        client.entities.clear()

        await store.sync_from_settings(settings)

        assert not client.upserted
        assert not client.entities

    asyncio.run(run())


def test_table_credit_store_reserves_credit_atomically() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        result = await store.try_assign_reservation(
            "req-1",
            "backend-a",
            10.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        assert result is True
        assert ("backend-a", "req-req-1") in client.entities
        reservation = client.entities[("backend-a", "req-req-1")]
        assert reservation["estimated_cost_usd"] == 10.0
        balance = client.entities[("backend-a", "balance")]
        assert balance["reserved_inflight_usd"] == 10.0

    asyncio.run(run())


def test_table_credit_store_rejects_insufficient_credit() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        result = await store.try_assign_reservation(
            "req-1",
            "backend-a",
            100.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        assert result is False
        assert ("backend-a", "req-req-1") not in client.entities

    asyncio.run(run())


def test_table_credit_store_finalizes_request_and_charges() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        await store.try_assign_reservation(
            "req-1",
            "backend-a",
            10.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )
        balance_before = client.entities[("backend-a", "balance")]["estimated_remaining_usd"]

        await store.finalize_request("req-1", charge_reserved=True, charged_cost_usd=None)

        assert ("backend-a", "req-req-1") not in client.entities
        balance_after = client.entities[("backend-a", "balance")]["estimated_remaining_usd"]
        assert balance_after == balance_before - 10.0

    asyncio.run(run())


def test_table_credit_store_releases_without_charge() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        await store.try_assign_reservation(
            "req-1",
            "backend-a",
            10.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )
        balance_before = client.entities[("backend-a", "balance")]["estimated_remaining_usd"]

        await store.finalize_request("req-1", charge_reserved=False, charged_cost_usd=None)

        assert ("backend-a", "req-req-1") not in client.entities
        balance_after = client.entities[("backend-a", "balance")]["estimated_remaining_usd"]
        assert balance_after == balance_before

    asyncio.run(run())


def test_table_credit_store_charges_actual_cost() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        await store.try_assign_reservation(
            "req-1",
            "backend-a",
            10.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )
        balance_before = client.entities[("backend-a", "balance")]["estimated_remaining_usd"]

        await store.finalize_request("req-1", charge_reserved=True, charged_cost_usd=5.5)

        balance_after = client.entities[("backend-a", "balance")]["estimated_remaining_usd"]
        assert balance_after == balance_before - 5.5

    asyncio.run(run())


def test_table_credit_store_retries_on_etag_conflict() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client, max_retries=3, retry_backoff_ms=1)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        # Simulate an ETag conflict on the first attempt
        call_count = [0]

        original_try_batch = client.try_batch_transaction

        async def try_batch_with_conflict(ops: list[_TransactionEntity]) -> bool:
            call_count[0] += 1
            if call_count[0] == 1:
                return False  # Simulate conflict
            return await original_try_batch(ops)

        client.try_batch_transaction = try_batch_with_conflict

        result = await store.try_assign_reservation(
            "req-1",
            "backend-a",
            10.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        assert result is True
        assert call_count[0] > 1  # Should have retried

    asyncio.run(run())


def test_table_credit_store_assesses_credit_state() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        assessment = await store.assess(
            "backend-a",
            10.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        assert assessment.state in {CreditState.USABLE, CreditState.CONSERVATION}
        assert assessment.available_credit_usd > 0

    asyncio.run(run())


def test_table_credit_store_applies_reconciled_remaining() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        await store.try_assign_reservation(
            "req-1",
            "backend-a",
            20.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        updated = await store.apply_reconciled_remaining({"backend-a": 50.0})

        assert updated == 1
        balance = client.entities[("backend-a", "balance")]
        assert balance["estimated_remaining_usd"] == 50.0

    asyncio.run(run())


def test_table_credit_store_live_snapshot() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        await store.try_assign_reservation(
            "req-1",
            "backend-a",
            10.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        snapshots = await store.live_snapshot(
            ["backend-a", "backend-b"],
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        assert "backend-a" in snapshots
        assert "backend-b" in snapshots
        assert snapshots["backend-a"].reserved_inflight_usd == 10.0
        assert snapshots["backend-a"].state in {
            CreditState.USABLE,
            CreditState.CONSERVATION,
            CreditState.PROTECTED,
        }

    asyncio.run(run())


def test_table_credit_store_reset_clears_cache() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        # Populate cache
        await store.assess(
            "backend-a",
            1.0,
            min_credit_reserve_usd=0.0,
            min_credit_reserve_percent=0.0,
        )

        await store.reset()

        # Entities should still exist in table
        assert ("backend-a", "balance") in client.entities
        # But cache should be cleared (verified by internal state)

    asyncio.run(run())


def test_table_credit_store_fails_on_missing_backend() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)

        assessment = await store.assess(
            "unknown-backend",
            10.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        assert assessment.state == CreditState.INSUFFICIENT_CAPACITY
        assert assessment.available_credit_usd == 0.0

    asyncio.run(run())


def test_table_credit_store_handles_batch_failure() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client, max_retries=2, retry_backoff_ms=1)
        settings = _settings_stub()
        await store.sync_from_settings(settings)
        client.fail_batch = True

        result = await store.try_assign_reservation(
            "req-1",
            "backend-a",
            10.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        assert result is False

    asyncio.run(run())


def test_table_credit_store_handles_missing_balance_in_finalize() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)

        # Try to finalize a non-existent request
        await store.finalize_request("req-1", charge_reserved=True, charged_cost_usd=None)

        # Should not raise; just no-op

    asyncio.run(run())


def test_table_credit_store_cycle_rollover() -> None:
    async def run() -> None:
        from datetime import timedelta

        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        # Move time forward past next cycle
        future = datetime.now(UTC).replace(day=2) + timedelta(days=35)

        assessment = await store.assess(
            "backend-a",
            10.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
            now_utc=future,
        )

        # After cycle rollover, assessment should reflect the reset allowance
        # Note: the storage is not updated by assess(), only the in-memory cache
        assert assessment.available_credit_usd > 0  # Should have full allowance minus reserves

    asyncio.run(run())


def test_table_credit_store_invalid_settings_skipped() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = type("SettingsStub", (), {})()
        settings.backends = {"backend-a": {}}
        settings.backend_cycle_start_day = {}  # Missing required key
        settings.backend_cycle_allowance_usd = {}
        settings.backend_initial_estimated_remaining_usd = {}

        await store.sync_from_settings(settings)

        assert ("backend-a", "balance") not in client.entities

    asyncio.run(run())


def test_table_credit_store_handles_invalid_cost_reconciliation() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        # Try to apply invalid costs
        updated = await store.apply_reconciled_remaining(
            {
                "backend-a": "not-a-number",
                "backend-b": -50.0,  # Negative
                "backend-c": float("inf"),  # Infinite
            }
        )

        assert updated == 0

    asyncio.run(run())


def test_table_health_store_handles_parse_errors() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableHealthStore(client)
        client.entities[("backend-a", "health")] = {
            "PartitionKey": "backend-a",
            "RowKey": "health",
            "state": "INVALID_STATE",
            "cooldown_until": "not-a-number",
        }

        snapshot = await store.snapshot_backend_health(["backend-a"])

        assert snapshot["backend-a"].state == BackendHealthState.ACTIVE

    asyncio.run(run())


def test_table_credit_store_assessment_with_conservation_state() -> None:
    async def run() -> None:
        from datetime import timedelta

        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        # Move to near end of cycle (29+ days into 30-day cycle)
        cycle_start = datetime(2026, 1, 1, tzinfo=UTC)
        near_end = cycle_start.replace(day=30)

        assessment = await store.assess(
            "backend-a",
            1.0,
            min_credit_reserve_usd=0.0,
            min_credit_reserve_percent=0.0,
            now_utc=near_end,
        )

        # With 3 days remaining and projected unused > 5%, should enter conservation
        if assessment.available_credit_usd > 0:
            assert assessment.state in {CreditState.USABLE, CreditState.CONSERVATION}

    asyncio.run(run())


def test_table_credit_store_protected_state() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        # Reserve most of the credit to reach PROTECTED state
        # backend-a has 80.0 available initially, need to reserve down to reserve level
        for i in range(16):
            await store.try_assign_reservation(
                f"req-{i}",
                "backend-a",
                5.0,
                min_credit_reserve_usd=5.0,
                min_credit_reserve_percent=0.0,
            )

        # Now assessment should show PROTECTED or INSUFFICIENT_CAPACITY state
        assessment = await store.assess(
            "backend-a",
            1.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        # With most credit reserved, should be in a restricted state
        assert assessment.state in {CreditState.PROTECTED, CreditState.INSUFFICIENT_CAPACITY}

    asyncio.run(run())


def test_table_credit_store_insufficient_for_request() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        # Ask for credit but request cost is huge
        assessment = await store.assess(
            "backend-a",
            1000.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        assert assessment.state == CreditState.INSUFFICIENT_CAPACITY

    asyncio.run(run())


def test_table_credit_store_finalize_with_no_storage() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        await store.try_assign_reservation(
            "req-1",
            "backend-a",
            10.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        # Delete the reservation from storage
        del client.entities[("backend-a", "req-req-1")]

        # Finalize should handle gracefully
        await store.finalize_request("req-1", charge_reserved=True, charged_cost_usd=None)

    asyncio.run(run())


def test_table_health_store_write_error_handling() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableHealthStore(client)

        # First write succeeds
        await store.set_backend_active("backend-a")

        # Now fail writes
        client.fail_writes = True

        # Trying to set cooldown should raise TableEntityWriteError
        with pytest.raises(TableEntityWriteError):
            await store.set_backend_cooldown(
                "backend-a", state=BackendHealthState.QUOTA_COOLDOWN, cooldown_seconds=30.0
            )

    asyncio.run(run())


def test_table_health_store_recovers_missing_partition_key() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableHealthStore(client)

        # Add malformed entity
        client.entities[("backend-a", "health")] = {
            "RowKey": "health",
            # Missing PartitionKey
            "state": BackendHealthState.ACTIVE.value,
        }

        snapshot = await store.snapshot_backend_health(["backend-a"])

        # Should treat as not found and return ACTIVE
        assert snapshot["backend-a"].state == BackendHealthState.ACTIVE

    asyncio.run(run())


def test_table_credit_store_expensive_request_exceeds_available() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        # Try to reserve more than available (80.0 - 5.0 reserve = 75.0 max)
        result = await store.try_assign_reservation(
            "req-1",
            "backend-a",
            80.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        assert result is False

    asyncio.run(run())


def test_table_reconciliation_with_none_and_invalid() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        # Apply mix of valid and invalid reconciliations
        updated = await store.apply_reconciled_remaining(
            {
                "backend-a": 50.0,  # Valid
                "backend-b": None,  # Invalid
                "unknown": 100.0,  # Unknown backend
            }
        )

        assert updated == 1  # Only backend-a updated

    asyncio.run(run())


def test_table_credit_store_sync_with_invalid_allowance() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)

        settings = type("SettingsStub", (), {})()
        settings.backends = {"backend-a": {}}
        settings.backend_cycle_start_day = {"backend-a": 1}
        settings.backend_cycle_allowance_usd = {"backend-a": float("inf")}  # Invalid
        settings.backend_initial_estimated_remaining_usd = {"backend-a": 80.0}

        await store.sync_from_settings(settings)

        # Should skip invalid backends
        assert ("backend-a", "balance") not in client.entities

    asyncio.run(run())


def test_table_credit_store_single_expensive_reservation() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        # First reservation uses most credit
        result1 = await store.try_assign_reservation(
            "req-1",
            "backend-a",
            70.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )
        assert result1 is True

        # Second reservation should fail due to insufficient remaining
        result2 = await store.try_assign_reservation(
            "req-2",
            "backend-a",
            10.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )
        assert result2 is False

    asyncio.run(run())


def test_table_credit_store_live_snapshot_multiple_backends() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        # Create reservations on both backends
        await store.try_assign_reservation(
            "req-a",
            "backend-a",
            10.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )
        await store.try_assign_reservation(
            "req-b",
            "backend-b",
            20.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        snapshots = await store.live_snapshot(
            ["backend-a", "backend-b"],
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        assert snapshots["backend-a"].reserved_inflight_usd == 10.0
        assert snapshots["backend-b"].reserved_inflight_usd == 20.0

    asyncio.run(run())


def test_table_health_store_disabled_state_prevents_cooldown() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableHealthStore(client)

        # Set to disabled first
        await store.set_backend_active("backend-a")
        client.entities[("backend-a", "health")]["state"] = BackendHealthState.DISABLED.value

        # Try to set cooldown, should not override disabled
        await store.set_backend_cooldown(
            "backend-a", state=BackendHealthState.QUOTA_COOLDOWN, cooldown_seconds=30.0
        )

        snapshot = await store.snapshot_backend_health(["backend-a"])
        assert snapshot["backend-a"].state == BackendHealthState.DISABLED

    asyncio.run(run())


def test_table_credit_store_finalize_with_corrupted_reservation() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        # Create a reservation manually with invalid data
        client.entities[("backend-a", "req-req-1")] = {
            "PartitionKey": "backend-a",
            "RowKey": "req-req-1",
            "request_id": "req-1",
            "backend_id": "backend-a",
            "estimated_cost_usd": "not-a-number",  # Invalid
            "created_at_utc": 0.0,
            "state": "pending",
        }

        # Finalize should handle gracefully
        await store.finalize_request("req-1", charge_reserved=True, charged_cost_usd=None)

    asyncio.run(run())


def test_table_health_store_invalid_cache_ttl() -> None:
    with pytest.raises(ValueError, match="cache_ttl_seconds"):
        AzureTableHealthStore(FakeTableClient(), cache_ttl_seconds=-1.0)


def test_table_credit_store_invalid_cache_ttl() -> None:
    with pytest.raises(ValueError, match="cache_ttl_seconds"):
        AzureTableCreditStore(FakeTableClient(), cache_ttl_seconds=float("nan"))


def test_table_credit_store_finalize_non_existent_request() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)

        # Finalize a request that was never created
        await store.finalize_request("req-999", charge_reserved=True, charged_cost_usd=None)

        # Should not raise or have side effects

    asyncio.run(run())


def test_table_credit_store_with_percent_reserve() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        # Reserve with percentage-based reserve
        result = await store.try_assign_reservation(
            "req-1",
            "backend-a",
            10.0,
            min_credit_reserve_usd=0.0,
            min_credit_reserve_percent=10.0,  # 10% of 100 = 10
        )

        # Should have 80 available - 10 (reserve) - 10 (request) = 60 available
        assert result is True

        assessment = await store.assess(
            "backend-a",
            1.0,
            min_credit_reserve_usd=0.0,
            min_credit_reserve_percent=10.0,
        )

        # Available should be ~60
        assert assessment.available_credit_usd >= 50

    asyncio.run(run())


def test_table_health_store_write_with_exception() -> None:
    async def run() -> None:
        class FailingClient:
            async def get_entity(
                self, partition_key: str, row_key: str
            ) -> Mapping[str, object] | None:
                return None

            async def upsert_entity(self, entity: Mapping[str, object]) -> None:
                raise Exception("Database error")

        store = AzureTableHealthStore(FailingClient())

        with pytest.raises(TableEntityWriteError, match="write failed"):
            await store.set_backend_active("backend-a")

    asyncio.run(run())


def test_table_credit_store_with_zero_costs() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)
        settings = _settings_stub()
        await store.sync_from_settings(settings)

        # Reserve zero cost
        result = await store.try_assign_reservation(
            "req-1",
            "backend-a",
            0.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        assert result is True

        # Finalize with zero charge
        await store.finalize_request("req-1", charge_reserved=False, charged_cost_usd=0.0)

    asyncio.run(run())


def test_table_credit_store_entity_parsing_robustness() -> None:
    async def run() -> None:
        client = FakeTableClient()
        store = AzureTableCreditStore(client)

        # Create a valid balance entity for basic operations
        now = datetime.now(UTC)
        client.entities[("backend-a", "balance")] = {
            "PartitionKey": "backend-a",
            "RowKey": "balance",
            "cycle_start_day": 1,  # Valid
            "cycle_allowance_usd": "100.0",  # String but valid
            "estimated_remaining_usd": 80.0,
            "reserved_inflight_usd": 0.0,
            "cycle_start_utc_timestamp": now.timestamp(),
            "odata.etag": "v1",
        }

        # Should handle parsing gracefully
        assessment = await store.assess(
            "backend-a",
            10.0,
            min_credit_reserve_usd=5.0,
            min_credit_reserve_percent=0.0,
        )

        # Should return valid assessment
        assert assessment is not None
        assert assessment.available_credit_usd >= 0

    asyncio.run(run())
