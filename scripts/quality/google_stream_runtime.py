"""Actual loopback Responses delivery with incremental provider usage observation."""

from __future__ import annotations

import asyncio
import json
import math
import secrets
import time

import httpx
from fastapi import FastAPI, HTTPException, Request
from google_compatible_runtime import INITIAL_USD, MODEL, PRICE_PER_MILLION, compatible_settings
from google_incremental_usage import MAX_FRAME_BYTES, MAX_INPUT_TOKENS, IncrementalUsage
from google_live_runtime import QuietLogger
from google_loopback import serve_loopback

from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.api.routes.openai import build_router
from foundry_router.auth import verify_client_auth
from foundry_router.backends import MAX_GOOGLE_RESPONSE_BYTES, AllowedBackendClient
from foundry_router.cleanup import protected_cleanup
from foundry_router.credit import InMemoryCreditStore, estimate_request_cost
from foundry_router.health import InMemoryHealthStore
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.ratelimit import InMemoryRateLimitStore

PROMPTS = {
    "ordinary": "Reply with the word ready.",
    "reasoning": "Explain (17*23-19)/4 in three short steps.",
    "cancel": "List the integers from 1 to 200.",
}
REQUEST_SECONDS = 25
CASE_SECONDS = 30
CLEANUP_SECONDS = 1
POLL_SECONDS = 0.01
MAX_REQUEST_BYTES = 4096
HTTP_OK = 200


class ObservedBytes(httpx.AsyncByteStream):
    def __init__(self, response, guard):
        self.response, self.guard = response, guard

    async def __aiter__(self):
        try:
            async for chunk in self.response.aiter_bytes():
                if self.guard.first_chunk is None:
                    self.guard.first_chunk = time.monotonic()
                try:
                    self.guard.observer.feed(chunk)
                finally:
                    # Persist retained partial numeric usage even if this chunk later fails.
                    self.guard.persist()
                if self.guard.observer.overrun:
                    raise ValueError("Verification token overrun")
                yield chunk
            self.guard.observer.finish()
            self.guard.eof_time = time.monotonic()
            self.guard.persist()
        finally:
            await self.aclose()

    async def aclose(self):
        await self.response.aclose()
        self.guard.closed.set()


class IncrementalGuard(httpx.AsyncBaseTransport):
    def __init__(self, transport, *, credential, case, reserve, progress, terminal_facts=False):  # noqa: PLR0913 -- owned verifier inputs
        self.transport, self.credential, self.case = transport, credential, case
        self.reserve, self.progress = reserve, progress
        self.observer = IncrementalUsage()
        self.dispatches = 0
        self.provider_status = None
        self.first_chunk = None
        self.eof_time = None
        self.closed = asyncio.Event()
        self.started = time.monotonic()
        self.terminal_facts = terminal_facts

    def persist(self):
        value = {
            "dispatches": self.dispatches,
            "provider_http_status": self.provider_status,
            "input_tokens": self.observer.input_tokens,
            "output_tokens": self.observer.output_tokens,
            "thought_tokens": self.observer.thought_tokens,
            "actual_tokens": self.observer.maximum_tokens,
            "budget_overrun": self.observer.overrun,
            "usage_invalid": self.observer.invalid,
        }
        if self.terminal_facts:
            value.update(terminal_metadata(self.observer))
        self.progress(value)

    async def handle_async_request(self, request):
        prompt = PROMPTS[self.case["prompt"]]
        expected = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_completion_tokens": 1024,
        }
        if self.case["stream"]:
            expected.update(stream=True, stream_options={"include_usage": True})
        if (
            self.dispatches
            or len(prompt.encode("ascii")) + 16 > MAX_INPUT_TOKENS
            or request.method != "POST"
            or str(request.url)
            != "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            or len(request.content) > MAX_REQUEST_BYTES
            or json.loads(request.content) != expected
            or request.headers.get("authorization") != "Bearer " + self.credential
            or request.headers.get("accept-encoding") != "identity"
        ):
            raise ValueError("Verification dispatch rejected")
        self.reserve()
        self.dispatches = 1
        self.persist()
        response = await self.transport.handle_async_request(request)
        try:
            self.provider_status = response.status_code
            self.persist()
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                raise ValueError("Verification encoded response rejected")  # noqa: TRY301 -- ownership cleanup catches all setup failures
            if not self.case["stream"] and response.status_code == HTTP_OK:
                return await self._nonstream(response)
            return httpx.Response(
                response.status_code, headers=response.headers, stream=ObservedBytes(response, self)
            )
        except BaseException:
            # Transfer ownership only after setup/persistence succeeds. Cancellation
            # or persistence failure cannot strand a received provider response.
            await response.aclose()
            self.closed.set()
            raise

    async def _nonstream(self, response):
        payload = bytearray()
        try:
            async for chunk in response.aiter_bytes():
                if len(payload) + len(chunk) > MAX_GOOGLE_RESPONSE_BYTES:
                    raise ValueError("Verification response bound")
                payload.extend(chunk)
            event = load_bounded_json(payload.decode(), max_bytes=MAX_GOOGLE_RESPONSE_BYTES)
            # Observe only existing usage; normal adapter validates message/output.
            if isinstance(event, dict):
                try:
                    usage = event.get("usage")
                    if isinstance(usage, dict):
                        self.observer._usage(usage, final=True)
                    else:
                        self.observer.invalid = True
                    choices = event.get("choices")
                    if isinstance(choices, list):
                        self.observer.finish_reason = any(
                            isinstance(item, dict) and item.get("finish_reason") == "stop"
                            for item in choices
                        )
                    else:
                        self.observer.invalid = True
                    self.observer.done = True
                    self.observer.finish()
                finally:
                    self.persist()
            else:
                self.observer.invalid = True
            self.eof_time = time.monotonic()
            self.persist()
            if self.observer.overrun:
                raise ValueError("Verification token overrun")
            return httpx.Response(
                response.status_code, headers=response.headers, content=bytes(payload)
            )
        finally:
            await response.aclose()
            self.closed.set()

    async def aclose(self):
        self.credential = ""
        await self.transport.aclose()


class PublicEvents:
    def __init__(self):
        self.buffer = bytearray()
        self.total = 0
        self.first_text = None
        self.completed = False
        self.usage = None
        self.text_present = False
        self.terminal = False
        self.invalid = False

    def feed(self, chunk):
        self.total += len(chunk)
        if (
            self.total > MAX_GOOGLE_RESPONSE_BYTES
            or len(self.buffer) + len(chunk) > MAX_FRAME_BYTES
        ):
            raise ValueError("Verification public stream bound")
        self.buffer.extend(chunk)
        while b"\n\n" in self.buffer:
            frame, rest = self.buffer.split(b"\n\n", 1)
            self.buffer = bytearray(rest)
            data = b"\n".join(
                line[5:].lstrip(b" ") for line in frame.splitlines() if line.startswith(b"data:")
            )
            if not data:
                continue
            event = load_bounded_json(data.decode(), max_bytes=MAX_FRAME_BYTES)
            if not isinstance(event, dict):
                raise ValueError("Verification public event invalid")  # noqa: TRY004 -- shared sanitized protocol failure
            if self.terminal:
                self.invalid = True
            kind = event.get("type")
            if kind in {"error", "response.failed", "response.incomplete"}:
                self.invalid = True
                self.terminal = True
            if (
                event.get("type") == "response.output_text.delta"
                and isinstance(event.get("delta"), str)
                and event["delta"].strip()
                and self.first_text is None
            ):
                self.first_text = time.monotonic()
                self.text_present = True
            if event.get("type") == "response.completed":
                self.terminal = True
                response = event.get("response")
                if isinstance(response, dict):
                    self.completed = (
                        response.get("status") == "completed"
                        and not response.get("error")
                        and not response.get("incomplete_details")
                    )
                    self.usage = response.get("usage")

    def finish(self):
        self.invalid |= bool(self.buffer) or not self.terminal


def make_app(settings, backend, credit, quota, caller_key, case_id):  # noqa: PLR0913, PLR0917 -- owned verification dependencies
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
    return app


def terminal_metadata(observer):
    return {
        "stop_seen": observer.finish_reason,
        "done_seen": observer.done,
        "upstream_eof": observer.eof,
        "final_usage_shape": observer.final_usage_shape,
    }


async def run_case(*, credential, case, transport, reserve, progress, terminal_facts=False):  # noqa: PLR0913 -- owned verifier inputs
    caller_key = secrets.token_urlsafe(32)
    settings = compatible_settings(credential, caller_key)
    guard = IncrementalGuard(
        transport,
        credential=credential,
        case=case,
        reserve=reserve,
        progress=progress,
        terminal_facts=terminal_facts,
    )
    backend = AllowedBackendClient(settings=settings)
    try:
        async with asyncio.timeout(CASE_SECONDS - 2):
            result = await _run_owned_case(
                settings=settings, guard=guard, backend=backend, caller_key=caller_key, case=case
            )
            if terminal_facts:
                result.update(terminal_metadata(guard.observer))
            return result
    finally:
        await protected_cleanup([backend.aclose], timeout_seconds=1)


async def _run_owned_case(*, settings, guard, backend, caller_key, case):  # noqa: PLR0915 -- one owned request lifecycle
    await backend._client.aclose()
    backend._client = httpx.AsyncClient(
        transport=guard,
        trust_env=False,
        follow_redirects=False,
        timeout=20,
        headers={"Accept-Encoding": "identity"},
    )
    credit, quota = InMemoryCreditStore(), InMemoryRateLimitStore()
    await credit.sync_from_settings(settings)
    await quota.sync_from_settings(settings)
    app = make_app(settings, backend, credit, quota, caller_key, case["case_id"])
    public = PublicEvents()
    status, error = None, None
    cancel_time = None
    body = {"model": "m", "input": PROMPTS[case["prompt"]], "max_output_tokens": 1024}
    estimate = estimate_request_cost(
        model="m", operation="responses", body=body, pricing=settings.pricing, settings=settings
    )
    natural_cleanup = False
    live = None
    try:
        async with asyncio.timeout(CASE_SECONDS):
            async with serve_loopback(app) as origin:
                try:
                    async with asyncio.timeout(REQUEST_SECONDS):
                        async with httpx.AsyncClient(trust_env=False, timeout=25) as client:
                            if case["stream"]:
                                async with client.stream(
                                    "POST",
                                    origin + "/openai/v1/responses",
                                    headers={"api-key": caller_key},
                                    json={**body, "stream": True},
                                ) as response:
                                    status = response.status_code
                                    async for chunk in response.aiter_bytes():
                                        public.feed(chunk)
                                        if case["cancel"] and public.first_text is not None:
                                            cancel_time = time.monotonic()
                                            break
                                    if not case["cancel"]:
                                        public.finish()
                            else:
                                response = await client.post(
                                    origin + "/openai/v1/responses",
                                    headers={"api-key": caller_key},
                                    json=body,
                                )
                                status = response.status_code
                                if status == HTTP_OK:
                                    value = load_bounded_json(
                                        response.text, max_bytes=MAX_GOOGLE_RESPONSE_BYTES
                                    )
                                    public.completed = (
                                        value.get("status") == "completed"
                                        and not value.get("error")
                                        and not value.get("incomplete_details")
                                    )
                                    public.usage = value.get("usage")
                                    output = value.get("output")
                                    if isinstance(output, list):
                                        public.text_present = any(
                                            isinstance(part, dict)
                                            and part.get("type") == "output_text"
                                            and isinstance(part.get("text"), str)
                                            and bool(part["text"].strip())
                                            for item in output
                                            if isinstance(item, dict)
                                            for part in (item.get("content") or [])
                                            if isinstance(item.get("content"), list)
                                        )
                except (ValueError, RuntimeError, OSError, TimeoutError, httpx.HTTPError):
                    error = "provider_or_protocol_failure"
                async with asyncio.timeout(CLEANUP_SECONDS):
                    while True:
                        live = (
                            await credit.live_snapshot(
                                ["g"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
                            )
                        )["g"]
                        natural_cleanup = (
                            guard.closed.is_set()
                            and live.active_reservations == 0
                            and live.reserved_inflight_usd == 0
                        )
                        if natural_cleanup or not guard.dispatches:
                            break
                        await asyncio.sleep(POLL_SECONDS)
    except (ValueError, RuntimeError, OSError, TimeoutError, httpx.HTTPError):
        error = "cleanup_or_execution_failure"
    finally:
        app.dependency_overrides.clear()
    observer = guard.observer
    debit = INITIAL_USD - live.estimated_remaining_usd if live is not None else None
    known_usage = observer.terminal_usage
    expected = (
        (observer.input_tokens + observer.output_tokens) * PRICE_PER_MILLION / 1_000_000
        if known_usage
        else estimate.estimated_cost_usd
        if estimate is not None
        else None
    )
    settlement = (
        debit is not None and expected is not None and math.isclose(debit, expected, abs_tol=1e-9)
    )
    early = public.first_text is not None and (
        guard.eof_time is None or public.first_text < guard.eof_time
    )
    cancelled_early = cancel_time is not None and (
        guard.eof_time is None or cancel_time < guard.eof_time
    )
    usage_matches = (
        isinstance(public.usage, dict)
        and public.usage.get("input_tokens") == observer.input_tokens
        and public.usage.get("output_tokens") == observer.output_tokens
    )
    normal = (
        public.completed
        and public.text_present
        and not public.invalid
        and known_usage
        and usage_matches
        and (early or not case["stream"])
    )
    passed = (
        status == HTTP_OK
        and guard.dispatches == 1
        and not observer.invalid
        and not observer.overrun
        and not public.invalid
        and natural_cleanup
        and settlement
        and error is None
        and (cancelled_early if case["cancel"] else normal)
    )
    return {
        **case,
        "model": MODEL,
        "status": "passed" if passed else "failed",
        "http_status": status,
        "provider_http_status": guard.provider_status,
        "dispatches": guard.dispatches,
        "actual_tokens": observer.maximum_tokens,
        "input_tokens": observer.input_tokens,
        "output_tokens": observer.output_tokens,
        "thought_tokens": observer.thought_tokens,
        "budget_overrun": observer.overrun,
        "usage_invalid": observer.invalid,
        "terminal_usage": known_usage,
        "public_completed": public.completed,
        "public_text_before_upstream_eof": early,
        "cancelled_before_upstream_eof": cancelled_early,
        "natural_cleanup": natural_cleanup,
        "usage_matches": usage_matches,
        "settlement_matches": settlement,
        "synthetic_debit_usd": round(debit, 9) if debit is not None else None,
        "settlement_kind": "observed_usage" if known_usage else "conservative_reservation",
        "first_upstream_chunk_seconds": round(guard.first_chunk - guard.started, 6)
        if guard.first_chunk
        else None,
        "first_public_text_seconds": round(public.first_text - guard.started, 6)
        if public.first_text
        else None,
        "elapsed_seconds": round(time.monotonic() - guard.started, 3),
        "error_category": error,
    }
