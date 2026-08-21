"""Unit tests for main application."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from fastapi import Request
from fastapi.testclient import TestClient
from httpx import Response

from foundry_router.config import Settings
from foundry_router.credit import CreditState
from foundry_router.main import (
    BackendHealthRecord,
    BackendHealthState,
    BackendRequestResult,
    _execute_with_single_failover,
    _forward_non_streaming_with_retries,
    _forward_streaming_with_retries,
    _parse_retry_after,
    _reset_backend_health_state,
    _reset_credit_state,
    _reset_metrics_state,
    _retry_delay_seconds,
    _set_backend_active,
    _set_backend_cooldown,
    _snapshot_backend_health,
    _stream_response,
    app,
    global_exception_handler,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_settings(monkeypatch):
    test_settings = Settings(
        backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key-a", "region": "eastus", "deployment": "gpt-4"}, "backend_b": {"endpoint": "https://b.openai.azure.com", "credential": "key-b", "region": "westus", "deployment": "gpt-4"}}',
        models_json='{"gpt-4": {"backends": {"backend_a": 1.0, "backend_b": 0.8}}, "text-embedding-3-large": {"backends": {"backend_a": 1.0, "backend_b": 0.8}}}',
        client_api_keys_json='["client-key-123"]',
        admin_api_keys_json='["admin-key-789"]',
        pricing_json='{"gpt-4": {"input_per_million": 10.0, "output_per_million": 30.0}, "text-embedding-3-large": {"input_per_million": 0.13, "output_per_million": 0.0}}',
        backend_cycle_start_day_json='{"backend_a": 1, "backend_b": 1}',
        backend_cycle_allowance_usd_json='{"backend_a": 200.0, "backend_b": 200.0}',
        backend_initial_estimated_remaining_usd_json='{"backend_a": 200.0, "backend_b": 200.0}',
        retry_attempts=2,
        retry_max_delay_seconds=0.01,
    )

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("foundry_router.main.load_settings", lambda: test_settings)
    monkeypatch.setattr("foundry_router.auth.load_settings", lambda: test_settings)
    monkeypatch.setattr("foundry_router.backends.load_settings", lambda: test_settings)
    monkeypatch.setattr("foundry_router.config.load_settings", lambda: test_settings)
    monkeypatch.setattr("foundry_router.main.asyncio.sleep", no_sleep)
    asyncio.run(_reset_backend_health_state())
    asyncio.run(_reset_credit_state())
    asyncio.run(_reset_metrics_state())
    yield test_settings
    asyncio.run(_reset_backend_health_state())
    asyncio.run(_reset_credit_state())
    asyncio.run(_reset_metrics_state())


class TestHealthEndpoints:
    def test_liveness(self) -> None:
        response: Response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    def test_readiness_healthy(self) -> None:
        response: Response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True
        assert all(data["checks"].values())

    def test_readiness_unhealthy_when_no_backends(self, monkeypatch) -> None:
        test_settings = Settings(
            backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key", "deployment": "gpt-4"}}',
            models_json='{"gpt-4": {"backends": {"backend_a": 1.0}}}',
            client_api_keys_json='["client-key"]',
            admin_api_keys_json='["admin-key"]',
            pricing_json="{}",
            backend_cycle_start_day_json="{}",
        )
        test_settings.backends = {}
        monkeypatch.setattr("foundry_router.main.load_settings", lambda: test_settings)

        response: Response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["ready"] is False

    def test_readiness_unhealthy_when_deployment_missing(self, monkeypatch) -> None:
        test_settings = Settings(
            backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key", "deployment": "gpt-4"}}',
            models_json='{"gpt-4": {"backends": {"backend_a": 1.0}}}',
            client_api_keys_json='["client-key"]',
            admin_api_keys_json='["admin-key"]',
            pricing_json="{}",
            backend_cycle_start_day_json="{}",
        )
        test_settings.backends["backend_a"].deployment = None
        monkeypatch.setattr("foundry_router.main.load_settings", lambda: test_settings)

        response = client.get("/health/ready")

        assert response.status_code == 503
        assert response.json()["checks"]["deployments_configured"] is False


class TestAdminEndpoint:
    def test_admin_status_requires_auth(self) -> None:
        response: Response = client.get("/admin/status")
        assert response.status_code == 401

    def test_admin_status_with_valid_key(self) -> None:
        response: Response = client.get("/admin/status", headers={"x-admin-key": "admin-key-789"})
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "0.1.0"
        assert "backends" in data
        assert "models" in data
        assert "config" in data
        assert "backend_a" in data["backends"]
        assert "backend_b" in data["backends"]
        assert "gpt-4" in data["models"]

    def test_admin_status_rejects_client_key(self) -> None:
        response: Response = client.get("/admin/status", headers={"x-admin-key": "client-key-123"})
        assert response.status_code == 401

    def test_admin_status_includes_live_diagnostics(self) -> None:
        asyncio.run(
            _set_backend_cooldown(
                "backend_a",
                state=BackendHealthState.QUOTA_COOLDOWN,
                cooldown_seconds=2,
            )
        )
        response = client.get("/admin/status", headers={"x-admin-key": "admin-key-789"})
        assert response.status_code == 200
        live = response.json()["backends"]["backend_a"]["live"]
        assert live["health_state"] == BackendHealthState.QUOTA_COOLDOWN
        assert live["cooldown_remaining_seconds"] is not None
        assert live["credit_state"] in {
            CreditState.USABLE,
            CreditState.CONSERVATION,
            CreditState.PROTECTED,
            CreditState.INSUFFICIENT_CAPACITY,
        }
        assert live["available_credit_usd"] is not None
        assert live["next_reset_utc"] is not None


class TestMetricsEndpoint:
    def test_metrics_endpoint_requires_admin_auth(self) -> None:
        response = client.get("/metrics")
        assert response.status_code == 401

    @respx.mock
    def test_metrics_endpoint_exposes_prometheus_series(self) -> None:
        respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(200, json={"id": "response-test", "output": []}))

        request_response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "hello"},
        )
        assert request_response.status_code == 200

        metrics_response = client.get("/metrics", headers={"x-admin-key": "admin-key-789"})
        assert metrics_response.status_code == 200
        body = metrics_response.text
        assert "foundry_router_requests_total" in body
        assert 'model="gpt-4"' in body
        assert 'backend="backend_a"' in body
        assert "foundry_router_latency_seconds_bucket" in body
        assert "foundry_router_estimated_cost_usd_total" in body
        assert "foundry_router_backend_health_state" in body
        assert "foundry_router_credit_available_usd" in body

    @respx.mock
    def test_metrics_cost_uses_finalized_usage_values(self) -> None:
        respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(
            return_value=Response(
                200,
                json={"id": "response-test", "usage": {"input_tokens": 10, "output_tokens": 5}},
            )
        )

        request_response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "hello", "max_output_tokens": 1024},
        )
        assert request_response.status_code == 200

        metrics_response = client.get("/metrics", headers={"x-admin-key": "admin-key-789"})
        assert metrics_response.status_code == 200
        assert (
            'foundry_router_estimated_cost_usd_total{model="gpt-4",backend="backend_a"} 0.000250000'
        ) in metrics_response.text


class TestOpenAIEndpoints:
    def test_models_requires_auth(self) -> None:
        response: Response = client.get("/openai/v1/models")
        assert response.status_code == 401

    def test_models_with_valid_key(self) -> None:
        response: Response = client.get("/openai/v1/models", headers={"api-key": "client-key-123"})
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 2
        model_ids = {m["id"] for m in data["data"]}
        assert model_ids == {"gpt-4", "text-embedding-3-large"}

    @respx.mock
    def test_responses_forward(self) -> None:
        route = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(
            return_value=Response(
                200,
                json={"id": "response-test", "output": []},
                headers={
                    "cache-control": "no-store",
                    "retry-after": "3",
                    "set-cookie": "backend-secret=hidden",
                    "x-backend-trace": "private",
                },
            )
        )
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "Hello"},
        )
        assert response.status_code == 200
        assert response.json()["id"] == "response-test"
        assert route.called
        assert route.calls[0].request.headers["api-key"] == "key-a"
        assert "authorization" not in route.calls[0].request.headers
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["retry-after"] == "3"
        assert "set-cookie" not in response.headers
        assert "x-backend-trace" not in response.headers

    @respx.mock
    def test_responses_forward_correlation_id(self) -> None:
        route = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(200, json={"id": "response-test", "output": []}))
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123", "x-request-id": "request-123"},
            json={"model": "gpt-4", "input": "Hello"},
        )
        assert response.status_code == 200
        assert route.calls[0].request.headers["x-request-id"] == "request-123"

    @respx.mock
    def test_embeddings_forward(self) -> None:
        route = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/embeddings",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(200, json={"object": "list", "data": []}))
        response = client.post(
            "/openai/v1/embeddings",
            headers={"api-key": "client-key-123"},
            json={"model": "text-embedding-3-large", "input": "Hello"},
        )
        assert response.status_code == 200
        assert response.json()["object"] == "list"
        assert route.called

    @respx.mock
    def test_429_triggers_quota_cooldown_and_failover(self) -> None:
        route_a = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(
            return_value=Response(429, json={"error": "rate limited"}, headers={"retry-after": "1"})
        )
        route_b = respx.post(
            "https://b.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(200, json={"id": "from-b"}))

        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "hello"},
        )

        assert response.status_code == 200
        assert response.json()["id"] == "from-b"
        assert route_a.call_count == 2
        assert route_b.call_count == 1

    @respx.mock
    def test_5xx_triggers_error_cooldown_and_failover(self) -> None:
        route_a = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/embeddings",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(503, json={"error": "busy"}))
        route_b = respx.post(
            "https://b.openai.azure.com/openai/deployments/gpt-4/embeddings",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(200, json={"object": "list", "data": []}))

        response = client.post(
            "/openai/v1/embeddings",
            headers={"api-key": "client-key-123"},
            json={"model": "text-embedding-3-large", "input": "hello"},
        )

        assert response.status_code == 200
        assert route_a.call_count == 2
        assert route_b.call_count == 1

    @respx.mock
    def test_retry_exhaustion_without_failover_when_single_backend(self, monkeypatch) -> None:
        single_backend_settings = Settings(
            backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key-a", "deployment": "gpt-4"}}',
            models_json='{"gpt-4": {"backends": {"backend_a": 1.0}}}',
            client_api_keys_json='["client-key-123"]',
            admin_api_keys_json='["admin-key-789"]',
            pricing_json='{"gpt-4": {"input_per_million": 10.0, "output_per_million": 30.0}}',
            backend_cycle_start_day_json='{"backend_a": 1}',
            backend_cycle_allowance_usd_json='{"backend_a": 200.0}',
            backend_initial_estimated_remaining_usd_json='{"backend_a": 200.0}',
            retry_attempts=2,
            retry_max_delay_seconds=0.01,
        )
        monkeypatch.setattr("foundry_router.main.load_settings", lambda: single_backend_settings)
        monkeypatch.setattr("foundry_router.auth.load_settings", lambda: single_backend_settings)
        monkeypatch.setattr(
            "foundry_router.backends.load_settings", lambda: single_backend_settings
        )
        monkeypatch.setattr("foundry_router.config.load_settings", lambda: single_backend_settings)

        route_a = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(503, json={"error": "busy"}))

        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "hello"},
        )

        assert response.status_code == 503
        assert response.headers["retry-after"] == "1"
        assert route_a.call_count == 2

    @respx.mock
    def test_retry_exhaustion_after_failover_returns_cooldown_response(self) -> None:
        route_a = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(503, json={"error": "busy-a"}))
        route_b = respx.post(
            "https://b.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(503, json={"error": "busy-b"}))

        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "hello"},
        )

        assert response.status_code == 503
        assert response.headers["retry-after"] == "1"
        assert route_a.call_count == 2
        assert route_b.call_count == 2

    @respx.mock
    def test_transport_failure_fails_over_to_next_backend(self) -> None:
        route_a = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(side_effect=httpx.ConnectError("boom"))
        route_b = respx.post(
            "https://b.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(200, json={"id": "ok-b"}))

        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "hello"},
        )

        assert response.status_code == 200
        assert response.json()["id"] == "ok-b"
        assert route_a.call_count == 2
        assert route_b.call_count == 1

    def test_all_backends_in_quota_cooldown_returns_429_with_retry_after(self) -> None:
        asyncio.run(
            _set_backend_cooldown(
                "backend_a",
                state=BackendHealthState.QUOTA_COOLDOWN,
                cooldown_seconds=3,
            )
        )
        asyncio.run(
            _set_backend_cooldown(
                "backend_b",
                state=BackendHealthState.QUOTA_COOLDOWN,
                cooldown_seconds=1,
            )
        )

        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "hello"},
        )

        assert response.status_code == 429
        assert response.headers["retry-after"] == "1"

    def test_all_backends_in_mixed_cooldown_returns_503_with_retry_after(self) -> None:
        asyncio.run(
            _set_backend_cooldown(
                "backend_a",
                state=BackendHealthState.QUOTA_COOLDOWN,
                cooldown_seconds=2,
            )
        )
        asyncio.run(
            _set_backend_cooldown(
                "backend_b",
                state=BackendHealthState.ERROR_COOLDOWN,
                cooldown_seconds=1,
            )
        )

        response = client.post(
            "/openai/v1/embeddings",
            headers={"api-key": "client-key-123"},
            json={"model": "text-embedding-3-large", "input": "hello"},
        )

        assert response.status_code == 503
        assert response.headers["retry-after"] == "1"

    @respx.mock
    def test_protected_emergency_fallback_uses_only_candidate(self, monkeypatch) -> None:
        single_backend_settings = Settings(
            backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key-a", "deployment": "gpt-4"}}',
            models_json='{"gpt-4": {"backends": {"backend_a": 1.0}}}',
            client_api_keys_json='["client-key-123"]',
            admin_api_keys_json='["admin-key-789"]',
            pricing_json='{"gpt-4": {"input_per_million": 10.0, "output_per_million": 30.0}}',
            backend_cycle_start_day_json='{"backend_a": 1}',
            backend_cycle_allowance_usd_json='{"backend_a": 200.0}',
            backend_initial_estimated_remaining_usd_json='{"backend_a": 200.0}',
            protected_emergency_fallback=True,
            retry_attempts=1,
            retry_max_delay_seconds=0.01,
        )
        monkeypatch.setattr("foundry_router.main.load_settings", lambda: single_backend_settings)
        monkeypatch.setattr("foundry_router.auth.load_settings", lambda: single_backend_settings)
        monkeypatch.setattr(
            "foundry_router.backends.load_settings", lambda: single_backend_settings
        )
        monkeypatch.setattr("foundry_router.config.load_settings", lambda: single_backend_settings)

        asyncio.run(
            _set_backend_cooldown(
                "backend_a",
                state=BackendHealthState.QUOTA_COOLDOWN,
                cooldown_seconds=10,
            )
        )

        route_a = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(200, json={"id": "emergency-ok"}))

        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "hello"},
        )

        assert response.status_code == 200
        assert response.json()["id"] == "emergency-ok"
        assert route_a.call_count == 1

    def test_retry_after_parsing_integer_and_http_date(self) -> None:
        parsed_integer = _parse_retry_after("5", 30.0)
        assert parsed_integer == 5.0

        future = datetime.now(UTC) + timedelta(seconds=4)
        parsed_date = _parse_retry_after(future.strftime("%a, %d %b %Y %H:%M:%S GMT"), 30.0)
        assert parsed_date is not None
        assert 0.0 <= parsed_date <= 30.0

    def test_retry_after_is_clamped(self) -> None:
        assert _parse_retry_after("300", 30.0) == 30.0

    def test_retry_delay_schedule_is_bounded_and_honors_retry_after(self) -> None:
        assert (
            _retry_delay_seconds(
                attempt_number=1,
                max_delay_seconds=30.0,
                retry_after_header=None,
            )
            == 1.0
        )
        assert (
            _retry_delay_seconds(
                attempt_number=2,
                max_delay_seconds=30.0,
                retry_after_header=None,
            )
            == 2.0
        )
        assert (
            _retry_delay_seconds(
                attempt_number=10,
                max_delay_seconds=3.0,
                retry_after_header=None,
            )
            == 3.0
        )
        assert (
            _retry_delay_seconds(
                attempt_number=1,
                max_delay_seconds=30.0,
                retry_after_header="5",
            )
            == 5.0
        )
        assert (
            _retry_delay_seconds(
                attempt_number=2,
                max_delay_seconds=3.0,
                retry_after_header="300",
            )
            == 3.0
        )
        assert (
            _retry_delay_seconds(
                attempt_number=1,
                max_delay_seconds=30.0,
                retry_after_header="invalid",
            )
            == 1.0
        )

    def test_retry_loop_sleeps_between_attempts_not_after_final_attempt(self, monkeypatch) -> None:
        sleeps: list[float] = []

        async def capture_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr("foundry_router.main.asyncio.sleep", capture_sleep)

        class FakeBackendClient:
            calls = 0

            async def request_backend(self, *_args, **_kwargs):
                self.calls += 1
                return Response(503, json={"error": "busy"})

        backend_client = FakeBackendClient()
        monkeypatch.setattr("foundry_router.main.get_backend_client", lambda: backend_client)
        result = asyncio.run(
            _forward_non_streaming_with_retries(
                settings=type(
                    "SettingsStub",
                    (),
                    {"retry_attempts": 2, "retry_max_delay_seconds": 30.0},
                )(),
                backend_id="backend_a",
                operation="responses",
                headers={},
                body={"model": "gpt-4"},
            )
        )
        assert result.retryable_failure is True
        assert backend_client.calls == 2
        assert sleeps == [1.0]

    def test_health_state_updates_are_concurrency_safe(self) -> None:
        async def run_concurrently() -> None:
            await asyncio.gather(
                _set_backend_cooldown(
                    "backend_a",
                    state=BackendHealthState.QUOTA_COOLDOWN,
                    cooldown_seconds=1,
                ),
                _set_backend_cooldown(
                    "backend_b",
                    state=BackendHealthState.ERROR_COOLDOWN,
                    cooldown_seconds=1,
                ),
            )

        asyncio.run(run_concurrently())

        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "hello"},
        )
        assert response.status_code in {429, 503}

    def test_same_backend_concurrent_updates_preserve_disabled_state(self) -> None:
        async def run_concurrently() -> None:
            await _set_backend_cooldown(
                "backend_a",
                state=BackendHealthState.ERROR_COOLDOWN,
                cooldown_seconds=10,
            )
            await asyncio.gather(
                _set_backend_cooldown(
                    "backend_a",
                    state=BackendHealthState.QUOTA_COOLDOWN,
                    cooldown_seconds=1,
                ),
                _set_backend_active("backend_a"),
            )

        asyncio.run(run_concurrently())
        snapshots = asyncio.run(_snapshot_backend_health(["backend_a"]))
        assert snapshots["backend_a"].state in {
            BackendHealthState.ACTIVE,
            BackendHealthState.QUOTA_COOLDOWN,
        }

        async def disable_then_update() -> None:
            from foundry_router.main import _backend_health_lock, _backend_health_state

            async with _backend_health_lock:
                _backend_health_state["backend_a"] = BackendHealthRecord(
                    state=BackendHealthState.DISABLED,
                )
            await asyncio.gather(
                _set_backend_active("backend_a"),
                _set_backend_cooldown(
                    "backend_a",
                    state=BackendHealthState.ERROR_COOLDOWN,
                    cooldown_seconds=10,
                ),
            )

        asyncio.run(disable_then_update())
        snapshots = asyncio.run(_snapshot_backend_health(["backend_a"]))
        assert snapshots["backend_a"].state == BackendHealthState.DISABLED

    def test_single_failover_does_not_attempt_third_backend(self) -> None:
        settings = Settings(
            backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "a", "deployment": "gpt-4"}, "backend_b": {"endpoint": "https://b.openai.azure.com", "credential": "b", "deployment": "gpt-4"}, "backend_c": {"endpoint": "https://c.openai.azure.com", "credential": "c", "deployment": "gpt-4"}}',
            models_json='{"gpt-4": {"backends": {"backend_a": 1.0, "backend_b": 0.9, "backend_c": 0.8}}}',
            client_api_keys_json='["client"]',
            admin_api_keys_json='["admin"]',
            pricing_json='{"gpt-4": {"input_per_million": 10.0, "output_per_million": 30.0}}',
            backend_cycle_start_day_json='{"backend_a": 1, "backend_b": 1, "backend_c": 1}',
            backend_cycle_allowance_usd_json='{"backend_a": 200.0, "backend_b": 200.0, "backend_c": 200.0}',
            backend_initial_estimated_remaining_usd_json='{"backend_a": 200.0, "backend_b": 200.0, "backend_c": 200.0}',
            retry_attempts=2,
            retry_max_delay_seconds=10.0,
        )
        calls: list[str] = []

        async def execute(backend_id: str) -> BackendRequestResult:
            calls.append(backend_id)
            await _set_backend_cooldown(
                backend_id,
                state=BackendHealthState.ERROR_COOLDOWN,
                cooldown_seconds=10,
            )
            return BackendRequestResult(Response(503), retryable_failure=True)

        result = asyncio.run(
            _execute_with_single_failover(
                settings,
                "gpt-4",
                operation="responses",
                body={"model": "gpt-4", "input": "hello"},
                request_id="req-single-failover",
                execute_backend=execute,
            )
        )
        assert result.status_code == 503
        assert calls == ["backend_a", "backend_b"]

    def test_pre_output_empty_chunks_are_bounded(self, monkeypatch) -> None:
        class SlowEmptyStream(httpx.AsyncByteStream):
            async def __aiter__(self):
                while True:
                    yield b""
                    await asyncio.Event().wait()

            async def aclose(self) -> None:
                return None

        class Context:
            async def __aenter__(self):
                return Response(
                    200,
                    headers={"content-type": "text/event-stream"},
                    stream=SlowEmptyStream(),
                )

            async def __aexit__(self, *_args) -> None:
                return None

        class BackendClient:
            def stream_backend(self, *_args, **_kwargs):
                return Context()

        monkeypatch.setattr("foundry_router.main.PRE_OUTPUT_TIMEOUT_SECONDS", 0.01)

        def get_backend_client() -> BackendClient:
            return BackendClient()

        monkeypatch.setattr("foundry_router.main.get_backend_client", get_backend_client)
        result = asyncio.run(
            _forward_streaming_with_retries(
                settings=type(
                    "SettingsStub", (), {"retry_attempts": 1, "retry_max_delay_seconds": 1.0}
                )(),
                backend_id="backend_a",
                request_id="req-pre-output",
                headers={},
                body={"model": "gpt-4", "stream": True},
            )
        )
        assert result.retryable_failure is True
        assert result.response.status_code == 502

    def test_stream_error_body_read_closes_context(self, monkeypatch) -> None:
        class BrokenErrorBody(httpx.AsyncByteStream):
            async def __aiter__(self):
                raise httpx.ReadError("error body failed")
                yield b""

            async def aclose(self) -> None:
                return None

        class Context:
            exits = 0

            async def __aenter__(self):
                return Response(503, stream=BrokenErrorBody())

            async def __aexit__(self, *_args) -> None:
                self.exits += 1

        context = Context()

        class BackendClient:
            def stream_backend(self, *_args, **_kwargs):
                return context

        def get_backend_client() -> BackendClient:
            return BackendClient()

        monkeypatch.setattr("foundry_router.main.get_backend_client", get_backend_client)
        result = asyncio.run(
            _forward_streaming_with_retries(
                settings=type(
                    "SettingsStub", (), {"retry_attempts": 1, "retry_max_delay_seconds": 1.0}
                )(),
                backend_id="backend_a",
                request_id="req-stream-error-body",
                headers={},
                body={"model": "gpt-4", "stream": True},
            )
        )
        assert result.retryable_failure is True
        assert result.response.status_code == 502
        assert context.exits == 1
        snapshots = asyncio.run(_snapshot_backend_health(["backend_a"]))
        assert snapshots["backend_a"].state == BackendHealthState.ERROR_COOLDOWN

    def test_stream_generator_closes_context_when_cancelled(self) -> None:
        class Context:
            exits = 0

            async def __aexit__(self, *_args) -> None:
                self.exits += 1

        async def chunks():
            yield b'data: {"id":"one"}\n\n'
            await asyncio.Event().wait()

        context = Context()

        async def exercise() -> None:
            stream = _stream_response(
                chunks(),
                b'data: {"id":"one"}\n\n',
                context,
                request_id="req-cancel",
                backend_id="backend_a",
                cooldown_seconds=10.0,
                model="gpt-4",
                pricing={
                    "gpt-4": type(
                        "PricingStub", (), {"input_per_million": 10.0, "output_per_million": 30.0}
                    )()
                },
                status_code=200,
            )
            assert await anext(stream)
            pending = asyncio.create_task(anext(stream))
            await asyncio.sleep(0)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            await stream.aclose()

        asyncio.run(exercise())
        assert context.exits == 1

    @respx.mock
    def test_unknown_model_does_not_contact_backend(self) -> None:
        route = respx.post("https://a.openai.azure.com/").mock(return_value=Response(200))
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "unknown", "input": "Hello"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["type"] == "model_not_found"
        assert not route.called

    @respx.mock
    def test_malformed_request_does_not_contact_backend(self) -> None:
        route = respx.post("https://a.openai.azure.com/").mock(return_value=Response(200))
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"input": "Hello"},
        )
        assert response.status_code == 422
        assert not route.called

    @respx.mock
    def test_invalid_embedding_items_do_not_contact_backend(self) -> None:
        route = respx.post("https://a.openai.azure.com/").mock(return_value=Response(200))
        response = client.post(
            "/openai/v1/embeddings",
            headers={"api-key": "client-key-123"},
            json={"model": "text-embedding-3-large", "input": ["valid", 123]},
        )
        assert response.status_code == 422
        assert not route.called

    @respx.mock
    def test_missing_pricing_fails_closed_without_egress(self, monkeypatch) -> None:
        no_pricing_settings = Settings(
            backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key-a", "deployment": "gpt-4"}}',
            models_json='{"gpt-4": {"backends": {"backend_a": 1.0}}}',
            client_api_keys_json='["client-key-123"]',
            admin_api_keys_json='["admin-key-789"]',
            pricing_json="{}",
            backend_cycle_start_day_json='{"backend_a": 1}',
            backend_cycle_allowance_usd_json='{"backend_a": 200.0}',
            backend_initial_estimated_remaining_usd_json='{"backend_a": 200.0}',
        )
        monkeypatch.setattr("foundry_router.main.load_settings", lambda: no_pricing_settings)
        monkeypatch.setattr("foundry_router.auth.load_settings", lambda: no_pricing_settings)
        monkeypatch.setattr("foundry_router.backends.load_settings", lambda: no_pricing_settings)
        monkeypatch.setattr("foundry_router.config.load_settings", lambda: no_pricing_settings)

        route = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(200, json={"id": "should-not-run"}))

        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "Hello"},
        )

        assert response.status_code == 503
        assert response.json()["error"]["type"] == "insufficient_credit_capacity"
        assert not route.called

    @respx.mock
    def test_insufficient_estimated_credit_fails_closed_without_egress(self, monkeypatch) -> None:
        low_credit_settings = Settings(
            backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key-a", "deployment": "gpt-4"}}',
            models_json='{"gpt-4": {"backends": {"backend_a": 1.0}}}',
            client_api_keys_json='["client-key-123"]',
            admin_api_keys_json='["admin-key-789"]',
            pricing_json='{"gpt-4": {"input_per_million": 10.0, "output_per_million": 30.0}}',
            backend_cycle_start_day_json='{"backend_a": 1}',
            backend_cycle_allowance_usd_json='{"backend_a": 50.0}',
            backend_initial_estimated_remaining_usd_json='{"backend_a": 1.0}',
        )
        monkeypatch.setattr("foundry_router.main.load_settings", lambda: low_credit_settings)
        monkeypatch.setattr("foundry_router.auth.load_settings", lambda: low_credit_settings)
        monkeypatch.setattr("foundry_router.backends.load_settings", lambda: low_credit_settings)
        monkeypatch.setattr("foundry_router.config.load_settings", lambda: low_credit_settings)

        route = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(200, json={"id": "should-not-run"}))

        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "Hello"},
        )

        assert response.status_code == 503
        assert response.json()["error"]["type"] == "insufficient_credit_capacity"
        assert not route.called

    def test_equal_weight_selection_is_lexicographically_smallest(self) -> None:
        from foundry_router.main import _select_backend

        settings = type("SettingsStub", (), {})()
        settings.models = {"gpt-4": type("PoolStub", (), {})()}
        settings.models["gpt-4"].backends = {"backend_b": 1.0, "backend_a": 1.0}
        assert _select_backend(settings, "gpt-4") == "backend_a"

    @respx.mock
    def test_responses_stream_is_passed_through(self) -> None:
        route = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(
            return_value=Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b'data: {"id":"one"}\n\ndata: [DONE]\n\n',
            )
        )
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "Hello", "stream": True},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.content == b'data: {"id":"one"}\n\ndata: [DONE]\n\n'
        assert route.called

    @respx.mock
    def test_stream_failure_before_first_chunk_retries_and_fails_over(self) -> None:
        route_a = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(200, headers={"content-type": "text/event-stream"}))
        route_b = respx.post(
            "https://b.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(
            return_value=Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b'data: {"id":"from-b"}\n\ndata: [DONE]\n\n',
            )
        )

        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "Hello", "stream": True},
        )

        assert response.status_code == 200
        assert b"from-b" in response.content
        assert route_a.call_count == 2
        assert route_b.call_count == 1

    @respx.mock
    def test_stream_empty_chunk_is_not_meaningful_output(self) -> None:
        class EmptyThenErrorStream(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b""
                raise httpx.ReadError("stream failed before output")

            async def aclose(self) -> None:
                return None

        route_a = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(
            side_effect=lambda _request: Response(
                200,
                headers={"content-type": "text/event-stream"},
                stream=EmptyThenErrorStream(),
            )
        )
        route_b = respx.post(
            "https://b.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(
            return_value=Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b'data: {"id":"from-b"}\n\ndata: [DONE]\n\n',
            )
        )

        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "Hello", "stream": True},
        )

        assert response.status_code == 200
        assert b"from-b" in response.content
        assert route_a.call_count == 2
        assert route_b.call_count == 1

    @respx.mock
    def test_stream_failure_after_first_chunk_emits_sse_error_without_failover(self) -> None:
        class BrokenStream(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b'data: {"id":"one"}\n\n'
                raise httpx.ReadError("stream failed")

            async def aclose(self) -> None:
                return None

        route_a = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(
            return_value=Response(
                200,
                headers={"content-type": "text/event-stream"},
                stream=BrokenStream(),
            )
        )
        route_b = respx.post(
            "https://b.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(
            return_value=Response(200, headers={"content-type": "text/event-stream"}, content=b"")
        )

        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "Hello", "stream": True},
        )

        assert response.status_code == 200
        assert b'{"id":"one"}' in response.content
        assert b'"type":"upstream_error"' in response.content
        assert route_a.call_count == 1
        assert route_b.call_count == 0

        follow_up_route = respx.post(
            "https://b.openai.azure.com/openai/deployments/gpt-4/embeddings",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(200, json={"object": "list", "data": []}))

        follow_up = client.post(
            "/openai/v1/embeddings",
            headers={"api-key": "client-key-123"},
            json={"model": "text-embedding-3-large", "input": "Hello"},
        )
        assert follow_up.status_code == 200
        assert follow_up_route.call_count == 1

    def test_stream_response_records_failure_metric_on_midstream_error(self, monkeypatch) -> None:
        observed: list[dict[str, object]] = []

        async def capture_observe_request(
            *,
            model: str,
            backend: str,
            status_code: int,
            latency_seconds: float,
            estimated_cost_usd: float | None,
        ) -> None:
            observed.append(
                {
                    "model": model,
                    "backend": backend,
                    "status_code": status_code,
                    "latency_seconds": latency_seconds,
                    "estimated_cost_usd": estimated_cost_usd,
                }
            )

        async def capture_finalize_request(
            request_id: str,
            *,
            charge_reserved: bool,
            charged_cost_usd: float | None,
        ) -> None:
            _ = (request_id, charge_reserved, charged_cost_usd)

        monkeypatch.setattr(
            "foundry_router.main._metrics_store.observe_request",
            capture_observe_request,
        )
        monkeypatch.setattr(
            "foundry_router.main._credit_store.finalize_request",
            capture_finalize_request,
        )

        class Context:
            async def __aexit__(self, *_args) -> None:
                return None

        async def broken_chunks():
            yield b'data: {"id":"chunk-one"}\n\n'
            raise httpx.ReadError("stream failed")

        async def run_stream() -> bytes:
            payload = b""
            stream = _stream_response(
                broken_chunks(),
                b'data: {"id":"first"}\n\n',
                Context(),
                request_id="req-stream-failure-metric",
                backend_id="backend_a",
                cooldown_seconds=10.0,
                model="gpt-4",
                pricing={
                    "gpt-4": type(
                        "PricingStub",
                        (),
                        {"input_per_million": 10.0, "output_per_million": 30.0},
                    )(),
                },
                status_code=200,
            )
            async for chunk in stream:
                payload += chunk
            return payload

        stream_payload = asyncio.run(run_stream())
        assert b'"type":"upstream_error"' in stream_payload
        assert len(observed) == 1
        assert observed[0]["status_code"] == 502

    @respx.mock
    def test_empty_responses_stream_returns_upstream_error(self, monkeypatch) -> None:
        single_backend_settings = Settings(
            backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key-a", "deployment": "gpt-4"}}',
            models_json='{"gpt-4": {"backends": {"backend_a": 1.0}}}',
            client_api_keys_json='["client-key-123"]',
            admin_api_keys_json='["admin-key-789"]',
            pricing_json='{"gpt-4": {"input_per_million": 10.0, "output_per_million": 30.0}}',
            backend_cycle_start_day_json='{"backend_a": 1}',
            backend_cycle_allowance_usd_json='{"backend_a": 200.0}',
            backend_initial_estimated_remaining_usd_json='{"backend_a": 200.0}',
            retry_attempts=2,
            retry_max_delay_seconds=0.01,
        )
        monkeypatch.setattr("foundry_router.main.load_settings", lambda: single_backend_settings)
        monkeypatch.setattr("foundry_router.auth.load_settings", lambda: single_backend_settings)
        monkeypatch.setattr(
            "foundry_router.backends.load_settings", lambda: single_backend_settings
        )
        monkeypatch.setattr("foundry_router.config.load_settings", lambda: single_backend_settings)

        respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(200, headers={"content-type": "text/event-stream"}))
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "Hello", "stream": True},
        )
        assert response.status_code == 503
        assert response.headers["retry-after"] == "1"
        assert response.json()["error"]["type"] == "upstream_unavailable"

    @respx.mock
    def test_failover_uses_backend_specific_credentials(self) -> None:
        route_a = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(503, json={"error": "busy"}))
        route_b = respx.post(
            "https://b.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(200, json={"id": "ok"}))

        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123", "authorization": "Bearer secret-client"},
            json={"model": "gpt-4", "input": "Hello"},
        )

        assert response.status_code == 200
        assert route_a.calls[0].request.headers["api-key"] == "key-a"
        assert route_b.calls[0].request.headers["api-key"] == "key-b"
        assert "authorization" not in route_a.calls[0].request.headers
        assert "authorization" not in route_b.calls[0].request.headers

    @respx.mock
    def test_non_2xx_response_releases_reservation_without_charge(self, monkeypatch) -> None:
        single_backend_settings = Settings(
            backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key-a", "deployment": "gpt-4"}}',
            models_json='{"gpt-4": {"backends": {"backend_a": 1.0}}}',
            client_api_keys_json='["client-key-123"]',
            admin_api_keys_json='["admin-key-789"]',
            pricing_json='{"gpt-4": {"input_per_million": 10.0, "output_per_million": 30.0}}',
            backend_cycle_start_day_json='{"backend_a": 1}',
            backend_cycle_allowance_usd_json='{"backend_a": 200.0}',
            backend_initial_estimated_remaining_usd_json='{"backend_a": 200.0}',
            retry_attempts=1,
            retry_max_delay_seconds=0.01,
        )
        monkeypatch.setattr("foundry_router.main.load_settings", lambda: single_backend_settings)
        monkeypatch.setattr("foundry_router.auth.load_settings", lambda: single_backend_settings)
        monkeypatch.setattr(
            "foundry_router.backends.load_settings", lambda: single_backend_settings
        )
        monkeypatch.setattr("foundry_router.config.load_settings", lambda: single_backend_settings)

        respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4/responses",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(400, json={"error": {"message": "bad request"}}))

        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "Hello"},
        )

        assert response.status_code == 400
        from foundry_router.main import _credit_store

        assessment = asyncio.run(
            _credit_store.assess(
                "backend_a",
                0.0,
                min_credit_reserve_usd=0.0,
                min_credit_reserve_percent=0.0,
            )
        )
        assert assessment.available_credit_usd == pytest.approx(200.0)

    def test_cancelled_first_backend_releases_credit_reservation(self) -> None:
        settings = Settings(
            backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "a", "deployment": "gpt-4"}}',
            models_json='{"gpt-4": {"backends": {"backend_a": 1.0}}}',
            client_api_keys_json='["client"]',
            admin_api_keys_json='["admin"]',
            pricing_json='{"gpt-4": {"input_per_million": 10.0, "output_per_million": 30.0}}',
            backend_cycle_start_day_json='{"backend_a": 1}',
            backend_cycle_allowance_usd_json='{"backend_a": 200.0}',
            backend_initial_estimated_remaining_usd_json='{"backend_a": 200.0}',
            retry_attempts=1,
            retry_max_delay_seconds=0.01,
        )

        async def execute(_backend_id: str) -> BackendRequestResult:
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            asyncio.run(
                _execute_with_single_failover(
                    settings,
                    "gpt-4",
                    operation="responses",
                    body={"model": "gpt-4", "input": "hello"},
                    request_id="req-cancelled-first",
                    execute_backend=execute,
                )
            )

        from foundry_router.main import _credit_store

        assessment = asyncio.run(
            _credit_store.assess(
                "backend_a",
                0.0,
                min_credit_reserve_usd=0.0,
                min_credit_reserve_percent=0.0,
            )
        )
        assert assessment.available_credit_usd == pytest.approx(200.0)

    def test_second_backend_exception_releases_credit_reservation(self) -> None:
        settings = Settings(
            backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "a", "deployment": "gpt-4"}, "backend_b": {"endpoint": "https://b.openai.azure.com", "credential": "b", "deployment": "gpt-4"}}',
            models_json='{"gpt-4": {"backends": {"backend_a": 1.0, "backend_b": 0.9}}}',
            client_api_keys_json='["client"]',
            admin_api_keys_json='["admin"]',
            pricing_json='{"gpt-4": {"input_per_million": 10.0, "output_per_million": 30.0}}',
            backend_cycle_start_day_json='{"backend_a": 1, "backend_b": 1}',
            backend_cycle_allowance_usd_json='{"backend_a": 200.0, "backend_b": 200.0}',
            backend_initial_estimated_remaining_usd_json='{"backend_a": 200.0, "backend_b": 200.0}',
            retry_attempts=1,
            retry_max_delay_seconds=0.01,
        )
        calls: list[str] = []

        async def execute(backend_id: str) -> BackendRequestResult:
            calls.append(backend_id)
            if backend_id == "backend_a":
                return BackendRequestResult(Response(503), retryable_failure=True)
            raise RuntimeError("secondary backend failure")

        with pytest.raises(RuntimeError, match="secondary backend failure"):
            asyncio.run(
                _execute_with_single_failover(
                    settings,
                    "gpt-4",
                    operation="responses",
                    body={"model": "gpt-4", "input": "hello"},
                    request_id="req-second-exception",
                    execute_backend=execute,
                )
            )
        assert calls == ["backend_a", "backend_b"]

        from foundry_router.main import _credit_store

        assessment = asyncio.run(
            _credit_store.assess(
                "backend_a",
                0.0,
                min_credit_reserve_usd=0.0,
                min_credit_reserve_percent=0.0,
            )
        )
        assert assessment.available_credit_usd == pytest.approx(200.0)

    def test_stream_response_uses_terminal_usage_to_finalize_charge(self, monkeypatch) -> None:
        finalize_calls: list[dict[str, float | bool | str | None]] = []

        async def capture_finalize(
            request_id: str,
            *,
            charge_reserved: bool,
            charged_cost_usd: float | None,
        ) -> None:
            finalize_calls.append(
                {
                    "request_id": request_id,
                    "charge_reserved": charge_reserved,
                    "charged_cost_usd": charged_cost_usd,
                }
            )

        monkeypatch.setattr("foundry_router.main._credit_store.finalize_request", capture_finalize)

        class Context:
            async def __aexit__(self, *_args) -> None:
                return None

        async def chunks():
            yield (
                b'data: {"type":"response.completed","usage":{"input_tokens":10,'
                b'"output_tokens":5}}\n\n'
            )
            yield b"data: [DONE]\\n\\n"

        async def consume_stream() -> None:
            stream = _stream_response(
                chunks(),
                b'data: {"id":"one"}\n\n',
                Context(),
                request_id="req-stream-usage",
                backend_id="backend_a",
                cooldown_seconds=10.0,
                model="gpt-4",
                pricing={
                    "gpt-4": type(
                        "PricingStub",
                        (),
                        {"input_per_million": 10.0, "output_per_million": 30.0},
                    )(),
                },
                status_code=200,
            )
            async for _ in stream:
                pass

        asyncio.run(consume_stream())
        assert len(finalize_calls) == 1
        assert finalize_calls[0]["request_id"] == "req-stream-usage"
        assert finalize_calls[0]["charge_reserved"] is True
        assert finalize_calls[0]["charged_cost_usd"] == pytest.approx(0.00025)


class TestCorrelationId:
    def test_correlation_id_in_response_header(self) -> None:
        response: Response = client.get("/health/live")
        assert "x-request-id" in response.headers
        assert len(response.headers["x-request-id"]) > 0

    def test_correlation_id_propagated(self) -> None:
        custom_id = "custom-request-id-123"
        response: Response = client.get("/health/live", headers={"x-request-id": custom_id})
        assert response.headers["x-request-id"] == custom_id

    def test_invalid_correlation_id_is_replaced(self) -> None:
        response: Response = client.get("/health/live", headers={"x-request-id": "bad id"})
        assert response.headers["x-request-id"] != "bad id"
        assert len(response.headers["x-request-id"]) > 0


class TestErrorHandling:
    def test_unknown_endpoint_returns_404(self) -> None:
        response: Response = client.get("/unknown")
        assert response.status_code == 404

    def test_exception_handler_does_not_log_exception_message(self, monkeypatch) -> None:
        secret_message = "Bearer secret-token prompt=private output=hidden"
        exception = RuntimeError(secret_message)
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/health/live",
                "headers": [],
            }
        )
        request.state.correlation_id = "test-request"
        events = []

        def capture_event(*args, **kwargs):
            events.append((args, kwargs))

        monkeypatch.setattr("foundry_router.main.logger.error", capture_event)

        response = asyncio.run(global_exception_handler(request, exception))

        assert response.status_code == 500
        assert events
        assert secret_message not in str(events)
