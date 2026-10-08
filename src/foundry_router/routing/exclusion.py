"""Persistent per-combination failure exclusion (routing-owned, in-memory).

A combination is a ``(backend_id, operation, stream_mode)`` triple. Streaming and
nonstreaming share ``operation="responses"``, so the stream dimension is load-bearing:
excluding by backend alone would kill working traffic. Counters reset on process
restart (documented memory-backed limitation); exclusion persists across selection
rounds with a fixed window, decay on success, and a single telemetry-marked
last-resort probe when exclusion would otherwise empty the candidate set.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any

EXCLUSION_THRESHOLD = 3
EXCLUSION_WINDOW_SECONDS = 1800.0
NOT_FOUND_STATUS = 404
SERVER_ERROR_MIN_STATUS = 500
SERVER_ERROR_MAX_STATUS = 599


def exclusion_stream_mode(body: Any) -> bool:
    """Derive the stream dimension exactly as dispatch does (``stream is True``)."""
    return isinstance(body, dict) and body.get("stream") is True


def classify_exclusion_event(
    status_code: Any,
    *,
    retryable_failure: bool = False,
    confirmed_pre_dispatch: bool = False,
) -> bool:
    """Return True iff a terminal attempt outcome counts toward exclusion.

    Evaluated on translated downstream-facing fields only. Anything never sent,
    quota signaling (429), or caller-shaped input never counts; Azure/Google
    pre-dispatch asymmetry is intended (Google sets the flag pre-dispatch,
    Azure terminal transport errors leave it unset and count). ``retryable_failure``
    is accepted for call-site symmetry and deliberately ignored: retryability
    describes failover handling, not failure ownership, and must not let a future
    reader "fix" the predicate into depending on it.
    """
    _ = retryable_failure
    if confirmed_pre_dispatch:
        return False
    if not isinstance(status_code, int) or isinstance(status_code, bool):
        return False
    return (
        status_code == NOT_FOUND_STATUS
        or SERVER_ERROR_MIN_STATUS <= status_code <= SERVER_ERROR_MAX_STATUS
    )


@dataclass
class _CombinationRecord:
    count: int = 0
    excluded_until_monotonic: float = 0.0
    excluded_since_monotonic: float = 0.0
    excluded_until_wall: float = 0.0
    generation: int = 0
    probe_token: str | None = None


@dataclass(frozen=True)
class AdmissionTicket:
    key: tuple[str, str, bool]
    epoch: int
    generation: int
    probe_token: str | None = None


@dataclass
class ExclusionFilterResult:
    eligible: list[str]
    excluded: dict[str, dict[str, Any]]
    probe_backend_id: str | None = None
    probe_candidates: tuple[str, ...] = ()


class CombinationExclusionStore:
    """Consecutive-failure exclusion with decay, fixed windows and one probe."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._records: dict[tuple[str, str, bool], _CombinationRecord] = {}
        self._epoch = 0

    @staticmethod
    def _expire(record: _CombinationRecord, now: float) -> None:
        if record.excluded_until_monotonic and now >= record.excluded_until_monotonic:
            record.excluded_until_monotonic = 0.0
            record.excluded_since_monotonic = 0.0
            record.excluded_until_wall = 0.0
            record.count = 0
            record.probe_token = None
            record.generation += 1

    async def admit(
        self, backend_id: str, operation: str, stream_mode: bool, *, probe: bool = False
    ) -> AdmissionTicket | None:
        """Claim a probe atomically after quota/credit admission, or admit ordinary work."""
        key = (backend_id, operation, stream_mode)
        async with self._lock:
            record = self._records.get(key)
            if record is not None:
                self._expire(record, time.monotonic())
            if record is not None and record.excluded_until_monotonic:
                if not probe or record.probe_token is not None:
                    return None
                record.probe_token = uuid.uuid4().hex
                return AdmissionTicket(key, self._epoch, record.generation, record.probe_token)
            return AdmissionTicket(key, self._epoch, record.generation if record else 0)

    async def release(self, ticket: AdmissionTicket | None) -> None:
        """Release an unused/cancelled probe without changing its exclusion window."""
        if ticket is None or ticket.probe_token is None:
            return
        async with self._lock:
            record = self._records.get(ticket.key)
            if (
                ticket.epoch == self._epoch
                and record is not None
                and record.generation == ticket.generation
                and record.probe_token == ticket.probe_token
            ):
                record.probe_token = None

    async def record_attempt(  # noqa: PLR0913, PLR0912 -- explicit generation-fenced outcome matrix
        self,
        backend_id: str,
        operation: str,
        stream_mode: bool,
        *,
        success: bool,
        countable_failure: bool,
        ticket: AdmissionTicket | None = None,
    ) -> str | None:
        """Record an outcome; return ``"entered"``/``"decayed"``/``"cleared"``.

        Success on a currently excluded triple can only be a probe: it clears
        the window and the count. Countable failure on an excluded triple is a
        failed probe: it re-arms a fresh window without double-counting an entry.
        """
        now = time.monotonic()
        wall = time.time()
        async with self._lock:
            record: _CombinationRecord | None = self._records.get(
                (backend_id, operation, stream_mode)
            )
            if record is not None:
                self._expire(record, now)
            if ticket is not None and (
                ticket.key != (backend_id, operation, stream_mode)
                or ticket.epoch != self._epoch
                or ticket.generation != (record.generation if record else 0)
                or (
                    ticket.probe_token is not None
                    and (record is None or record.probe_token != ticket.probe_token)
                )
            ):
                return None
            if record is None:
                if not countable_failure:
                    return None
                record = _CombinationRecord()
                self._records[(backend_id, operation, stream_mode)] = record
            excluded = record.excluded_until_monotonic > now
            if excluded and ticket is not None and ticket.probe_token is None:
                return None
            if ticket is not None and ticket.probe_token is not None:
                record.probe_token = None
            transition: str | None = None
            if success:
                if excluded:
                    record.excluded_until_monotonic = 0.0
                    record.excluded_since_monotonic = 0.0
                    record.excluded_until_wall = 0.0
                    record.count = 0
                    record.generation += 1
                    transition = "cleared"
                elif record.count > 0:
                    record.count -= 1
                    transition = "decayed"
            elif countable_failure:
                if excluded:
                    record.excluded_until_monotonic = now + EXCLUSION_WINDOW_SECONDS
                    record.excluded_since_monotonic = now
                    record.excluded_until_wall = wall + EXCLUSION_WINDOW_SECONDS
                else:
                    record.count += 1
                    if (
                        record.count >= EXCLUSION_THRESHOLD
                        and record.excluded_until_monotonic == 0.0
                    ):
                        record.excluded_until_monotonic = now + EXCLUSION_WINDOW_SECONDS
                        record.excluded_since_monotonic = now
                        record.excluded_until_wall = wall + EXCLUSION_WINDOW_SECONDS
                        record.generation += 1
                        transition = "entered"
            return transition

    async def filter_candidates(
        self,
        backend_ids: list[str],
        operation: str,
        stream_mode: bool,
    ) -> ExclusionFilterResult:
        """Split candidates; probe the least-recently-excluded when all excluded."""
        now = time.monotonic()
        async with self._lock:
            for entry in list(self._records.values()):
                self._expire(entry, now)
            eligible: list[str] = []
            excluded: dict[str, dict[str, Any]] = {}
            for backend_id in backend_ids:
                record: _CombinationRecord | None = self._records.get(
                    (backend_id, operation, stream_mode)
                )
                if record is not None and record.excluded_until_monotonic > now:
                    excluded[backend_id] = {
                        "consecutive_failures": record.count,
                        "excluded_until_wall": record.excluded_until_wall,
                        "excluded_since_monotonic": record.excluded_since_monotonic,
                        "probe_inflight": record.probe_token is not None,
                    }
                else:
                    eligible.append(backend_id)
            probe = None
            probe_candidates: tuple[str, ...] = ()
            if not eligible and excluded:
                probe_candidates = tuple(
                    sorted(
                        (
                            backend
                            for backend in excluded
                            if not excluded[backend]["probe_inflight"]
                        ),
                        key=lambda backend: (
                            excluded[backend]["excluded_since_monotonic"],
                            backend,
                        ),
                    )
                )
                eligible.extend(probe_candidates)
                probe = probe_candidates[0] if probe_candidates else None
            return ExclusionFilterResult(
                eligible=eligible,
                excluded=excluded,
                probe_backend_id=probe,
                probe_candidates=probe_candidates,
            )

    async def snapshot(self) -> dict[tuple[str, str, bool], dict[str, Any]]:
        now = time.monotonic()
        async with self._lock:
            for record in self._records.values():
                self._expire(record, now)
            return {
                key: {
                    "consecutive_failures": record.count,
                    "excluded": bool(record.excluded_until_monotonic > now),
                    "excluded_until_wall": record.excluded_until_wall or None,
                    "probe_inflight": record.probe_token is not None,
                }
                for key, record in self._records.items()
                if record.count > 0 or record.excluded_until_monotonic > now
            }

    async def reset(self) -> None:
        async with self._lock:
            self._records.clear()
            self._epoch += 1


__all__ = [
    "EXCLUSION_THRESHOLD",
    "EXCLUSION_WINDOW_SECONDS",
    "CombinationExclusionStore",
    "ExclusionFilterResult",
    "classify_exclusion_event",
    "exclusion_stream_mode",
]
