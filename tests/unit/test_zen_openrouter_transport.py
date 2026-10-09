"""Unit tests for OpenCode Zen and OpenRouter backend transport."""

from __future__ import annotations

import httpx
import pytest
import respx

from foundry_router.backends import AllowedBackendClient
from foundry_router.config import Settings


def _settings(monkeypatch, backends_json: str, models_json: str) -> Settings:
    settings = Settings(
        backends_json=backends_json,
        models_json=models_json,
        client_api_keys_json='["client-key"]',
        admin_api_keys_json='["admin-key"]',
        pricing_json="{}",
        backend_cycle_start_day_json="{}",
    )
    monkeypatch.setattr("foundry_router.backends.load_settings", lambda: settings)
    monkeypatch.setattr("foundry_router.config.load_settings", lambda: settings)
    return settings


class TestZenTransport:
    @respx.mock
    async def test_zen_responses_url_auth_and_model_substitution(self, monkeypatch) -> None:
        _settings(
            monkeypatch,
            '{"zen_a": {"provider": "opencode_zen", "endpoint": "https://opencode.ai/zen/v1", "credential": "synthetic-zen-key", "deployment": "gpt-5.4"}}',
            '{"gpt-5.4": {"backends": {"zen_a": 1.0}}}',
        )
        captured: dict = {}

        def capture(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["auth"] = request.headers.get("authorization")
            import json as jsonlib

            captured["body"] = jsonlib.loads(request.content.decode())
            return httpx.Response(200, json={"ok": True})

        respx.post("https://opencode.ai/zen/v1/responses").mock(side_effect=capture)
        client = AllowedBackendClient()
        response = await client.request_backend(
            "zen_a",
            "responses",
            json={"model": "gpt-5.4", "input": "hello"},
            headers={"authorization": "Bearer caller-key", "api-key": "caller-key"},
        )
        assert response.status_code == 200
        assert captured["url"] == "https://opencode.ai/zen/v1/responses"
        assert captured["auth"] == "Bearer synthetic-zen-key"
        # Only the model is substituted; no Chat dialect is injected.
        assert captured["body"] == {"model": "gpt-5.4", "input": "hello"}

    async def test_zen_rejects_non_responses_operation(self, monkeypatch) -> None:
        _settings(
            monkeypatch,
            '{"zen_a": {"provider": "opencode_zen", "endpoint": "https://opencode.ai/zen/v1", "credential": "synthetic-zen-key", "deployment": "gpt-5.4"}}',
            '{"gpt-5.4": {"backends": {"zen_a": 1.0}}}',
        )
        client = AllowedBackendClient()
        with pytest.raises(ValueError, match="only the Responses operation"):
            await client.request_backend(
                "zen_a", "embeddings", json={"model": "gpt-5.4", "input": "hi"}
            )
        await client.aclose()


class TestOpenRouterTransport:
    @respx.mock
    async def test_openrouter_chat_url_auth_and_namespaced_model(self, monkeypatch) -> None:
        _settings(
            monkeypatch,
            '{"or_a": {"provider": "openrouter", "endpoint": "https://openrouter.ai/api/v1", "credential": "synthetic-or-key", "deployment": "organization/model"}}',
            '{"my-model": {"backends": {"or_a": 1.0}}}',
        )
        captured: dict = {}

        def capture(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["auth"] = request.headers.get("authorization")
            import json as jsonlib

            captured["body"] = jsonlib.loads(request.content.decode())
            return httpx.Response(200, json={"ok": True})

        respx.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=capture)
        client = AllowedBackendClient()
        response = await client.request_backend(
            "or_a",
            "responses",
            json={"model": "my-model", "messages": [{"role": "user", "content": "hi"}]},
            headers={"authorization": "Bearer caller-key"},
        )
        assert response.status_code == 200
        assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
        assert captured["auth"] == "Bearer synthetic-or-key"
        assert captured["body"]["model"] == "organization/model"

    @respx.mock
    async def test_openrouter_embeddings_url(self, monkeypatch) -> None:
        _settings(
            monkeypatch,
            '{"or_e": {"provider": "openrouter", "endpoint": "https://openrouter.ai/api/v1", "credential": "synthetic-or-key", "deployment": "organization/embed", "supported_operations": ["embeddings"]}}',
            '{"my-embed": {"backends": {"or_e": 1.0}}}',
        )
        respx.post("https://openrouter.ai/api/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client = AllowedBackendClient()
        response = await client.request_backend(
            "or_e", "embeddings", json={"model": "my-embed", "input": "hi"}
        )
        assert response.status_code == 200
