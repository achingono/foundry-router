"""Synthetic full HTTP signed lifecycle benchmark; never reads keys or calls providers."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import platform
import resource
import struct
import time
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import httpx

import foundry_router.api.google_intake as intake
from foundry_router.api import common
from foundry_router.backends import AllowedBackendClient
from foundry_router.config import Settings
from foundry_router.main import _health_store, app

CALLERS = 8
ATTEMPTS = 100


def configured(*, audio: bool = False, pdf: bool = False, video: bool = False) -> Settings:
    keys = {
        "scope_key": base64.urlsafe_b64encode(b"s" * 32).decode(),
        "keys": {"fixture": base64.urlsafe_b64encode(b"k" * 32).decode()},
        "active": "fixture",
        "generation": "fixture",
    }
    settings = Settings(
        backends_json=json.dumps(
            {
                "g": {
                    "provider": "google_ai_studio",
                    "api_surface": "native",
                    "endpoint": "https://fixture.example.test",
                    "credential": "fixture",
                    "deployment": "fixture",
                    "credit_metered": False,
                    "google_features": {
                        "native_thinking_disabled": True,
                        **(
                            {
                                "features": ["inline_video"],
                                "video_input_tokens_per_frame": 258,
                                "video_token_pricing": True,
                                "video_tpm_tokens": True,
                            }
                            if video
                            else {}
                        ),
                        **(
                            {
                                "features": ["inline_audio", "inline_pdfs"]
                                if pdf
                                else ["inline_audio"],
                                **(
                                    {
                                        "combinations": [["inline_audio", "inline_pdfs"]],
                                        "pdf_input_tokens_per_page": 258,
                                        "pdf_native_text_tokens_per_page": 65536,
                                        "pdf_token_pricing": True,
                                    }
                                    if pdf
                                    else {}
                                ),
                                "audio_input_tokens_per_second": 32,
                                "audio_token_pricing": True,
                                "audio_tpm_tokens": True,
                            }
                            if audio
                            else {}
                        ),
                    },
                }
            }
        ),
        models_json='{"m":{"backends":{"g":1}}}',
        client_api_keys_json='["fixture"]',
        admin_api_keys_json='["admin-fixture"]',
        google_state_keys_json=json.dumps(keys),
    )
    if audio or video:
        return settings
    # Synthetic harness only: startup remains disabled pending benchmark/review.
    settings.backends["g"].google_features = settings.backends["g"].google_features.model_copy(
        update={
            "continuation_policy": "sealed_native",
            "native_thinking_budget": 0,
            "thought_token_pricing": True,
            "signature_input_token_bound": 2000000,
        }
    )
    settings.models["m"].continuation_policy = "bound_history_required"
    return settings


def rss() -> int:
    if platform.system() == "Linux":
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


async def run(  # noqa: PLR0912, PLR0915 -- complete benchmark ownership
    workload: str, pdf_fixture: Path | None = None, video_fixture: Path | None = None
) -> dict:
    audio_workload = workload in {"audio", "audio_pdf"}
    settings = configured(
        audio=audio_workload, pdf=workload == "audio_pdf", video=workload == "video"
    )
    signatures = base64.b64encode(
        b"x" * (16384 if workload in {"signature", "aggregate"} else 1)
    ).decode()
    parts = [
        {"text": "fixture", "thoughtSignature": signatures}
        for _ in range(
            64
            if workload == "parts"
            else 16
            if workload == "carriers"
            else 2
            if workload == "aggregate"
            else 1
        )
    ]
    if audio_workload or workload == "video":
        parts = [{"text": "fixture"}]
    provider = {
        "candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 3, "totalTokenCount": 7},
    }
    body = {
        "model": "m",
        "input": [{"role": "user", "content": "fixture"}],
        "foundry_provider_state": {"version": 1},
        "max_output_tokens": 10,
    }
    if audio_workload:
        raw = (
            struct.pack(
                "<4sI4s4sIHHIIHH4sI",
                b"RIFF",
                320036,
                b"WAVE",
                b"fmt ",
                16,
                1,
                1,
                16000,
                32000,
                2,
                16,
                b"data",
                320000,
            )
            + b"\0" * 320000
        )
        part = {
            "type": "input_file",
            "filename": "fixture.wav",
            "file_data": "data:audio/wav;base64," + base64.b64encode(raw).decode(),
        }
        body["input"] = [{"role": "user", "content": [part, part]}]
        body.pop("foundry_provider_state")
    if workload == "audio_pdf":
        if pdf_fixture is None:
            raise ValueError("Synthetic PDF fixture required")
        body["input"][0]["content"].append(
            {
                "type": "input_file",
                "filename": "fixture.pdf",
                "file_data": "data:application/pdf;base64,"
                + base64.b64encode(await asyncio.to_thread(pdf_fixture.read_bytes)).decode(),
            }
        )
    if workload == "video":
        if video_fixture is None:
            raise ValueError("Synthetic AVI fixture required")
        part = {
            "type": "input_file",
            "filename": "fixture.avi",
            "file_data": "data:video/avi;base64,"
            + base64.b64encode(await asyncio.to_thread(video_fixture.read_bytes)).decode(),
        }
        body["input"] = [{"role": "user", "content": [part, part]}]
        body.pop("foundry_provider_state")
    if workload == "context":
        body["instructions"] = "x" * 120000

    stage_timings: dict[str, list[float]] = {"raw_json_parse": [], "snapshot_encode": []}

    def timed(name, function):
        def measure(*args, **kwargs):
            started = time.monotonic()
            try:
                return function(*args, **kwargs)
            finally:
                stage_timings[name].append(time.monotonic() - started)

        return measure

    delays = []
    latencies = []
    counts: dict[int, int] = {}
    baseline = rss()
    peak = baseline
    active = True

    async def sample():
        nonlocal peak
        while active:
            begin = time.monotonic()
            await asyncio.sleep(0.005)
            delays.append(max(0, time.monotonic() - begin - 0.005))
            peak = max(peak, rss())

    with patch("foundry_router.backends.load_settings", return_value=settings):
        backend = AllowedBackendClient()
    await backend._client.aclose()
    backend._client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: (
                httpx.Response(
                    200,
                    content=f"data: {json.dumps(provider)}\n\n".encode(),
                    headers={"content-type": "text/event-stream"},
                )
                if "streamGenerateContent" in str(request.url)
                else httpx.Response(200, json=provider)
            )
        )
    )
    patches = [
        patch(name, return_value=settings)
        for name in [
            "foundry_router.main.load_settings",
            "foundry_router.auth.load_settings",
            "foundry_router.config.load_settings",
        ]
    ]
    patches.append(patch("foundry_router.backends._backend_client", backend))
    patches.append(
        patch.object(common, "load_bounded_json", timed("raw_json_parse", common.load_bounded_json))
    )
    patches.append(
        patch.object(
            intake, "canonical_wire_bytes", timed("snapshot_encode", intake.canonical_wire_bytes)
        )
    )
    for item in patches:
        item.start()
    monitor = asyncio.create_task(sample())
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://fixture.test"
        ) as client:
            initial = await client.post(
                "/openai/v1/responses",
                headers={"api-key": "fixture"},
                json=body,
            )
            if workload in {"history", "aggregate"}:
                for _ in range(14 if workload == "history" else 2):
                    body = {
                        **body,
                        "input": [
                            *body["input"],
                            *initial.json()["output"],
                            {"role": "user", "content": "next"},
                        ],
                    }
                    initial = await client.post(
                        "/openai/v1/responses", headers={"api-key": "fixture"}, json=body
                    )
                    if initial.status_code != HTTPStatus.OK:
                        raise ValueError("Synthetic history seed failed")
            if initial.status_code != HTTPStatus.OK and workload != "parts":
                raise ValueError("Synthetic seed failed")
            if workload == "parts":
                await _health_store.set_backend_active("g")
            replay = {
                **body,
                "input": [
                    *body["input"],
                    *(initial.json()["output"] if initial.status_code == HTTPStatus.OK else []),
                    {"role": "user", "content": "next"},
                ],
            }

            request_wires = [
                json.dumps({**replay, "stream": stream}).encode() for stream in (False, True)
            ]

            async def caller():
                for index in range(ATTEMPTS):
                    begin = time.monotonic()
                    response = await client.post(
                        "/openai/v1/responses",
                        content=request_wires[index % 2],
                        headers={"api-key": "fixture", "content-type": "application/json"},
                    )
                    counts[response.status_code] = counts.get(response.status_code, 0) + 1
                    latencies.append(time.monotonic() - begin)
                    if workload == "parts":
                        await _health_store.set_backend_active("g")
                    await asyncio.sleep(0)

            async with asyncio.timeout(60):
                await asyncio.gather(*(caller() for _ in range(CALLERS)))
    finally:
        active = False
        await monitor
        for item in reversed(patches):
            item.stop()
        await backend.aclose()
    return {
        "workload": workload,
        "max_stage_ms": {
            name: max(values, default=0) * 1000 for name, values in stage_timings.items()
        },
        "platform": platform.platform(),
        "callers": CALLERS,
        "attempts_per_caller": ATTEMPTS,
        "input_history_items": len(replay["input"]),
        "signed_input_carrier_occurrences": sum(
            "foundry_provider_state" in item for item in replay["input"]
        ),
        "native_output_parts": len(parts),
        "provider_output_signature_decoded_bytes": sum(
            len(base64.b64decode(part.get("thoughtSignature", ""))) for part in parts
        ),
        "audio_files": 2 if audio_workload else 0,
        "audio_decoded_bytes": 640088 if audio_workload else 0,
        "audio_frames": 320000 if audio_workload else 0,
        "instruction_bytes": len(body.get("instructions", "").encode()),
        "status_counts": counts,
        "wall_seconds": time.monotonic() - started,
        "max_request_ms": max(latencies) * 1000,
        "max_loop_delay_ms": max(delays) * 1000,
        "baseline_rss": baseline,
        "peak_rss": peak,
        "incremental_rss": peak - baseline,
        "synthetic_only": True,
        "cooldown_reset_for_invalid_workload": workload == "parts",
        "startup_gate_bypassed_only_in_harness": not audio_workload and workload != "video",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workload",
        choices=[
            "signature",
            "parts",
            "context",
            "history",
            "carriers",
            "aggregate",
            "audio",
            "audio_pdf",
            "video",
        ],
        required=True,
    )
    parser.add_argument("--pdf-fixture", type=Path)
    parser.add_argument("--video-fixture", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(run(args.workload, args.pdf_fixture, args.video_fixture)), sort_keys=True
        )
    )
