"""Configured compatible root, model, credential and text capability boundaries."""

import asyncio
import json
import time

import pytest
from pydantic import ValidationError

from foundry_router.api.adapters import get_adapter
from foundry_router.api.adapters.compatible_text import (
    MAX_HISTORY_ITEMS,
    MAX_TEXT_BYTES,
    MAX_TEXT_PARTS,
    CompatibleTextAdapter,
)
from foundry_router.backends import AllowedBackendClient, SecurityError
from foundry_router.config import BackendConfig, Settings


def backend(**patch):
    return BackendConfig(
        provider="openai_compatible",
        endpoint="https://compatible.example.test/api/v1",
        credential="server-marker",
        deployment="organization/model",
        **patch,
    )


@pytest.mark.parametrize(
    "root",
    [
        "https://example.test/v1/../admin",
        "https://example.test/v1/%2e%2e/admin",
        "https://example.test/v1/%2fadmin",
        "https://example.test/v1/%5cadmin",
        "https://example.test/v1\\admin",
        "https://example.test/v1//admin",
        "https://example.test/v1/chat/completions",
        "https://example.test/v1/embeddings",
        "https://user:secret@example.test/v1",
        "https://example.test/v1?key=secret",
        "https://example.test/v1#frag",
        "http://example.test/v1",
    ],
)
def test_unsafe_raw_api_roots_rejected(root):
    with pytest.raises(ValidationError):
        BackendConfig(
            provider="openai_compatible",
            endpoint=root,
            credential="synthetic",
            deployment="organization/model",
        )


@pytest.mark.parametrize(
    "patch",
    [
        {"api_surface": "native"},
        {"google_features": {"native_thinking_disabled": True}},
        {"deployment": "x" * 513},
        {"deployment": "bad\nmodel"},
        {"deployment": None},
    ],
)
def test_provider_configuration_fail_closed(patch):
    values = {
        "provider": "openai_compatible",
        "endpoint": "https://example.test/v1",
        "credential": "synthetic",
        "deployment": "organization/model",
    }
    with pytest.raises(ValidationError):
        BackendConfig(**{**values, **patch})


@pytest.mark.parametrize("provider", ["azure_foundry", "google_ai_studio"])
def test_existing_path_model_restrictions_preserved(provider):
    with pytest.raises(ValidationError, match="path segment"):
        BackendConfig(
            provider=provider,
            endpoint="https://example.test",
            credential="synthetic",
            deployment="organization/model",
        )


def test_namespaced_model_root_bearer_and_confinement():
    settings = Settings(
        backends_json=json.dumps({"compatible": backend().model_dump(mode="json")}),
        models_json='{"m":{"backends":{"compatible":1}}}',
        client_api_keys_json='["synthetic"]',
        admin_api_keys_json='["synthetic-admin"]',
    )
    client = AllowedBackendClient(settings=settings)
    assert (
        str(client._backend_url("compatible", "responses"))
        == "https://compatible.example.test/api/v1/chat/completions"
    )
    assert (
        str(client._backend_url("compatible", "embeddings"))
        == "https://compatible.example.test/api/v1/embeddings"
    )
    headers = client._backend_headers(
        "compatible",
        {
            "Authorization": "caller-marker",
            "api-key": "caller-marker",
            "x-goog-api-key": "caller-marker",
            "cookie": "caller-marker",
            "forwarded": "caller-marker",
            "X-Request-ID": "owned",
        },
    )
    assert headers == {"authorization": "Bearer server-marker", "X-Request-ID": "owned"}
    for operation in ("responses", "embeddings"):
        assert (
            client.prepare_upstream_payload("compatible", {"model": "alias"}, operation)["model"]
            == "organization/model"
        )
    for target in (
        "https://compatible.example.test/admin",
        "https://compatible.example.test:444/api/v1/chat/completions",
        "https://other.example.test/api/v1/chat/completions",
    ):
        with pytest.raises(SecurityError):
            client._validate_url(target, "compatible")
    with pytest.raises(ValueError):
        client._backend_url("compatible", "models")
    asyncio.run(client.aclose())


def test_independent_text_history_and_instructions():
    adapter = get_adapter("openai_compatible")
    assert isinstance(adapter, CompatibleTextAdapter)
    body = {
        "instructions": "system",
        "input": [
            {"role": "developer", "content": "developer"},
            {
                "role": "user",
                "content": [{"type": "input_text", "text": "one"}, {"type": "text", "text": "two"}],
            },
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "answer"}],
            },
        ],
    }
    assert adapter.check_request("responses", body) is None
    upstream = adapter.build_upstream_body(
        "responses", body, deployment="organization/model", default_output_tokens=8
    )
    assert upstream["model"] == "organization/model"
    assert upstream["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "developer", "content": "developer"},
        {"role": "user", "content": "onetwo"},
        {"role": "assistant", "content": "answer"},
    ]


@pytest.mark.parametrize(
    "patch",
    [
        {"tools": []},
        {"text": {"format": {"type": "json_object"}}},
        {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_image", "image_url": "https://outside.test"}],
                }
            ]
        },
        {"input": [{"role": "assistant", "content": "x", "foundry_provider_state": {}}]},
        {"input": [{"type": "function_call", "call_id": "x"}]},
        {"input": [{"role": "user", "content": "x"}] * (MAX_HISTORY_ITEMS + 1)},
        {"input": "x" * (MAX_TEXT_BYTES + 1)},
        {
            "input": [
                {"role": "user", "content": [{"type": "text", "text": "x"}] * (MAX_TEXT_PARTS + 1)}
            ]
        },
        {"input": [{"role": "tool", "content": "x"}]},
        {"input": [{"role": "user", "content": [["nested"]]}]},
    ],
)
def test_text_contract_and_history_bounds(patch):
    assert CompatibleTextAdapter().check_request("responses", {"input": "x", **patch}) is not None


def test_intake_deadline_and_calls_fail_closed():
    adapter = CompatibleTextAdapter()
    assert (
        adapter.check_request("responses", {"input": "x"}, deadline_monotonic=time.monotonic() - 1)
        is not None
    )
    for raw in (None, [{}]):
        with pytest.raises(ValueError):
            adapter.translate_calls(raw, adapter.request_context({}), completed=True, refusal=False)
