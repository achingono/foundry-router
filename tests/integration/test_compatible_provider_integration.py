"""Actual API-to-compatible-wire routing, SSE and financial failure behavior."""

import asyncio
import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from foundry_router.config import Settings
from foundry_router.main import (
    _reset_backend_health_state,
    _reset_credit_state,
    _reset_metrics_state,
    _reset_rate_limit_state,
    app,
)
from tests.integration.test_google_adapter_integration import _wire
from tests.unit.test_google_lifecycle import (
    FakeBackendClient,
    FakeStreamContext,
    FakeUpstream,
    _execute,
    _stores,
)


@pytest.fixture(autouse=True)
def reset():
    yield
    asyncio.run(_reset_backend_health_state())
    asyncio.run(_reset_credit_state())
    asyncio.run(_reset_metrics_state())
    asyncio.run(_reset_rate_limit_state())


def settings(*, second=False, operations=None, metered=False):
    ids = ["a", "b"] if second else ["a"]
    backends = {
        key: {
            "provider": "openai_compatible",
            "endpoint": f"https://{key}.compatible.test/api/v1",
            "credential": f"server-{key}",
            "deployment": f"organization/model-{key}",
            "credit_metered": metered,
            "quota_group": key,
            "supported_operations": operations or ["responses"],
        }
        for key in ids
    }
    return Settings(
        backends_json=json.dumps(backends),
        models_json=json.dumps({"logical": {"backends": dict.fromkeys(ids, 1)}}),
        model_aliases_json='{"alias":"logical"}',
        client_api_keys_json='["client-key"]',
        admin_api_keys_json='["admin-key"]',
        pricing_json='{"logical":{"input_per_million":1000000,"output_per_million":1000000}}'
        if metered
        else "{}",
        backend_cycle_start_day_json=json.dumps(dict.fromkeys(ids, 1)) if metered else "{}",
        backend_cycle_allowance_usd_json=json.dumps(dict.fromkeys(ids, 1000)) if metered else "{}",
        backend_initial_estimated_remaining_usd_json=json.dumps(dict.fromkeys(ids, 1000))
        if metered
        else "{}",
        retry_attempts=2,
        quota_group_rate_limits_json=json.dumps({key: {"rpm": 20, "tpm": 10000} for key in ids}),
    )


def chat(text="answer", usage=True):
    body = {
        "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}]
    }
    if usage:
        body["usage"] = {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}
    return body


@respx.mock
@pytest.mark.parametrize("stream", [False, True])
def test_alias_responses_actual_model_bearer_and_usage(monkeypatch, stream):
    _wire(monkeypatch, settings())
    if stream:
        payload = b'data: {"choices":[{"delta":{"content":"answer"},"finish_reason":"stop"}]}\n\ndata: {"choices":[],"usage":{"prompt_tokens":4,"completion_tokens":2}}\n\ndata: [DONE]\n\n'
        upstream = httpx.Response(
            200, content=payload, headers={"content-type": "text/event-stream"}
        )
    else:
        upstream = httpx.Response(200, json=chat())
    route = respx.post("https://a.compatible.test/api/v1/chat/completions").mock(
        return_value=upstream
    )
    response = TestClient(app).post(
        "/openai/v1/responses",
        headers={"api-key": "client-key", "x-goog-api-key": "caller-secret"},
        json={"model": "alias", "input": "synthetic", "max_output_tokens": 8, "stream": stream},
    )
    assert response.status_code == 200
    assert route.call_count == 1
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer server-a"
    assert "x-goog-api-key" not in request.headers and "api-key" not in request.headers
    body = json.loads(request.content)
    assert body["model"] == "organization/model-a" and body["max_completion_tokens"] == 8
    if stream:
        assert body["stream_options"] == {"include_usage": True}
        events = [
            json.loads(event.split("data: ")[1]) for event in response.text.strip().split("\n\n")
        ]
        public = events[-1]["response"]
        assert events[-1]["type"] == "response.completed"
    else:
        public = response.json()
    assert public["model"] == "logical" and public["usage"]["total_tokens"] == 6
    assert public["output"][0]["content"][0]["text"] == "answer"
    status = TestClient(app).get("/admin/status", headers={"x-admin-key": "admin-key"}).json()
    assert "server-a" not in json.dumps(status)


@respx.mock
def test_embeddings_namespaced_model_dimensions_and_usage(monkeypatch):
    _wire(monkeypatch, settings(operations=["embeddings"]))
    route = respx.post("https://a.compatible.test/api/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"index": 0, "embedding": [0.5, 1.0]},
                    {"index": 1, "embedding": [1.5, 2.0]},
                ],
                "usage": {"prompt_tokens": 4},
            },
        )
    )
    response = TestClient(app).post(
        "/openai/v1/embeddings",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": ["one", "two"], "dimensions": 2},
    )
    assert response.status_code == 200 and response.json()["usage"]["prompt_tokens"] == 4
    assert json.loads(route.calls[0].request.content) == {
        "model": "organization/model-a",
        "input": ["one", "two"],
        "dimensions": 2,
        "encoding_format": "float",
    }


@respx.mock
@pytest.mark.parametrize("status", [401, 403, 500, 503, 429])
def test_failure_single_shot_and_only_429_failover(monkeypatch, status):
    _wire(monkeypatch, settings(second=True))
    first = respx.post("https://a.compatible.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            status, json={"private": "provider-marker"}, headers={"retry-after": "1"}
        )
    )
    second = respx.post("https://b.compatible.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=chat())
    )
    response = TestClient(app).post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "synthetic", "max_output_tokens": 8},
    )
    assert first.call_count == 1
    assert second.call_count == (1 if status == 429 else 0)
    assert response.status_code == (
        200 if status == 429 else (502 if status in (401, 403) else status)
    )
    assert "provider-marker" not in response.text


@respx.mock
@pytest.mark.parametrize(
    "body",
    [
        {"tools": []},
        {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_file", "file_url": "https://outside.test"}],
                }
            ]
        },
        {"text": {"format": {"type": "json_object"}}},
    ],
)
def test_unsupported_features_rejected_before_dispatch(monkeypatch, body):
    _wire(monkeypatch, settings())
    route = respx.post("https://a.compatible.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=chat())
    )
    response = TestClient(app).post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "synthetic", **body},
    )
    assert response.status_code == 422 and route.call_count == 0


@respx.mock
def test_post_output_failure_keeps_failed_terminal_without_failover(monkeypatch):
    _wire(monkeypatch, settings(second=True))
    first = respx.post("https://a.compatible.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            content=b'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":null}]}\n\n',
            headers={"content-type": "text/event-stream"},
        )
    )
    second = respx.post("https://b.compatible.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=chat())
    )
    response = TestClient(app).post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "synthetic", "max_output_tokens": 8, "stream": True},
    )
    assert response.status_code == 200 and '"type":"response.failed"' in response.text
    assert first.call_count == 1 and second.call_count == 0


@respx.mock
@pytest.mark.parametrize("outcome", ["success", "missing_usage", "malformed", "server_failure"])
def test_metered_settlement_and_reservation_cleanup(monkeypatch, outcome):
    _wire(monkeypatch, settings(metered=True))
    if outcome == "server_failure":
        upstream = httpx.Response(503, json={"private": "marker"})
    elif outcome == "malformed":
        upstream = httpx.Response(
            200, json={"choices": [], "usage": {"prompt_tokens": 4, "completion_tokens": 2}}
        )
    else:
        upstream = httpx.Response(200, json=chat(usage=outcome == "success"))
    route = respx.post("https://a.compatible.test/api/v1/chat/completions").mock(
        return_value=upstream
    )
    response = TestClient(app).post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "hi", "max_output_tokens": 8},
    )
    assert response.status_code == (
        503 if outcome == "server_failure" else (502 if outcome == "malformed" else 200)
    )
    assert route.call_count == 1
    status = TestClient(app).get("/admin/status", headers={"x-admin-key": "admin-key"}).json()
    live = status["backends"]["a"]["live"]
    debit = 6 if outcome in {"success", "malformed"} else 9
    assert live["estimated_remaining_usd"] == pytest.approx(1000 - debit)
    assert live["reserved_inflight_usd"] == 0 and live["active_reservations"] == 0
    assert live["rate_limit"]["rpm_used_60s"] == 1


@respx.mock
def test_mixed_google_generic_pool_429_failover(monkeypatch):
    config = settings(second=True)
    backends = json.loads(config.backends_json)
    backends["b"] = {
        **backends["b"],
        "provider": "google_ai_studio",
        "deployment": "synthetic-google",
        "endpoint": "https://google.example.test",
    }
    config = Settings(**{**config.model_dump(), "backends_json": json.dumps(backends)})
    _wire(monkeypatch, config)
    first = respx.post("https://a.compatible.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(429, headers={"retry-after": "1"})
    )
    second = respx.post("https://google.example.test/v1beta/openai/chat/completions").mock(
        return_value=httpx.Response(200, json=chat())
    )
    response = TestClient(app).post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "synthetic", "max_output_tokens": 8},
    )
    assert response.status_code == 200
    assert first.call_count == 1 and second.call_count == 1
    assert json.loads(second.calls[0].request.content)["model"] == "synthetic-google"


@pytest.mark.parametrize("stream", [False, True])
async def test_cancelled_dispatch_settles_and_closes_once(stream):
    stores = _stores(settings(metered=True))
    entered = asyncio.Event()

    class BlockingUpstream(FakeUpstream):
        async def aiter_bytes(self):
            entered.set()
            await asyncio.Event().wait()
            yield b""

    context = FakeStreamContext(BlockingUpstream())
    fake = FakeBackendClient()
    fake.handler = lambda *_args: context
    task = asyncio.create_task(
        _execute(
            {"model": "logical", "input": "hi", "max_output_tokens": 8, "stream": stream},
            fake=fake,
            stores=stores,
        )
    )
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    response = await asyncio.wait_for(task, 1)
    assert response.status_code == 502 and context.closed
    assert fake.calls == [("a", "responses")]
    snapshot = await stores.credit.live_snapshot(
        ["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshot["a"].estimated_remaining_usd == pytest.approx(991)
    assert snapshot["a"].active_reservations == 0
    quota = await stores.rate.snapshot_quota_groups(["a"])
    assert quota["a"].rpm_used_60s == 1


@respx.mock
@pytest.mark.parametrize("outcome", ["complete", "missing_usage", "truncated"])
def test_metered_stream_settlement(monkeypatch, outcome):
    _wire(monkeypatch, settings(metered=True))
    payload = b'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":null}]}\n\n'
    if outcome != "truncated":
        payload += b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
        if outcome == "complete":
            payload += b'data: {"choices":[],"usage":{"prompt_tokens":4,"completion_tokens":2}}\n\n'
        payload += b"data: [DONE]\n\n"
    route = respx.post("https://a.compatible.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, content=payload, headers={"content-type": "text/event-stream"}
        )
    )
    client = TestClient(app)
    response = client.post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "hi", "max_output_tokens": 8, "stream": True},
    )
    terminal = "response.failed" if outcome == "truncated" else "response.completed"
    assert response.status_code == 200 and terminal in response.text
    assert route.call_count == 1
    live = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "a"
    ]["live"]
    assert live["estimated_remaining_usd"] == pytest.approx(994 if outcome == "complete" else 991)
    assert live["active_reservations"] == live["reserved_inflight_usd"] == 0
    assert live["rate_limit"]["rpm_used_60s"] == 1


@respx.mock
@pytest.mark.parametrize("operation", ["responses", "embeddings"])
def test_mixed_azure_generic_operation_filter(monkeypatch, operation):
    config = settings(second=True)
    backends = json.loads(config.backends_json)
    backends["a"] = {
        **backends["a"],
        "provider": "azure_foundry",
        "deployment": "azure-model",
        "endpoint": "https://azure.example.test",
        "supported_operations": ["responses"],
    }
    backends["b"]["supported_operations"] = ["embeddings"]
    _wire(monkeypatch, Settings(**{**config.model_dump(), "backends_json": json.dumps(backends)}))
    azure = respx.post("https://azure.example.test/openai/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "synthetic",
                "object": "response",
                "status": "completed",
                "model": "azure-model",
                "output": [],
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            },
        )
    )
    generic = respx.post("https://b.compatible.test/api/v1/embeddings").mock(
        return_value=httpx.Response(
            200, json={"data": [{"index": 0, "embedding": [0.5]}], "usage": {"prompt_tokens": 1}}
        )
    )
    response = TestClient(app).post(
        f"/openai/v1/{operation}",
        headers={"api-key": "client-key"},
        json={"model": "alias", "input": "hi"},
    )
    assert response.status_code == 200
    assert azure.call_count == (1 if operation == "responses" else 0)
    assert generic.call_count == (1 if operation == "embeddings" else 0)
    if operation == "responses":
        assert json.loads(azure.calls[0].request.content)["model"] == "azure-model"
    else:
        assert json.loads(generic.calls[0].request.content)["model"] == "organization/model-b"
