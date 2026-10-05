"""Integration tests for full request flow."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from foundry_router.config import Settings
from foundry_router.main import (
    _rate_limit_store,
    _reset_backend_health_state,
    _reset_credit_state,
    _reset_metrics_state,
    _reset_rate_limit_state,
    app,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_settings(monkeypatch):
    test_settings = Settings(
        backends_json='{"mock_backend": {"endpoint": "https://testserver", "credential": "mock-key", "deployment": "gpt-4"}}',
        models_json='{"gpt-4": {"backends": {"mock_backend": 1.0}}}',
        client_api_keys_json='["client-key-123"]',
        admin_api_keys_json='["admin-key-789"]',
        pricing_json='{"gpt-4": {"input_per_million": 10.0, "output_per_million": 30.0}}',
        backend_cycle_start_day_json='{"mock_backend": 1}',
        backend_cycle_allowance_usd_json='{"mock_backend": 200.0}',
        backend_initial_estimated_remaining_usd_json='{"mock_backend": 200.0}',
    )
    monkeypatch.setattr("foundry_router.main.load_settings", lambda: test_settings)
    monkeypatch.setattr("foundry_router.auth.load_settings", lambda: test_settings)
    monkeypatch.setattr("foundry_router.backends.load_settings", lambda: test_settings)
    monkeypatch.setattr("foundry_router.backends._backend_client", None)
    monkeypatch.setattr("foundry_router.config.load_settings", lambda: test_settings)
    asyncio.run(_reset_backend_health_state())
    asyncio.run(_reset_credit_state())
    asyncio.run(_reset_metrics_state())
    asyncio.run(_reset_rate_limit_state())
    yield
    asyncio.run(_reset_backend_health_state())
    asyncio.run(_reset_credit_state())
    asyncio.run(_reset_metrics_state())
    asyncio.run(_reset_rate_limit_state())


class TestFullFlow:
    @respx.mock
    def test_google_keys_route_by_project_quota_headroom(self, monkeypatch, caplog) -> None:
        caplog.set_level(logging.INFO)
        backend_configs = {
            f"gemini-key-{suffix}": {
                "provider": "google_ai_studio",
                "endpoint": "https://generativelanguage.googleapis.com",
                "credential": f"synthetic-project-{suffix}-key",
                "deployment": "gemini-2.5-flash",
                "quota_group": f"project-{suffix}",
                "credit_metered": False,
            }
            for suffix in ("a", "b", "c")
        }
        settings = Settings(
            backends_json=json.dumps(backend_configs),
            models_json=json.dumps(
                {"gemini-2.5-flash": {"backends": dict.fromkeys(backend_configs, 1.0)}}
            ),
            client_api_keys_json='["client-key-123"]',
            admin_api_keys_json='["admin-key-789"]',
            quota_group_rate_limits_json=json.dumps(
                {
                    "project-a": {"rpm": 3, "tpm": 1000, "rpd": 100},
                    "project-b": {"rpm": 10, "tpm": 1000, "rpd": 100},
                    "project-c": {"rpm": 20, "tpm": 1000, "rpd": 100},
                }
            ),
        )
        monkeypatch.setattr("foundry_router.main.load_settings", lambda: settings)
        monkeypatch.setattr("foundry_router.auth.load_settings", lambda: settings)
        monkeypatch.setattr("foundry_router.backends.load_settings", lambda: settings)
        monkeypatch.setattr("foundry_router.config.load_settings", lambda: settings)

        async def seed_quota_usage() -> None:
            await _rate_limit_store.sync_from_settings(settings)
            await _rate_limit_store.record_estimate(
                "project-a", request_count=1, estimated_input_tokens=0
            )

        asyncio.run(seed_quota_usage())
        route = respx.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "chatcmpl-synthetic",
                    "object": "chat.completion",
                    "created": 1700000000,
                    "model": "gemini-2.5-flash",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "synthetic hello"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
                },
            )
        )

        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "gemini-2.5-flash", "input": "hello"},
        )
        status = client.get("/admin/status", headers={"x-admin-key": "admin-key-789"})
        metrics = client.get("/metrics", headers={"x-admin-key": "admin-key-789"})

        assert response.status_code == 200
        public = response.json()
        assert public["object"] == "response"
        assert public["model"] == "gemini-2.5-flash"
        assert public["status"] == "completed"
        assert public["output"][0]["content"][0]["text"] == "synthetic hello"
        assert public["usage"] == {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3}
        assert route.call_count == 1
        upstream_json = json.loads(route.calls[0].request.content)
        assert upstream_json["model"] == "gemini-2.5-flash"
        assert upstream_json["messages"] == [{"role": "user", "content": "hello"}]
        assert upstream_json["max_completion_tokens"] == 4096
        assert route.calls[0].request.headers["authorization"] == "Bearer synthetic-project-c-key"
        assert status.status_code == 200
        assert metrics.status_code == 200
        assert "synthetic-project-c-key" not in response.text
        assert "synthetic-project-c-key" not in status.text
        assert "synthetic-project-c-key" not in metrics.text
        assert all(
            "synthetic-project-c-key" not in record.getMessage() for record in caplog.records
        )
        project_c = status.json()["backends"]["gemini-key-c"]["live"]["rate_limit"]
        assert project_c["quota_group"] == "project-c"
        assert project_c["rpm_used_60s"] == 1

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
