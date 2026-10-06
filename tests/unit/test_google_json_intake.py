"""Server-owned bounded JSON offload preserves strict intake and deadlines."""

import asyncio
import json
import time

import pytest
from fastapi import Request

from foundry_router.api.common import request_body
from foundry_router.api.google_work import SignedWorkLease


def request(wire: bytes):
    async def receive():
        return {"type": "http.request", "body": wire, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"content-type", b"application/json")],
        },
        receive,
    )


@pytest.mark.parametrize("offload", [False, True])
@pytest.mark.parametrize(
    "wire", [b'{"model":"m","model":"other"}', b'{"model":"m","input":NaN}', b'{"model":', b"[]"]
)
async def test_strict_malformed_json_equal_errors(offload, wire):
    result = await request_body(
        request(wire),
        "responses",
        max_body_bytes=1024,
        deadline_monotonic=time.monotonic() + 1,
        offload_json=offload,
    )
    assert result.status_code == 400


async def test_saturation_before_parse_and_ordinary_default_stays_usable():
    leases = [SignedWorkLease(), SignedWorkLease()]
    wire = json.dumps({"model": "m", "input": "fixture"}).encode()
    try:
        busy = await request_body(
            request(wire),
            "responses",
            max_body_bytes=1024,
            deadline_monotonic=time.monotonic() + 1,
            offload_json=True,
        )
        assert busy.status_code == 503
        ordinary = await request_body(
            request(wire), "responses", max_body_bytes=1024, deadline_monotonic=time.monotonic() + 1
        )
        assert ordinary == {"model": "m", "input": "fixture"}
        too_large = await request_body(
            request(wire),
            "responses",
            max_body_bytes=1,
            deadline_monotonic=time.monotonic() + 1,
            offload_json=True,
        )
        assert too_large.status_code == 503
        declared = request(wire)
        declared.scope["headers"].append((b"content-length", str(len(wire)).encode()))
        assert (
            await request_body(declared, "responses", max_body_bytes=1, offload_json=True)
        ).status_code == 413
    finally:
        for lease in leases:
            lease.close()


async def test_expired_deadline_never_dispatches_parser(monkeypatch):
    def parser(*_args, **_kwargs):
        pytest.fail("expired parser ran")

    monkeypatch.setattr("foundry_router.api.common.load_bounded_json", parser)
    result = await request_body(
        request(b'{"model":"m"}'),
        "responses",
        max_body_bytes=1024,
        deadline_monotonic=time.monotonic() - 1,
        offload_json=True,
    )
    assert result.status_code == 408


async def test_parse_receives_immutable_bytes_and_runs_off_event_loop(monkeypatch):
    import threading

    from foundry_router.api.adapters.google_schema import load_bounded_json

    main_thread = threading.get_ident()
    observed = []

    def parse(*args, **kwargs):
        observed.append(threading.get_ident())
        return load_bounded_json(*args, **kwargs)

    monkeypatch.setattr("foundry_router.api.common.load_bounded_json", parse)
    result = await request_body(
        request(b'{"model":"m"}'),
        "responses",
        max_body_bytes=1024,
        deadline_monotonic=time.monotonic() + 1,
        offload_json=True,
    )
    assert result == {"model": "m"}
    assert observed and all(thread != main_thread for thread in observed)


async def test_busy_intake_does_not_read_or_allocate_body(monkeypatch):
    def allocate():
        pytest.fail("busy body allocation")

    async def receive():
        pytest.fail("busy body receive")

    incoming = request(b"")
    incoming._receive = receive
    monkeypatch.setattr("foundry_router.api.common.bytearray", allocate, raising=False)
    leases = [SignedWorkLease(), SignedWorkLease()]
    try:
        result = await request_body(incoming, "responses", max_body_bytes=1024, offload_json=True)
        assert result.status_code == 503
    finally:
        for lease in leases:
            lease.close()


async def test_two_slow_readers_hold_capacity_until_original_deadline():
    entered = [asyncio.Event(), asyncio.Event()]

    async def receive(index):
        entered[index].set()
        await asyncio.Event().wait()

    requests = [request(b""), request(b"")]
    for index, incoming in enumerate(requests):
        incoming._receive = lambda i=index: receive(i)
    tasks = [
        asyncio.create_task(
            request_body(
                incoming,
                "responses",
                max_body_bytes=1024,
                offload_json=True,
                deadline_monotonic=time.monotonic() + 0.1,
            )
        )
        for incoming in requests
    ]
    await asyncio.gather(*(event.wait() for event in entered))
    busy = await request_body(request(b""), "responses", max_body_bytes=1024, offload_json=True)
    assert busy.status_code == 503
    assert [result.status_code for result in await asyncio.gather(*tasks)] == [408, 408]
    leases = [SignedWorkLease(), SignedWorkLease()]
    for lease in leases:
        lease.close()


@pytest.mark.parametrize("disconnect", [False, True])
async def test_chunk_overflow_and_disconnect_release_intake_capacity(disconnect):
    from starlette.requests import ClientDisconnect

    incoming = request(b"x" * 2048)
    if disconnect:

        async def receive():
            return {"type": "http.disconnect"}

        incoming._receive = receive
        with pytest.raises(ClientDisconnect):
            await request_body(incoming, "responses", max_body_bytes=1024, offload_json=True)
    else:
        result = await request_body(incoming, "responses", max_body_bytes=1024, offload_json=True)
        assert result.status_code == 413
    leases = [SignedWorkLease(), SignedWorkLease()]
    for lease in leases:
        lease.close()


async def test_oversized_chunk_is_not_copied_into_router_buffer(monkeypatch):
    class BoundedBuffer(bytearray):
        def extend(self, _chunk):
            pytest.fail("oversized chunk copied")

    monkeypatch.setattr("foundry_router.api.common.bytearray", BoundedBuffer, raising=False)
    result = await request_body(request(b"x" * 2048), "responses", max_body_bytes=1024)
    assert result.status_code == 413
