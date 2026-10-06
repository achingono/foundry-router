"""Synthetic Linux HTTP/admission/settlement/actual worker measurement; no network."""

from __future__ import annotations

import argparse
import asyncio
import base64
import importlib.util
import json
import random
import struct
import time
import zlib
from collections import Counter
from pathlib import Path

import httpx
from fastapi import FastAPI, Request

from foundry_router.api.routes.openai import build_router
from foundry_router.auth import verify_client_auth
from foundry_router.backends import AllowedBackendClient
from foundry_router.config import Settings
from foundry_router.config.google_features import GoogleFeatureProfile
from foundry_router.credit import InMemoryCreditStore, estimate_request_cost
from foundry_router.health import InMemoryHealthStore
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.ratelimit import InMemoryRateLimitStore

spec = importlib.util.spec_from_file_location(
    "png_benchmark", Path(__file__).with_name("google-output-png-benchmark.py")
)
assert spec is not None and spec.loader is not None
png_benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(png_benchmark)


RSS_LIMIT_BYTES = 128 * 1024 * 1024
SETTLEMENT_TOLERANCE = 1e-8


class LocalSettings(Settings):
    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        _ = settings_cls, env_settings, dotenv_settings, file_secret_settings
        return (init_settings,)


class QuietLogger:
    def info(self, *args, **kwargs):
        pass

    warning = info
    error = info
    debug = info
    exception = info


async def run(invalid, combined=False, exact=False, mixed=False, audio=False):  # noqa: PLR0912, PLR0915 -- isolated harness
    if audio and combined:
        raise ValueError("Generated audio supports no input media")
    raw = (
        struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            480036,
            b"WAVE",
            b"fmt ",
            16,
            1,
            1,
            24000,
            48000,
            2,
            16,
            b"data",
            479998 if invalid else 480000,
        )
        + b"\0" * 480000
        if audio
        else png_benchmark.fixture(invalid, exact)
    )
    encoded = base64.b64encode(raw).decode()
    settings = LocalSettings(
        _env_file=None,
        backends_json=json.dumps(
            {
                "g": {
                    "provider": "google_ai_studio",
                    "api_surface": "native",
                    "endpoint": "https://synthetic.example.test",
                    "deployment": "configured",
                    "credential": "synthetic",
                    "quota_group": "project",
                    "google_features": {"native_thinking_disabled": True},
                }
            }
        ),
        models_json='{"m":{"backends":{"g":1}}}',
        client_api_keys_json='["synthetic-caller"]',
        admin_api_keys_json='["synthetic-admin"]',
        pricing_json='{"m":{"input_per_million":10,"output_per_million":30,"image_output_per_image":0.2,"audio_output_per_second":0.01}}',
        backend_cycle_start_day_json='{"g":1}',
        backend_cycle_allowance_usd_json='{"g":1000}',
        backend_initial_estimated_remaining_usd_json='{"g":1000}',
        quota_group_rate_limits_json='{"project":{"rpm":100000,"tpm":10000000}}',
        protected_emergency_fallback=False,
        state_backend="memory",
        reservation_max_age_seconds=30,
    )
    # Synthetic harness only: no supported runtime enablement switch bypasses the gate.
    settings.backends["g"].google_features = GoogleFeatureProfile(
        features=("image_output", "inline_images") if combined else ("image_output",),
        combinations=(("image_output", "inline_images"),) if combined else (),
        image_input_tokens=258 if combined else None,
        image_token_pricing=combined,
        max_image_bytes=524288,
        max_total_image_bytes=1048576,
        native_thinking_disabled=True,
        generated_output_tokens_bound=2048,
        image_output_price_ceiling_usd=0.2,
        image_output_input_token_pricing=True,
        image_output_quota_via_rpm=True,
        image_output_input_tpm_tokens=True,
        image_output_ipm=100000,
    )
    if audio:
        settings.backends["g"].google_features = GoogleFeatureProfile(
            features=("audio_output",),
            generated_output_tokens_bound=2048,
            audio_output_voices=("Kore",),
            audio_output_thinking_policy="omit",
            audio_output_thinking_affirmed=True,
            audio_output_price_ceiling_usd_per_second=0.01,
            audio_output_input_token_pricing=True,
            audio_output_quota_via_rpm=True,
            audio_output_input_tpm_tokens=True,
            audio_output_rpm=100000,
        )
    public_input: object = "synthetic"
    input_bytes = 0
    if combined:
        rows = random.Random(8).randbytes(384 * 384 * 3)
        raster = b"".join(b"\0" + rows[i * 1152 : (i + 1) * 1152] for i in range(384))
        compressed = zlib.compress(raster)
        if exact:
            for split in range(1, 100):
                compressor = zlib.compressobj()
                head = compressor.compress(raster[:split]) + compressor.flush(zlib.Z_SYNC_FLUSH)
                tail = compressor.compress(raster[split:]) + compressor.flush()
                remaining = 524288 - 57 - len(head) - len(tail)
                if remaining >= 0 and remaining % 5 == 0:
                    compressed = head + b"\0\0\0\xff\xff" * (remaining // 5) + tail
                    break
            else:
                raise ValueError("Exact input fixture cannot be constructed")
        input_png = (
            b"\x89PNG\r\n\x1a\n"
            + png_benchmark.chunk(b"IHDR", struct.pack(">IIBBBBB", 384, 384, 8, 2, 0, 0, 0))
            + png_benchmark.chunk(b"IDAT", compressed)
            + png_benchmark.chunk(b"IEND", b"")
        )
        input_bytes = 2 * len(input_png)
        uri = "data:image/png;base64," + base64.b64encode(input_png).decode()
        public_input = [
            {
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": uri},
                    {"type": "input_image", "image_url": uri},
                ],
            }
        ]
        settings.pricing["m"].image_input_tokens = 258
    if mixed:
        if not combined and not audio:
            raise ValueError("Mixed capacity requires combined image or audio workload")
        settings.backends["plain"] = settings.backends["g"].model_copy(
            update={
                "credit_group": "plain",
                "google_features": GoogleFeatureProfile(
                    features=("image_output",),
                    native_thinking_disabled=True,
                    generated_output_tokens_bound=2048,
                    image_output_price_ceiling_usd=0.2,
                    image_output_input_token_pricing=True,
                    image_output_quota_via_rpm=True,
                    image_output_input_tpm_tokens=True,
                    image_output_ipm=100000,
                ),
            }
        )
        settings.models["plain"] = settings.models["m"].model_copy(
            update={"backends": {"plain": 1}}
        )
        settings.pricing["plain"] = settings.pricing["m"].model_copy()
        settings.backend_cycle_start_day["plain"] = 1
        settings.backend_cycle_allowance_usd["plain"] = 1000
        settings.backend_initial_estimated_remaining_usd["plain"] = 1000
    image_encoded = (
        base64.b64encode(png_benchmark.fixture(exact=True)).decode() if audio and mixed else encoded
    )
    request_bodies = {
        "m": {"model": "m", "input": public_input},
        "plain": {"model": "plain", "input": "synthetic"},
    }
    for name, body in request_bodies.items():
        if audio and name == "m":
            body["foundry_audio_generation"] = {"version": 1, "format": "wav", "voice": "Kore"}
        else:
            body["tools"] = [
                {"type": "image_generation", "output_format": "png", "size": "1024x1024"}
            ]
    estimated = {
        name: estimate_request_cost(
            model=name,
            operation="responses",
            body=request_bodies[name],
            pricing=settings.pricing,
            settings=settings,
        ).estimated_cost_usd
        for name in settings.models
    }
    dispatch_counts = Counter()
    dispatches = 0

    async def provider(request):
        nonlocal dispatches
        if request.url.host != "synthetic.example.test":
            raise ValueError("Unexpected synthetic destination")
        upstream = json.loads(request.content)
        is_audio = upstream["generationConfig"]["responseModalities"] == ["AUDIO"]
        name = (
            "m"
            if not mixed or is_audio or (combined and len(upstream["contents"][0]["parts"]) > 1)
            else "plain"
        )
        dispatch_counts[name] += 1
        dispatches += 1
        await asyncio.sleep(0.005)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "audio/wav" if is_audio else "image/png",
                                        "data": encoded if is_audio or not audio else image_encoded,
                                    }
                                }
                            ],
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 4,
                    "candidatesTokenCount": 2,
                    "totalTokenCount": 6,
                },
            },
        )

    backend = AllowedBackendClient(settings=settings)
    await backend._client.aclose()
    backend._client = httpx.AsyncClient(transport=httpx.MockTransport(provider))
    credit = InMemoryCreditStore()
    health = InMemoryHealthStore()
    quota = InMemoryRateLimitStore()
    app = FastAPI()
    sequence = 0

    async def authenticate(request: Request):
        nonlocal sequence
        sequence += 1
        request.state.request_key = f"synthetic-{sequence}"
        request.state.correlation_id = request.state.request_key
        return "synthetic-caller"

    app.dependency_overrides[verify_client_auth] = authenticate
    app.include_router(
        build_router(
            load_settings_fn=lambda: settings,
            get_backend_client_fn=lambda: backend,
            sleep_fn=asyncio.sleep,
            health_store=health,
            credit_store=credit,
            metrics_store=InMemoryMetricsStore(),
            rate_limit_store=quota,
            logger=QuietLogger(),
        )
    )
    baseline = png_benchmark.aggregate_rss()
    peak = baseline
    running = True
    delays = []
    latencies = []
    statuses = Counter()
    pool_statuses = {name: Counter() for name in settings.models}
    output_valid = True

    async def monitor():
        nonlocal peak
        while running:
            start = time.monotonic()
            await asyncio.sleep(0.005)
            delays.append(max(0, time.monotonic() - start - 0.005))
            peak = max(peak, png_benchmark.aggregate_rss())

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://synthetic.test"
    ) as client:

        async def caller(index):
            nonlocal output_valid
            for _ in range(100):
                start = time.monotonic()
                result = await client.post(
                    "/openai/v1/responses",
                    json=request_bodies["plain" if mixed and index % 2 else "m"],
                )
                statuses[result.status_code] += 1
                pool_statuses["plain" if mixed and index % 2 else "m"][result.status_code] += 1
                if result.status_code == httpx.codes.OK:
                    payload = result.json()
                    if audio and not (mixed and index % 2):
                        output_valid &= (
                            payload["output"] == []
                            and payload["foundry_generated_audio"]["data"] == encoded
                        )
                    else:
                        items = payload["output"]
                        output_valid &= (
                            len(items) == 1
                            and items[0]["type"] == "image_generation_call"
                            and items[0]["result"] == image_encoded
                        )
                        del items
                    del payload
                latencies.append(time.monotonic() - start)
                # Consume and release the synthetic client's output before the
                # next request, matching a reader that does not retain artifacts.
                del result
                await asyncio.sleep(0.001)

        watcher = asyncio.create_task(monitor())
        try:
            async with asyncio.timeout(60):
                await asyncio.gather(*(caller(index) for index in range(8)))
        finally:
            running = False
            await watcher
            await backend._client.aclose()
    snapshots = await credit.live_snapshot(
        list(settings.backends), min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    snapshot = snapshots["g"]
    settlement_valid = all(
        item.reserved_inflight_usd == 0
        and item.active_reservations == 0
        and abs(1000 - item.estimated_remaining_usd - dispatch_counts[name] * estimated[name])
        < SETTLEMENT_TOLERANCE
        for backend_name, item in snapshots.items()
        for name in ["m" if backend_name == "g" else "plain"]
    )
    quota_snapshot = (await quota.snapshot_quota_groups(["project"]))["project"]
    quota_valid = (
        quota_snapshot.rpm_used_60s == dispatches
        and quota_snapshot.input_tpm_used_60s == 4 * dispatches
        and not quota._reservations
    )
    outcomes_valid = all(
        dispatch_counts[name] > 0
        and outcomes[502 if invalid and (name == "m" or not audio) else 200]
        == dispatch_counts[name]
        and set(outcomes) <= {502 if invalid and (name == "m" or not audio) else 200, 503}
        for name, outcomes in pool_statuses.items()
    )
    return {
        "synthetic_only": True,
        "network_disabled": True,
        "workload": ("header-invalid" if audio else "late-invalid") if invalid else "near-maximum",
        "scope": (
            "bare route HTTP/admission/settlement/readiness; actual finite parser; "
            "synthetic provider; no delivery-owner claim"
        ),
        "callers": 8,
        "attempts_per_caller": 100,
        "media_type": "audio/wav" if audio else "image/png",
        "decoded_bytes": len(raw),
        "expanded_bytes": 480000 if audio else 4195328,
        "input_image_decoded_bytes": input_bytes,
        "client_releases_consumed_output": True,
        "mixed_output_pool_capacities": mixed,
        "outcomes": dict(statuses),
        "outcomes_by_pool": {name: dict(value) for name, value in pool_statuses.items()},
        "provider_dispatches": dispatches,
        "output_valid": output_valid,
        "settlement_valid": settlement_valid,
        "quota_valid": quota_valid,
        "project_request_count": quota_snapshot.rpm_used_60s,
        "project_input_token_count": quota_snapshot.input_tpm_used_60s,
        "credit_partitions": {
            name: {
                "remaining_usd": item.estimated_remaining_usd,
                "inflight_usd": item.reserved_inflight_usd,
                "active_reservations": item.active_reservations,
            }
            for name, item in snapshots.items()
        },
        "dispatches_by_pool": dict(dispatch_counts),
        "reserved_inflight_usd": snapshot.reserved_inflight_usd,
        "estimated_remaining_usd": snapshot.estimated_remaining_usd,
        "baseline_parent_children_rss": baseline,
        "sampled_peak_parent_children_rss": peak,
        "incremental_parent_children_rss": peak - baseline,
        "container_peak_bytes": png_benchmark.container_peak(),
        "container_memory_bytes": 536870912,
        "container_cpus": 2,
        "max_loop_delay_ms": max(delays) * 1000,
        "max_request_ms": max(latencies) * 1000,
        "passed": outcomes_valid
        and output_valid
        and settlement_valid
        and quota_valid
        and peak - baseline <= RSS_LIMIT_BYTES,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", action="store_true")
    parser.add_argument("--invalid", action="store_true")
    parser.add_argument("--combined", action="store_true")
    parser.add_argument("--exact", action="store_true")
    parser.add_argument("--mixed", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(run(args.invalid, args.combined, args.exact, args.mixed, args.audio))
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["passed"] else 1)
