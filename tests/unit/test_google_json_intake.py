"""Server-owned bounded JSON offload preserves strict intake and deadlines."""

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
        assert too_large.status_code == 413
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
