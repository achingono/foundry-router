"""Request-owned capacity for finite signed preparation and generation stages."""

from __future__ import annotations

import asyncio
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_SLOTS = threading.BoundedSemaphore(2)


class SignedWorkLease:
    """Close releases capacity only after any shielded worker actually completes."""

    def __init__(self) -> None:
        if not _SLOTS.acquire(blocking=False):
            raise ValueError("Provider state preparation is busy")
        self._lock = threading.Lock()
        self._active = False
        self._closed = False
        self._released = False

    def __repr__(self) -> str:
        return "<SignedWorkLease>"

    def start(self) -> None:
        with self._lock:
            if self._closed or self._active:
                raise ValueError("Provider state preparation is unavailable")
            self._active = True

    def finish(self) -> None:
        with self._lock:
            self._active = False
            self._release_closed()

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._release_closed()

    def _release_closed(self) -> None:
        if self._closed and not self._active and not self._released:
            self._released = True
            _SLOTS.release()


class SignedIntakeError(ValueError):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


def check_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise SignedIntakeError(408, "request_timeout", "Request intake exceeded its deadline")


async def bounded_signed_work[T](
    work: Callable[[], T],
    *,
    deadline: float,
    before_submit: Callable[[], None] | None = None,
    lease: SignedWorkLease | None = None,
) -> T:
    """Acquire before scheduling; at most two queued/running executor jobs globally.

    Shield the submitted task so timeout cannot cancel an executor job before its
    release-finally starts. The task owns the slot until work actually finishes.
    """
    check_deadline(deadline)
    owned = lease is None
    try:
        capacity = lease or SignedWorkLease()
        capacity.start()
    except ValueError:
        raise SignedIntakeError(
            503, "provider_state_unavailable", "Provider state preparation is busy"
        ) from None

    ownership_lock = threading.Lock()
    released = False
    started = False

    def release_once() -> None:
        nonlocal released
        with ownership_lock:
            if not released:
                released = True
                capacity.finish()
                if owned:
                    capacity.close()

    def run() -> T:
        nonlocal started
        with ownership_lock:
            started = True
        try:
            check_deadline(deadline)
            return work()
        finally:
            release_once()

    try:
        if before_submit is not None:
            before_submit()
        check_deadline(deadline)
        task = asyncio.create_task(asyncio.to_thread(run))
    except BaseException:
        release_once()
        raise

    def consume(completed: asyncio.Task[T]) -> None:
        with ownership_lock:
            worker_started = started
        if not worker_started:
            release_once()
        if not completed.cancelled():
            completed.exception()

    task.add_done_callback(consume)
    try:
        async with asyncio.timeout_at(deadline):
            result = await asyncio.shield(task)
            check_deadline(deadline)
            return result
    except TimeoutError:
        raise SignedIntakeError(
            408, "request_timeout", "Request intake exceeded its deadline"
        ) from None
