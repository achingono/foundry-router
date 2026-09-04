"""Azure Table Storage adapters for cross-replica state.

The client is injected deliberately so the domain package does not require an
Azure SDK at import time. An application integration can wrap the Azure Tables
client with the small async protocol below, typically using ``to_thread`` for
the SDK's synchronous calls.
"""

from __future__ import annotations

import asyncio
import math
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Protocol

from foundry_router.health import (
    COOLDOWN_STATES,
    BackendHealthSnapshot,
    BackendHealthState,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


class TableEntityClient(Protocol):
    """Minimal entity operations required by the health adapter."""

    async def get_entity(self, partition_key: str, row_key: str) -> Mapping[str, object] | None: ...

    async def upsert_entity(self, entity: Mapping[str, object]) -> None: ...


class TableEntityWriteError(RuntimeError):
    """A best-effort health-state write failed."""


class AzureTableHealthStore:
    """Health store backed by timestamped Azure Table entities.

    Health is intentionally eventually consistent per ADR-005. Each backend
    has one entity in the backend partition, and cooldown expiry is represented
    as a UTC epoch timestamp rather than a process-local monotonic clock.
    Timestamped upserts use last-write-wins semantics in the Azure client
    integration; credit state must use a separate conditional transaction path.
    """

    _ROW_KEY = "health"

    def __init__(self, client: TableEntityClient, *, cache_ttl_seconds: float = 1.0) -> None:
        if not math.isfinite(cache_ttl_seconds) or cache_ttl_seconds < 0.0:
            raise ValueError("cache_ttl_seconds must be finite and non-negative")
        self._client = client
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, tuple[float, BackendHealthSnapshot]] = {}

    async def set_backend_active(self, backend_id: str) -> None:
        cached = self._cache.get(backend_id)
        if cached is not None and time.monotonic() - cached[0] <= self._cache_ttl_seconds:
            if cached[1].state == BackendHealthState.ACTIVE:
                return
            if cached[1].state == BackendHealthState.DISABLED:
                return
            await self._write(backend_id, BackendHealthState.ACTIVE, 0.0)
            return
        existing = await self._client.get_entity(backend_id, self._ROW_KEY)
        if existing is not None:
            current_state = _parse_state(existing.get("state"))
            if current_state == BackendHealthState.DISABLED:
                return
            if current_state == BackendHealthState.ACTIVE:
                self._cache[backend_id] = (
                    time.monotonic(),
                    BackendHealthSnapshot(BackendHealthState.ACTIVE, 0.0),
                )
                return
        await self._write(backend_id, BackendHealthState.ACTIVE, 0.0)

    async def set_backend_cooldown(
        self,
        backend_id: str,
        *,
        state: BackendHealthState,
        cooldown_seconds: float,
    ) -> None:
        self._cache.pop(backend_id, None)
        if state not in COOLDOWN_STATES or not math.isfinite(cooldown_seconds):
            raise ValueError("cooldown state must be a cooldown state")
        duration = max(0.0, cooldown_seconds)
        existing = await self._client.get_entity(backend_id, self._ROW_KEY)
        if existing is not None:
            current_state = _parse_state(existing.get("state"))
            current_until = _parse_float(existing.get("cooldown_until"))
            if current_state == BackendHealthState.DISABLED:
                return
            if current_state in COOLDOWN_STATES and current_until >= time.time() + duration:
                return
        await self._write(backend_id, state, duration)

    async def snapshot_backend_health(
        self, backend_ids: list[str]
    ) -> dict[str, BackendHealthSnapshot]:
        snapshots = await asyncio.gather(
            *(self._snapshot_one(backend_id) for backend_id in backend_ids)
        )
        return dict(zip(backend_ids, snapshots, strict=True))

    async def reset(self) -> None:
        """Clear only local cache; never delete shared health state on shutdown."""
        self._cache.clear()

    async def _snapshot_one(self, backend_id: str) -> BackendHealthSnapshot:
        cached = self._cache.get(backend_id)
        if cached is not None and time.monotonic() - cached[0] <= self._cache_ttl_seconds:
            return cached[1]

        entity = await self._client.get_entity(backend_id, self._ROW_KEY)
        if entity is None:
            snapshot = BackendHealthSnapshot(BackendHealthState.ACTIVE, 0.0)
            self._cache[backend_id] = (time.monotonic(), snapshot)
            return snapshot

        state = _parse_state(entity.get("state"))
        cooldown_until = _parse_float(entity.get("cooldown_until"))
        now = time.time()
        if state in COOLDOWN_STATES and cooldown_until <= now:
            snapshot = BackendHealthSnapshot(BackendHealthState.ACTIVE, 0.0)
            self._cache[backend_id] = (time.monotonic(), snapshot)
            with suppress(TableEntityWriteError):
                await self._write(backend_id, BackendHealthState.ACTIVE, 0.0)
            return snapshot

        remaining = max(0.0, cooldown_until - now) if state in COOLDOWN_STATES else 0.0
        snapshot = BackendHealthSnapshot(state, remaining)
        if state in {BackendHealthState.ACTIVE, BackendHealthState.DISABLED}:
            self._cache[backend_id] = (time.monotonic(), snapshot)
        return snapshot

    async def _write(
        self, backend_id: str, state: BackendHealthState, cooldown_seconds: float
    ) -> None:
        self._cache.pop(backend_id, None)
        now = time.time()
        try:
            await self._client.upsert_entity(
                {
                    "PartitionKey": backend_id,
                    "RowKey": self._ROW_KEY,
                    "state": state.value,
                    "cooldown_until": now + cooldown_seconds,
                    "updated_at": now,
                }
            )
        except TableEntityWriteError:
            self._cache.pop(backend_id, None)
            raise
        except Exception as exc:
            self._cache.pop(backend_id, None)
            raise TableEntityWriteError("health state write failed") from exc
        if state in {BackendHealthState.ACTIVE, BackendHealthState.DISABLED}:
            self._cache[backend_id] = (
                time.monotonic(),
                BackendHealthSnapshot(state, 0.0),
            )


def _parse_state(value: object) -> BackendHealthState:
    try:
        return BackendHealthState(str(value))
    except ValueError:
        return BackendHealthState.ACTIVE


def _parse_float(value: object) -> float:
    if not isinstance(value, (int, float, str)) or isinstance(value, bool):
        return 0.0
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0
