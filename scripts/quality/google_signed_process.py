"""Private synthetic signed replay child; stdout is a bounded test pipe, never live evidence."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import sys
from http import HTTPStatus

import httpx
from fastapi import FastAPI, HTTPException, Request
from google_live_runtime import IsolatedSettings, QuietLogger
from openai import AsyncOpenAI, OpenAIError

from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.api.google_work import SignedWorkLease
from foundry_router.api.routes.openai import build_router
from foundry_router.auth import verify_client_auth
from foundry_router.backends import AllowedBackendClient
from foundry_router.config.google_features import GoogleFeatureProfile
from foundry_router.credit import InMemoryCreditStore, estimate_request_cost
from foundry_router.health import InMemoryHealthStore
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.ratelimit import InMemoryRateLimitStore

MAX_PIPE_BYTES = 262144
INPUT_TOKENS = 40
OUTPUT_TOKENS = 12
COST_TOLERANCE = 1e-8
PARTS = [{"text": "synthetic-answer", "thoughtSignature": "c3ludGhldGljLXNpZw=="}]
BODY = {
    "model": "m",
    "input": [{"role": "user", "content": "synthetic-question"}],
    "foundry_provider_state": {"version": 1},
    "max_output_tokens": 10,
}


def configured(changed_key):
    settings = IsolatedSettings(
        _env_file=None,
        backends_json=json.dumps(
            {
                "g": {
                    "provider": "google_ai_studio",
                    "api_surface": "native",
                    "endpoint": "https://synthetic.example.test",
                    "credential": "synthetic-key",
                    "deployment": "configured",
                    "quota_group": "project",
                    "google_features": {"native_thinking_disabled": True},
                }
            }
        ),
        models_json='{"m":{"backends":{"g":1}}}',
        client_api_keys_json='["synthetic-caller"]',
        admin_api_keys_json='["synthetic-admin"]',
        google_state_keys_json=json.dumps(
            {
                "scope_key": base64.urlsafe_b64encode(b"s" * 32).decode(),
                "keys": {
                    "fixture": base64.urlsafe_b64encode(
                        (b"n" if changed_key else b"k") * 32
                    ).decode()
                },
                "active": "fixture",
                "generation": "fixture",
            }
        ),
        pricing_json='{"m":{"input_per_million":10,"output_per_million":30}}',
        quota_group_rate_limits_json='{"project":{"rpm":100,"tpm":1000000}}',
        backend_cycle_start_day_json='{"g":1}',
        backend_cycle_allowance_usd_json='{"g":200}',
        backend_initial_estimated_remaining_usd_json='{"g":200}',
        model_aliases_json="{}",
        state_backend="memory",
        retry_attempts=0,
    )
    # Test-owned profile only: unconditional production startup gate stays closed.
    settings.backends["g"].google_features = GoogleFeatureProfile(
        features=("function_tools",),
        continuation_policy="sealed_native",
        native_thinking_disabled=False,
        native_thinking_budget=8,
        thought_token_pricing=True,
        signature_input_token_bound=100000,
    )
    settings.models["m"].continuation_policy = "bound_history_required"
    return settings


async def run(payload):  # noqa: PLR0915 -- isolated complete ownership
    if set(payload) != {"body", "changed_key"} or type(payload["changed_key"]) is not bool:
        raise ValueError("Invalid private fixture")
    settings = configured(payload["changed_key"])
    body = payload["body"]
    replay = len(body["input"]) > 1
    dispatches = 0

    async def provider(request):
        nonlocal dispatches
        if (
            request.url != "https://synthetic.example.test/v1beta/models/configured:generateContent"
            or request.method != "POST"
        ):
            raise ValueError("Unexpected synthetic destination")
        upstream = json.loads(request.content)
        if replay:
            assert upstream["contents"][1]["parts"] == PARTS
        assert "foundry_provider_state" not in request.content.decode()
        dispatches += 1
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"role": "model", "parts": PARTS}, "finishReason": "STOP"}
                ],
                "usageMetadata": {
                    "promptTokenCount": 40,
                    "candidatesTokenCount": 10,
                    "thoughtsTokenCount": 2,
                    "totalTokenCount": 52,
                },
            },
        )

    backend = AllowedBackendClient(settings=settings)
    await backend._client.aclose()
    backend._client = httpx.AsyncClient(transport=httpx.MockTransport(provider))
    credit = InMemoryCreditStore()
    quota = InMemoryRateLimitStore()
    app = FastAPI()

    async def authenticate(request: Request):
        if (
            request.headers.get("api-key") != "synthetic-caller"
            and request.headers.get("authorization") != "Bearer synthetic-caller"
        ):
            raise HTTPException(status_code=401, detail="Invalid synthetic caller")
        request.state.request_key = "independent-owned-request"
        request.state.correlation_id = "independent-owned-request"
        request.state.google_state_key_configuration = settings.google_state_keys
        request.state.google_caller_scope = hmac.new(
            b"s" * 32,
            b"caller\0synthetic-caller",
            hashlib.sha256,
        ).hexdigest()
        return "synthetic-caller"

    app.dependency_overrides[verify_client_auth] = authenticate
    app.include_router(
        build_router(
            load_settings_fn=lambda: settings,
            get_backend_client_fn=lambda: backend,
            sleep_fn=asyncio.sleep,
            health_store=InMemoryHealthStore(),
            credit_store=credit,
            metrics_store=InMemoryMetricsStore(),
            rate_limit_store=quota,
            logger=QuietLogger(),
        )
    )
    http_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app))
    sdk = AsyncOpenAI(
        api_key="synthetic-caller",
        base_url="http://synthetic.test/openai/v1",
        http_client=http_client,
        max_retries=0,
    )
    public = None
    try:
        if payload["changed_key"]:
            response = await http_client.post(
                "http://synthetic.test/openai/v1/responses",
                headers={"api-key": "synthetic-caller"},
                json=body,
            )
            status = response.status_code
            assert (
                status == HTTPStatus.UNPROCESSABLE_ENTITY
                and response.json()["error"]["type"] == "invalid_provider_state"
            )
            assert dispatches == 0
        else:
            response = await sdk.responses.create(
                model="m",
                input=body["input"],
                max_output_tokens=10,
                extra_body={"foundry_provider_state": {"version": 1}},
            )
            status = 200
            assert response.status == "completed"
            assert (
                response.usage.input_tokens == INPUT_TOKENS
                and response.usage.output_tokens == OUTPUT_TOKENS
            )
            public = response.model_dump(exclude_none=True)
            assert public["output"][0]["foundry_provider_state"]["version"] == 1
            assert dispatches == 1
        snapshots = await credit.live_snapshot(
            ["g"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
        )
        snapshot = snapshots.get("g")
        if dispatches:
            assert snapshot is not None
            assert abs(200 - snapshot.estimated_remaining_usd - 0.00076) < COST_TOLERANCE
        if snapshot is not None:
            assert snapshot.active_reservations == 0 and snapshot.reserved_inflight_usd == 0
        assert not credit._reservations and not quota._reservations
        quota_state = (await quota.snapshot_quota_groups(["project"]))["project"]
        assert quota_state.rpm_used_60s == dispatches
        assert quota_state.input_tpm_used_60s == 40 * dispatches
        leases = [SignedWorkLease(), SignedWorkLease()]
        for lease in leases:
            lease.close()
        return {
            "private_response": public,
            "summary": {
                "pid": os.getpid(),
                "http_status": status,
                "dispatches": dispatches,
                "input_tokens": 40 * dispatches,
                "output_tokens": 12 * dispatches,
                "credit_and_quota_cleanup": True,
                "signed_capacity_released": True,
                "exact_native_replay": replay and bool(dispatches),
                "estimated_reserve_usd": estimate_request_cost(
                    model="m",
                    operation="responses",
                    body=body,
                    pricing=settings.pricing,
                    settings=settings,
                ).estimated_cost_usd
                if not payload["changed_key"]
                else None,
            },
        }
    finally:
        await sdk.close()
        await backend.aclose()
        app.dependency_overrides.clear()


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_PIPE_BYTES + 1)
        if len(raw) > MAX_PIPE_BYTES:
            raise ValueError("Private fixture exceeds boundary")  # noqa: TRY301
        payload = load_bounded_json(raw.decode(), max_bytes=MAX_PIPE_BYTES)
        result = asyncio.run(run(payload))
        encoded = json.dumps(result).encode()
        if len(encoded) > MAX_PIPE_BYTES:
            raise ValueError("Private result exceeds boundary")  # noqa: TRY301
        sys.stdout.buffer.write(encoded)
        return 0  # noqa: TRY300
    except (OSError, ValueError, TypeError, KeyError, AssertionError, OpenAIError):
        sys.stderr.write("Synthetic process verification failed\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
