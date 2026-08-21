"""Unit tests for main application."""

from __future__ import annotations

import asyncio

import pytest
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
            backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key"}}',
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

    def test_responses_stub(self) -> None:
        response: Response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gpt-4", "input": "Hello"},
        )
        assert response.status_code == 501
        assert "not yet implemented" in response.json()["error"]["message"]

    def test_embeddings_stub(self) -> None:
        response: Response = client.post(
            "/openai/v1/embeddings",
            headers={"api-key": "client-key-123"},
            json={"model": "text-embedding-3-large", "input": "Hello"},
        )
        assert response.status_code == 501
        assert "not yet implemented" in response.json()["error"]["message"]


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
