"""Opt-in Google failover counts independent dispatches and stops at public output."""

import json

import pytest
from pydantic import ValidationError

from foundry_router.config import BackendConfig, Settings
from tests.unit.test_google_lifecycle import (
    MODEL,
    FakeBackendClient,
    FakeStreamContext,
    FakeUpstream,
    _chat_chunk,
    _chat_ok,
    _execute,
    _google_settings,
    _quota_used,
    _stores,
)


def config(enabled=True):
    original = _google_settings()
    backends = json.loads(original.backends_json)
    for backend in backends.values():
        backend.update(credit_metered=False, google_pre_output_failover=enabled)
    return Settings(**{**original.model_dump(), "backends_json": json.dumps(backends)})


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("status", [500, 502, 503, 504])
async def test_pre_output_failure_admits_second_project_and_retains_quota(stream, status):
    stores = _stores(config())
    fake = FakeBackendClient()
    chunks = [
        _chat_chunk("ready"),
        _chat_chunk(finish="stop"),
        b'data: {"choices":[],"usage":{"prompt_tokens":4,"completion_tokens":2,"total_tokens":6}}\n\n',
        b"data: [DONE]\n\n",
    ]
    fake.handler = lambda backend, *_: FakeStreamContext(
        FakeUpstream(status, body=b"error")
        if backend == "gm-a"
        else FakeUpstream(body=json.dumps(_chat_ok()).encode(), chunks=chunks if stream else None)
    )
    response = await _execute(
        {"model": MODEL, "input": "hi", "stream": stream}, fake=fake, stores=stores
    )
    if stream:
        assert b"response.completed" in b"".join([piece async for piece in response.body_iterator])
    assert response.status_code == 200
    assert [c[0] for c in fake.calls] == ["gm-a", "gm-b"]
    assert await _quota_used(stores.rate, "pa") == 1
    assert await _quota_used(stores.rate, "pb") == 1
    assert all(context.closed for context in fake.contexts)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 501, 505])
async def test_other_failures_are_terminal(status):
    stores = _stores(config())
    fake = FakeBackendClient()
    fake.handler = lambda *_: FakeStreamContext(FakeUpstream(status, body=b"error"))
    await _execute({"model": MODEL, "input": "hi"}, fake=fake, stores=stores)
    assert len(fake.calls) == 1


async def test_default_off_and_two_attempt_exhaustion():
    for enabled, expected in [(False, 1), (True, 2)]:
        stores = _stores(config(enabled))
        fake = FakeBackendClient()
        fake.handler = lambda *_: FakeStreamContext(FakeUpstream(503, body=b"error"))
        response = await _execute({"model": MODEL, "input": "hi"}, fake=fake, stores=stores)
        assert response.status_code == 503 and len(fake.calls) == expected


async def test_failure_after_public_output_never_failovers():
    stores = _stores(config())
    fake = FakeBackendClient()
    fake.handler = lambda *_: FakeStreamContext(
        FakeUpstream(chunks=[_chat_chunk("ready"), b"data: invalid\n\n"])
    )
    response = await _execute(
        {"model": MODEL, "input": "hi", "stream": True}, fake=fake, stores=stores
    )
    wire = b"".join([piece async for piece in response.body_iterator])
    assert b"response.output_text.delta" in wire and b"response.failed" in wire
    assert len(fake.calls) == 1


@pytest.mark.parametrize(
    "provider,metered",
    [("azure_foundry", False), ("openai_compatible", False), ("google_ai_studio", True)],
)
def test_flag_rejects_other_providers_and_metered_credit(provider, metered):
    with pytest.raises(ValidationError):
        BackendConfig(
            provider=provider,
            endpoint="https://example.test",
            credential="synthetic",
            deployment="m",
            credit_metered=metered,
            google_pre_output_failover=True,
        )
