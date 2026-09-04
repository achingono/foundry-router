"""Ephemeral backend health state and cooldown snapshots."""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from collections.abc import Callable


class BackendHealthState(StrEnum):
    """Ephemeral backend routing health state."""

    ACTIVE = "ACTIVE"
    QUOTA_COOLDOWN = "QUOTA_COOLDOWN"
    ERROR_COOLDOWN = "ERROR_COOLDOWN"
    DISABLED = "DISABLED"


COOLDOWN_STATES = frozenset({BackendHealthState.QUOTA_COOLDOWN, BackendHealthState.ERROR_COOLDOWN})


@dataclass
class BackendHealthRecord:
    state: BackendHealthState = BackendHealthState.ACTIVE
    cooldown_until: float = 0.0


@dataclass(frozen=True)
class BackendHealthSnapshot:
    state: BackendHealthState
    cooldown_remaining_seconds: float


@runtime_checkable
class HealthStore(Protocol):
    """Storage boundary for backend health and cooldown state."""

    async def set_backend_active(self, backend_id: str) -> None: ...

    async def set_backend_cooldown(
        self,
        backend_id: str,
        *,
        state: BackendHealthState,
        cooldown_seconds: float,
    ) -> None: ...

    async def snapshot_backend_health(
        self, backend_ids: list[str]
    ) -> dict[str, BackendHealthSnapshot]: ...

    async def reset(self) -> None: ...


class InMemoryHealthStore:
    """Single-replica in-memory backend health state."""

    def __init__(self) -> None:
        self._state: dict[str, BackendHealthRecord] = {}
        self._lock = asyncio.Lock()

    @property
    def state(self) -> dict[str, BackendHealthRecord]:
        return self._state

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    async def set_backend_active(self, backend_id: str) -> None:
        async with self._lock:
            existing = self._state.get(backend_id)
            if existing is not None and existing.state == BackendHealthState.DISABLED:
                return
            self._state[backend_id] = BackendHealthRecord(
                state=BackendHealthState.ACTIVE,
                cooldown_until=0.0,
            )

    async def set_backend_cooldown(
        self,
        backend_id: str,
        *,
        state: BackendHealthState,
        cooldown_seconds: float,
    ) -> None:
        duration = max(0.0, cooldown_seconds)
        async with self._lock:
            existing = self._state.get(backend_id)
            if existing is not None and existing.state == BackendHealthState.DISABLED:
                return
            self._state[backend_id] = BackendHealthRecord(
                state=state,
                cooldown_until=time.monotonic() + duration,
            )

    async def snapshot_backend_health(
        self, backend_ids: list[str]
    ) -> dict[str, BackendHealthSnapshot]:
        now = time.monotonic()
        snapshots: dict[str, BackendHealthSnapshot] = {}
        async with self._lock:
            for backend_id in backend_ids:
                record = self._state.get(backend_id)
                if record is None:
                    snapshots[backend_id] = BackendHealthSnapshot(BackendHealthState.ACTIVE, 0.0)
                    continue
                if record.state in COOLDOWN_STATES and record.cooldown_until <= now:
                    record = BackendHealthRecord(
                        state=BackendHealthState.ACTIVE, cooldown_until=0.0
                    )
                    self._state[backend_id] = record
                remaining = (
                    max(0.0, record.cooldown_until - now)
                    if record.state in COOLDOWN_STATES
                    else 0.0
                )
                snapshots[backend_id] = BackendHealthSnapshot(record.state, remaining)
        return snapshots

    async def reset(self) -> None:
        async with self._lock:
            self._state.clear()


def cooldown_exhausted_response(
    candidates: list[str],
    snapshots: dict[str, BackendHealthSnapshot],
    *,
    api_error: Callable[[int, str, str], JSONResponse],
) -> JSONResponse | None:
    if not candidates:
        return None
    candidate_states = [snapshots[backend_id] for backend_id in candidates]
    if not candidate_states or any(
        snapshot.state not in COOLDOWN_STATES for snapshot in candidate_states
    ):
        return None
    status_code = (
        429
        if all(snapshot.state == BackendHealthState.QUOTA_COOLDOWN for snapshot in candidate_states)
        else 503
    )
    message = (
        "All configured backends are in quota cooldown"
        if status_code == 429
        else "All configured backends are in cooldown"
    )
    response = api_error(status_code, message, "upstream_unavailable")
    response.headers["retry-after"] = str(
        max(0, math.ceil(min(snapshot.cooldown_remaining_seconds for snapshot in candidate_states)))
    )
    return response
