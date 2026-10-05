"""Streaming inspection resource bounds and settlement compatibility regressions."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from foundry_router import forwarding


def usage_event(input_tokens: int, output_tokens: int) -> bytes:
    return (
        b'data: {"usage":{"input_tokens":'
        + str(input_tokens).encode()
        + b',"output_tokens":'
        + str(output_tokens).encode()
        + b"}}\n\n"
    )


@pytest.mark.parametrize("delimiter", [b"\n\n", b"\r\n\r\n"], ids=["lf", "crlf"])
@pytest.mark.parametrize("recovery", ["usage", "no-usage", "unterminated"])
async def test_oversized_inspection_preserves_bytes_usage_and_recovers(
    monkeypatch, delimiter, recovery
):
    inspected_sizes = []
    extract = forwarding._extract_next_sse_event

    def bounded_extract(buffer):
        inspected_sizes.append(len(buffer))
        assert len(buffer) <= forwarding.MAX_SSE_EVENT_BUFFER_BYTES
        return extract(buffer)

    monkeypatch.setattr(forwarding, "_extract_next_sse_event", bounded_extract)
    # A single upstream chunk exceeds the bound several times. Its final data
    # line must not be mistaken for a standalone usage event during recovery.
    oversized = (
        b"data: "
        + b"x" * (3 * forwarding.MAX_SSE_EVENT_BUFFER_BYTES)
        + b'\ndata: {"usage":{"input_tokens":999,"output_tokens":999}}'
    )
    parts = [usage_event(10, 5), oversized]
    if recovery != "unterminated":
        parts.extend(bytes([byte]) for byte in delimiter)
        parts.append(usage_event(13, 7) if recovery == "usage" else b"data: [DONE]\n\n")
    context = SimpleNamespace(__aexit__=AsyncMock())
    credit = SimpleNamespace(finalize_request=AsyncMock())
    metrics = SimpleNamespace(observe_request=AsyncMock())
    quota = SimpleNamespace(finalize_request=AsyncMock())

    async def chunks():
        for part in parts[1:]:
            yield part

    forwarded = [
        chunk
        async for chunk in forwarding.stream_response(
            chunks(),
            parts[0],
            context,
            request_id="oversized",
            backend_id="backend_a",
            cooldown_seconds=10.0,
            model="alias",
            pricing={"alias": SimpleNamespace(input_per_million=10.0, output_per_million=30.0)},
            status_code=200,
            set_backend_cooldown=AsyncMock(),
            credit_store=credit,
            metrics_store=metrics,
            rate_limit_store=quota,
        )
    ]
    assert len(forwarded) == len(parts)
    assert all(actual is expected for actual, expected in zip(forwarded, parts, strict=True))
    assert max(inspected_sizes) == forwarding.MAX_SSE_EVENT_BUFFER_BYTES
    cost = 0.00034 if recovery == "usage" else 0.00025
    credit.finalize_request.assert_awaited_once_with(
        "oversized",
        backend_id="backend_a",
        charge_reserved=True,
        charged_cost_usd=pytest.approx(cost),
    )
    quota.finalize_request.assert_awaited_once_with(
        "oversized", actual_input_tokens=13 if recovery == "usage" else 10
    )
    metrics.observe_request.assert_awaited_once()
    assert metrics.observe_request.await_args.kwargs["estimated_cost_usd"] == pytest.approx(cost)
    context.__aexit__.assert_awaited_once()


async def test_usage_then_transport_error_preserves_cost_with_legacy_finalize_signature():
    finalize = AsyncMock()

    async def legacy_finalize(request_id, *, charge_reserved, charged_cost_usd):
        await finalize(
            request_id, charge_reserved=charge_reserved, charged_cost_usd=charged_cost_usd
        )

    async def broken_chunks():
        raise httpx.ReadError("disconnect after usage")
        yield b""

    metrics = SimpleNamespace(observe_request=AsyncMock())
    cooldown = AsyncMock()
    forwarded = [
        chunk
        async for chunk in forwarding.stream_response(
            broken_chunks(),
            usage_event(13, 7),
            SimpleNamespace(__aexit__=AsyncMock()),
            request_id="legacy",
            backend_id="backend_a",
            cooldown_seconds=10.0,
            model="alias",
            pricing={"alias": SimpleNamespace(input_per_million=10.0, output_per_million=30.0)},
            status_code=200,
            set_backend_cooldown=cooldown,
            credit_store=SimpleNamespace(finalize_request=legacy_finalize),
            metrics_store=metrics,
        )
    ]
    assert forwarded[0] == usage_event(13, 7)
    assert b'"type":"upstream_error"' in forwarded[1]
    finalize.assert_awaited_once_with(
        "legacy", charge_reserved=True, charged_cost_usd=pytest.approx(0.00034)
    )
    cooldown.assert_awaited_once()
    metrics.observe_request.assert_awaited_once()
    assert metrics.observe_request.await_args.kwargs["status_code"] == 502
    assert metrics.observe_request.await_args.kwargs["estimated_cost_usd"] == pytest.approx(0.00034)
