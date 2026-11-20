"""Bounded completion observations for existing console-log collection.

One lazy process-owned daemon drains a fixed queue. Console backpressure never
runs on the request event loop, and repeated application lifespans do not create
additional blocked logging threads. Delivery is best-effort, not a ledger.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import queue
import sys
import threading
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from foundry_router.logging import redact_dict

if TYPE_CHECKING:
    from collections.abc import Callable

QUEUE_CAPACITY = 256
MAX_LABEL_BYTES = 128
MAX_RECORD_BYTES = 2048
MIN_STATUS = 100
MAX_STATUS = 599
ASCII_CONTROL_LIMIT = 32
ASCII_DELETE = 127
SHUTDOWN_GRACE_SECONDS = 1.0
_PROCESS_LOCK = threading.Lock()
_DISPATCHER: _Dispatcher | None = None


@dataclass
class _Counts:
    submitted: int = 0
    written: int = 0
    failed: int = 0
    dropped: int = 0
    invalid: int = 0
    observation_errors: int = 0


def _write_console(payload: str) -> None:
    # The record is already serialized/redacted; no ambient request context is merged.
    sys.stdout.write(payload + "\n")
    sys.stdout.flush()


class _Dispatcher:
    def __init__(self, writer: Callable[[str], None] = _write_console) -> None:
        self.pid = os.getpid()
        self.instance_id = uuid.uuid4().hex
        self.queue: queue.Queue[tuple[str, _Counts]] = queue.Queue(maxsize=QUEUE_CAPACITY)
        self.writer = writer
        self.thread = threading.Thread(
            target=self._drain, name="foundry-completion-logs", daemon=True
        )
        self.thread.start()

    def _drain(self) -> None:
        while True:
            payload, counts = self.queue.get()
            try:
                self.writer(payload)
            except Exception:
                # Console callbacks are an external boundary. Never log their messages
                # or retry the record; both could disclose content or amplify failure.
                counts.failed += 1
            else:
                counts.written += 1
            finally:
                self.queue.task_done()

    def submit(self, payload: str, counts: _Counts) -> None:
        try:
            self.queue.put_nowait((payload, counts))
        except queue.Full:
            counts.dropped += 1
        else:
            counts.submitted += 1


def _process_dispatcher() -> _Dispatcher:
    global _DISPATCHER  # noqa: PLW0603 -- one bounded dispatcher per process
    with _PROCESS_LOCK:
        if _DISPATCHER is None or _DISPATCHER.pid != os.getpid():
            _DISPATCHER = _Dispatcher()
        return _DISPATCHER


def validate_labels(labels: list[str]) -> None:
    """Configured identifiers may contain model namespaces but never URLs/controls."""
    if any(
        not label
        or len(label.encode()) > MAX_LABEL_BYTES
        or "://" in label
        or any(ord(char) < ASCII_CONTROL_LIMIT or ord(char) == ASCII_DELETE for char in label)
        for label in labels
    ):
        raise ValueError("Completion log identifiers must be bounded configuration identifiers")


def _finite_nonnegative(value: float) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and value >= 0
    )


class CompletionEventSink:
    def __init__(self, settings: Any, *, dispatcher: _Dispatcher | None = None) -> None:
        validate_labels([*settings.models, *settings.backends])
        self._pairs = {
            (model, backend) for model, pool in settings.models.items() for backend in pool.backends
        }
        self._pairs.update((model, "none") for model in settings.models)
        self._dispatcher = dispatcher or _process_dispatcher()
        self._counts = _Counts()
        self._closed = False

    def observe(
        self,
        *,
        model: str,
        backend: str,
        status_code: int,
        latency_seconds: float,
        estimated_cost_usd: float | None,
    ) -> None:
        if self._closed:
            self._counts.dropped += 1
            return
        if (
            type(status_code) is not int
            or not MIN_STATUS <= status_code <= MAX_STATUS
            or not _finite_nonnegative(latency_seconds)
            or (estimated_cost_usd is not None and not _finite_nonnegative(estimated_cost_usd))
        ):
            self._counts.invalid += 1
            return
        if (model, backend) not in self._pairs:
            model, backend = "other", "none"
        record = {
            "event": "foundry_router_completion",
            "schema_version": 1,
            "event_id": uuid.uuid4().hex,
            "process_instance_id": self._dispatcher.instance_id,
            "model": model,
            "backend": backend,
            "status_code": status_code,
            "duration_seconds": latency_seconds,
        }
        if estimated_cost_usd is not None:
            record["estimated_cost_usd"] = estimated_cost_usd
        payload = json.dumps(redact_dict(record), allow_nan=False, separators=(",", ":"))
        if len(payload.encode()) > MAX_RECORD_BYTES:
            self._counts.invalid += 1
            return
        self._dispatcher.submit(payload, self._counts)

    def status(self) -> dict[str, Any]:
        counts = self._counts
        return {
            "enabled": True,
            "process_instance_id": self._dispatcher.instance_id,
            "queue_capacity": QUEUE_CAPACITY,
            "max_record_bytes": MAX_RECORD_BYTES,
            "submitted": counts.submitted,
            "written": counts.written,
            "failed": counts.failed,
            "dropped": counts.dropped,
            "invalid": counts.invalid,
            "observation_errors": counts.observation_errors,
            "pending": max(0, counts.submitted - counts.written - counts.failed),
            "closed": self._closed,
        }

    async def close(self) -> None:
        self._closed = True
        # No join/callback runs on the event loop. A blocked console retains at most
        # one in-flight event plus the shared fixed queue, across all lifespans.
        if self.status()["pending"]:
            await asyncio.sleep(SHUTDOWN_GRACE_SECONDS)


class CompletionMetricsStore:
    """Add one best-effort event after the existing local/OTLP observation completes."""

    def __init__(
        self, store: Any, settings: Any, *, sink: CompletionEventSink | None = None
    ) -> None:
        self._store = store
        self._sink = sink or CompletionEventSink(settings)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._store, name)

    async def observe_request(
        self,
        *,
        model: str,
        backend: str,
        status_code: int,
        latency_seconds: float,
        estimated_cost_usd: float | None,
    ) -> None:
        observation: dict[str, Any] = {
            "model": model,
            "backend": backend,
            "status_code": status_code,
            "latency_seconds": latency_seconds,
            "estimated_cost_usd": estimated_cost_usd,
        }
        await self._store.observe_request(**observation)
        try:
            self._sink.observe(**observation)
        except Exception:
            # An observation sink cannot alter successful metrics/settlement or cause
            # another upstream dispatch. No exception text or request data is logged.
            self._sink._counts.observation_errors += 1

    def export_status(self) -> dict[str, Any]:
        status = (
            self._store.export_status()
            if hasattr(self._store, "export_status")
            else {"enabled": False}
        )
        return {**status, "completion_logs": self._sink.status()}

    async def shutdown(self) -> None:
        try:
            if hasattr(self._store, "shutdown"):
                await self._store.shutdown()
        finally:
            await self._sink.close()
