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
    """Close releases capacity only after any independent worker actually completes."""

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

    An owned future hands off the independent task's outcome. Caller cancellation
    cancels only that future; the task owns capacity until work actually finishes.
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

    def run(owned_work: Callable[[], T] = work) -> T:
        nonlocal started
        with ownership_lock:
            started = True
        try:
            check_deadline(deadline)
            return owned_work()
        finally:
            del owned_work
            release_once()

    try:
        if before_submit is not None:
            before_submit()
        check_deadline(deadline)
        task = asyncio.create_task(asyncio.to_thread(run))
    except BaseException:
        release_once()
        del run, work, before_submit
        raise

    handoff: asyncio.Future[T] = asyncio.get_running_loop().create_future()

    def consume(completed: asyncio.Task[T], owned_handoff: asyncio.Future[T] = handoff) -> None:
        with ownership_lock:
            worker_started = started
        if not worker_started:
            release_once()
        if completed.cancelled():
            if not owned_handoff.done():
                owned_handoff.cancel()
            return
        # Retrieve late failures even when the caller has already abandoned work.
        # Avoid asyncio.shield's Python 3.14 late-error reporting of raw exceptions.
        error = completed.exception()
        if not owned_handoff.done():
            if error is None:
                owned_handoff.set_result(completed.result())
            else:
                owned_handoff.set_exception(error)

    task.add_done_callback(consume)
    del run
    try:
        async with asyncio.timeout_at(deadline):
            result = await handoff
            check_deadline(deadline)
            return result
    except TimeoutError:
        raise SignedIntakeError(
            408, "request_timeout", "Request intake exceeded its deadline"
        ) from None
    finally:
        del task, handoff, consume, work, before_submit
