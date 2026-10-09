"""Actual API traffic using durable quota store and synthetic transport."""

import asyncio
import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from foundry_router.config import Settings
from foundry_router.main import app
from foundry_router.state.quota import AzureTableRateLimitStore
from tests.integration.test_compatible_provider_integration import chat, settings
from tests.integration.test_google_adapter_integration import _wire
from tests.unit.test_table_quota import AtomicClient


def wire(monkeypatch, *, second=False, rpm=4):
    config = settings(second=second, metered=True)
    backends = json.loads(config.backends_json)
    for backend in backends.values():
        backend["quota_group"] = "shared"
    config = Settings(
        **{
            **config.model_dump(),
            "backends_json": json.dumps(backends),
            "quota_group_rate_limits_json": json.dumps(
                {"shared": {"rpm": rpm, "tpm": 100, "rpd": 10}}
            ),
            "rate_limit_backend": "table",
            "protected_emergency_fallback": True,
            "table_endpoint": "https://synthetic.table.test",
        }
    )
    _wire(monkeypatch, config)
    client = AtomicClient()
    store = AzureTableRateLimitStore(client)
    asyncio.run(store.sync_from_settings(config))
    monkeypatch.setattr("foundry_router.main._rate_limit_store", store)
    return store, client


@respx.mock
@pytest.mark.parametrize("stream", [False, True])
def test_api_settles_distinct_attempts_and_shared_quota(monkeypatch, stream):
    store, _ = wire(monkeypatch, second=True)
    first = respx.post("https://a.compatible.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(429, headers={"retry-after": "1"})
    )
    if stream:
        upstream = httpx.Response(
            200,
            content=b'data: {"choices":[{"delta":{"content":"answer"},"finish_reason":"stop"}]}\n\ndata: {"choices":[],"usage":{"prompt_tokens":4,"completion_tokens":2}}\n\ndata: [DONE]\n\n',
            headers={"content-type": "text/event-stream"},
        )
    else:
        upstream = httpx.Response(200, json=chat())
    second = respx.post("https://b.compatible.test/api/v1/chat/completions").mock(
        return_value=upstream
    )
    response = TestClient(app).post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "alias", "input": "hi", "max_output_tokens": 8, "stream": stream},
    )
    assert response.status_code == 200
    assert first.call_count == second.call_count == 1
    snap = (asyncio.run(store.snapshot_quota_groups(["shared"])))["shared"]
    assert (snap.rpm_used_60s, snap.input_tpm_used_60s, snap.rpd_used) == (2, 5, 2)
    assert store._owners == {}


@respx.mock
def test_storage_outage_or_lost_ack_never_dispatches(monkeypatch):
    store, client = wire(monkeypatch, second=True)
    route = respx.post("https://a.compatible.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=chat())
    )
    client.fail_after_commit = True  # Routing snapshot CAS loses acknowledgement.
    response = TestClient(app).post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "alias", "input": "hi", "max_output_tokens": 8},
    )
    assert (
        response.status_code == 503
        and response.json()["error"]["type"] == "quota_store_unavailable"
    )
    assert route.call_count == 0
    assert (asyncio.run(store.snapshot_quota_groups(["shared"])))["shared"].rpd_used == 0


@respx.mock
def test_admission_lost_ack_and_cleanup_outage_returns_503(monkeypatch):
    store, client = wire(monkeypatch, second=True)
    first = respx.post("https://a.compatible.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=chat())
    )
    second = respx.post("https://b.compatible.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=chat())
    )
    original = client.try_batch_transaction

    async def fail_admission(operations):
        import json

        state = json.loads(operations[0].entity["state"])
        if state["records"]:
            client.fail_after_commit = True
        return await original(operations)

    client.try_batch_transaction = fail_admission
    response = TestClient(app).post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "alias", "input": "hi", "max_output_tokens": 8},
    )
    assert response.status_code == 503
    assert response.json()["error"]["type"] == "quota_store_unavailable"
    assert first.call_count == second.call_count == 0
    client.try_batch_transaction = original
    assert asyncio.run(store.snapshot_quota_groups(["shared"]))["shared"].rpd_used == 0
