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
MAX_PROMPT_CHARS = 1024

RESERVED_TOKENS = 512
OUTPUT_TOKENS = 64
LEVEL_OUTPUT_TOKENS = 1024
LEVEL_INPUT_ESTIMATE = 64
LEVEL_RESERVED_TOKENS = LEVEL_OUTPUT_TOKENS + LEVEL_INPUT_ESTIMATE
PROMPT = "Reply with the word ready."
HARD_PROMPT = "What is the sum of the first 50 prime numbers? Reply with just the number."
BUDGET_ZERO_THINKING = {"thinkingBudget": 0}


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


def extract_stream_usage(chunks: bytes) -> tuple[int | None, int | None, int | None]:
    """Return (prompt, output, thoughts) from native nonstream JSON or SSE chunks.

    SSE form is one JSON object per ``data:`` line terminated by ``[DONE]``;
    the last line carrying ``usageMetadata`` wins. Anything unparseable yields
    unknowns, which the caller treats as ambiguous (debit retained, no refund).
    """
    try:
        raw = load_bounded_json(chunks.decode(), max_bytes=MAX_GOOGLE_RESPONSE_BYTES)
        prompt, output = native_usage(raw)
        usage = raw.get("usageMetadata") if isinstance(raw, dict) else None
        thoughts = usage.get("thoughtsTokenCount") if isinstance(usage, dict) else None
        return prompt, output, thoughts if isinstance(thoughts, int) else None
    except (ValueError, UnicodeError, TypeError, AttributeError):
        pass
    metadata = None
    try:
        text = chunks.decode()
    except UnicodeError:
        return None, None, None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("data:"):
            continue
        payload = stripped[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            event = load_bounded_json(payload, max_bytes=MAX_GOOGLE_RESPONSE_BYTES)
        except (ValueError, TypeError):
            return None, None, None
        if isinstance(event, dict) and isinstance(event.get("usageMetadata"), dict):
            metadata = event["usageMetadata"]
    if metadata is None:
        return None, None, None
    prompt, output = native_usage({"usageMetadata": metadata})
    thoughts = metadata.get("thoughtsTokenCount")
    return prompt, output, thoughts if isinstance(thoughts, int) else None


class GuardedTransport(httpx.AsyncBaseTransport):
    def __init__(  # noqa: PLR0913 -- explicit owned validation inputs
        self,
        transport: httpx.AsyncBaseTransport,
        *,
        ledger: BudgetLedger,
        project: str,
        case_id: str,
        model: str,
        expected_thinking: dict | None = None,
        output_tokens: int = OUTPUT_TOKENS,
        reserved_tokens: int = RESERVED_TOKENS,
        expected_prompt: str = PROMPT,
        expect_stream: bool = False,
    ):
        if not isinstance(expected_prompt, str) or not expected_prompt.strip():
            raise ValueError("Invalid validation prompt")
        if len(expected_prompt) > MAX_PROMPT_CHARS:
            raise ValueError("Validation prompt exceeds bound")
        self.transport = transport
        self.ledger = ledger
        self.project = project
        self.case_id = case_id
        self.model = model
        self.expected_thinking = (
            dict(expected_thinking) if expected_thinking is not None else dict(BUDGET_ZERO_THINKING)
        )
        self.output_tokens = output_tokens
        self.reserved_tokens = reserved_tokens
        self.expected_prompt = expected_prompt
        self.expect_stream = expect_stream
        self.dispatched = False
        self.actual_tokens: int | None = None
        self.thought_tokens: int | None = None
        self.overrun = False

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        method = "streamGenerateContent" if self.expect_stream else "generateContent"
        expected_path = f"/v1beta/models/{self.model}:{method}"
        expected_body = {
            "contents": [{"role": "user", "parts": [{"text": self.expected_prompt}]}],
            "generationConfig": {
                "maxOutputTokens": self.output_tokens,
                "candidateCount": 1,
                "responseModalities": ["TEXT"],
                "thinkingConfig": self.expected_thinking,
            },
        }
        query_ok = request.url.query == b"alt=sse" if self.expect_stream else not request.url.query
        if (
            self.dispatched
            or request.method != "POST"
            or request.url.scheme != "https"
            or request.url.host != "generativelanguage.googleapis.com"
            or request.url.port not in (None, 443)
            or request.url.path != expected_path
            or not query_ok
            or request.url.userinfo
            or len(request.content) > MAX_REQUEST_BYTES
            or json.loads(request.content) != expected_body
        ):
            raise ValueError("Validation dispatch rejected")
        # Durably retain the debit before the first provider await. No retry/refund.
        self.ledger.reserve(self.project, self.case_id, self.reserved_tokens)
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
            prompt, output, thoughts = extract_stream_usage(bytes(chunks))
            # Ambiguous/malformed usage retains the full debit; never auto-refund.
            self.thought_tokens = thoughts
            if prompt is not None and output is not None:
                self.ledger.record_usage(self.project, self.case_id, prompt + output)
                self.actual_tokens = prompt + output
                self.overrun = self.actual_tokens > self.reserved_tokens
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


def isolated_settings(
    *, credential: str, model: str, caller_key: str, thinking_level: str | None = None
) -> IsolatedSettings:
    if thinking_level is None:
        features: dict[str, Any] = {"native_thinking_disabled": True}
    else:
        if thinking_level not in ("minimal", "low"):
            raise ValueError("Unsupported validation thinking level")
        features = {"native_thinking_disabled": False, "native_thinking_level": thinking_level}
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
                    "google_features": features,
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


async def _read_public_stream(
    client: httpx.AsyncClient, *, caller_key: str, prompt: str, output_tokens: int
) -> tuple[int, dict[str, Any]]:
    """Read router SSE to a single terminal response; failures yield no terminal."""
    wire = bytearray()
    async with client.stream(
        "POST",
        "/openai/v1/responses",
        headers={"api-key": caller_key},
        json={"model": "m", "input": prompt, "max_output_tokens": output_tokens, "stream": True},
    ) as response:
        if response.status_code != HTTPStatus.OK:
            return response.status_code, {}
        async for chunk in response.aiter_bytes():
            if len(wire) + len(chunk) > MAX_GOOGLE_RESPONSE_BYTES:
                raise ValueError("Validation stream bound exceeded")
            wire.extend(chunk)
    try:
        text = bytes(wire).decode()
    except UnicodeError:
        return HTTPStatus.OK, {}
    terminal = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("data:"):
            continue
        payload = stripped[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            event = load_bounded_json(payload, max_bytes=MAX_GOOGLE_RESPONSE_BYTES)
        except (ValueError, TypeError):
            return HTTPStatus.OK, {}
        if not isinstance(event, dict):
            continue
        if event.get("type") in {"response.failed", "error"}:
            return HTTPStatus.OK, {}
        if event.get("type") in {"response.completed", "response.incomplete"}:
            terminal = event.get("response") if isinstance(event.get("response"), dict) else None
    if not isinstance(terminal, dict):
        return HTTPStatus.OK, {}
    return HTTPStatus.OK, terminal


async def run_text_case(  # noqa: PLR0913 -- explicit owned validation inputs
    *,
    credential: str,
    model: str,
    ledger: BudgetLedger,
    project: str,
    case_id: str,
    transport: httpx.AsyncBaseTransport,
    thinking_level: str | None = None,
    output_tokens: int = OUTPUT_TOKENS,
    reserved_tokens: int = RESERVED_TOKENS,
    prompt: str = PROMPT,
    stream: bool = False,
) -> dict[str, Any]:
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError("Invalid validation prompt")
    caller_key = secrets.token_urlsafe(32)
    settings = isolated_settings(
        credential=credential, model=model, caller_key=caller_key, thinking_level=thinking_level
    )
    expected_thinking = {"thinkingLevel": thinking_level} if thinking_level is not None else None
    guard = GuardedTransport(
        transport,
        ledger=ledger,
        project=project,
        case_id=case_id,
        model=model,
        expected_thinking=expected_thinking,
        output_tokens=output_tokens,
        reserved_tokens=reserved_tokens,
        expected_prompt=prompt,
        expect_stream=stream,
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
                if not stream:
                    result = await client.post(
                        "/openai/v1/responses",
                        headers={"api-key": caller_key},
                        json={"model": "m", "input": prompt, "max_output_tokens": output_tokens},
                    )
                    public = result.json() if result.status_code == HTTPStatus.OK else {}
                    http_status = result.status_code
                else:
                    http_status, public = await _read_public_stream(
                        client,
                        caller_key=caller_key,
                        prompt=prompt,
                        output_tokens=output_tokens,
                    )
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
            "capability": "text_stream" if stream else "text_nonstream",
            "http_status": http_status,
            "dispatched": guard.dispatched,
            "status": "passed"
            if http_status == HTTPStatus.OK
            and valid_text
            and guard.actual_tokens is not None
            and not guard.overrun
            else "failed",
            "actual_tokens": guard.actual_tokens,
            "thought_tokens": guard.thought_tokens,
            "budget_overrun": guard.overrun,
        }
    finally:
        await backend.aclose()
        app.dependency_overrides.clear()
