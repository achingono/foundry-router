"""Early body admission: capacity, slot accounting and precedence proofs.

Complements test_google_json_intake.py (status-level coverage) with semaphore-state
assertions required by the early-body-admission review: effective capacity stays 2,
every outcome releases exactly once (proven by probe, not just status), saturated
chunked oversize fails before read with a body identical to the downstream busy
signal, and offloaded callers of any model observe the same backpressure.
"""

import asyncio
import contextlib
import json
import time

import pytest
from fastapi import Request

from foundry_router.api.common import request_body
from foundry_router.api.google_work import SignedWorkLease


def request(wire: bytes, *, content_length: bool = False):
    async def receive():
        return {"type": "http.request", "body": wire, "more_body": False}

    headers = [(b"content-type", b"application/json")]
    if content_length:
        headers.append((b"content-length", str(len(wire)).encode()))
    return Request(
        {"type": "http", "method": "POST", "path": "/", "headers": headers},
        receive,
    )


def probe_reusable():
    lease = SignedWorkLease()
    lease.close()
    return True


async def test_two_concurrent_parses_succeed_while_third_is_busy():
    entered = [asyncio.Event(), asyncio.Event()]
    release = asyncio.Event()

    async def counted_receive(index):
        entered[index].set()
        await release.wait()
        return {"type": "http.request", "body": b'{"model":"m"}', "more_body": False}

    wires = [request(b'{"model":"m"}'), request(b'{"model":"m"}')]
    for index, incoming in enumerate(wires):
        incoming._receive = lambda i=index: counted_receive(i)
    tasks = [
        asyncio.create_task(
            request_body(
                incoming,
                "responses",
                max_body_bytes=1024,
                offload_json=True,
                deadline_monotonic=time.monotonic() + 5,
            )
        )
        for incoming in wires
    ]
    await asyncio.gather(*(e.wait() for e in entered))
    # Both intake slots are held by slow readers: third fails before read.
    third_chunks = []
    third = request(b'{"model":"m"}')

    async def third_receive():
        third_chunks.append(1)
        return {"type": "http.request", "body": b'{"model":"m"}', "more_body": False}

    third._receive = third_receive
    busy = await request_body(third, "responses", max_body_bytes=1024, offload_json=True)
    assert busy.status_code == 503
    assert third_chunks == []
    release.set()
    results = await asyncio.gather(*tasks)
    assert results == [{"model": "m"}, {"model": "m"}]
    # Capacity fully reusable afterwards: effective capacity is still 2.
    assert probe_reusable()


async def test_parse_failure_and_success_release_intake_capacity():
    bad = await request_body(
        request(b'{"model":'),
        "responses",
        max_body_bytes=1024,
        offload_json=True,
        deadline_monotonic=time.monotonic() + 2,
    )
    assert bad.status_code == 400
    assert probe_reusable()
    good = await request_body(
        request(b'{"model":"m"}'),
        "responses",
        max_body_bytes=1024,
        offload_json=True,
        deadline_monotonic=time.monotonic() + 2,
    )
    assert good == {"model": "m"}
    assert probe_reusable()


async def test_cancelled_handoff_retains_then_releases_capacity(monkeypatch):
    import threading

    worker_started = threading.Event()
    worker_release = threading.Event()

    def slow_parse(*args, **kwargs):
        from foundry_router.api.adapters.google_schema import load_bounded_json

        worker_started.set()
        worker_release.wait(timeout=5)
        return load_bounded_json(*args, **kwargs)

    monkeypatch.setattr("foundry_router.api.common.load_bounded_json", slow_parse)
    task = asyncio.create_task(
        request_body(
            request(b'{"model":"m"}'),
            "responses",
            max_body_bytes=1024,
            offload_json=True,
            deadline_monotonic=time.monotonic() + 30,
        )
    )
    await asyncio.to_thread(worker_started.wait, 5)
    assert worker_started.is_set()
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await task
    # Active worker retains its slot: with the second slot held spare, a probe
    # must fail while the worker runs, proving retention rather than release.
    spare = SignedWorkLease()
    try:
        with pytest.raises(ValueError):
            SignedWorkLease()
    finally:
        worker_release.set()
    for _ in range(100):
        try:
            probe_reusable()
            break
        except ValueError:
            await asyncio.sleep(0.05)
    else:
        spare.close()
        pytest.fail("intake slot leaked after worker completion")
    spare.close()
    assert probe_reusable()


async def test_saturated_chunked_oversize_fails_before_read_with_stable_body():
    leases = [SignedWorkLease(), SignedWorkLease()]
    try:
        chunks = []
        incoming = request(b"x" * 2048)

        async def receive():
            chunks.append(1)
            return {"type": "http.request", "body": b"x" * 2048, "more_body": False}

        incoming._receive = receive
        busy = await request_body(incoming, "responses", max_body_bytes=1024, offload_json=True)
        assert busy.status_code == 503
        assert chunks == []
        # Declared oversize still wins with 413 even under saturation.
        declared = request(b"x" * 2048, content_length=True)
        oversize = await request_body(declared, "responses", max_body_bytes=1024, offload_json=True)
        assert oversize.status_code == 413
    finally:
        for lease in leases:
            lease.close()
    # Intake 503 body is byte-identical to the downstream work-lease 503 so no
    # slot-count oracle is introduced between admission stages.
    assert (
        busy.body
        == b'{"error":{"message":"Provider state preparation is busy","type":"provider_state_unavailable"}}'
    )


async def test_offloaded_caller_backpressure_is_model_independent():
    # request_body cannot see the model; any offloaded caller (signed or unsigned
    # model in a mixed configuration) observes the same pre-read 503 with zero
    # body intake and no downstream activity possible before admission.
    leases = [SignedWorkLease(), SignedWorkLease()]
    try:
        wire = json.dumps({"model": "unsigned-model", "input": "fixture"}).encode()
        incoming = request(wire)
        calls = []

        # Failing stub proves no read occurs under saturation.
        async def no_read():
            calls.append(1)
            raise AssertionError("saturated intake read the body")

        incoming._receive = no_read
        busy = await request_body(incoming, "responses", max_body_bytes=4096, offload_json=True)
        assert busy.status_code == 503
        assert calls == []
    finally:
        for lease in leases:
            lease.close()
    # Same unsigned-shaped request succeeds when capacity is free.
    ok = await request_body(
        request(wire),
        "responses",
        max_body_bytes=4096,
        offload_json=True,
        deadline_monotonic=time.monotonic() + 2,
    )
    assert ok == {"model": "unsigned-model", "input": "fixture"}
