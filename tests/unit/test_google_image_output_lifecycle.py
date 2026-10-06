"""Generated output cancellation and inspector errors retain the full owned reserve."""

import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_google_lifecycle import FakeBackendClient, FakeStreamContext, FakeUpstream

from foundry_router.api.common import api_error
from foundry_router.config import BackendConfig, PricingConfig
from foundry_router.credit import estimate_request_cost
from foundry_router.forwarding import forward_non_streaming_with_retries
from tests.unit.test_google_image_output import artifact, native
from tests.unit.test_google_image_output_config import profile

BODY = {
    "model": "m",
    "input": "synthetic",
    "tools": [{"type": "image_generation", "output_format": "png", "size": "1024x1024"}],
    "max_output_tokens": 2048,
}


def settings():
    return SimpleNamespace(
        backends={
            "g": BackendConfig(
                provider="google_ai_studio",
                api_surface="native",
                endpoint="https://synthetic.example.test",
                deployment="configured",
                credential="synthetic",
                google_features=profile(),
            )
        },
        models={"m": SimpleNamespace(backends={"g": 1})},
        pricing={
            "m": PricingConfig(
                input_per_million=10, output_per_million=30, image_output_per_image=0.2
            )
        },
        retry_attempts=1,
        retry_max_delay_seconds=0.01,
        reservation_max_age_seconds=30,
    )


@pytest.mark.parametrize("failure", ["cancel", "oserror", "deadline"])
async def test_known_usage_cannot_reduce_image_reserve_after_inspection_failure(failure):
    config = settings()
    provider = FakeBackendClient()
    raw = native([artifact()])
    raw["usageMetadata"] = {"promptTokenCount": 4, "candidatesTokenCount": 2, "totalTokenCount": 6}
    provider.handler = lambda *_: FakeStreamContext(FakeUpstream(body=json.dumps(raw).encode()))
    started = asyncio.Event()

    class Lease:
        def bind_delivery_deadline(self, deadline):
            pass

        async def inspect(self, *_args, **_kwargs):
            started.set()
            if failure == "oserror":
                raise OSError("PRIVATE_WORKER_ERROR")
            if failure == "deadline":
                raise TimeoutError("PRIVATE_DEADLINE")
            await asyncio.Event().wait()

    result_task = asyncio.create_task(
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
            output_lease=Lease(),
            reservation_deadline_monotonic=time.monotonic() + 1,
        )
    )
    await asyncio.wait_for(started.wait(), 1)
    if failure == "cancel":
        result_task.cancel()
    result = await result_task
    reserve = estimate_request_cost(
        model="m", operation="responses", body=BODY, pricing=config.pricing, settings=config
    )
    assert result.response.status_code == 502 and result.force_charge
    assert (
        result.settlement_cost_usd == reserve.estimated_cost_usd
        and result.settlement_input_tokens == 4
    )
    assert len(provider.calls) == 1 and provider.contexts[0].closed
    assert b"PRIVATE" not in result.response.body
