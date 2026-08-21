"""Unit tests for authentication module."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from foundry_router.auth import verify_admin_auth, verify_client_auth
from foundry_router.config import Settings

# Create test app with auth dependencies
app = FastAPI()


@app.get("/client-test")
async def client_endpoint(auth: str = Depends(verify_client_auth)):
    return {"authenticated": True, "key_prefix": auth[:8]}


@app.get("/admin-test")
async def admin_endpoint(auth: str = Depends(verify_admin_auth)):
    return {"authenticated": True, "key_prefix": auth[:8]}


client = TestClient(app)


class TestClientAuth:
    @pytest.fixture(autouse=True)
    def setup_settings(self, monkeypatch):
        # Mock settings with known keys
        test_settings = Settings(
            backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key", "deployment": "gpt-4"}}',
            models_json='{"gpt-4": {"backends": {"backend_a": 1.0}}}',
            client_api_keys_json='["client-key-123", "client-key-456"]',
            admin_api_keys_json='["admin-key-789"]',
            pricing_json="{}",
            backend_cycle_start_day_json="{}",
        )
        monkeypatch.setattr("foundry_router.auth.load_settings", lambda: test_settings)

    def test_valid_api_key_header(self) -> None:
        response: Response = client.get("/client-test", headers={"api-key": "client-key-123"})
        assert response.status_code == 200
        assert response.json()["authenticated"] is True

    def test_valid_bearer_header(self) -> None:
        response: Response = client.get(
            "/client-test", headers={"Authorization": "Bearer client-key-456"}
        )
        assert response.status_code == 200
        assert response.json()["authenticated"] is True

    def test_invalid_key(self) -> None:
        response: Response = client.get("/client-test", headers={"api-key": "invalid-key"})
        assert response.status_code == 401
        assert "Invalid client API key" in response.json()["detail"]

    def test_missing_auth(self) -> None:
        response: Response = client.get("/client-test")
        assert response.status_code == 401
        assert "Missing authentication" in response.json()["detail"]

    def test_wrong_scheme(self) -> None:
        response: Response = client.get("/client-test", headers={"Authorization": "Basic abc123"})
        assert response.status_code == 401

    def test_returns_www_authenticate_header(self) -> None:
        response: Response = client.get("/client-test", headers={"api-key": "invalid"})
        assert response.headers.get("WWW-Authenticate") == 'Bearer realm="foundry-router"'


class TestAdminAuth:
    @pytest.fixture(autouse=True)
    def setup_settings(self, monkeypatch):
        test_settings = Settings(
            backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key", "deployment": "gpt-4"}}',
            models_json='{"gpt-4": {"backends": {"backend_a": 1.0}}}',
            client_api_keys_json='["client-key-123"]',
            admin_api_keys_json='["admin-key-789", "admin-key-abc"]',
            pricing_json="{}",
            backend_cycle_start_day_json="{}",
        )
        monkeypatch.setattr("foundry_router.auth.load_settings", lambda: test_settings)

    def test_valid_admin_api_key_header(self) -> None:
        response: Response = client.get("/admin-test", headers={"x-admin-key": "admin-key-789"})
        assert response.status_code == 200
        assert response.json()["authenticated"] is True

    def test_valid_admin_bearer_header(self) -> None:
        response: Response = client.get(
            "/admin-test", headers={"Authorization": "Bearer admin-key-abc"}
        )
        assert response.status_code == 200

    def test_client_key_rejected_for_admin(self) -> None:
        response: Response = client.get("/admin-test", headers={"x-admin-key": "client-key-123"})
        assert response.status_code == 401

    def test_admin_key_rejected_for_client(self) -> None:
        response: Response = client.get("/client-test", headers={"api-key": "admin-key-789"})
        assert response.status_code == 401

    def test_invalid_admin_key(self) -> None:
        response: Response = client.get("/admin-test", headers={"x-admin-key": "invalid"})
        assert response.status_code == 401

    def test_missing_admin_auth(self) -> None:
        response: Response = client.get("/admin-test")
        assert response.status_code == 401
        assert "Missing admin authentication" in response.json()["detail"]
