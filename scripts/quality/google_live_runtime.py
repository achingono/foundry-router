"""Owned isolated text validation runtime and durable actual-dispatch guard."""

from __future__ import annotations

import asyncio
import json
import secrets
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import FastAPI, HTTPException, Request

if TYPE_CHECKING:
    from google_live_budget import BudgetLedger

from foundry_router.api.adapters.google_native import native_usage
from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.api.routes.openai import build_router
from foundry_router.auth import verify_client_auth
from foundry_router.backends import MAX_GOOGLE_RESPONSE_BYTES, AllowedBackendClient
from foundry_router.config import Settings
from foundry_router.credit import InMemoryCreditStore
from foundry_router.health import InMemoryHealthStore
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.ratelimit import InMemoryRateLimitStore

MAX_REQUEST_BYTES = 4096

RESERVED_TOKENS = 512
OUTPUT_TOKENS = 64
PROMPT = "Reply with the word ready."


class IsolatedSettings(Settings):
    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        _ = settings_cls, env_settings, dotenv_settings, file_secret_settings
        return (init_settings,)


class QuietLogger:
    def info(self, *args, **kwargs):
        pass

    warning = info
    debug = info
    error = info
    exception = info


class GuardedTransport(httpx.AsyncBaseTransport):
    def __init__(
        self,
        transport: httpx.AsyncBaseTransport,
        *,
        ledger: BudgetLedger,
        project: str,
        case_id: str,
        model: str,
    ):
        self.transport = transport
        self.ledger = ledger
        self.project = project
        self.case_id = case_id
        self.model = model
        self.dispatched = False
        self.actual_tokens: int | None = None
        self.overrun = False

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        expected_path = f"/v1beta/models/{self.model}:generateContent"
        expected_body = {
            "contents": [{"role": "user", "parts": [{"text": PROMPT}]}],
            "generationConfig": {
                "maxOutputTokens": OUTPUT_TOKENS,
                "candidateCount": 1,
                "responseModalities": ["TEXT"],
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        if (
            self.dispatched
            or request.method != "POST"
            or request.url.scheme != "https"
            or request.url.host != "generativelanguage.googleapis.com"
            or request.url.port not in (None, 443)
            or request.url.path != expected_path
            or request.url.query
            or request.url.userinfo
            or len(request.content) > MAX_REQUEST_BYTES
            or json.loads(request.content) != expected_body
        ):
            raise ValueError("Validation dispatch rejected")
        # Durably retain the debit before the first provider await. No retry/refund.
        self.ledger.reserve(self.project, self.case_id, RESERVED_TOKENS)
        self.dispatched = True
        response = await self.transport.handle_async_request(request)
        try:
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                raise ValueError("Encoded validation response rejected")
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                if len(chunks) + len(chunk) > MAX_GOOGLE_RESPONSE_BYTES:
                    raise ValueError("Validation response bound exceeded")
                chunks.extend(chunk)
            try:
                raw = load_bounded_json(chunks.decode(), max_bytes=MAX_GOOGLE_RESPONSE_BYTES)
                prompt, output = native_usage(raw)
            except (ValueError, UnicodeError, TypeError):
                # Ambiguous/malformed usage retains the full debit; never auto-refund.
                prompt, output = None, None
            if prompt is not None and output is not None:
                self.ledger.record_usage(self.project, self.case_id, prompt + output)
                self.actual_tokens = prompt + output
                self.overrun = self.actual_tokens > RESERVED_TOKENS
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

    async def aclose(self):
        await self.transport.aclose()


def isolated_settings(*, credential: str, model: str, caller_key: str) -> IsolatedSettings:
    return IsolatedSettings(
        _env_file=None,
        backends_json=json.dumps(
            {
                "g": {
                    "provider": "google_ai_studio",
                    "api_surface": "native",
                    "endpoint": "https://generativelanguage.googleapis.com",
                    "credential": credential,
                    "deployment": model,
                    "credit_metered": False,
                    "quota_group": "isolated-project",
                    "google_features": {"native_thinking_disabled": True},
                }
            }
        ),
        models_json='{"m":{"backends":{"g":1}}}',
        client_api_keys_json=json.dumps([caller_key]),
        admin_api_keys_json=json.dumps([secrets.token_urlsafe(32)]),
        state_backend="memory",
        retry_attempts=0,
        reservation_max_age_seconds=30,
        http_max_connections=1,
        model_aliases_json="{}",
        pricing_json="{}",
        google_state_keys_json=None,
    )


async def run_text_case(  # noqa: PLR0913 -- explicit owned validation inputs
    *,
    credential: str,
    model: str,
    ledger: BudgetLedger,
    project: str,
    case_id: str,
    transport: httpx.AsyncBaseTransport,
) -> dict[str, Any]:
    caller_key = secrets.token_urlsafe(32)
    settings = isolated_settings(credential=credential, model=model, caller_key=caller_key)
    guard = GuardedTransport(
        transport, ledger=ledger, project=project, case_id=case_id, model=model
    )
    backend = AllowedBackendClient(settings=settings)
    await backend._client.aclose()
    backend._client = httpx.AsyncClient(
        transport=guard, timeout=20, follow_redirects=False, headers={"Accept-Encoding": "identity"}
    )
    app = FastAPI()

    async def authenticate(request: Request):
        if request.headers.get("api-key") != caller_key:
            raise HTTPException(status_code=401, detail="Invalid validation caller")
        request.state.correlation_id = case_id
        request.state.request_key = case_id
        return caller_key

    app.dependency_overrides[verify_client_auth] = authenticate

    def get_client():
        return backend

    app.include_router(
        build_router(
            load_settings_fn=lambda: settings,
            get_backend_client_fn=get_client,
            sleep_fn=asyncio.sleep,
            health_store=InMemoryHealthStore(),
            credit_store=InMemoryCreditStore(),
            metrics_store=InMemoryMetricsStore(),
            rate_limit_store=InMemoryRateLimitStore(),
            logger=QuietLogger(),
        )
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://isolated.test"
        ) as client:
            async with asyncio.timeout(25):
                result = await client.post(
                    "/openai/v1/responses",
                    headers={"api-key": caller_key},
                    json={"model": "m", "input": PROMPT, "max_output_tokens": OUTPUT_TOKENS},
                )
        public = result.json() if result.status_code == HTTPStatus.OK else {}
        valid_text = (
            public.get("status") == "completed"
            and not public.get("error")
            and not public.get("incomplete_details")
        )
        texts = [
            part.get("text")
            for item in public.get("output", [])
            if isinstance(item, dict) and item.get("type") == "message"
            for part in item.get("content", [])
            if isinstance(part, dict) and part.get("type") == "output_text"
        ]
        valid_text = valid_text and any(isinstance(value, str) and value.strip() for value in texts)
        return {
            "case_id": case_id,
            "model": model,
            "project": project,
            "capability": "text_nonstream",
            "http_status": result.status_code,
            "dispatched": guard.dispatched,
            "status": "passed"
            if result.status_code == HTTPStatus.OK
            and valid_text
            and guard.actual_tokens is not None
            and not guard.overrun
            else "failed",
            "actual_tokens": guard.actual_tokens,
            "budget_overrun": guard.overrun,
        }
    finally:
        await backend.aclose()
        app.dependency_overrides.clear()
