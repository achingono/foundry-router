"""Foundry provider routes, image ownership, and local credit integrity."""

import asyncio
import base64
import hashlib
import json
import time
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from openai.types.responses.response_output_item import ImageGenerationCall
from pydantic import ValidationError
from test_google_lifecycle import FakeBackendClient, FakeStreamContext, FakeUpstream

from foundry_router.api.adapters import get_adapter
from foundry_router.api.adapters.azure_mai import AzureMaiAdapter, translate_mai_image_output
from foundry_router.api.common import api_error
from foundry_router.api.google_output_delivery import GeneratedOutputDeliveryMiddleware
from foundry_router.api.google_output_png import inspect_output_png
from foundry_router.api.routes.openai import build_router
from foundry_router.auth import verify_client_auth
from foundry_router.backends import AllowedBackendClient
from foundry_router.config import BackendConfig, Settings
from foundry_router.credit import InMemoryCreditStore, estimate_request_cost
from foundry_router.forwarding import forward_non_streaming_with_retries
from foundry_router.health import InMemoryHealthStore
from foundry_router.logging import get_logger
from foundry_router.metrics import InMemoryMetricsStore
from tests.unit.test_google_output_png import png
from tests.unit.test_opencode_anthropic import message

BODY = {
    "model": "logical",
    "input": "synthetic",
    "store": False,
    "tools": [{"type": "image_generation", "output_format": "png", "size": "1024x1024"}],
}
BASE = {
    "provider": "azure_mai",
    "endpoint": "https://resource.example.test",
    "credential": "synthetic",
    "deployment": "physical",
    "credit_group": "account",
}


def settings(provider="azure_mai", **kwargs):
    return Settings(
        _env_file=None,
        backends_json=json.dumps({"a": {**BASE, "provider": provider}}),
        models_json='{"logical":{"backends":{"a":1},"streaming_enabled":false}}',
        client_api_keys_json='["synthetic"]',
        admin_api_keys_json='["synthetic-admin"]',
        pricing_json='{"logical":{"input_per_million":0,"output_per_million":0,"image_output_per_image":0.2}}',
        backend_cycle_start_day_json='{"account":1}',
        backend_cycle_allowance_usd_json='{"account":10}',
        backend_initial_estimated_remaining_usd_json='{"account":10}',
        min_credit_reserve_usd=0,
        min_credit_reserve_percent=0,
        **kwargs,
    )


def envelope():
    return {"data": [{"b64_json": base64.b64encode(png()).decode()}]}


class Lease:
    instances: ClassVar[list] = []
    failure = None
    delivery_deadline = None

    def __init__(self, slots=1, allow_c2pa=False):
        self.allow_c2pa = allow_c2pa
        self.slots = slots
        self.closes = 0
        self.instances.append(self)

    async def ready(self, *, deadline):
        return True

    def bind_delivery_deadline(self, deadline):
        self.delivery_deadline = deadline

    async def inspect(self, raw, *, deadline):
        if self.failure:
            raise self.failure
        inspect_output_png(raw, allow_c2pa=self.allow_c2pa)
        return SimpleNamespace(decoded_bytes=len(raw), digest=hashlib.sha256(raw).hexdigest())

    def close(self):
        self.closes += 1


@pytest.mark.parametrize("provider", ["azure_anthropic", "azure_mai"])
@pytest.mark.parametrize(
    "patch",
    [
        {"endpoint": "https://resource.example.test/path/.."},
        {"endpoint": "https://resource.example.test/mai/v1"},
        {"endpoint": "https://resource.example.test/%2e"},
        {"deployment": "a/b"},
        {"deployment": ".."},
        {"credit_metered": False},
        {"api_surface": "native"},
        {"supported_operations": ["embeddings"]},
    ],
)
def test_unsafe_provider_config_rejected(provider, patch):
    with pytest.raises(ValidationError):
        BackendConfig(**{**BASE, "provider": provider, **patch})


@pytest.mark.parametrize(
    "field,value",
    [
        ("streaming_enabled", True),
        ("continuation_policy", "bound_history_required"),
    ],
)
def test_image_pool_cannot_advertise_unsupported_state(field, value):
    config = settings()
    data = config.model_dump()
    data["models_json"] = json.dumps({"logical": {"backends": {"a": 1}, field: value}})
    with pytest.raises(ValidationError):
        Settings(**data)


@pytest.mark.parametrize("price", [0, -1, None])
def test_image_missing_or_nonpositive_ceiling_fails(price):
    config = settings().model_dump()
    config["pricing_json"] = json.dumps(
        {
            "logical": {
                "input_per_million": 0,
                "output_per_million": 0,
                "image_output_per_image": price,
            }
        }
    )
    with pytest.raises(ValidationError):
        Settings(**config)


@pytest.mark.parametrize(
    "provider,path",
    [
        ("azure_anthropic", "/anthropic/v1/messages"),
        ("azure_mai", "/mai/v1/images/generations"),
    ],
)
async def test_resource_route_auth_and_physical_identity(monkeypatch, provider, path):
    config = settings(provider)
    monkeypatch.setattr("foundry_router.backends.load_settings", lambda: config)
    client = AllowedBackendClient()
    try:
        assert str(client._backend_url("a", "responses")) == "https://resource.example.test" + path
        for operation, streaming in (("embeddings", False), ("responses", True)):
            with pytest.raises(ValueError):
                client._backend_url("a", operation, streaming=streaming)
        headers = client._backend_headers(
            "a",
            {
                "Authorization": "untrusted",
                "X-Api-Key": "untrusted",
                "Api-Key": "untrusted",
                "Anthropic-Version": "untrusted",
                "Anthropic-Beta": "untrusted",
            },
        )
        assert headers["api-key"] == "synthetic" and "untrusted" not in httpx.Headers(headers).get(
            "api-key"
        )
        if provider == "azure_anthropic":
            assert httpx.Headers(headers)["x-api-key"] == "synthetic"
            assert httpx.Headers(headers)["anthropic-version"] == "2023-06-01"
            assert "anthropic-beta" not in httpx.Headers(headers)
        original = {"model": "logical", "input": "x"}
        assert client.prepare_upstream_payload("a", original)["model"] == "physical"
        assert original["model"] == "logical"
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "patch",
    [
        {"stream": True},
        {"store": True},
        {"input": []},
        {"input": "x" * 65537},
        {"instructions": "x"},
        {"max_output_tokens": 1},
        {"tools": []},
        {"web_grounding": True},
        {"metadata": {"k": []}},
    ],
)
def test_mai_rejects_features_before_assembly(patch):
    adapter = AzureMaiAdapter()
    assert adapter.check_request("responses", {**BODY, **patch}) is not None
    with pytest.raises(ValueError):
        adapter.build_upstream_body(
            "responses", {**BODY, **patch}, deployment="physical", default_output_tokens=1
        )


def test_mai_request_and_cache_inclusive_anthropic_usage():
    adapter = AzureMaiAdapter()
    assert adapter.build_upstream_body(
        "responses", BODY, deployment="physical", default_output_tokens=1
    ) == {"model": "physical", "prompt": "synthetic", "width": 1024, "height": 1024}
    assert adapter.extract_usage("responses", envelope()) == (None, None)
    with pytest.raises(ValueError):
        adapter.translate_success("responses", envelope(), logical_model="logical")
    with pytest.raises(ValueError):
        adapter.create_stream_decoder(logical_model="logical")
    text = get_adapter("azure_anthropic")
    assert text.extract_usage("responses", message()) == (15, 5)
    assert (
        text.translate_success("responses", message(), logical_model="logical").body["model"]
        == "logical"
    )


async def test_worker_validated_image_is_consumable_without_fabricated_usage():
    result = await translate_mai_image_output(
        envelope(),
        request_body=BODY,
        logical_model="logical",
        lease=Lease(),
        deadline=time.monotonic() + 1,
    )
    assert result.body["usage"] is None and result.body["model"] == "logical"
    item = ImageGenerationCall.model_validate(result.body["output"][0])
    assert base64.b64decode(item.result) == png()
    assert len(result.body["output"]) == 1


@pytest.mark.parametrize(
    "raw",
    [
        {},
        {"data": []},
        {"data": [{}, {}]},
        {"data": [{"b64_json": "!!"}]},
        {"data": [{"url": "https://untrusted.test"}]},
        {"data": [{"b64_json": "AAAA"}], "state": "private"},
    ],
)
async def test_malformed_image_never_exposes_provider_artifact(raw):
    with pytest.raises(ValueError):
        await translate_mai_image_output(
            raw,
            request_body=BODY,
            logical_model="logical",
            lease=Lease(),
            deadline=time.monotonic() + 1,
        )


@pytest.mark.parametrize("failure", [None, OSError("PRIVATE"), TimeoutError("PRIVATE")])
async def test_api_image_cost_and_exactly_once_lease_cleanup(monkeypatch, failure):
    import foundry_router.api.routes.openai as routes

    config = settings()
    store = InMemoryCreditStore()
    await store.sync_from_settings(config)
    backend = FakeBackendClient()
    backend.handler = lambda *_: FakeStreamContext(
        FakeUpstream(body=json.dumps(envelope()).encode())
    )
    Lease.instances = []
    monkeypatch.setattr(Lease, "failure", failure)
    monkeypatch.setattr(routes, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(routes, "OutputInspectionLease", Lease)
    app = FastAPI()
    app.dependency_overrides[verify_client_auth] = lambda: None

    @app.middleware("http")
    async def request_identity(request, call_next):
        request.state.correlation_id = "synthetic"
        request.state.request_key = "synthetic"
        return await call_next(request)

    app.add_middleware(GeneratedOutputDeliveryMiddleware)
    app.include_router(
        build_router(
            load_settings_fn=lambda: config,
            get_backend_client_fn=lambda: backend,
            sleep_fn=asyncio.sleep,
            health_store=InMemoryHealthStore(),
            credit_store=store,
            metrics_store=InMemoryMetricsStore(),
            logger=get_logger(__name__),
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="https://router.test"
    ) as c:
        response = await c.post("/openai/v1/responses", json=BODY)
    assert response.status_code == (200 if failure is None else 502)
    live = (
        await store.live_snapshot(
            ["account"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
        )
    )["account"]
    assert live.estimated_remaining_usd == pytest.approx(9.8)
    assert live.debited_usd_total == pytest.approx(0.2) and live.active_reservations == 0
    assert len(backend.calls) == 1 and backend.contexts[0].closed
    assert len(Lease.instances) == 1 and Lease.instances[0].closes == 1
    assert Lease.instances[0].allow_c2pa is True
    assert b"PRIVATE" not in response.content


@pytest.mark.parametrize("before_dispatch", [False, True])
async def test_cancel_retains_image_cost_only_after_dispatch(before_dispatch):
    config = settings()
    backend = FakeBackendClient()
    started = asyncio.Event()

    class BlockingLease(Lease):
        async def inspect(self, *_args, **_kwargs):
            started.set()
            await asyncio.Event().wait()

    backend.handler = lambda *_: FakeStreamContext(
        FakeUpstream(body=json.dumps(envelope()).encode())
    )
    deadline = time.monotonic() - 1 if before_dispatch else time.monotonic() + 2
    task = asyncio.create_task(
        forward_non_streaming_with_retries(
            settings=config,
            backend_id="a",
            operation="responses",
            headers={},
            body=BODY,
            get_backend_client=lambda: backend,
            set_backend_active=AsyncMock(),
            set_backend_cooldown=AsyncMock(),
            sleep=asyncio.sleep,
            api_error=api_error,
            output_lease=BlockingLease(),
            reservation_deadline_monotonic=deadline,
        )
    )
    if not before_dispatch:
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
    result = await task
    assert result.response.status_code == 502
    assert result.confirmed_pre_dispatch == before_dispatch
    assert result.force_charge is not before_dispatch
    assert len(backend.calls) == (0 if before_dispatch else 1)
    if not before_dispatch:
        estimate = estimate_request_cost(
            model="logical",
            operation="responses",
            body=BODY,
            pricing=config.pricing,
            settings=config,
        )
        assert result.settlement_cost_usd == estimate.estimated_cost_usd == 0.2
        assert backend.contexts[0].closed


async def test_mai_native_metadata_is_ignored_without_invented_usage():
    native = envelope() | {
        "created": 123,
        "model": "physical",
        "usage": {"output_tokens": 99},
        "metadata": {"private": "do not project"},
    }
    result = await translate_mai_image_output(
        native,
        request_body=BODY,
        logical_model="logical",
        lease=Lease(),
        deadline=time.monotonic() + 1,
    )
    assert result.body["usage"] is None
    assert "private" not in json.dumps(result.body)
    assert result.body["model"] == "logical"
