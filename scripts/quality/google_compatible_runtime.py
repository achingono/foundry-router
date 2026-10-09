"""Isolated metered compatible-text verification; never production configuration."""

from __future__ import annotations

import asyncio
import json
import math
import secrets

import httpx
from fastapi import FastAPI, HTTPException, Request
from google_live_runtime import IsolatedSettings, QuietLogger, _read_public_stream

from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.api.routes.openai import build_router
from foundry_router.auth import verify_client_auth
from foundry_router.backends import MAX_GOOGLE_RESPONSE_BYTES, AllowedBackendClient
from foundry_router.credit import InMemoryCreditStore
from foundry_router.health import InMemoryHealthStore
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.ratelimit import InMemoryRateLimitStore

MODEL = "gemini-3.5-flash-lite"
PROMPT = "Reply with the word ready."
OUTPUT_TOKENS = 1024
RESERVED_TOKENS = 1088
INITIAL_USD = 100.0
PRICE_PER_MILLION = 1000.0
MAX_REQUEST_BYTES = 4096
HTTP_OK = 200
CASE_TIMEOUT_SECONDS = 25


class CompatibleGuard(httpx.AsyncBaseTransport):
    def __init__(self, transport, *, credential, ledger, project, case_id, stream):  # noqa: PLR0913 -- owned verification inputs
        self.transport = transport
        self.credential = credential
        self.ledger = ledger
        self.project = project
        self.case_id = case_id
        self.stream = stream
        self.dispatched = False
        self.provider_http_status = None
        self.usage = None
        self.reasoning_tokens = None
        self.actual_tokens = None
        self.overrun = False
        self.valid_usage = False

    async def handle_async_request(self, request):
        expected = {
            "model": MODEL,
            "messages": [{"role": "user", "content": PROMPT}],
            "max_completion_tokens": OUTPUT_TOKENS,
        }
        if self.stream:
            expected.update(stream=True, stream_options={"include_usage": True})
        if (
            self.dispatched
            or request.method != "POST"
            or str(request.url)
            != "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            or len(request.content) > MAX_REQUEST_BYTES
            or json.loads(request.content) != expected
            or request.headers.get("authorization") != "Bearer " + self.credential
            or request.headers.get("accept-encoding") != "identity"
        ):
            raise ValueError("Compatible validation dispatch rejected")
        self.ledger.reserve(self.project, self.case_id, RESERVED_TOKENS)
        self.dispatched = True
        response = await self.transport.handle_async_request(request)
        self.provider_http_status = response.status_code
        try:
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                raise ValueError("Compatible encoded response rejected")
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                if len(chunks) + len(chunk) > MAX_GOOGLE_RESPONSE_BYTES:
                    raise ValueError("Compatible response bound exceeded")
                chunks.extend(chunk)
            self._capture_usage(bytes(chunks))
            return httpx.Response(
                response.status_code,
                headers={
                    key: value
                    for key, value in response.headers.items()
                    if key.lower()
                    not in {"content-encoding", "content-length", "transfer-encoding"}
                },
                content=bytes(chunks),
            )
        finally:
            await response.aclose()

    def _capture_usage(self, wire):
        events = []
        invalid = False
        if self.stream:
            payloads = [
                line.strip()[5:].strip()
                for line in wire.splitlines()
                if line.strip().startswith(b"data:")
                and line.strip()[5:].strip() not in {b"", b"[DONE]"}
            ]
        else:
            payloads = [wire]
        for payload in payloads:
            try:
                events.append(
                    load_bounded_json(payload.decode(), max_bytes=MAX_GOOGLE_RESPONSE_BYTES)
                )
            except (ValueError, UnicodeError):
                invalid = True
        if not events:
            return
        usages = [
            event["usage"]
            for event in events
            if isinstance(event, dict) and isinstance(event.get("usage"), dict)
        ]
        aggregates = []
        for usage in usages:
            prompt, completion, total = (
                usage.get(name) for name in ("prompt_tokens", "completion_tokens", "total_tokens")
            )
            if type(total) is int and total >= 0:
                aggregates.append(total)
            if type(prompt) is int and prompt >= 0 and type(completion) is int and completion >= 0:
                aggregates.append(prompt + completion)
        if aggregates:
            self.actual_tokens = max(aggregates)
            self.ledger.record_usage(self.project, self.case_id, self.actual_tokens)
            self.overrun = self.actual_tokens > RESERVED_TOKENS
        if not usages:
            return
        usage = usages[-1]
        counts = tuple(
            usage.get(name) for name in ("prompt_tokens", "completion_tokens", "total_tokens")
        )
        if any(type(value) is not int or value < 0 for value in counts):
            return
        prompt, completion, total = counts
        self.usage = counts
        details = usage.get("completion_tokens_details")
        reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
        self.reasoning_tokens = reasoning if type(reasoning) is int and reasoning >= 0 else None
        reasoning_ok = reasoning is None or (
            type(reasoning) is int and 0 <= reasoning <= completion
        )
        self.valid_usage = (
            not invalid
            and total == prompt + completion
            and completion <= OUTPUT_TOKENS
            and reasoning_ok
            and not self.overrun
            and self.actual_tokens == total
        )

    async def aclose(self):
        self.credential = ""
        await self.transport.aclose()


def compatible_settings(credential, caller_key):
    return IsolatedSettings(
        _env_file=None,
        backends_json=json.dumps(
            {
                "g": {
                    "provider": "google_ai_studio",
                    "api_surface": "openai_compat",
                    "endpoint": "https://generativelanguage.googleapis.com",
                    "credential": credential,
                    "deployment": MODEL,
                    "credit_group": "g",
                    "quota_group": "isolated-project",
                }
            }
        ),
        models_json='{"m":{"backends":{"g":1}}}',
        client_api_keys_json=json.dumps([caller_key]),
        admin_api_keys_json=json.dumps([secrets.token_urlsafe(32)]),
        state_backend="memory",
        rate_limit_backend="memory",
        retry_attempts=0,
        reservation_max_age_seconds=30,
        http_max_connections=1,
        backend_cycle_start_day_json='{"g":1}',
        backend_cycle_allowance_usd_json='{"g":100}',
        backend_initial_estimated_remaining_usd_json='{"g":100}',
        min_credit_reserve_usd=0,
        min_credit_reserve_percent=0,
        pricing_json=json.dumps(
            {"m": {"input_per_million": PRICE_PER_MILLION, "output_per_million": PRICE_PER_MILLION}}
        ),
        google_state_keys_json=None,
    )


async def run_compatible_case(*, credential, ledger, project, case_id, transport, stream):  # noqa: PLR0913 -- owned verification inputs
    caller_key = secrets.token_urlsafe(32)
    settings = compatible_settings(credential, caller_key)
    guard = CompatibleGuard(
        transport,
        credential=credential,
        ledger=ledger,
        project=project,
        case_id=case_id,
        stream=stream,
    )
    backend = AllowedBackendClient(settings=settings)
    await backend._client.aclose()
    backend._client = httpx.AsyncClient(
        transport=guard,
        timeout=20,
        trust_env=False,
        follow_redirects=False,
        headers={"Accept-Encoding": "identity"},
    )
    credit = InMemoryCreditStore()
    await credit.sync_from_settings(settings)
    quota = InMemoryRateLimitStore()
    await quota.sync_from_settings(settings)
    app = FastAPI()

    async def authenticate(request: Request):
        if request.headers.get("api-key") != caller_key:
            raise HTTPException(status_code=401, detail="Invalid verification caller")
        request.state.correlation_id = case_id
        request.state.request_key = case_id
        return caller_key

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
    public = {}
    status = None
    error_category = None
    try:
        try:
            async with asyncio.timeout(CASE_TIMEOUT_SECONDS):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://isolated.test"
                ) as client:
                    if stream:
                        status, public = await _read_public_stream(
                            client,
                            caller_key=caller_key,
                            prompt=PROMPT,
                            output_tokens=OUTPUT_TOKENS,
                        )
                    else:
                        result = await client.post(
                            "/openai/v1/responses",
                            headers={"api-key": caller_key},
                            json={
                                "model": "m",
                                "input": PROMPT,
                                "max_output_tokens": OUTPUT_TOKENS,
                            },
                        )
                        status = result.status_code
                        public = result.json() if status == HTTP_OK else {}
        except (ValueError, RuntimeError, OSError, TimeoutError, httpx.HTTPError):
            error_category = "provider_or_protocol_failure"
        live = (
            await credit.live_snapshot(
                ["g"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
            )
        )["g"]
        debit = INITIAL_USD - live.estimated_remaining_usd
        expected = sum(guard.usage[:2]) * PRICE_PER_MILLION / 1_000_000 if guard.usage else None
        cleanup = live.active_reservations == 0 and live.reserved_inflight_usd == 0
        output = public.get("output")
        if not isinstance(output, list):
            output = []
        text_present = any(
            isinstance(part, dict)
            and isinstance(part.get("text"), str)
            and bool(part["text"].strip())
            for item in output
            if isinstance(item, dict)
            for part in item.get("content", [])
            if isinstance(item.get("content"), list)
        )
        completed = (
            public.get("status") == "completed"
            and not public.get("error")
            and not public.get("incomplete_details")
        )
        public_usage = public.get("usage")
        usage_matches = (
            guard.usage is not None
            and isinstance(public_usage, dict)
            and public_usage.get("input_tokens") == guard.usage[0]
            and public_usage.get("output_tokens") == guard.usage[1]
        )
        settlement_matches = expected is not None and math.isclose(debit, expected, abs_tol=1e-9)
        passed = (
            status == HTTP_OK
            and completed
            and text_present
            and guard.valid_usage
            and usage_matches
            and settlement_matches
            and cleanup
        )
        return {
            "case_id": case_id,
            "project": project,
            "model": MODEL,
            "surface": "openai_compat",
            "stream": stream,
            "thinking_policy": "provider_default",
            "status": "passed" if passed else "failed",
            "http_status": status,
            "provider_http_status": guard.provider_http_status,
            "dispatched": guard.dispatched,
            "actual_tokens": guard.actual_tokens,
            "input_tokens": guard.usage[0] if guard.usage else None,
            "output_tokens": guard.usage[1] if guard.usage else None,
            "thought_tokens": guard.reasoning_tokens,
            "budget_overrun": guard.overrun,
            "public_completed": completed,
            "public_text_present": text_present,
            "usage_matches": usage_matches,
            "synthetic_debit_usd": round(debit, 9),
            "settlement_matches": settlement_matches,
            "reservations_cleared": cleanup,
            "error_category": error_category,
        }
    finally:
        await backend.aclose()
        app.dependency_overrides.clear()
