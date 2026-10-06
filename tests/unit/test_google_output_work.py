"""Generated-output leases retain slots during shielded child work and cancellation."""

import asyncio
import json
import sys
import time

import pytest

from foundry_router.api.google_output_work import OutputInspectionLease
from tests.unit.test_google_output_png import png


class InputPipe:
    def write(self, raw):
        assert raw

    async def drain(self):
        pass

    def close(self):
        pass

    async def wait_closed(self):
        pass


class FakeChild:
    def __init__(self, gate):
        self.stdin = InputPipe()
        self.stdout = self
        self.gate = gate
        self.returncode = None
        self.killed = False
        self.sent = False

    async def read(self, count):
        await self.gate.wait()
        if self.sent:
            return b""
        self.sent = True
        raw = png()
        return json.dumps(
            {"bytes": len(raw), "width": 1024, "height": 1024, "expanded_bytes": 4195328}
        ).encode()[:count]

    async def wait(self):
        self.returncode = 0
        return 0

    def kill(self):
        self.killed = True
        self.returncode = -9


@pytest.mark.parametrize("weighted", [False, True])
async def test_nonqueued_capacity_and_cancel_retains_until_child_done(monkeypatch, weighted):
    monkeypatch.setattr(sys, "platform", "linux")
    gate = asyncio.Event()
    child = FakeChild(gate)

    async def spawn(*_args, **kwargs):
        assert kwargs["env"] == {"PATH": "", "PYTHONDONTWRITEBYTECODE": "1"}
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    first = OutputInspectionLease(slots=2 if weighted else 1)
    second = None if weighted else OutputInspectionLease()
    task = asyncio.create_task(first.inspect(png(), deadline=time.monotonic() + 2))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    first.close()
    with pytest.raises(ValueError, match="busy"):
        OutputInspectionLease()
    gate.set()
    # Bounded poll: the worker releases deterministically once gated, but a
    # fixed sleep flakes under load and a failure would leak slots file-wide.
    async with asyncio.timeout(5):
        while True:
            try:
                third = OutputInspectionLease()
            except ValueError:
                await asyncio.sleep(0.01)
                continue
            break
    assert child.returncode == 0
    third.close()
    if second is not None:
        second.close()


async def test_deadline_kills_and_reaps_before_capacity_reuse(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    child = FakeChild(asyncio.Event())

    async def spawn(*_args, **_kwargs):
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    lease = OutputInspectionLease()
    try:
        with pytest.raises(TimeoutError):
            await lease.inspect(png(), deadline=time.monotonic() + 0.03)
        assert child.killed and child.returncode is not None
    finally:
        lease.close()
    replacement = OutputInspectionLease()
    replacement.close()


@pytest.mark.skipif(sys.platform != "linux", reason="Isolated inspector requires Linux")
async def test_actual_linux_child_inspects_finite_png():
    lease = OutputInspectionLease()
    try:
        facts = await lease.inspect(png(), deadline=time.monotonic() + 2)
        assert facts.decoded_bytes == len(png()) and facts.expanded_bytes == 4195328
    finally:
        lease.close()


async def test_task_submission_failure_releases_slot(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")

    def reject_task(_work):
        raise RuntimeError("task factory failure")

    lease = OutputInspectionLease()
    monkeypatch.setattr(asyncio, "create_task", reject_task)
    with pytest.raises(RuntimeError):
        await lease.inspect(png(), deadline=time.monotonic() + 2)
    lease.close()
    first, second = OutputInspectionLease(), OutputInspectionLease()
    first.close()
    second.close()


@pytest.mark.parametrize("failure", ["write", "read", "overflow", "metadata"])
async def test_child_failures_close_and_release(monkeypatch, failure):
    monkeypatch.setattr(sys, "platform", "linux")
    gate = asyncio.Event()
    gate.set()
    child = FakeChild(gate)
    if failure == "write":

        def write(_raw):
            raise BrokenPipeError("synthetic")

        child.stdin.write = write
    elif failure == "read":

        async def read(_count):
            raise ConnectionResetError("synthetic")

        child.read = read
    elif failure == "overflow":

        async def read(count):
            return b"x" * count

        child.read = read
    else:

        async def read(_count):
            return b"{}" if not child.sent else b""

        async def once(_count):
            if child.sent:
                return b""
            child.sent = True
            return b"{}"

        child.read = once

    async def spawn(*_args, **_kwargs):
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    lease = OutputInspectionLease()
    try:
        with pytest.raises((ValueError, OSError)):
            await lease.inspect(png(), deadline=time.monotonic() + 2)
        assert child.returncode is not None
    finally:
        lease.close()
    replacement = OutputInspectionLease()
    replacement.close()


async def test_exit_race_still_reaps_and_releases(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    child = FakeChild(asyncio.Event())

    async def read(_count):
        raise BrokenPipeError("synthetic read")

    def kill():
        raise ProcessLookupError("already exited")

    child.read = read
    child.kill = kill

    async def spawn(*_args, **_kwargs):
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    lease = OutputInspectionLease()
    with pytest.raises(BrokenPipeError):
        await lease.inspect(png(), deadline=time.monotonic() + 2)
    lease.close()
    assert child.returncode == 0
    first, second = OutputInspectionLease(), OutputInspectionLease()
    first.close()
    second.close()


async def test_delayed_spawn_repeated_caller_cancel_keeps_slot_until_reap(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    spawn_gate = asyncio.Event()
    child = FakeChild(asyncio.Event())

    async def spawn(*_args, **_kwargs):
        await spawn_gate.wait()
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    first, second = OutputInspectionLease(), OutputInspectionLease()
    task = asyncio.create_task(first.inspect(png(), deadline=time.monotonic() + 0.02))
    await asyncio.sleep(0.01)
    task.cancel()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    first.close()
    await asyncio.sleep(0.03)
    with pytest.raises(ValueError, match="busy"):
        OutputInspectionLease()
    spawn_gate.set()
    # Bounded poll for the same file-wide isolation reason as above.
    async with asyncio.timeout(5):
        while True:
            try:
                replacement = OutputInspectionLease()
            except ValueError:
                await asyncio.sleep(0.01)
                continue
            break
    assert child.killed and child.returncode is not None
    replacement.close()
    second.close()


async def test_failed_inspection_does_not_retain_artifact_until_cyclic_gc(monkeypatch):
    import gc
    import weakref

    monkeypatch.setattr(sys, "platform", "linux")
    raw = png()

    class Payload:
        def __len__(self):
            return len(raw)

    payload = Payload()
    reference = weakref.ref(payload)
    lease = OutputInspectionLease()

    class InvalidMetadataChild(FakeChild):
        async def read(self, count):
            if self.sent:
                return b""
            self.sent = True
            return b"{}"[:count]

    child = InvalidMetadataChild(asyncio.Event())

    async def spawn(*_args, **_kwargs):
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        with pytest.raises(ValueError, match="inspector metadata"):
            await lease.inspect(payload, deadline=time.monotonic() + 1)
        del payload
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert reference() is None
    finally:
        lease.close()
        if was_enabled:
            gc.enable()
    replacement = OutputInspectionLease()
    replacement.close()


def test_weighted_capacity_is_atomic_and_double_close_is_idempotent():
    one = OutputInspectionLease()
    with pytest.raises(ValueError, match="busy"):
        OutputInspectionLease(slots=2)
    other = OutputInspectionLease()
    other.close()
    one.close()
    both = OutputInspectionLease(slots=2)
    with pytest.raises(ValueError, match="busy"):
        OutputInspectionLease()
    both.close()
    both.close()
    first, second = OutputInspectionLease(), OutputInspectionLease()
    first.close()
    second.close()


@pytest.mark.parametrize("slots", [0, 3, True, 1.0])
def test_invalid_weighted_capacity_is_rejected(slots):
    with pytest.raises(ValueError, match="capacity"):
        OutputInspectionLease(slots=slots)


def test_weighted_thread_contention_never_leaks_partial_capacity():
    import concurrent.futures
    import threading

    barrier = threading.Barrier(8)

    def compete(index):
        barrier.wait()
        for _ in range(100):
            try:
                lease = OutputInspectionLease(slots=2 if index % 2 else 1)
            except ValueError:
                continue
            lease.close()
            lease.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(compete, range(8)))
    both = OutputInspectionLease(slots=2)
    both.close()
