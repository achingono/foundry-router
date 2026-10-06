"""Outer ASGI output ownership preserves ordinary sends and immutable deadlines."""

import asyncio
import time

import pytest
from starlette.datastructures import State

from foundry_router.api.google_output_delivery import (
    GeneratedOutputDeliveryMiddleware,
    OutputDeliveryOwner,
    delivery_owner,
)
from foundry_router.api.google_output_work import OutputInspectionLease


@pytest.mark.parametrize("deadline", [True, float("inf"), float("nan"), "later"])
def test_invalid_delivery_deadline_cannot_transfer_or_extend(deadline):
    lease = OutputInspectionLease()
    try:
        with pytest.raises(ValueError):
            lease.bind_delivery_deadline(deadline)
        owner = OutputDeliveryOwner()
        with pytest.raises(ValueError):
            owner.transfer(lease, deadline)
        lease.bind_delivery_deadline(time.monotonic() + 1)
        with pytest.raises(ValueError):
            lease.bind_delivery_deadline(time.monotonic() + 2)
    finally:
        lease.close()


async def test_ordinary_http_and_nonhttp_are_unchanged():
    messages = []

    async def inner(_scope, _receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ordinary"})

    async def send(message):
        messages.append(message)

    middleware = GeneratedOutputDeliveryMiddleware(inner)
    for kind in ("http", "websocket"):
        await middleware({"type": kind}, None, send)
    assert [m.get("body") for m in messages] == [None, b"ordinary", None, b"ordinary"]
    assert delivery_owner(State({"_foundry_generated_output_delivery": "untrusted"})) is None


async def test_inner_error_after_transfer_closes_weighted_lease():
    lease = OutputInspectionLease(slots=2)

    async def inner(scope, _receive, send):
        owner = delivery_owner(State(scope["state"]))
        owner.transfer(lease, time.monotonic() + 1)
        _ = send
        raise OSError("synthetic")

    with pytest.raises(OSError):
        await GeneratedOutputDeliveryMiddleware(inner)({"type": "http"}, None, None)
    replacement = OutputInspectionLease(slots=2)
    replacement.close()


async def test_sender_failure_releases_transferred_lease_once():
    lease = OutputInspectionLease(slots=2)

    async def inner(scope, _receive, send):
        owner = delivery_owner(State(scope["state"]))
        owner.transfer(lease, time.monotonic() + 1)
        with pytest.raises(ValueError):
            owner.transfer(lease, time.monotonic() + 2)
        await send({"type": "http.response.start", "status": 200, "headers": []})

    async def send(_message):
        await asyncio.sleep(0)
        raise OSError("synthetic send failure")

    with pytest.raises(OSError):
        await GeneratedOutputDeliveryMiddleware(inner)({"type": "http"}, None, send)
    lease.close()
    replacement = OutputInspectionLease(slots=2)
    replacement.close()


async def test_drain_cleanup_survives_anyio_cancellation_and_runs_once():
    from unittest.mock import AsyncMock

    import anyio

    lease = OutputInspectionLease(slots=2)
    owner = OutputDeliveryOwner()
    owner.transfer(lease, time.monotonic() + 1)
    cleanup = AsyncMock()
    owner.attach_drain_cleanup(cleanup)
    with pytest.raises(ValueError, match="drain"):
        owner.attach_drain_cleanup(cleanup)
    with anyio.CancelScope() as scope:
        scope.cancel()
        await owner.finalize()
    await owner.finalize()
    cleanup.assert_awaited_once()
    with pytest.raises(ValueError):
        owner.attach_drain_cleanup(cleanup)
    replacement = OutputInspectionLease(slots=2)
    replacement.close()


async def test_repeated_task_cancel_does_not_interrupt_drain_cleanup():
    started = asyncio.Event()
    release = asyncio.Event()
    count = 0
    owner = OutputDeliveryOwner()
    owner.transfer(OutputInspectionLease(slots=2), time.monotonic() + 1)

    async def cleanup():
        nonlocal count
        started.set()
        await release.wait()
        count += 1

    owner.attach_drain_cleanup(cleanup)
    task = asyncio.create_task(owner.finalize())
    await started.wait()
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await owner.finalize()
    assert count == 1
    replacement = OutputInspectionLease(slots=2)
    replacement.close()
