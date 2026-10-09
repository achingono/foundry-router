"""Native audio uses the original reservation deadline and independent cleanup."""

import asyncio
import json
import time
from unittest.mock import AsyncMock

import pytest
from test_google_lifecycle import (
    FakeBackendClient,
    FakeStreamContext,
    FakeUpstream,
    _credit_remaining,
    _stores,
)

from foundry_router.api.common import api_error
from foundry_router.api.google_audio import prepare_audio
from foundry_router.api.google_pdf import PreparedGoogleMedia
from foundry_router.api.google_video import prepare_video
from foundry_router.config import Settings
from foundry_router.credit import estimate_request_cost
from foundry_router.forwarding import forward_streaming_with_retries
from tests.unit.test_google_audio import audio_body, audio_profile, wav_part
from tests.unit.test_google_video import video_body, video_part, video_profile


@pytest.mark.parametrize("block_start", [False, True])
@pytest.mark.parametrize("media_kind", ["audio", "video"])
async def test_audio_blocked_downstream_settles_and_closes(block_start, media_kind):
    settings = Settings(
        backends_json=json.dumps(
            {
                "g": {
                    "provider": "google_ai_studio",
                    "api_surface": "native",
                    "endpoint": "https://audio.example.test",
                    "credential": "synthetic",
                    "deployment": "configured",
                    "quota_group": "p",
                    "google_features": {
                        **(
                            audio_profile() if media_kind == "audio" else video_profile()
                        ).model_dump(),
                        "native_thinking_disabled": True,
                    },
                }
            }
        ),
        models_json='{"m":{"backends":{"g":1}}}',
        client_api_keys_json='["synthetic"]',
        admin_api_keys_json='["admin-synthetic"]',
        quota_group_rate_limits_json='{"p":{"rpm":100,"tpm":1000000}}',
        pricing_json='{"m":{"input_per_million":10,"output_per_million":30}}',
        backend_cycle_start_day_json='{"g":1}',
        backend_cycle_allowance_usd_json='{"g":200}',
        backend_initial_estimated_remaining_usd_json='{"g":200}',
    )
    body = {
        **(audio_body(wav_part()) if media_kind == "audio" else video_body(video_part())),
        "stream": True,
        "max_output_tokens": 10,
    }
    media = (
        PreparedGoogleMedia((), prepare_audio(body))
        if media_kind == "audio"
        else PreparedGoogleMedia((), (), prepare_video(body))
    )
    estimate = estimate_request_cost(
        model="m", operation="responses", body=body, pricing=settings.pricing
    )
    stores = _stores(settings)
    await stores.credit.sync_from_settings(settings)
    await stores.credit.try_assign_reservation(
        "audio-deadline",
        "g",
        estimate.estimated_cost_usd,
        min_credit_reserve_usd=0,
        min_credit_reserve_percent=0,
    )
    await stores.rate.sync_from_settings(settings)
    await stores.rate.try_reserve_estimate(
        "audio-deadline", "p", estimated_input_tokens=estimate.input_tokens
    )
    raw = {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": "answer"}]}, "finishReason": "STOP"}
        ],
        "usageMetadata": {"promptTokenCount": 40, "candidatesTokenCount": 5, "totalTokenCount": 45},
    }
    context = FakeStreamContext(FakeUpstream(chunks=[f"data: {json.dumps(raw)}\n\n".encode()]))
    fake = FakeBackendClient()
    fake.handler = lambda *_: context
    result = await forward_streaming_with_retries(
        settings=settings,
        backend_id="g",
        request_id="audio-deadline",
        headers={},
        body=body,
        prepared_media=media,
        get_backend_client=lambda: fake,
        set_backend_active=stores.health.set_backend_active,
        set_backend_cooldown=stores.health.set_backend_cooldown,
        sleep=AsyncMock(),
        api_error=api_error,
        credit_store=stores.credit,
        metrics_store=stores.metrics,
        rate_limit_store=stores.rate,
        reservation_deadline_monotonic=time.monotonic() + 0.05,
    )

    async def send(message):
        if block_start or message["type"] == "http.response.body":
            await asyncio.Event().wait()

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(result.response.stream_response(send), 0.5)
    assert context.closed and fake.calls == [("g", "responses")]
    assert await _credit_remaining(stores.credit, "g") == pytest.approx(
        200 - estimate.estimated_cost_usd
    )
    quota = (await stores.rate.snapshot_quota_groups(["p"]))["p"]
    assert quota.rpm_used_60s == 1 and quota.input_tpm_used_60s == 40
