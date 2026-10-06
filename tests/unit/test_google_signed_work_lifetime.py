"""Signed worker payload lifetime and late exception handling without cyclic GC."""

import asyncio
import gc
import threading
import time
import weakref

import pytest

from foundry_router.api.google_work import SignedIntakeError, SignedWorkLease, bounded_signed_work


class Payload:
    pass


@pytest.mark.parametrize("fails", [False, True])
async def test_completed_job_drops_payload_without_cyclic_gc(fails):
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        payload = Payload()
        reference = weakref.ref(payload)

        def fail(_owned=payload):
            if fails:
                raise ValueError("synthetic failure")
            return 7

        if fails:
            with pytest.raises(ValueError):
                await bounded_signed_work(fail, deadline=time.monotonic() + 1)
        else:
            assert await bounded_signed_work(fail, deadline=time.monotonic() + 1) == 7
        del payload, fail
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert reference() is None
    finally:
        if was_enabled:
            gc.enable()


@pytest.mark.parametrize("cancel", [False, True])
async def test_active_job_retains_payload_capacity_and_consumes_late_failure(cancel):
    was_enabled = gc.isenabled()
    gc.disable()
    release = threading.Event()
    entered = asyncio.Event()
    finished = asyncio.Event()
    loop = asyncio.get_running_loop()
    reported = []
    original_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: reported.append(context))
    lease = SignedWorkLease()
    try:
        payload = Payload()
        reference = weakref.ref(payload)

        def work(_owned=payload):
            loop.call_soon_threadsafe(entered.set)
            release.wait(2)
            loop.call_soon_threadsafe(finished.set)
            raise ValueError("PRIVATE_LATE_FAILURE")

        task = asyncio.create_task(
            bounded_signed_work(
                work,
                deadline=time.monotonic() + (1 if cancel else 0.1),
                lease=lease,
            )
        )
        await asyncio.wait_for(entered.wait(), 1)
        if cancel:
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else SignedIntakeError):
            await task
        lease.close()
        del payload, work, task
        assert reference() is not None
        other = SignedWorkLease()
        try:
            with pytest.raises(ValueError, match="busy"):
                SignedWorkLease()
        finally:
            other.close()
        release.set()
        await asyncio.wait_for(finished.wait(), 1)
        await asyncio.to_thread(time.sleep, 0.02)
        for _ in range(10):
            await asyncio.sleep(0)
        assert not reported
        assert reference() is None
        replacement = SignedWorkLease()
        replacement.close()
    finally:
        release.set()
        lease.close()
        loop.set_exception_handler(original_handler)
        if was_enabled:
            gc.enable()


@pytest.mark.parametrize("fails", [False, True])
async def test_completion_races_caller_cancellation_without_late_reports(monkeypatch, fails):
    loop = asyncio.get_running_loop()
    original_handler = loop.get_exception_handler()
    reported = []
    loop.set_exception_handler(lambda _loop, context: reported.append(context))

    async def completion(_run):
        # Both caller cancellation and worker completion are scheduled in this turn.
        loop.call_soon(caller.cancel)
        if fails:
            raise ValueError("PRIVATE_RACE_FAILURE")
        return 9

    monkeypatch.setattr(asyncio, "to_thread", completion)
    try:
        caller = asyncio.create_task(bounded_signed_work(lambda: 9, deadline=time.monotonic() + 1))
        with pytest.raises(asyncio.CancelledError):
            await caller
        for _ in range(4):
            await asyncio.sleep(0)
        assert not reported
        leases = [SignedWorkLease(), SignedWorkLease()]
        for lease in leases:
            lease.close()
    finally:
        loop.set_exception_handler(original_handler)


async def test_cancelled_inner_task_before_submission_releases_capacity(monkeypatch):
    async def cancelled(_run):
        raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "to_thread", cancelled)
    for _ in range(3):
        with pytest.raises(asyncio.CancelledError):
            await bounded_signed_work(
                lambda: pytest.fail("cancelled job ran"), deadline=time.monotonic() + 1
            )
    leases = [SignedWorkLease(), SignedWorkLease()]
    for lease in leases:
        lease.close()


async def test_abandoned_delayed_submission_keeps_capacity_until_task_finishes(monkeypatch):
    original = asyncio.to_thread
    queued = asyncio.Event()
    release = asyncio.Event()
    completed = asyncio.Event()

    async def delayed(run):
        queued.set()
        try:
            await release.wait()
            return await original(run)
        finally:
            completed.set()

    monkeypatch.setattr(asyncio, "to_thread", delayed)
    caller = asyncio.create_task(bounded_signed_work(lambda: 3, deadline=time.monotonic() + 1))
    try:
        await asyncio.wait_for(queued.wait(), 1)
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller
        other = SignedWorkLease()
        try:
            with pytest.raises(ValueError, match="busy"):
                SignedWorkLease()
        finally:
            other.close()
        release.set()
        await asyncio.wait_for(completed.wait(), 1)
        await asyncio.sleep(0)
        leases = [SignedWorkLease(), SignedWorkLease()]
        for lease in leases:
            lease.close()
    finally:
        release.set()
