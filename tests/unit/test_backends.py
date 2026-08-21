"""Unit tests for backend allow-list enforcement."""

from __future__ import annotations

import httpx
import pytest
import respx

from foundry_router.backends import (
    AllowedBackendClient,
    SecurityError,
    close_backend_client,
    get_backend_client,
)
from foundry_router.config import Settings


@pytest.fixture
def test_settings(monkeypatch):
    settings = Settings(
        backends_json='{"backend_a": {"endpoint": "https://allowed-a.openai.azure.com", "credential": "key-a"}, "backend_b": {"endpoint": "https://allowed-b.openai.azure.com", "credential": "key-b"}}',
        models_json='{"gpt-4": {"backends": {"backend_a": 1.0}}}',
        client_api_keys_json='["client-key"]',
        admin_api_keys_json='["admin-key"]',
        pricing_json="{}",
        backend_cycle_start_day_json="{}",
    )
    monkeypatch.setattr("foundry_router.backends.load_settings", lambda: settings)
    monkeypatch.setattr("foundry_router.config.load_settings", lambda: settings)
    yield settings
    # Cleanup
    import foundry_router.backends as backends_module

    backends_module._backend_client = None


class TestAllowedBackendClient:
    def test_allowed_hostname_succeeds(self, test_settings):
        client = AllowedBackendClient()
        assert "allowed-a.openai.azure.com" in client.allowed_hostnames
        assert "allowed-b.openai.azure.com" in client.allowed_hostnames

    @respx.mock
    async def test_request_to_allowed_backend_succeeds(self, test_settings):
        respx.get("https://allowed-a.openai.azure.com/test").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        client = AllowedBackendClient()
        response = await client.get("https://allowed-a.openai.azure.com/test")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    @respx.mock
    async def test_request_to_blocked_backend_raises(self, test_settings):
        respx.get("https://blocked.openai.azure.com/test").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        client = AllowedBackendClient()

        with pytest.raises(SecurityError, match="blocked.*not in configured backend allow-list"):
            await client.get("https://blocked.openai.azure.com/test")

    async def test_request_rejects_wrong_origin_components(self, test_settings):
        client = AllowedBackendClient()

        with pytest.raises(SecurityError):
            await client.get("http://allowed-a.openai.azure.com/test")
        with pytest.raises(SecurityError):
            await client.get("https://allowed-a.openai.azure.com:444/test")
        with pytest.raises(SecurityError):
            await client.get("https://user:pass@allowed-a.openai.azure.com/test")

    async def test_request_rejects_redirects_and_credentials(self, test_settings):
        client = AllowedBackendClient()

        with pytest.raises(SecurityError):
            await client.get("https://allowed-a.openai.azure.com/test", follow_redirects=True)
        with pytest.raises(SecurityError):
            await client.get("https://allowed-a.openai.azure.com/test", auth=("user", "pass"))
        with pytest.raises(SecurityError):
            await client.get("https://allowed-a.openai.azure.com/test", cookies={"key": "value"})
        with pytest.raises(SecurityError):
            await client.get(
                "https://allowed-a.openai.azure.com/test",
                params={"api-key": "secret"},
            )

    @respx.mock
    async def test_request_strips_sensitive_headers(self, test_settings):
        captured_headers = {}

        def capture_headers(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, json={"ok": True})

        respx.get("https://allowed-a.openai.azure.com/test").mock(side_effect=capture_headers)

        client = AllowedBackendClient()
        await client.get(
            "https://allowed-a.openai.azure.com/test",
            headers={
                "Authorization": "Bearer secret",
                "api-key": "secret-key",
                "x-api-key": "secret",
                "Cookie": "session=abc",
                "Content-Type": "application/json",
                "X-Custom-Header": "keep-this",
            },
        )

        # Sensitive headers should be stripped
        assert "Authorization" not in captured_headers
        assert "api-key" not in captured_headers
        assert "x-api-key" not in captured_headers
        assert "Cookie" not in captured_headers

        # Safe headers should be preserved
        assert captured_headers.get("content-type") == "application/json"
        assert captured_headers.get("x-custom-header") == "keep-this"

    @respx.mock
    async def test_stream_request_allowed(self, test_settings):
        respx.get("https://allowed-a.openai.azure.com/stream").mock(
            return_value=httpx.Response(200, text="data: chunk1\n\ndata: chunk2\n\n")
        )

        client = AllowedBackendClient()
        async with client.stream("GET", "https://allowed-a.openai.azure.com/stream") as response:
            assert response.status_code == 200

    @respx.mock
    async def test_stream_request_blocked(self, test_settings):
        respx.get("https://blocked.openai.azure.com/stream").mock(return_value=httpx.Response(200))

        client = AllowedBackendClient()

        with pytest.raises(SecurityError):
            async with client.stream("GET", "https://blocked.openai.azure.com/stream"):
                pass


class TestGlobalBackendClient:
    async def test_get_backend_client_returns_singleton(self, test_settings):
        client1 = get_backend_client()
        client2 = get_backend_client()
        assert client1 is client2

    async def test_close_backend_client(self, test_settings):
        client = get_backend_client()
        await close_backend_client()
        import foundry_router.backends as backends_module

        assert backends_module._backend_client is None

        # Getting again should create new instance
        new_client = get_backend_client()
        assert new_client is not client
