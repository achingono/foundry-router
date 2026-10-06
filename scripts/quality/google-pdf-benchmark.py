"""Linux-only real PDF worker/encoding benchmark with live aggregate RSS sampling."""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import platform
import re
import statistics
import time
from http import HTTPStatus
from pathlib import Path
from unittest.mock import MagicMock

from fastapi import Request
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from foundry_router.api.adapters.google_native import GoogleNativeAdapter
from foundry_router.api.common import request_body
from foundry_router.api.google_pdf import PdfPreparationError, PdfPreparer
from foundry_router.config import Settings
from foundry_router.config.google_features import GoogleFeatureProfile
from foundry_router.credit import InMemoryCreditStore
from foundry_router.health import InMemoryHealthStore
from foundry_router.ratelimit import InMemoryRateLimitStore
from foundry_router.routing import select_candidate_backend

CALLERS = 8
REQUESTS = 100
RSS_LIMIT = 128 * 1024 * 1024
INTAKE_SECONDS = 5


def aggregate_rss() -> int:
    total = 0
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            text = (directory / "status").read_text()
        except (FileNotFoundError, ProcessLookupError):
            continue
        for line in text.splitlines():
            if line.startswith("VmRSS:"):
                total += int(line.split()[1]) * 1024
    return total


def container_memory_peak() -> int | None:
    for name in ("/sys/fs/cgroup/memory.peak", "/sys/fs/cgroup/memory/memory.max_usage_in_bytes"):
        path = Path(name)
        if path.exists():
            return int(path.read_text())
    return None


def fixture(workload: str, *, pages: int = 4) -> bytes:
    writer = PdfWriter()
    writer.pdf_header = b"%PDF-1.4"
    for _page_index in range(pages):
        page = writer.add_blank_page(width=14400, height=14400)
        if workload in {"work", "mixed", "work-invalid"}:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject(
                        {NameObject("/F1"): writer._add_object(font)}
                    )
                }
            )
            stream = DecodedStreamObject()
            repetitions = 509
            stream.set_data(b"BT /F1 12 Tf " + b"(x) Tj " * repetitions + b"ET")
            page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    raw = output.getvalue()
    if workload in {"maximum", "late-invalid", "work", "mixed", "work-invalid", "aggregate"}:
        # A comment before the first object expands exact raw spans without new parser objects.
        shift = 65536 - len(raw) - 2  # enlarged startxref decimal adds two wire bytes
        padding = b"%" + b"x" * (shift - 2) + b"\n"
        raw = raw[:9] + padding + raw[9:]

        raw = re.sub(
            rb"(?m)^(\d{10}) 00000 n ",
            lambda match: f"{int(match[1]) + shift:010d} 00000 n ".encode(),
            raw,
        )
        raw = re.sub(
            rb"startxref\n(\d+)",
            lambda match: b"startxref\n" + str(int(match[1]) + shift).encode(),
            raw,
        )
        if workload == "late-invalid":
            raw = re.sub(
                rb"/Size (\d+)", lambda match: b"/Size " + str(int(match[1]) + 1).encode(), raw
            )
        if workload == "work-invalid":
            # Last page fails only after the preceding content streams were tokenized.
            location = raw.rfind(b"ET\nendstream")
            if location < 0:
                raise ValueError("Expected final fixture text operator")
            raw = raw[:location] + b"Do" + raw[location + 2 :]
    return raw


def request_fixture(workload: str) -> tuple[bytes, GoogleFeatureProfile, int]:
    raw = fixture(workload, pages=1 if workload == "aggregate" else 4)
    features = ("inline_pdfs", "inline_images") if workload == "mixed" else ("inline_pdfs",)
    profile = GoogleFeatureProfile(
        features=features,
        combinations=(features,) if workload == "mixed" else (),
        native_thinking_disabled=True,
        pdf_input_tokens_per_page=258,
        pdf_native_text_tokens_per_page=65536,
        pdf_token_pricing=True,
        image_input_tokens=258,
        image_token_pricing=True,
    )
    part = {
        "type": "input_file",
        "filename": "fixture.pdf",
        "file_data": "data:application/pdf;base64," + base64.b64encode(raw).decode(),
    }
    content = [part] * (2 if workload == "aggregate" else 1)
    if workload == "mixed":
        raster = io.BytesIO()
        Image.new("RGB", (384, 384), (10, 20, 30)).save(raster, format="PNG")
        content.extend(
            [
                {
                    "type": "input_image",
                    "image_url": "data:image/png;base64,"
                    + base64.b64encode(raster.getvalue()).decode(),
                }
            ]
            * 4
        )
    wire = json.dumps(
        {"model": "synthetic", "input": [{"role": "user", "content": content}]}
    ).encode()
    return wire, profile, len(raw) * (2 if workload == "aggregate" else 1)


def selection_settings(profile: GoogleFeatureProfile) -> Settings:
    return Settings(
        backends_json=json.dumps(
            {
                "fixture": {
                    "provider": "google_ai_studio",
                    "api_surface": "native",
                    "endpoint": "https://fixture.example.test",
                    "credential": "synthetic",
                    "deployment": "fixture",
                    "credit_metered": False,
                    "google_features": profile.model_dump(),
                }
            }
        ),
        models_json='{"synthetic":{"backends":{"fixture":1}}}',
        client_api_keys_json='["synthetic"]',
        admin_api_keys_json='["synthetic-admin"]',
    )


async def intake(wire: bytes, deadline: float) -> dict[str, object]:
    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": wire, "more_body": False}

    request = Request(
        {"type": "http", "headers": [(b"content-type", b"application/json")]}, receive
    )
    body = await request_body(
        request, "responses", max_body_bytes=2 * 1024 * 1024, deadline_monotonic=deadline
    )
    if not isinstance(body, dict):
        raise TypeError("Fixture intake failed")
    return body


async def benchmark(workload: str) -> dict[str, object]:
    wire, profile, decoded_bytes = request_fixture(workload)
    adapter, preparer = GoogleNativeAdapter(profile=profile), PdfPreparer()
    settings = selection_settings(profile)
    credit, health, quota = InMemoryCreditStore(), InMemoryHealthStore(), InMemoryRateLimitStore()
    baseline = aggregate_rss()
    peaks, delays, latencies = [baseline], [], []
    rejected, inspected_invalid, running = 0, 0, True

    async def monitor() -> None:
        while running:
            start = time.monotonic()
            await asyncio.sleep(0.005)
            delays.append(max(0, time.monotonic() - start - 0.005))
            peaks.append(aggregate_rss())

    async def caller() -> None:
        nonlocal rejected, inspected_invalid
        for _ in range(REQUESTS):
            start = time.monotonic()

            body = await intake(wire, start + INTAKE_SECONDS)
            try:
                prepared = await preparer.prepare(body, deadline=start + 5)
            except PdfPreparationError as exc:
                if (
                    workload in {"late-invalid", "work-invalid"}
                    and exc.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
                ):
                    latencies.append(time.monotonic() - start)
                    inspected_invalid += 1
                    continue
                if exc.status_code != HTTPStatus.SERVICE_UNAVAILABLE:
                    raise
                rejected += 1
                await asyncio.sleep(0.01)
                continue
            assert adapter.check_request("responses", body, prepared_media=prepared) is None
            request_id = str(time.monotonic_ns())
            selection = await select_candidate_backend(
                settings,
                "synthetic",
                operation="responses",
                body=body,
                request_id=request_id,
                health_store=health,
                credit_store=credit,
                rate_limit_store=quota,
                logger=MagicMock(),
                prepared_media=prepared,
                intake_deadline_monotonic=start + INTAKE_SECONDS,
            )
            if selection.backend_id != "fixture":
                raise ValueError("Fixture selection failed")
            upstream = adapter.build_upstream_body(
                "responses",
                body,
                deployment="synthetic",
                default_output_tokens=5,
                prepared_media=prepared,
            )
            json.dumps(upstream).encode()
            await credit.finalize_request(
                request_id, backend_id="fixture", charge_reserved=False, charged_cost_usd=None
            )
            await quota.finalize_request(request_id, actual_input_tokens=None)
            latencies.append(time.monotonic() - start)

    task = asyncio.create_task(monitor())
    try:
        async with asyncio.timeout(60):
            await asyncio.gather(*(caller() for _ in range(CALLERS)))
    finally:
        running = False
        await task
    peak = max(peaks)
    container_peak = container_memory_peak()
    passed = (
        bool(latencies)
        and peak - baseline <= RSS_LIMIT
        and peak <= 512 * 1024 * 1024
        and max(delays) <= 1
        and max(latencies) < INTAKE_SECONDS
        and preparer.active == 0
        and (container_peak is None or container_peak <= 512 * 1024 * 1024)
    )
    return {
        "platform": platform.platform(),
        "workload": workload,
        "python": platform.python_version(),
        "callers": CALLERS,
        "attempts": CALLERS * REQUESTS,
        "admitted_valid": len(latencies) - inspected_invalid,
        "inspected_invalid": inspected_invalid,
        "document_outcome": "rejected"
        if workload in {"late-invalid", "work-invalid"}
        else "accepted",
        "saturated": rejected,
        "decoded_bytes": decoded_bytes,
        "pages": 2 if workload == "aggregate" else 4,
        "documents": 2 if workload == "aggregate" else 1,
        "content_operations": [512, 512, 512, 512]
        if workload in {"work", "mixed", "work-invalid"}
        else [],
        "mean_intake_ms": statistics.mean(latencies) * 1000,
        "max_intake_ms": max(latencies) * 1000,
        "max_loop_delay_ms": max(delays) * 1000,
        "baseline_aggregate_rss": baseline,
        "peak_aggregate_rss": peak,
        "incremental_aggregate_rss": peak - baseline,
        "container_peak_bytes": container_peak,
        "passed": passed,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workload",
        choices=("normal", "maximum", "late-invalid", "work", "mixed", "work-invalid", "aggregate"),
        default="normal",
    )
    result = asyncio.run(benchmark(parser.parse_args().workload))
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
