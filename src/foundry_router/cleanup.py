"""Bounded independent cleanup protected from repeated caller cancellation."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

DEFAULT_CLEANUP_TIMEOUT_SECONDS = 5.0
CLEANUP_JOIN_SECONDS = 0.1
MAX_CLEANUP_TASKS = 64
_active_cleanup_tasks: set[asyncio.Task[object]] = set()


async def protected_cleanup(
    operations: list[Callable[[], Awaitable[object]]],
    *,
    timeout_seconds: float = DEFAULT_CLEANUP_TIMEOUT_SECONDS,
) -> None:
    """Give every subsystem its own deadline; context-close cannot starve settlement."""

    async def run_one(operation: Callable[[], Awaitable[object]]) -> BaseException | None:
        async def invoke() -> object:
            return await operation()

        if len(_active_cleanup_tasks) >= MAX_CLEANUP_TASKS:
            return RuntimeError("Cleanup capacity exhausted; conservative credit recovery required")
        task = asyncio.create_task(invoke())
        _active_cleanup_tasks.add(task)
        task.add_done_callback(consume_result)
        done, _ = await asyncio.wait({task}, timeout=timeout_seconds)
        if not done:
            task.cancel()
            done, _ = await asyncio.wait({task}, timeout=CLEANUP_JOIN_SECONDS)
            if not done:
                # Non-cooperative dependencies remain tracked; never allow unbounded detachment.
                pass
            else:
                consume_result(task)
            return TimeoutError("Cleanup deadline exhausted; conservative credit recovery required")
        try:
            task.result()
        except BaseException as exc:
            return exc
        return None

    def consume_result(task: asyncio.Task[object]) -> None:
        _active_cleanup_tasks.discard(task)
        if not task.cancelled():
            task.exception()

    async def run_all() -> list[BaseException]:
        results = await asyncio.gather(*(run_one(operation) for operation in operations))
        return [result for result in results if result is not None]

    cleanup = asyncio.create_task(run_all(), name="protected-financial-cleanup")
    cancelled = False
    while not cleanup.done():
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            cancelled = True
    failures = cleanup.result()
    if failures:
        # Prefer financial errors over an unrelated close error; preserve every failure as notes.
        failure = failures[0]
        for other in failures[1:]:
            failure.add_note(f"Independent cleanup failure: {type(other).__name__}")
        raise failure
    if cancelled:
        raise asyncio.CancelledError()
