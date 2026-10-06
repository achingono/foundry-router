"""Local bounded intake/validation/mapping measurements; no provider requests.

Run one format per fresh process so RSS peaks are independently attributable:
.venv/bin/python scripts/quality/google-media-benchmark.py --format png
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import platform
import random
import resource
import statistics
import sys
import time

from fastapi import Request
from google_media_fixtures import worst_entropy_jpeg
from PIL import Image

from foundry_router.api.adapters.google_ai_studio import GoogleAiStudioAdapter
from foundry_router.api.adapters.google_native import GoogleNativeAdapter
from foundry_router.api.common import request_body
from foundry_router.config.google_features import GoogleFeatureProfile

BODY_CAP = 2 * 1024 * 1024
HARD_AGGREGATE = 1048576
RSS_LIMIT_BYTES = 128 * 1024 * 1024
DELAY_LIMIT_SECONDS = 1
INTAKE_LIMIT_SECONDS = 5
CALLERS = 8
REQUESTS = 100


def rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def fixture(kind: str, workload: str) -> tuple[bytes, GoogleFeatureProfile]:
    formats = ("jpeg", "png", "webp") if workload in {"mixed", "expanded"} else (kind,)
    content = []
    total = 0
    for image_format in formats:
        dimension = 128 if image_format == "jpeg" else 384
        raster = Image.frombytes(
            "RGB", (dimension, dimension), random.Random(23).randbytes(dimension * dimension * 3)
        )
        if workload == "expanded":
            raster = Image.new("RGB", (dimension, dimension), (20, 50, 100))
        output = io.BytesIO()
        raster.save(
            output, format=image_format, **({"lossless": True} if image_format == "webp" else {})
        )
        raw = output.getvalue()
        count = min(8, HARD_AGGREGATE // len(raw))
        if image_format == "jpeg":
            count = 1
        if (
            workload in {"worst", "late-invalid", "tables", "mixed", "expanded"}
            and image_format == "jpeg"
        ):
            raw = worst_entropy_jpeg(8 if workload == "tables" else 88, all_tables=True)
            count = 8 if workload == "tables" else 1
        if workload == "late-invalid":
            raw = raw[:-2] + b"\xff\xd8"
        if workload == "mixed":
            count = 1
        if workload == "expanded":
            count = 1 if image_format == "jpeg" else 3 if image_format == "png" else 4
        if workload == "invalid":
            raw = b"X" * 524288
            count = 2
        uri = f"data:image/{image_format};base64," + base64.b64encode(raw).decode()
        content.extend([{"type": "input_image", "image_url": uri}] * count)
        total += len(raw) * count
    profile = GoogleFeatureProfile(
        features=("inline_images",),
        image_formats=formats,
        max_images=len(content),
        max_image_bytes=524288,
        max_total_image_bytes=total,
        image_input_tokens=258,
        image_token_pricing=True,
    )
    wire = json.dumps(
        {"model": "synthetic", "input": [{"role": "user", "content": content}]}
    ).encode()
    if len(wire) > BODY_CAP:
        raise ValueError("Fixture exceeds unchanged request body cap")
    return wire, profile


async def benchmark(kind: str, workload: str, surface: str = "openai_compat") -> dict[str, object]:
    wire, profile = fixture(kind, workload)
    invalid = workload in {"invalid", "late-invalid"}
    if surface == "native":
        profile = profile.model_copy(update={"native_thinking_disabled": True})
    adapter = (
        GoogleNativeAdapter(profile=profile)
        if surface == "native"
        else GoogleAiStudioAdapter(profile=profile)
    )
    baseline_rss = rss_bytes()
    latencies: list[float] = []
    delays: list[float] = []
    encoded_sizes: list[int] = []
    stopped = False

    async def monitor() -> None:
        while not stopped:
            start = time.monotonic()
            await asyncio.sleep(0.01)
            delays.append(max(0, time.monotonic() - start - 0.01))

    async def caller() -> None:
        for _ in range(REQUESTS):
            await asyncio.sleep(0)
            start = time.monotonic()
            deadline = start + 30

            async def receive() -> dict[str, object]:
                await asyncio.sleep(0)
                return {"type": "http.request", "body": wire, "more_body": False}

            request = Request(
                {"type": "http", "headers": [(b"content-type", b"application/json")]}, receive
            )
            body = await request_body(
                request, "responses", max_body_bytes=BODY_CAP, deadline_monotonic=deadline
            )
            if not isinstance(body, dict):
                raise TypeError("Outer fixture intake failed")
            rejection = adapter.check_request("responses", body, deadline_monotonic=deadline)
            if bool(rejection) != invalid:
                raise ValueError("Fixture capability gate disagrees with workload")
            if not invalid:
                upstream = adapter.build_upstream_body(
                    "responses", body, deployment="synthetic", default_output_tokens=100
                )
                encoded_sizes.append(len(json.dumps(upstream).encode()))
            latencies.append(time.monotonic() - start)

    monitor_task = asyncio.create_task(monitor())
    started = time.monotonic()
    await asyncio.gather(*(caller() for _ in range(CALLERS)))
    stopped = True
    await monitor_task
    peak_rss = rss_bytes()
    delay = max(delays, default=0)
    intake = max(latencies)
    passed = (
        peak_rss - baseline_rss <= RSS_LIMIT_BYTES
        and delay <= DELAY_LIMIT_SECONDS
        and intake < INTAKE_LIMIT_SECONDS
    )
    return {
        "format": kind,
        "surface": surface,
        "invalid": invalid,
        "workload": workload,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "callers": CALLERS,
        "requests": len(latencies),
        "body_bytes": len(wire),
        "max_images": profile.max_images,
        "aggregate_decoded_cap": profile.max_total_image_bytes,
        "seconds": time.monotonic() - started,
        "mean_request_ms": statistics.mean(latencies) * 1000,
        "max_request_ms": intake * 1000,
        "max_event_loop_delay_ms": delay * 1000,
        "baseline_peak_rss_bytes": baseline_rss,
        "final_peak_rss_bytes": peak_rss,
        "incremental_peak_rss_bytes": peak_rss - baseline_rss,
        "max_upstream_encoded_bytes": max(encoded_sizes, default=0),
        "thresholds": {
            "incremental_rss_bytes": RSS_LIMIT_BYTES,
            "event_loop_delay_seconds": DELAY_LIMIT_SECONDS,
            "intake_seconds": INTAKE_LIMIT_SECONDS,
        },
        "passed": passed,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("png", "jpeg", "webp"), required=True)
    parser.add_argument("--surface", choices=("openai_compat", "native"), default="openai_compat")
    parser.add_argument(
        "--workload",
        choices=("normal", "worst", "invalid", "late-invalid", "tables", "mixed", "expanded"),
        default="normal",
    )
    arguments = parser.parse_args()
    result = asyncio.run(benchmark(arguments.format, arguments.workload, arguments.surface))
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
