"""Unit tests for main application."""

from __future__ import annotations

import asyncio

import pytest
import respx
from fastapi import Request
from fastapi.testclient import TestClient
from httpx import Response

from foundry_router.config import Settings
from foundry_router.main import app, global_exception_handler

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_settings(monkeypatch):
    test_settings = Settings(
        backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key", "region": "eastus", "deployment": "gpt-4"}}',
        models_json='{"gpt-4": {"backends": {"backend_a": 1.0}}, "text-embedding-3-large": {"backends": {"backend_a": 1.0}}}',
        client_api_keys_json='["client-key-123"]',
        admin_api_keys_json='["admin-key-789"]',
        pricing_json='{"gpt-4": {"input_per_million": 10.0, "output_per_million": 30.0}}',
        backend_cycle_start_day_json='{"backend_a": 1}',
    )
    monkeypatch.setattr("foundry_router.main.load_settings", lambda: test_settings)
    monkeypatch.setattr("foundry_router.auth.load_settings", lambda: test_settings)
    monkeypatch.setattr("foundry_router.backends.load_settings", lambda: test_settings)
    monkeypatch.setattr("foundry_router.config.load_settings", lambda: test_settings)


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
        assert route.calls[0].request.headers["api-key"] == "key"
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
    def test_empty_responses_stream_returns_upstream_error(self) -> None:
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
