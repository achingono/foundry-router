"""Existing real route/settlement sites keep one egress when console observation fails."""

import asyncio

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from foundry_router import main
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.metrics.completion import CompletionEventSink, CompletionMetricsStore
from tests.integration.test_compatible_provider_integration import chat, settings
from tests.integration.test_google_adapter_integration import _wire
from tests.unit.test_completion_metrics import CapturingDispatcher


@pytest.fixture(autouse=True)
def reset():
    yield
    asyncio.run(main._reset_backend_health_state())
    asyncio.run(main._reset_credit_state())
    asyncio.run(main._reset_metrics_state())
    asyncio.run(main._reset_rate_limit_state())


@respx.mock
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("sink_fails", [False, True])
def test_response_and_usage_settlement_survive_completion_logging(monkeypatch, stream, sink_fails):
    configured = settings(metered=True)
    _wire(monkeypatch, configured)
    dispatcher = CapturingDispatcher()
    sink = CompletionEventSink(configured, dispatcher=dispatcher)
    metrics = CompletionMetricsStore(InMemoryMetricsStore(), configured, sink=sink)
    monkeypatch.setattr(main, "_metrics_store", metrics)
    if sink_fails:

        def fail(**_values):
            raise OSError("private-logger-error")

        monkeypatch.setattr(sink, "observe", fail)
    if stream:
        payload = b'data: {"choices":[{"delta":{"content":"private-answer"},"finish_reason":"stop"}]}\n\ndata: {"choices":[],"usage":{"prompt_tokens":4,"completion_tokens":2}}\n\ndata: [DONE]\n\n'
        response = httpx.Response(
            200, content=payload, headers={"content-type": "text/event-stream"}
        )
    else:
        response = httpx.Response(200, json=chat("private-answer"))
    route = respx.post("https://a.compatible.test/api/v1/chat/completions").mock(
        return_value=response
    )
    client = TestClient(main.app)
    result = client.post(
        "/openai/v1/responses",
        headers={"api-key": "client-key", "x-request-id": "caller-sensitive-id"},
        json={
            "model": "logical",
            "input": "private-prompt",
            "max_output_tokens": 8,
            "stream": stream,
        },
    )
    assert result.status_code == 200 and route.call_count == 1
    status = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()
    assert status["credit_groups"]["a"]["live"]["debited_usd_total"] == 6
    assert status["credit_groups"]["a"]["live"]["reserved_inflight_usd"] == 0
    if sink_fails:
        assert sink.status()["observation_errors"] == 1 and dispatcher.payloads == []
    else:
        assert len(dispatcher.payloads) == 1
        assert dispatcher.payloads[0]["estimated_cost_usd"] == 6
        assert dispatcher.payloads[0]["status_code"] == 200
        assert all(
            secret not in str(dispatcher.payloads)
            for secret in [
                "private-prompt",
                "private-answer",
                "caller-sensitive-id",
                "client-key",
                "server-a",
            ]
        )
