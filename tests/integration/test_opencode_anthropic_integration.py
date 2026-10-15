"""Anthropic routing, cache settlement, admission and error invariants."""

import json

import httpx
import pytest
import respx
from test_google_adapter_integration import (  # noqa: F401 -- fixture registration
    _clean,
    _settings,
    _wire,
    client,
)

from tests.unit.test_opencode_anthropic import message

pytestmark = pytest.mark.usefixtures("_clean")
URL = "https://zen.example.test/inference/v1/messages"


def settings():
    return _settings(
        {
            "a": {
                "provider": "opencode_anthropic",
                "endpoint": "https://zen.example.test/inference/v1",
                "deployment": "physical",
                "credential": "synthetic-provider",
                "credit_group": "account",
            }
        },
        {"logical": {"backends": {"a": 1}, "streaming_enabled": False}},
        model_aliases_json='{"alias":"logical"}',
        pricing_json='{"logical":{"input_per_million":4,"output_per_million":10}}',
        backend_cycle_start_day_json='{"account":1}',
        backend_cycle_allowance_usd_json='{"account":100}',
        backend_initial_estimated_remaining_usd_json='{"account":100}',
        retry_attempts=3,
    )


def live():
    return client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()[
        "credit_groups"
    ]["account"]["live"]


@respx.mock
def test_wire_and_cache_settlement(monkeypatch):
    _wire(monkeypatch, settings())
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=message()))
    response = client.post(
        "/openai/v1/responses",
        headers={
            "api-key": "client-key",
            "anthropic-beta": "caller-beta",
            "anthropic-version": "caller-version",
        },
        json={
            "model": "alias",
            "input": "hello",
            "instructions": "rules",
            "max_output_tokens": 128,
            "stream": False,
            "store": False,
        },
    )
    assert response.status_code == 200 and route.call_count == 1
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer synthetic-provider"
    assert request.headers["anthropic-version"] == "2023-06-01"
    assert "anthropic-beta" not in request.headers and "api-key" not in request.headers
    assert json.loads(request.content) == {
        "model": "physical",
        "system": [{"type": "text", "text": "rules"}],
        "messages": [{"role": "user", "content": [{"type": "text", "text": "hello"}]}],
        "max_tokens": 128,
    }
    assert response.json()["usage"]["input_tokens"] == 15
    assert 100 - live()["estimated_remaining_usd"] == pytest.approx(0.00011)
    assert live()["reserved_inflight_usd"] == 0


@respx.mock
@pytest.mark.parametrize(
    "extra",
    [{"stream": True}, {"tools": []}, {"thinking": {}}, {"cache_control": {}}, {"messages": []}],
)
def test_unsupported_zero_admission(monkeypatch, extra):
    _wire(monkeypatch, settings())
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=message()))
    response = client.post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "alias", "input": "x", **extra},
    )
    assert (
        response.status_code == (400 if extra.get("stream") is True else 422)
        and route.call_count == 0
    )
    assert live()["estimated_remaining_usd"] == 100 and live()["reserved_inflight_usd"] == 0


@respx.mock
@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_failure_single_shot_and_charge(monkeypatch, status):
    _wire(monkeypatch, settings())
    route = respx.post(URL).mock(
        return_value=httpx.Response(status, json={"error": {"message": "PRIVATE"}})
    )
    response = client.post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "x", "max_output_tokens": 128},
    )
    assert response.status_code >= 400 and route.call_count == 1 and "PRIVATE" not in response.text
    assert live()["reserved_inflight_usd"] == 0
    if status >= 500:
        assert live()["estimated_remaining_usd"] < 100
    else:
        assert live()["estimated_remaining_usd"] == 100


@respx.mock
def test_malformed_message_charges_known_usage(monkeypatch):
    _wire(monkeypatch, settings())
    raw = message()
    raw["content"] = [{"type": "thinking", "thinking": "PRIVATE"}]
    respx.post(URL).mock(return_value=httpx.Response(200, json=raw))
    response = client.post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "x"},
    )
    assert response.status_code == 502 and "PRIVATE" not in response.text
    assert 100 - live()["estimated_remaining_usd"] == pytest.approx(0.00011)
    assert live()["reserved_inflight_usd"] == 0


@respx.mock
@pytest.mark.parametrize("accepted", [True, False])
def test_nullable_metadata_settlement_through_public_route(monkeypatch, accepted):
    _wire(monkeypatch, settings())
    raw = message()
    raw.update(
        container=None if accepted else {"id": "private-state"}, diagnostics=None, stop_details=None
    )
    raw["content"][0]["citations"] = []
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=raw))
    response = client.post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "synthetic", "max_output_tokens": 128},
    )
    assert response.status_code == (200 if accepted else 502)
    assert route.call_count == 1
    assert 100 - live()["estimated_remaining_usd"] == pytest.approx(0.00011)
    assert live()["active_reservations"] == 0
    assert b"private-state" not in response.content
