"""Regression tests for deep-review findings 7edd2c0..d1b45ac8."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import struct
import time
import zlib
from contextlib import suppress
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image

from foundry_router.api.adapters.google_media import validate_inline_image
from foundry_router.api.common import api_error
from foundry_router.api.google_pdf import PdfPreparer
from foundry_router.api.routes.openai import _backend_execution_deadline
from foundry_router.config import Settings
from foundry_router.config.google_features import GoogleFeatureProfile
from foundry_router.credit import InMemoryCreditStore
from foundry_router.forwarding import BackendRequestResult
from foundry_router.health import InMemoryHealthStore
from foundry_router.routing import execute_with_single_failover


def _azure_settings() -> Settings:
    return Settings(
        _env_file=None,
        backends_json=json.dumps(
            {
                "a": {
                    "endpoint": "https://example.test",
                    "credential": "fixture",
                    "deployment": "fixture",
                    "credit_metered": False,
                }
            }
        ),
        models_json='{"m":{"backends":{"a":1}}}',
        client_api_keys_json='["c"]',
        admin_api_keys_json='["a"]',
        reservation_max_age_seconds=900,
    )


async def test_azure_execution_not_truncated_by_intake():
    """Reservation lifetime bounds Azure execution, not remaining intake time."""
    settings = _azure_settings()

    async def backend(_backend_id: str, *, reservation_deadline_monotonic: float):
        _ = reservation_deadline_monotonic
        await asyncio.sleep(0.15)
        from fastapi.responses import JSONResponse

        return BackendRequestResult(
            response=JSONResponse({"status": "completed"}), retryable_failure=False
        )

    started = time.monotonic()
    response = await execute_with_single_failover(
        settings,
        "m",
        operation="responses",
        body={"model": "m", "input": "hello"},
        request_id="fixture-intake-isolation",
        execute_backend=backend,
        health_store=InMemoryHealthStore(),
        credit_store=InMemoryCreditStore(),
        metrics_store=MagicMock(observe_request=AsyncMock()),
        logger=MagicMock(),
        api_error=api_error,
        finalize_non_streaming_credit=AsyncMock(),
        intake_deadline_monotonic=started + 0.1,
    )
    assert response.status_code == 200
    assert time.monotonic() - started >= 0.15


def test_backend_execution_deadline_google_vs_azure():
    settings = Settings(
        _env_file=None,
        backends_json=json.dumps(
            {
                "g": {
                    "provider": "google_ai_studio",
                    "api_surface": "native",
                    "endpoint": "https://example.test",
                    "credential": "k",
                    "deployment": "m",
                    "credit_metered": False,
                    "google_features": {"native_thinking_disabled": True},
                },
                "a": {
                    "endpoint": "https://example.test",
                    "credential": "k",
                    "deployment": "d",
                    "credit_metered": False,
                },
            }
        ),
        models_json='{"m":{"backends":{"g":1}},"n":{"backends":{"a":1}}}',
        client_api_keys_json='["c"]',
        admin_api_keys_json='["a"]',
    )
    assert _backend_execution_deadline(settings, "g", 1000.0, 100.0) == 100.0
    assert _backend_execution_deadline(settings, "a", 1000.0, 100.0) == 1000.0
    assert _backend_execution_deadline(settings, "g", 1000.0, None) == 1000.0


def _png_profile() -> GoogleFeatureProfile:
    return GoogleFeatureProfile(
        features=("inline_images",),
        image_input_tokens=258,
        image_token_pricing=True,
    )


def _png_bytes(payload: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", payload)
        + chunk(b"IEND", b"")
    )


def _part(raw: bytes) -> dict:
    return {
        "type": "input_image",
        "image_url": "data:image/png;base64," + base64.b64encode(raw).decode(),
    }


def test_png_exact_raster_completion_rejects_truncation_and_surplus():
    profile = _png_profile()
    valid = zlib.compress(b"\x00\xff\x00\x00")
    assert validate_inline_image(_part(_png_bytes(valid)), profile) == len(_png_bytes(valid))
    for bad in (
        valid[:-4],
        valid[:-1] + bytes([valid[-1] ^ 1]),
        zlib.compress(b"\x00\xff\x00\x00" + b"x" * 1000),
        valid + zlib.compress(b"extra"),
    ):
        try:
            validate_inline_image(_part(_png_bytes(bad)), profile)
        except ValueError:
            continue
        raise AssertionError("incomplete or surplus PNG payload was accepted")


def test_png_pillow_fixture_still_accepted():
    profile = _png_profile()
    out = io.BytesIO()
    Image.new("RGB", (8, 8), (20, 50, 100)).save(out, format="PNG")
    raw = out.getvalue()
    assert validate_inline_image(_part(raw), profile) == len(raw)


async def test_pdf_probe_retries_after_transient_failure(monkeypatch):
    monkeypatch.setattr("foundry_router.api.google_pdf.pdf_worker_available", lambda: True)
    preparer = PdfPreparer()
    calls = {"count": 0}

    async def inspect(_data: bytes, *, deadline: float):
        _ = deadline
        calls["count"] += 1
        if calls["count"] == 1:
            from foundry_router.api.google_pdf import PdfPreparationError

            raise PdfPreparationError(503, "temporary spawn failure")
        return 1

    monkeypatch.setattr(preparer, "inspect", inspect)
    assert await preparer.ready() is False
    assert await preparer.ready() is True
    assert calls["count"] == 2
    # Successful probe stays cached without another worker spawn.
    assert await preparer.ready() is True
    assert calls["count"] == 2


async def test_embeddings_body_read_respects_intake_deadline():
    """Stalled embeddings bodies hit the intake deadline instead of hanging."""
    from starlette.requests import Request

    from foundry_router.api.common import request_body

    async def stalled_receive():
        await asyncio.sleep(5)
        return {"type": "http.request", "body": b"{}", "more_body": False}

    request = Request(
        {"type": "http", "headers": [(b"content-type", b"application/json")]}, stalled_receive
    )
    response = await request_body(
        request,
        "embeddings",
        max_body_bytes=2048,
        deadline_monotonic=time.monotonic() + 0.05,
    )
    assert response.status_code == 408


def test_provider_state_scan_ignores_non_list_input():
    """Malformed `input` never crashes the provider-state carrier scan."""
    from foundry_router.api.google_history import STATE_FIELD

    for bad_input in (None, 123, "text", {"role": "user"}):
        body = {"model": "m", "input": bad_input}
        hit = STATE_FIELD in body or (
            isinstance(body.get("input"), list)
            and any(isinstance(item, dict) and STATE_FIELD in item for item in body["input"])
        )
        assert hit is False


async def test_pdf_stalled_reap_releases_promptly_and_tracks_orphan(monkeypatch):
    """Deadline expiry never waits out a stalled PDF inspector reap."""
    from foundry_router.api import google_pdf as pdf_module
    from foundry_router.api.google_pdf import PdfPreparationError

    released = asyncio.Event()

    class Input:
        def write(self, data):
            self.data = data

        async def drain(self):
            pass

        def close(self):
            pass

        async def wait_closed(self):
            pass

    class Output:
        def __init__(self):
            self.sent = False

        async def read(self, size):
            if self.sent:
                return b""
            self.sent = True
            return b'{"pages":1,"bytes":5}'[:size]

    class Child:
        def __init__(self):
            self.stdin = Input()
            self.stdout = Output()
            self.returncode = None
            self.killed = False
            self.reaped = False

        def kill(self):
            self.killed = True

        async def wait(self):
            await released.wait()
            self.returncode = 0
            self.reaped = True
            return 0

    child = Child()

    async def spawn(*_args, **_kwargs):
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    base_orphans = pdf_module.pdf_orphaned_children()
    started = time.monotonic()
    with pytest.raises(PdfPreparationError) as failure:
        await PdfPreparer().inspect(b"12345", deadline=time.monotonic() + 0.05)
    assert time.monotonic() - started < 4
    assert failure.value.status_code == 408
    assert child.killed
    assert pdf_module.pdf_orphaned_children() == base_orphans + 1
    released.set()
    async with asyncio.timeout(2):
        while pdf_module.pdf_orphaned_children() > base_orphans:  # noqa: ASYNC110
            await asyncio.sleep(0.01)
    assert child.reaped


async def test_output_stalled_wait_releases_slot_and_tracks_orphan(monkeypatch):
    """A stalled generated-output reap releases its slot within a bound."""
    import sys

    from foundry_router.api.google_output_work import (
        OutputInspectionLease,
        output_orphaned_children,
    )
    from tests.unit.test_google_output_png import png

    monkeypatch.setattr(sys, "platform", "linux")
    released = asyncio.Event()

    class InputPipe:
        def write(self, raw):
            assert raw

        async def drain(self):
            pass

        def close(self):
            pass

        async def wait_closed(self):
            pass

    class StalledChild:
        def __init__(self):
            self.stdin = InputPipe()
            self.stdout = self
            self.returncode = None
            self.killed = False
            self.sent = False

        async def read(self, count):
            if self.sent:
                return b""
            self.sent = True
            raw = png()
            return json.dumps(
                {"bytes": len(raw), "width": 1024, "height": 1024, "expanded_bytes": 4195328}
            ).encode()[:count]

        async def wait(self):
            await released.wait()
            self.returncode = 0
            return 0

        def kill(self):
            self.killed = True

    child = StalledChild()

    async def spawn(*_args, **_kwargs):
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    base_orphans = output_orphaned_children()
    lease = OutputInspectionLease()
    try:
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            await lease.inspect(png(), deadline=time.monotonic() + 0.05)
        assert time.monotonic() - started < 4
        assert child.killed
        assert output_orphaned_children() == base_orphans + 1
        # The slot is released even though the child has not been reaped.
        replacement = OutputInspectionLease()
        replacement.close()
    finally:
        lease.close()
    released.set()
    async with asyncio.timeout(2):
        while output_orphaned_children() > base_orphans:  # noqa: ASYNC110
            await asyncio.sleep(0.01)


async def test_output_stalled_spawn_is_cancelled_and_slot_released(monkeypatch):
    """A spawn that never returns cannot hold an inspection slot past the deadline."""
    import sys

    from foundry_router.api.google_output_work import (
        OutputInspectionLease,
        output_orphaned_children,
    )
    from tests.unit.test_google_output_png import png

    monkeypatch.setattr(sys, "platform", "linux")
    gate = asyncio.Event()

    async def spawn(*_args, **_kwargs):
        await gate.wait()
        return object()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    base_orphans = output_orphaned_children()
    lease = OutputInspectionLease()
    try:
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            await lease.inspect(png(), deadline=time.monotonic() + 0.05)
        assert time.monotonic() - started < 4
        assert output_orphaned_children() == base_orphans
        # The slot is released even though spawning never finished.
        replacement = OutputInspectionLease()
        replacement.close()
    finally:
        lease.close()
        gate.set()


async def test_orphan_capacity_rejects_further_inspection():
    """Exhausted orphan capacity fails closed instead of accumulating children."""
    from foundry_router.api import google_output_work as output_module
    from foundry_router.api import google_pdf as pdf_module
    from foundry_router.api.google_output_work import (
        _MAX_ORPHANS as OUTPUT_MAX,
    )
    from foundry_router.api.google_output_work import (
        OutputInspectionLease,
        output_orphaned_children,
    )
    from foundry_router.api.google_pdf import (
        _MAX_PDF_ORPHANS as PDF_MAX,
    )
    from foundry_router.api.google_pdf import (
        PdfPreparationError,
        PdfPreparer,
        pdf_orphaned_children,
    )
    from tests.unit.test_google_output_png import png

    pdf_markers = [object() for _ in range(PDF_MAX)]
    output_markers = [object() for _ in range(OUTPUT_MAX)]
    for marker in pdf_markers:
        pdf_module._ORPHANED_PDF_CHILDREN.add(marker)
    for marker in output_markers:
        output_module._ORPHANED_OUTPUT_CHILDREN.add(marker)
    try:
        assert pdf_orphaned_children() == PDF_MAX
        assert output_orphaned_children() == OUTPUT_MAX
        with pytest.raises(PdfPreparationError) as pdf_failure:
            await PdfPreparer().inspect(b"x", deadline=time.monotonic() + 5)
        assert pdf_failure.value.status_code == 503
        lease = OutputInspectionLease()
        try:
            with pytest.raises(ValueError, match="busy"):
                await lease.inspect(png(), deadline=time.monotonic() + 5)
            assert await lease.ready(deadline=time.monotonic() + 1) is False
        finally:
            lease.close()
    finally:
        for marker in pdf_markers:
            pdf_module._ORPHANED_PDF_CHILDREN.discard(marker)
        for marker in output_markers:
            output_module._ORPHANED_OUTPUT_CHILDREN.discard(marker)


async def test_stalled_reap_starts_exactly_one_waiter(monkeypatch):
    """A stalled reap transfers its single wait task; no second waiter starts."""
    from foundry_router.api import google_pdf as pdf_module
    from foundry_router.api.google_pdf import PdfPreparationError, PdfPreparer

    released = asyncio.Event()
    live_waits = {"count": 0}

    class Input:
        def write(self, data):
            self.data = data

        async def drain(self):
            pass

        def close(self):
            pass

        async def wait_closed(self):
            pass

    class Output:
        def __init__(self):
            self.sent = False

        async def read(self, size):
            if self.sent:
                return b""
            self.sent = True
            return b'{"pages":1,"bytes":5}'[:size]

    class Child:
        def __init__(self):
            self.stdin = Input()
            self.stdout = Output()
            self.returncode = None
            self.killed = False

        def kill(self):
            self.killed = True

        async def wait(self):
            live_waits["count"] += 1
            try:
                await released.wait()
            finally:
                live_waits["count"] -= 1
            self.returncode = 0
            return 0

    child = Child()

    async def spawn(*_args, **_kwargs):
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    base_orphans = pdf_module.pdf_orphaned_children()
    with pytest.raises(PdfPreparationError):
        await PdfPreparer().inspect(b"12345", deadline=time.monotonic() + 0.05)
    # The timed-out main-path waiter is dead; exactly the transferred task waits.
    assert live_waits["count"] == 1
    assert pdf_module.pdf_orphaned_children() == base_orphans + 1
    released.set()
    async with asyncio.timeout(2):
        while pdf_module.pdf_orphaned_children() > base_orphans:  # noqa: ASYNC110
            await asyncio.sleep(0.01)
    assert live_waits["count"] == 0


async def test_pdf_failed_wait_retained_against_limit_and_logged(monkeypatch, caplog):
    """An OSError wait never confirms reaping: tracking stays, warning fires."""
    import logging

    from foundry_router.api import google_pdf as pdf_module
    from foundry_router.api.google_pdf import PdfPreparationError, PdfPreparer

    class Input:
        def write(self, data):
            self.data = data

        async def drain(self):
            pass

        def close(self):
            pass

        async def wait_closed(self):
            pass

    class Output:
        def __init__(self):
            self.sent = False

        async def read(self, size):
            if self.sent:
                return b""
            self.sent = True
            return b'{"pages":1,"bytes":5}'[:size]

    class Child:
        def __init__(self):
            self.stdin = Input()
            self.stdout = Output()
            self.returncode = None
            self.killed = False

        def kill(self):
            self.killed = True

        async def wait(self):
            raise OSError("synthetic reap failure")

    child = Child()

    async def spawn(*_args, **_kwargs):
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    base_orphans = pdf_module.pdf_orphaned_children()
    try:
        with caplog.at_level(logging.WARNING, logger="foundry_router.api.google_pdf"):
            with pytest.raises(PdfPreparationError) as failure:
                await PdfPreparer().inspect(b"12345", deadline=time.monotonic() + 5)
        assert failure.value.status_code == 503
        assert child.returncode is None
        await asyncio.sleep(0.01)
        assert pdf_module.pdf_orphaned_children() == base_orphans + 1
        await asyncio.sleep(0.05)
        # No drain is possible: the failed wait stays against the limit.
        assert pdf_module.pdf_orphaned_children() == base_orphans + 1
        assert "reap_unconfirmed" in caplog.text
    finally:
        pdf_module._ORPHANED_PDF_CHILDREN.discard(child)


async def test_output_failed_wait_retained_against_limit_and_logged(monkeypatch, caplog):
    """An OSError wait never confirms reaping: tracking stays, warning fires."""
    import logging
    import sys

    from foundry_router.api import google_output_work as output_module
    from foundry_router.api.google_output_work import (
        OutputInspectionLease,
        output_orphaned_children,
    )
    from tests.unit.test_google_output_png import png

    monkeypatch.setattr(sys, "platform", "linux")

    class InputPipe:
        def write(self, raw):
            assert raw

        async def drain(self):
            pass

        def close(self):
            pass

        async def wait_closed(self):
            pass

    class FailingChild:
        def __init__(self):
            self.stdin = InputPipe()
            self.stdout = self
            self.returncode = None
            self.killed = False
            self.sent = False

        async def read(self, count):
            if self.sent:
                return b""
            self.sent = True
            raw = png()
            return json.dumps(
                {"bytes": len(raw), "width": 1024, "height": 1024, "expanded_bytes": 4195328}
            ).encode()[:count]

        async def wait(self):
            raise OSError("synthetic reap failure")

        def kill(self):
            self.killed = True

    child = FailingChild()

    async def spawn(*_args, **_kwargs):
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    base_orphans = output_orphaned_children()
    lease = OutputInspectionLease()
    try:
        with caplog.at_level(logging.WARNING, logger="foundry_router.api.google_output_work"):
            with pytest.raises(OSError, match="synthetic reap failure"):
                await lease.inspect(png(), deadline=time.monotonic() + 5)
        assert child.returncode is None
        await asyncio.sleep(0.01)
        assert output_orphaned_children() == base_orphans + 1
        await asyncio.sleep(0.05)
        assert output_orphaned_children() == base_orphans + 1
        assert "reap_unconfirmed" in caplog.text
    finally:
        lease.close()
        output_module._ORPHANED_OUTPUT_CHILDREN.discard(child)


async def test_cancelled_wait_task_retained_and_logged(caplog):
    """A cancelled wait task never confirms reaping in either inspector pool."""
    import logging

    from foundry_router.api import google_output_work as output_module
    from foundry_router.api import google_pdf as pdf_module
    from foundry_router.api.google_output_work import _track_orphan_wait as track_output
    from foundry_router.api.google_pdf import _track_orphan_wait as track_pdf

    async def never():
        await asyncio.Event().wait()

    cases = [
        (pdf_module._ORPHANED_PDF_CHILDREN, track_pdf, "foundry_router.api.google_pdf"),
        (
            output_module._ORPHANED_OUTPUT_CHILDREN,
            track_output,
            "foundry_router.api.google_output_work",
        ),
    ]
    for orphans, track, logger_name in cases:
        child = type("Child", (), {"returncode": None})()
        base_orphans = len(orphans)
        try:
            with caplog.at_level(logging.WARNING, logger=logger_name):
                task = asyncio.create_task(never())
                track(child, task)
                assert len(orphans) == base_orphans + 1
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
                await asyncio.sleep(0.01)
                # Cancelled waits stay retained against the admission limit.
                assert len(orphans) == base_orphans + 1
                assert "reap_unconfirmed" in caplog.text
        finally:
            orphans.discard(child)


def test_live_catalog_and_manifest_fixtures_present():
    root = Path(__file__).resolve().parents[2]
    catalog_path = root / "docs/plans/google-ai-studio-tools-multimodal/live-discovery.json"
    manifest_path = root / "docs/plans/google-ai-studio-tools-multimodal/live-runner/manifest.json"
    assert catalog_path.is_file() and manifest_path.is_file()
    catalog = json.loads(catalog_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    assert len(manifest["models"]) == 61
    assert len(catalog["projects"][0]["models"]) == 61
    assert {row["id"] for row in manifest["models"]} == {
        row["id"] for row in catalog["projects"][0]["models"]
    }
