"""No-network Linux fixture: real bounded children plus native mocked transport."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import struct
import sys
import zlib

import httpx
from fastapi import FastAPI
from structlog import get_logger

from foundry_router.api.azure_intake import AzureIntakeDeliveryMiddleware, AzureIntakeRuntime
from foundry_router.api.google_output_delivery import GeneratedOutputDeliveryMiddleware
from foundry_router.api.routes.openai import build_router
from foundry_router.auth import verify_client_auth
from foundry_router.backends import AllowedBackendClient
from foundry_router.config import Settings
from foundry_router.credit import InMemoryCreditStore
from foundry_router.health import InMemoryHealthStore
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.ratelimit import InMemoryRateLimitStore

MIB = 1024 * 1024


class Events(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'data: {"type":"response.output_text.delta","delta":"ok"}\n\n'
        yield b'data: {"type":"response.completed","response":{"usage":{"input_tokens":5,"output_tokens":2}}}\n\n'
        yield b"data: [DONE]\n\n"


async def verify(provider: str = "azure_foundry") -> dict[str, object]:  # noqa: PLR0915 -- complete owned lifetime fixture
    if sys.platform != "linux":
        raise AssertionError("Linux fixture required")
    settings = Settings(
        _env_file=None,
        client_api_keys_json='["synthetic-client"]',
        admin_api_keys_json='["synthetic-admin"]',
        backends_json=json.dumps(
            {
                "a": {
                    "endpoint": "https://native.invalid",
                    "credential": "synthetic-provider",
                    "deployment": "physical-a",
                    "provider": provider,
                }
            }
        ),
        models_json=json.dumps(
            {"logical": {"backends": {"a": 1}, "streaming_enabled": provider == "azure_foundry"}}
        ),
        model_aliases_json='{"alias":"logical"}',
        pricing_json=json.dumps(
            {
                "logical": {
                    "input_per_million": 0 if provider == "azure_mai" else 10,
                    "output_per_million": 0 if provider == "azure_mai" else 30,
                    **({"image_output_per_image": 0.1} if provider == "azure_mai" else {}),
                }
            }
        ),
        backend_cycle_start_day_json='{"a":1}',
        backend_cycle_allowance_usd_json='{"a":200}',
        backend_initial_estimated_remaining_usd_json='{"a":200}',
        azure_intake_enabled=True,
        azure_max_request_body_bytes=32 * MIB,
        azure_intake_scratch_bytes=96 * MIB,
        azure_intake_child_address_space_bytes=8 * 1024 * MIB,
        retry_attempts=2,
    )
    processes = []
    original_spawn = asyncio.create_subprocess_exec
    os.environ["INTAKE_SYNTHETIC_SECRET"] = "must-not-inherit"

    async def spawn(*args, **kwargs):
        if any("azure_intake_worker" in str(arg) for arg in args):
            environment = kwargs["env"]
            assert "INTAKE_SYNTHETIC_SECRET" not in environment
            assert kwargs["close_fds"] is True
            process = await original_spawn(*args, **kwargs)
            processes.append(process)
            return process
        return await original_spawn(*args, **kwargs)

    asyncio.create_subprocess_exec = spawn
    runtime = AzureIntakeRuntime(settings)
    await runtime.start(settings)
    if not runtime.matches(settings):
        raise AssertionError("Native startup probe failed")
    root = runtime.resources.root
    assert (await asyncio.to_thread(root.stat)).st_mode & 0o777 == 0o700
    client = AllowedBackendClient(settings=settings)
    await client._client.aclose()
    upstream_count = 0
    lengths = []

    def png_chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    image = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1024, 1024, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress((b"\0" * 4097) * 1024))
        + png_chunk(b"IEND", b"")
    )

    async def handler(request):
        nonlocal upstream_count
        wire = await request.aread()
        assert int(request.headers["content-length"]) == len(wire)
        assert len(request.headers.get_list("content-type")) == 1
        body = json.loads(wire)
        assert body["model"] == "physical-a"
        lengths.append(len(wire))
        upstream_count += 1
        if body.get("stream"):
            return httpx.Response(
                200, stream=Events(), headers={"content-type": "text/event-stream"}
            )
        if provider == "azure_anthropic":
            assert len(body["messages"][0]["content"][0]["text"].encode()) > 2 * MIB
            return httpx.Response(
                200,
                json={
                    "id": "msg_test",
                    "type": "message",
                    "role": "assistant",
                    "model": "physical-a",
                    "content": [{"type": "text", "text": "ok"}],
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {"input_tokens": 5, "output_tokens": 2},
                },
            )
        if provider == "azure_mai":
            assert len(body["prompt"].encode()) > 2 * MIB
            return httpx.Response(
                200, json={"data": [{"b64_json": base64.b64encode(image).decode()}]}
            )
        return httpx.Response(200, json={"usage": {"input_tokens": 5, "output_tokens": 2}})

    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    credit = InMemoryCreditStore()
    app = FastAPI()
    app.state.azure_intake_runtime = runtime
    app.dependency_overrides[verify_client_auth] = lambda: None

    async def no_sleep(_seconds):
        return None

    app.include_router(
        build_router(
            load_settings_fn=lambda: settings,
            get_backend_client_fn=lambda: client,
            sleep_fn=no_sleep,
            health_store=InMemoryHealthStore(),
            credit_store=credit,
            metrics_store=InMemoryMetricsStore(),
            rate_limit_store=InMemoryRateLimitStore(),
            logger=get_logger(),
        )
    )
    app.add_middleware(AzureIntakeDeliveryMiddleware)
    app.add_middleware(GeneratedOutputDeliveryMiddleware)

    async def identity(scope, receive, send):
        scope.setdefault("state", {}).update(
            request_key="synthetic-request", correlation_id="synthetic-correlation"
        )
        await app(scope, receive, send)

    results = []
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=identity), base_url="http://synthetic"
        ) as downstream:
            cases = [("x" * (8 * MIB), False), ("é" * (4 * MIB), False)]
            if provider == "azure_foundry":
                cases = [("ordinary", False), *cases, ("x" * (8 * MIB), True)]
            for text, stream in cases:
                payload = {"input": text, "metadata": {"note": "😀" * 512}, "model": "alias"}
                if provider == "azure_mai":
                    payload["tools"] = [
                        {"type": "image_generation", "output_format": "png", "size": "1024x1024"}
                    ]
                else:
                    payload.update(max_output_tokens=8, stream=stream)
                raw = json.dumps(payload, ensure_ascii=False).encode()
                response = await downstream.post(
                    "/openai/v1/responses",
                    content=raw,
                    headers={"content-type": "application/json"},
                )
                assert response.status_code == 200, response.content[:1024]
                if stream:
                    assert response.content.endswith(b"data: [DONE]\n\n")
                if provider != "azure_foundry":
                    assert response.json()["metadata"] == payload["metadata"]
                if provider == "azure_mai":
                    assert (
                        response.json()["output"][0]["result"] == base64.b64encode(image).decode()
                    )
                assert runtime.resources.active == runtime.resources.scratch_reserved == 0
                assert not runtime.resources.leases and not list(root.iterdir())
                assert not credit._reservations
                results.append(
                    {
                        "literal_unicode": text.startswith("é"),
                        "stream": stream,
                        "input_bytes": len(raw),
                    }
                )
        assert len(processes) == (7 if provider == "azure_foundry" else 5) and all(
            process.returncode == 0 for process in processes
        )
        assert len({process.pid for process in processes}) == len(processes)
        return {
            "passed": True,
            "linux": True,
            "native_children": len(processes) if provider == "azure_foundry" else 0,
            "translated_children": len(processes) if provider != "azure_foundry" else 0,
            "provider": provider,
            "child_exit_codes": [process.returncode for process in processes],
            "no_inherited_secret": True,
            "closed_unrelated_fds": True,
            "private_root": True,
            "requests": results,
            "upstream_dispatches": upstream_count,
            "encoded_lengths": lengths,
            "all_leases_clean": True,
            "no_provider_network": True,
            "capacity_acceptance": False,
        }
    finally:
        await client.aclose()
        await runtime.close()
        assert not await asyncio.to_thread(root.exists)
        asyncio.create_subprocess_exec = original_spawn


async def verify_all():
    receipts = [
        await verify(provider) for provider in ("azure_foundry", "azure_anthropic", "azure_mai")
    ]
    native = receipts[0]
    native["translated_children"] = sum(item["translated_children"] for item in receipts)
    native["translated_receipts"] = receipts[1:]
    return native


if __name__ == "__main__":
    print(json.dumps(asyncio.run(verify_all()), sort_keys=True))
