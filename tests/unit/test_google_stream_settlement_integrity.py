"""Preterminal cumulative counts cannot replace a request reservation debit."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from foundry_router.api.adapters.google_ai_studio import GoogleAiStudioAdapter
from foundry_router.forwarding import GoogleAttemptSettlement, _google_stream_response
from tests.unit.test_google_lifecycle import (
    MODEL,
    TEXT_ESTIMATE,
    FakeBackendClient,
    FakeStreamContext,
    FakeUpstream,
    _chat_chunk,
    _credit_remaining,
    _execute,
    _google_settings,
    _stores,
)

COUNTS = (
    b'data: {"choices":[],"usage":{"prompt_tokens":4,"completion_tokens":2,"total_tokens":6}}\n\n'
)
OBSERVED_COST = (4 * 10 + 2 * 30) / 1_000_000


@pytest.mark.asyncio
@pytest.mark.parametrize("end", ["cancel", "transport", "protocol", "success", "zero"])
async def test_actual_decoder_stream_retains_fallback_until_clean_end(end):
    decoder = GoogleAiStudioAdapter().create_stream_decoder(logical_model=MODEL)
    prefetched = decoder.feed(_chat_chunk("ready") + COUNTS)

    async def chunks():
        if end == "transport":
            raise httpx.ReadError("synthetic failure")
        if end == "protocol":
            yield b"data: invalid\n\n"
        else:
            yield _chat_chunk(finish="stop") + b"data: [DONE]\n\n"

    credit, quota, metrics = (
        SimpleNamespace(finalize_request=AsyncMock()),
        SimpleNamespace(finalize_request=AsyncMock()),
        SimpleNamespace(observe_request=AsyncMock()),
    )
    context = SimpleNamespace(__aexit__=AsyncMock())
    price = 0 if end == "zero" else 1
    iterator = _google_stream_response(
        chunks(),
        decoder,
        prefetched,
        context,
        request_id="integrity",
        backend_id="gm-a",
        cooldown_seconds=1,
        model=MODEL,
        pricing={
            MODEL: SimpleNamespace(input_per_million=10 * price, output_per_million=30 * price)
        },
        status_code=200,
        set_backend_cooldown=AsyncMock(),
        credit_store=credit,
        metrics_store=metrics,
        rate_limit_store=quota,
        fallback_cost_usd=TEXT_ESTIMATE,
        fallback_input_tokens=1,
    )
    if end == "cancel":
        await anext(iterator)
        await iterator.aclose()
    else:
        _ = [part async for part in iterator]
    expected = OBSERVED_COST if end == "success" else 0 if end == "zero" else TEXT_ESTIMATE
    credit.finalize_request.assert_awaited_once_with(
        "integrity",
        backend_id="gm-a",
        charge_reserved=True,
        charged_cost_usd=pytest.approx(expected),
    )
    quota.finalize_request.assert_awaited_once_with("integrity", actual_input_tokens=4)
    context.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("unstarted", [False, True])
async def test_routing_cancel_with_partial_counts_preserves_credit_and_input_quota(unstarted):
    settings = _google_settings()
    stores = _stores(settings)
    context = FakeStreamContext(FakeUpstream(chunks=[_chat_chunk("ready") + COUNTS]))
    fake = FakeBackendClient()
    fake.handler = lambda *_args: context
    response = await _execute(
        {"model": MODEL, "input": "hi", "stream": True}, fake=fake, stores=stores
    )
    if unstarted:
        await response.cleanup()
    else:
        await anext(response.original_iterator)
        await response.original_iterator.aclose()
    assert context.closed and len(fake.calls) == 1
    assert await _credit_remaining(stores.credit, "gm-a") == pytest.approx(200 - TEXT_ESTIMATE)
    quota = await stores.rate.snapshot_quota_groups(["pa"])
    assert quota["pa"].input_tpm_used_60s == 4
    snapshot = await stores.credit.live_snapshot(
        ["gm-a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshot["gm-a"].active_reservations == 0


@pytest.mark.parametrize("complete", [False, True])
def test_complete_signed_prefetch_is_explicit_full_body_exception(complete):
    settlement = GoogleAttemptSettlement(TEXT_ESTIMATE, 1)
    settlement.decoder = SimpleNamespace(usage=(4, 2), prefetch_finished=complete)
    settlement.capture_stream_usage(_google_settings(), MODEL)
    assert settlement.cost == pytest.approx(OBSERVED_COST if complete else TEXT_ESTIMATE)
    assert settlement.input_tokens == 4


def test_usage_only_prefetch_retains_estimate():
    decoder = GoogleAiStudioAdapter().create_stream_decoder(logical_model=MODEL)
    decoder.feed(COUNTS)
    settlement = GoogleAttemptSettlement(TEXT_ESTIMATE, 1, decoder=decoder)
    settlement.capture_stream_usage(_google_settings(), MODEL)
    assert settlement.cost == TEXT_ESTIMATE and settlement.input_tokens == 4
