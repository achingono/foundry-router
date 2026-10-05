"""Regressions for provider stream errors and request/metadata contracts."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_google_lifecycle import (
    MODEL,
    TEXT_ESTIMATE,
    FakeBackendClient,
    _chat_chunk,
    _execute,
    _google_settings,
    _stores,
)

from foundry_router.api.adapters.google_ai_studio import GoogleAiStudioAdapter, GoogleStreamDecoder
from foundry_router.forwarding import _google_stream_response


@pytest.mark.parametrize("content", ["", "  ", [" "], [{"type": "input_text", "text": " "}]])
async def test_blank_history_rejected_before_egress(content):
    stores = _stores(_google_settings())
    fake = FakeBackendClient()
    response = await _execute(
        {"model": MODEL, "input": [{"role": "user", "content": content}]},
        fake=fake,
        stores=stores,
    )
    assert response.status_code == 422
    assert json.loads(response.body)["error"]["type"] == "invalid_request"
    assert fake.calls == []


@pytest.mark.parametrize("role", ["system", "developer"])
def test_system_parts_flatten_in_order(role):
    adapter = GoogleAiStudioAdapter()
    body = {
        "input": [{"role": role, "content": [{"type": "input_text", "text": "first"}, " second"]}]
    }
    assert adapter.check_request("responses", body) is None
    upstream = adapter.build_upstream_body(
        "responses", body, deployment="synthetic", default_output_tokens=10
    )
    assert upstream["messages"] == [{"role": "system", "content": "first second"}]


@pytest.mark.parametrize(
    "payload",
    [
        {"error": {"message": "PRIVATE_PROVIDER_MARKER", "code": 429}},
        {"choices": [], "usage": "PRIVATE_PROVIDER_MARKER"},
        {"choices": [{"delta": {"content": "text"}}], "usage": 5},
    ],
)
async def test_invalid_provider_events_fail_immediately_and_redact(payload):
    decoder = GoogleStreamDecoder(logical_model=MODEL)
    first = decoder.feed(_chat_chunk("hello"))
    read_after_failure = False

    async def chunks():
        nonlocal read_after_failure
        yield f"data: {json.dumps(payload)}\n\n".encode()
        read_after_failure = True
        yield b"data: [DONE]\n\n"

    credit = SimpleNamespace(finalize_request=AsyncMock())
    quota = SimpleNamespace(finalize_request=AsyncMock())
    cooldown = AsyncMock()
    context = SimpleNamespace(__aexit__=AsyncMock())
    events = [
        event
        async for event in _google_stream_response(
            chunks(),
            decoder,
            first,
            context,
            request_id="review",
            backend_id="gm-a",
            cooldown_seconds=1,
            model=MODEL,
            pricing={},
            status_code=200,
            set_backend_cooldown=cooldown,
            credit_store=credit,
            metrics_store=SimpleNamespace(observe_request=AsyncMock()),
            rate_limit_store=quota,
            fallback_cost_usd=TEXT_ESTIMATE,
        )
    ]
    assert not read_after_failure
    assert b"PRIVATE_PROVIDER_MARKER" not in b"".join(events)
    failures = [json.loads(event[6:]) for event in events if b"response.failed" in event]
    assert len(failures) == 1
    assert failures[0]["response"]["status"] == "failed"
    cooldown.assert_awaited_once()
    credit.finalize_request.assert_awaited_once()
    quota.finalize_request.assert_awaited_once()
    context.__aexit__.assert_awaited_once()


def test_metadata_echo_on_json_and_stream_lifecycle():
    adapter = GoogleAiStudioAdapter()
    metadata = {"trace": "private-trace"}
    body = {"model": MODEL, "input": "hi", "metadata": metadata}
    upstream = adapter.build_upstream_body(
        "responses", body, deployment="synthetic", default_output_tokens=10
    )
    assert "metadata" not in upstream
    result = adapter.translate_success(
        "responses",
        {
            "choices": [
                {"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}
            ]
        },
        logical_model=MODEL,
        metadata=metadata,
    )
    assert result.body["metadata"] == metadata
    decoder = adapter.create_stream_decoder(logical_model=MODEL, metadata=metadata)
    events = decoder.feed(_chat_chunk("hello", finish="stop") + b"data: [DONE]\n\n")
    for event in events:
        payload = json.loads(event[6:])
        if "response" in payload:
            assert payload["response"]["metadata"] == metadata
    failed = adapter.create_stream_decoder(logical_model=MODEL, metadata=metadata)
    failed.feed(_chat_chunk("hello"))
    assert json.loads(failed.build_failure("safe error")[0][6:])["response"]["metadata"] == metadata


@pytest.mark.parametrize("metadata", [{"trace": 1}, {"x" * 65: "value"}, {"key": "x" * 513}])
def test_metadata_limits(metadata):
    adapter = GoogleAiStudioAdapter()
    rejection = adapter.check_request(
        "responses", {"model": MODEL, "input": "hi", "metadata": metadata}
    )
    assert rejection is not None
    assert rejection.status_code == 422


async def test_negative_stream_cost_keeps_estimate():
    decoder = GoogleStreamDecoder(logical_model=MODEL)
    first = decoder.feed(_chat_chunk("hello", finish="stop"))

    async def chunks():
        yield b'data: {"choices":[],"usage":{"prompt_tokens":4,"completion_tokens":2}}\n\ndata: [DONE]\n\n'

    credit = SimpleNamespace(finalize_request=AsyncMock())
    _ = [
        event
        async for event in _google_stream_response(
            chunks(),
            decoder,
            first,
            SimpleNamespace(__aexit__=AsyncMock()),
            request_id="negative",
            backend_id="gm-a",
            cooldown_seconds=1,
            model=MODEL,
            pricing={MODEL: SimpleNamespace(input_per_million=-10, output_per_million=-30)},
            status_code=200,
            set_backend_cooldown=AsyncMock(),
            credit_store=credit,
            metrics_store=SimpleNamespace(observe_request=AsyncMock()),
            fallback_cost_usd=TEXT_ESTIMATE,
        )
    ]
    assert credit.finalize_request.await_args.kwargs["charged_cost_usd"] == TEXT_ESTIMATE
