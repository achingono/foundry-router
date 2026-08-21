"""Integration tests for full request flow."""

from __future__ import annotations

import subprocess
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from foundry_router.config import Settings
from foundry_router.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_settings(monkeypatch):
    test_settings = Settings(
        backends_json='{"mock_backend": {"endpoint": "https://testserver", "credential": "mock-key", "deployment": "gpt-4"}}',
        models_json='{"gpt-4": {"backends": {"mock_backend": 1.0}}}',
        client_api_keys_json='["client-key-123"]',
        admin_api_keys_json='["admin-key-789"]',
        pricing_json="{}",
        backend_cycle_start_day_json="{}",
    )
    monkeypatch.setattr("foundry_router.main.load_settings", lambda: test_settings)
    monkeypatch.setattr("foundry_router.auth.load_settings", lambda: test_settings)
    monkeypatch.setattr("foundry_router.backends.load_settings", lambda: test_settings)
    monkeypatch.setattr("foundry_router.config.load_settings", lambda: test_settings)


class TestFullFlow:
    def test_health_endpoints_without_auth(self) -> None:
        # Liveness
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

        # Readiness
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["ready"] is True

    def test_admin_endpoint_requires_admin_auth(self) -> None:
        response = client.get("/admin/status")
        assert response.status_code == 401

        response = client.get("/admin/status", headers={"x-admin-key": "admin-key-789"})
        assert response.status_code == 200

    def test_openai_endpoints_require_client_auth(self) -> None:
        response = client.get("/openai/v1/models")
        assert response.status_code == 401

        response = client.post("/openai/v1/responses", json={})
        assert response.status_code == 401

        response = client.post("/openai/v1/embeddings", json={})
        assert response.status_code == 401

    def test_models_endpoint_with_auth(self) -> None:
        response = client.get("/openai/v1/models", headers={"api-key": "client-key-123"})
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 1
        assert data["data"][0]["id"] == "gpt-4"

    def test_unknown_model_returns_404(self) -> None:
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "unknown-model", "input": "Hello"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["type"] == "model_not_found"

    def test_malformed_request_returns_422(self) -> None:
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"invalid": "request"},
        )
        assert response.status_code == 422

    def test_correlation_id_in_all_responses(self) -> None:
        endpoints = [
            ("GET", "/health/live"),
            ("GET", "/health/ready"),
            ("GET", "/admin/status", {"x-admin-key": "admin-key-789"}),
            ("GET", "/openai/v1/models", {"api-key": "client-key-123"}),
        ]

        for method, path, *headers in endpoints:
            header_dict = headers[0] if headers else {}
            if method == "GET":
                response = client.get(path, headers=header_dict)
            else:
                response = client.post(path, headers=header_dict, json={})

            assert "x-request-id" in response.headers
            assert len(response.headers["x-request-id"]) > 0


class TestSecurity:
    def test_client_key_not_accepted_for_admin(self) -> None:
        response = client.get("/admin/status", headers={"x-admin-key": "client-key-123"})
        assert response.status_code == 401

    def test_admin_key_not_accepted_for_client(self) -> None:
        response = client.get("/openai/v1/models", headers={"api-key": "admin-key-789"})
        assert response.status_code == 401

    def test_bearer_token_works_for_client(self) -> None:
        response = client.get(
            "/openai/v1/models", headers={"Authorization": "Bearer client-key-123"}
        )
        assert response.status_code == 200

    def test_bearer_token_works_for_admin(self) -> None:
        response = client.get("/admin/status", headers={"Authorization": "Bearer admin-key-789"})
        assert response.status_code == 200


class TestLoggingRedaction:
    def test_no_secrets_in_logs(self, caplog):
        import logging

        caplog.set_level(logging.INFO)

        client.get("/openai/v1/models", headers={"api-key": "client-key-123"})

        # Check that no log contains the API key
        for record in caplog.records:
            assert "client-key-123" not in record.getMessage()
            assert (
                "REDACTED" not in record.getMessage() or "client-key-123" not in record.getMessage()
            )


class TestDockerBuild:
    """Test that Docker image builds and runs."""

    @pytest.mark.slow
    @pytest.mark.docker
    def test_docker_build_and_health(self):
        """Build Docker image and verify health endpoint."""
        # This test requires Docker and is marked as slow
        # Run with: pytest -m docker tests/integration/test_full_flow.py::TestDockerBuild::test_docker_build_and_health

        # Build image
        result = subprocess.run(
            ["docker", "build", "-t", "foundry-router:test-integration", "."],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, f"Docker build failed: {result.stderr}"

        try:
            # Run container
            run_result = subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    "foundry-router-test",
                    "-p",
                    "18000:8000",
                    "-e",
                    'FOUNDRY_BACKENDS_JSON={"mock": {"endpoint": "https://mock.openai.azure.com", "credential": "key", "deployment": "gpt-4"}}',
                    "-e",
                    'FOUNDRY_MODELS_JSON={"gpt-4": {"backends": {"mock": 1.0}}}',
                    "-e",
                    'FOUNDRY_CLIENT_API_KEYS_JSON=["client-key"]',
                    "-e",
                    'FOUNDRY_ADMIN_API_KEYS_JSON=["admin-key"]',
                    "-e",
                    "FOUNDRY_PRICING_JSON={}",
                    "-e",
                    "FOUNDRY_BACKEND_CYCLE_START_DAY_JSON={}",
                    "foundry-router:test-integration",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert run_result.returncode == 0, f"Docker run failed: {run_result.stderr}"

            # Wait for startup
            time.sleep(3)

            # Test health endpoint
            for _ in range(10):
                try:
                    response = httpx.get("http://localhost:18000/health/live", timeout=2)
                    if response.status_code == 200:
                        break
                except Exception:
                    pass
                time.sleep(1)
            else:
                pytest.fail("Health endpoint did not become ready")

            assert response.json() == {"status": "alive"}

        finally:
            # Cleanup
            subprocess.run(["docker", "stop", "foundry-router-test"], capture_output=True)
            subprocess.run(["docker", "rm", "foundry-router-test"], capture_output=True)
