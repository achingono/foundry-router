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
from foundry_router.main import (
    BackendHealthState,
    _parse_retry_after,
    _reset_backend_health_state,
    _set_backend_cooldown,
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
        pricing_json='{"gpt-4": {"input_per_million": 10.0, "output_per_million": 30.0}}',
        backend_cycle_start_day_json='{"backend_a": 1, "backend_b": 1}',
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
    yield test_settings
    asyncio.run(_reset_backend_health_state())


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
        ).mock(return_value=Response(200, json={"id": "response-test", "output": []}))
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
            pricing_json="{}",
            backend_cycle_start_day_json='{"backend_a": 1}',
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
        assert route_a.call_count == 2

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
            pricing_json="{}",
            backend_cycle_start_day_json='{"backend_a": 1}',
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

    @respx.mock
    def test_empty_responses_stream_returns_upstream_error(self, monkeypatch) -> None:
        single_backend_settings = Settings(
            backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key-a", "deployment": "gpt-4"}}',
            models_json='{"gpt-4": {"backends": {"backend_a": 1.0}}}',
            client_api_keys_json='["client-key-123"]',
            admin_api_keys_json='["admin-key-789"]',
            pricing_json="{}",
            backend_cycle_start_day_json='{"backend_a": 1}',
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
        assert response.status_code == 502
        assert response.json()["error"]["type"] == "upstream_error"

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
