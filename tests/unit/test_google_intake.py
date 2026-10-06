"""No queued caller amplification and finite ownership after timeout/cancellation."""

import asyncio
import threading
import time

import pytest

from foundry_router.api.google_state import check_state_deadline
from foundry_router.api.google_work import SignedIntakeError, bounded_signed_work


@pytest.mark.parametrize("cancel", [False, True])
async def test_abandoned_work_retains_slot_until_worker_finishes(cancel):
    loop = asyncio.get_running_loop()
    entered = [asyncio.Event(), asyncio.Event()]
    release = threading.Event()
    finished = [asyncio.Event(), asyncio.Event()]

    def work(index):
        loop.call_soon_threadsafe(entered[index].set)
        try:
            assert release.wait(timeout=2)
            return index
        finally:
            loop.call_soon_threadsafe(finished[index].set)

    deadlines = [time.monotonic() + (2 if cancel else 0.1), time.monotonic() + 2]
    tasks = [
        asyncio.create_task(bounded_signed_work(lambda i=i: work(i), deadline=deadlines[i]))
        for i in range(2)
    ]
    try:
        async with asyncio.timeout(1):
            await asyncio.gather(*(event.wait() for event in entered))
        if cancel:
            tasks[0].cancel()
            with pytest.raises(asyncio.CancelledError):
                await tasks[0]
        else:
            with pytest.raises(SignedIntakeError) as error:
                await tasks[0]
            assert error.value.status == 408
        with pytest.raises(SignedIntakeError) as error:
            await bounded_signed_work(
                lambda: pytest.fail("queued saturated work"),
                deadline=time.monotonic() + 1,
                before_submit=lambda: pytest.fail("saturated snapshot"),
            )
        assert error.value.status == 503
        release.set()
        assert await tasks[1] == 1
        async with asyncio.timeout(1):
            await asyncio.gather(*(event.wait() for event in finished))
        # Give the shielded abandoned task its completion callback turn.
        await asyncio.sleep(0)
        assert (
            await bounded_signed_work(lambda: "recovered", deadline=time.monotonic() + 1)
            == "recovered"
        )
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_worker_exception_releases_slot_and_deadline_checks_fail_closed():
    def fail():
        raise ValueError("fixture")

    with pytest.raises(ValueError, match="fixture"):
        await bounded_signed_work(fail, deadline=time.monotonic() + 1)
    assert await bounded_signed_work(lambda: 1, deadline=time.monotonic() + 1) == 1
    with pytest.raises(SignedIntakeError):
        await bounded_signed_work(
            lambda: pytest.fail("expired work"), deadline=time.monotonic() - 1
        )
    with pytest.raises(TimeoutError):
        check_state_deadline(time.monotonic() - 1)


async def test_executor_submission_failure_releases_slot(monkeypatch):
    original = asyncio.to_thread

    async def unavailable(*_args, **_kwargs):
        raise RuntimeError("executor unavailable")

    monkeypatch.setattr(asyncio, "to_thread", unavailable)
    for _ in range(3):
        with pytest.raises(RuntimeError, match="executor unavailable"):
            await bounded_signed_work(lambda: 1, deadline=time.monotonic() + 1)
    monkeypatch.setattr(asyncio, "to_thread", original)
    assert await bounded_signed_work(lambda: 1, deadline=time.monotonic() + 1) == 1


async def test_snapshot_failure_releases_slot_and_saturation_skips_snapshot():
    def fail_snapshot():
        raise ValueError("snapshot failed")

    for _ in range(3):
        with pytest.raises(ValueError, match="snapshot failed"):
            await bounded_signed_work(
                lambda: 1, deadline=time.monotonic() + 1, before_submit=fail_snapshot
            )
    assert await bounded_signed_work(lambda: 1, deadline=time.monotonic() + 1) == 1


async def test_request_owned_capacity_spans_stages_and_rejects_closed_reuse():
    from foundry_router.api.google_work import SignedWorkLease

    leases = [SignedWorkLease(), SignedWorkLease()]
    try:
        for lease in leases:
            assert (
                await bounded_signed_work(lambda: 1, deadline=time.monotonic() + 1, lease=lease)
                == 1
            )
        with pytest.raises(ValueError):
            SignedWorkLease()
        for lease in leases:
            assert (
                await bounded_signed_work(lambda: 2, deadline=time.monotonic() + 1, lease=lease)
                == 2
            )
        leases[0].close()
        with pytest.raises(SignedIntakeError):
            await bounded_signed_work(lambda: 1, deadline=time.monotonic() + 1, lease=leases[0])
        replacement = SignedWorkLease()
        replacement.close()
    finally:
        for lease in leases:
            lease.close()


async def test_closed_lease_with_running_cancelled_worker_holds_capacity():
    from foundry_router.api.google_work import SignedWorkLease

    leases = [SignedWorkLease(), SignedWorkLease()]
    loop = asyncio.get_running_loop()
    entered = asyncio.Event()
    completed = asyncio.Event()
    release = threading.Event()

    def work():
        loop.call_soon_threadsafe(entered.set)
        try:
            assert release.wait(timeout=2)
        finally:
            loop.call_soon_threadsafe(completed.set)

    task = asyncio.create_task(
        bounded_signed_work(work, deadline=time.monotonic() + 2, lease=leases[0])
    )
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        leases[0].close()
        with pytest.raises(ValueError):
            SignedWorkLease()
        release.set()
        await asyncio.wait_for(completed.wait(), timeout=1)
        await asyncio.sleep(0)
        replacement = SignedWorkLease()
        replacement.close()
    finally:
        release.set()
        for lease in leases:
            lease.close()
        await asyncio.gather(task, return_exceptions=True)
