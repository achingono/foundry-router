"""Finite audio cancellation before body completion preserves the whole reserve."""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from test_google_lifecycle import FakeBackendClient, FakeStreamContext, FakeUpstream

from foundry_router.api.common import api_error
from foundry_router.api.google_output_work import OutputInspectionLease
from foundry_router.config import BackendConfig, PricingConfig
from foundry_router.credit import estimate_request_cost
from foundry_router.forwarding import forward_non_streaming_with_retries
from tests.unit.test_google_audio_output import BODY
from tests.unit.test_google_audio_output_config import profile
from tests.unit.test_google_image_output_lifecycle import settings


@pytest.mark.parametrize("cancel", [False, True])
async def test_audio_body_read_cancel_or_deadline_never_retries_and_keeps_full_reserve(cancel):
    config = settings()
    config.backends["g"] = BackendConfig(
        provider="google_ai_studio",
        api_surface="native",
        endpoint="https://synthetic.example.test",
        deployment="configured",
        credential="synthetic",
        google_features=profile(),
    )
    config.pricing["m"] = PricingConfig(
        input_per_million=10,
        output_per_million=30,
        audio_output_per_second=0.01,
    )
    started = asyncio.Event()

    class HangingBody(FakeUpstream):
        async def aiter_bytes(self):
            started.set()
            await asyncio.Event().wait()
            yield b""

    provider = FakeBackendClient()
    provider.handler = lambda *_: FakeStreamContext(HangingBody())
    lease = OutputInspectionLease(slots=2)
    try:
        task = asyncio.create_task(
            forward_non_streaming_with_retries(
                settings=config,
                backend_id="g",
                operation="responses",
                headers={},
                body=BODY,
                get_backend_client=lambda: provider,
                set_backend_active=AsyncMock(),
                set_backend_cooldown=AsyncMock(),
                sleep=asyncio.sleep,
                api_error=api_error,
                output_lease=lease,
                reservation_deadline_monotonic=time.monotonic() + 0.1,
            )
        )
        await asyncio.wait_for(started.wait(), 1)
        if cancel:
            task.cancel()
        result = await asyncio.wait_for(task, 1)
        reserve = estimate_request_cost(
            model="m",
            operation="responses",
            body=BODY,
            pricing=config.pricing,
            settings=config,
        )
        assert result.force_charge and not result.retryable_failure
        assert result.settlement_cost_usd == pytest.approx(reserve.estimated_cost_usd)
        assert len(provider.calls) == 1 and provider.contexts[0].closed
        with pytest.raises(ValueError, match="busy"):
            OutputInspectionLease()
    finally:
        lease.close()
    replacement = OutputInspectionLease(slots=2)
    replacement.close()
