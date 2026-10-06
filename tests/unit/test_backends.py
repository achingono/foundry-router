"""Unit tests for backend allow-list enforcement."""

from __future__ import annotations

import json
from copy import deepcopy

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
        backends_json='{"backend_a": {"endpoint": "https://allowed-a.openai.azure.com", "credential": "key-a", "deployment": "gpt-4"}, "backend_b": {"endpoint": "https://allowed-b.openai.azure.com", "credential": "key-b", "deployment": "gpt-4"}}',
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
    @pytest.mark.parametrize("streaming", [False, True], ids=["request", "stream"])
    @pytest.mark.parametrize("operation", ["responses", "embeddings"])
    @respx.mock
    async def test_azure_operation_url_and_payload_contract(
        self, test_settings, streaming, operation
    ):
        config = test_settings.backends["backend_a"]
        config.endpoint = httpx.URL("https://allowed-a.openai.azure.com/gateway/")
        config.deployment = "configured-deployment"
        config.api_version = "2024-02-01"
        body = {
            "model": "logical-alias",
            "input": [{"role": "user", "content": "hello"}],
            "metadata": {"trace": "client-trace"},
        }
        if streaming:
            body["stream"] = True
        original = deepcopy(body)
        if operation == "responses":
            url = "https://allowed-a.openai.azure.com/gateway/openai/v1/responses"
            expected_body = {**original, "model": "configured-deployment"}
        else:
            url = (
                "https://allowed-a.openai.azure.com/gateway/openai/deployments/"
                "configured-deployment/embeddings?api-version=2024-02-01"
            )
            expected_body = original
        route = respx.post(url).mock(return_value=httpx.Response(200, content=b"upstream"))

        client = AllowedBackendClient()
        try:
            if streaming:
                async with client.stream_backend("backend_a", operation, json=body) as response:
                    assert await response.aread() == b"upstream"
            else:
                response = await client.request_backend("backend_a", operation, json=body)
                assert response.content == b"upstream"
            assert route.call_count == 1
            request = route.calls[0].request
            assert str(request.url) == url
            assert json.loads(request.content) == expected_body
            assert request.headers["api-key"] == "key-a"
            assert body == original
        finally:
            await client.aclose()

    async def test_azure_payload_default_is_responses_and_returns_copy(self, test_settings):
        test_settings.backends["backend_a"].deployment = "configured-deployment"
        body = {"model": "logical-alias", "input": "hello"}
        client = AllowedBackendClient()
        try:
            payload = client.prepare_upstream_payload("backend_a", body)
            assert payload == {"model": "configured-deployment", "input": "hello"}
            assert payload is not body
            assert body == {"model": "logical-alias", "input": "hello"}
        finally:
            await client.aclose()

    @pytest.mark.parametrize("streaming", [False, True], ids=["request", "stream"])
    @pytest.mark.parametrize(
        "target",
        [
            "https://allowed-b.openai.azure.com/openai/v1/responses",
            "https://allowed-a.openai.azure.com/other/openai/v1/responses",
            "https://allowed-a.openai.azure.com/gateway-sibling/openai/v1/responses",
            "http://allowed-a.openai.azure.com/gateway/openai/v1/responses",
            "https://allowed-a.openai.azure.com:444/gateway/openai/v1/responses",
        ],
    )
    @respx.mock
    async def test_azure_responses_enforces_selected_origin_and_prefix(
        self, test_settings, monkeypatch, streaming, target
    ):
        test_settings.backends["backend_a"].endpoint = httpx.URL(
            "https://allowed-a.openai.azure.com/gateway"
        )
        client = AllowedBackendClient()
        monkeypatch.setattr(client, "_backend_url", lambda *_args: httpx.URL(target))
        try:
            with pytest.raises(SecurityError):
                if streaming:
                    async with client.stream_backend("backend_a", "responses", json={}):
                        pytest.fail("Rejected target opened a stream")
                else:
                    await client.request_backend("backend_a", "responses", json={})
            assert not respx.calls
        finally:
            await client.aclose()

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
    async def test_google_ai_studio_backend_uses_google_openai_compat_url_and_header(
        self, monkeypatch
    ):
        settings = Settings(
            backends_json='{"gemini_a": {"provider": "google_ai_studio", "endpoint": "https://generativelanguage.googleapis.com", "credential": "AIza-test-key", "deployment": "gemini-2.5-flash", "quota_group": "project-a"}}',
            models_json='{"gemini-2.5-flash": {"backends": {"gemini_a": 1.0}}}',
            client_api_keys_json='["client-key"]',
            admin_api_keys_json='["admin-key"]',
            pricing_json="{}",
            backend_cycle_start_day_json="{}",
        )
        monkeypatch.setattr("foundry_router.backends.load_settings", lambda: settings)
        monkeypatch.setattr("foundry_router.config.load_settings", lambda: settings)

        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            headers={"authorization": "Bearer AIza-test-key"},
        ).mock(return_value=httpx.Response(200, json={"ok": True}))

        client = AllowedBackendClient()
        response = await client.request_backend(
            "gemini_a",
            "chat/completions",
            json={"model": "gemini-2.5-flash", "messages": [{"role": "user", "content": "hi"}]},
            headers={"authorization": "Bearer injected", "x-goog-api-key": "injected"},
        )

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    @respx.mock
    async def test_google_ai_studio_substitutes_deployment_and_maps_responses(self, monkeypatch):
        settings = Settings(
            backends_json='{"gemini_a": {"provider": "google_ai_studio", "endpoint": "https://generativelanguage.googleapis.com", "credential": "AIza-test-key", "deployment": "gemini-2.5-flash", "quota_group": "project-a"}}',
            models_json='{"my-alias": {"backends": {"gemini_a": 1.0}}}',
            client_api_keys_json='["client-key"]',
            admin_api_keys_json='["admin-key"]',
            pricing_json="{}",
            backend_cycle_start_day_json="{}",
        )
        monkeypatch.setattr("foundry_router.backends.load_settings", lambda: settings)
        monkeypatch.setattr("foundry_router.config.load_settings", lambda: settings)

        captured: dict = {}

        def capture(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["json"] = __import__("json").loads(request.content.decode())
            return httpx.Response(200, json={"ok": True})

        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        ).mock(side_effect=capture)

        client = AllowedBackendClient()
        # Logical alias in body must be rewritten to the Google deployment id.
        assert (
            client.prepare_upstream_payload("gemini_a", {"model": "my-alias", "input": "hi"})[
                "model"
            ]
            == "gemini-2.5-flash"
        )
        # Responses operation maps onto Google-supported chat/completions.
        assert client._backend_url("gemini_a", "responses").path.endswith(
            "/v1beta/openai/chat/completions"
        )
        response = await client.request_backend(
            "gemini_a",
            "responses",
            json={"model": "my-alias", "input": "hi"},
        )
        assert response.status_code == 200
        assert captured["json"]["model"] == "gemini-2.5-flash"
        assert captured["url"].endswith("/v1beta/openai/chat/completions")

    async def test_google_ai_studio_backend_rejects_non_https_or_unapproved_host(
        self, test_settings
    ):
        client = AllowedBackendClient()

        with pytest.raises(SecurityError):
            client._validate_url(
                "http://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            )
        with pytest.raises(SecurityError):
            client._validate_url("https://not-allowed.example/v1beta/openai/chat/completions")

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
        with pytest.raises(SecurityError):
            await client.get(
                "https://allowed-a.openai.azure.com/test",
                params={"x-goog-api-key": "secret"},
            )

    async def test_request_rejects_sensitive_query_params_from_query_params_object(
        self, test_settings
    ):
        client = AllowedBackendClient()

        with pytest.raises(SecurityError):
            await client.get(
                "https://allowed-a.openai.azure.com/test",
                params=httpx.QueryParams({"api-key": "secret"}),
            )

        with pytest.raises(SecurityError):
            await client.get(
                "https://allowed-a.openai.azure.com/test",
                params=httpx.QueryParams({"x-goog-api-key": "secret"}),
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

    @respx.mock
    async def test_shared_hostname_targets_are_validated_independently(self, monkeypatch):
        settings = Settings(
            backends_json='{"backend_a": {"endpoint": "https://shared.example/a", "credential": "key-a", "deployment": "gpt-4"}, "backend_b": {"endpoint": "https://shared.example/b", "credential": "key-b", "deployment": "gpt-4"}}',
            models_json='{"gpt-4": {"backends": {"backend_a": 1.0, "backend_b": 1.0}}}',
            client_api_keys_json='["client-key"]',
            admin_api_keys_json='["admin-key"]',
            pricing_json="{}",
            backend_cycle_start_day_json="{}",
        )
        monkeypatch.setattr("foundry_router.backends.load_settings", lambda: settings)
        respx.post(
            "https://shared.example/a/openai/v1/responses",
        ).mock(return_value=httpx.Response(200, json={"ok": True}))
        client = AllowedBackendClient()
        response = await client.request_backend("backend_a", "responses", json={})
        assert response.status_code == 200


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


async def test_owned_settings_constructor_does_not_load_ambient(monkeypatch):
    from foundry_router.config import Settings

    settings = Settings(
        backends_json='{"g":{"provider":"google_ai_studio","endpoint":"https://synthetic.example.test","deployment":"configured","credential":"synthetic","credit_metered":false}}',
        models_json='{"m":{"backends":{"g":1}}}',
        client_api_keys_json='["synthetic"]',
        admin_api_keys_json='["admin-synthetic"]',
    )

    def reject_ambient():
        raise AssertionError("ambient settings read")

    monkeypatch.setattr("foundry_router.backends.load_settings", reject_ambient)
    backend = AllowedBackendClient(settings=settings)
    assert backend._settings is settings
    await backend.aclose()
