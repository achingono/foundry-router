"""Backend forwarding, bounded retries, and streaming passthrough."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from fastapi import Response
from fastapi.responses import StreamingResponse

from foundry_router.credit import estimate_response_usage_cost
from foundry_router.health import BackendHealthState

MAX_UPSTREAM_ERROR_BYTES = 64 * 1024
HTTP_OK = 200
HTTP_SUCCESS_LIMIT = 300
HTTP_TOO_MANY_REQUESTS = 429
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
SAFE_UPSTREAM_RESPONSE_HEADERS = frozenset({"cache-control", "retry-after"})
MAX_EMPTY_PRE_OUTPUT_CHUNKS = 16
PRE_OUTPUT_TIMEOUT_SECONDS = 60.0


def _extract_next_sse_event(buffer: bytes) -> tuple[bytes | None, bytes]:
    for delimiter in (b"\r\n\r\n", b"\n\n"):
        if delimiter in buffer:
            event, remaining = buffer.split(delimiter, 1)
            return event, remaining
    return None, buffer


@dataclass(frozen=True)
class BackendRequestResult:
    response: Response
    retryable_failure: bool


def is_retryable_status(status_code: int) -> bool:
    return status_code in RETRYABLE_STATUS_CODES


def parse_retry_after(raw_value: str | None, max_delay_seconds: float) -> float | None:
    if raw_value is None:
        return None
    value = raw_value.strip()
    if not value:
        return None
    parsed_seconds: float | None = None
    if value.isdigit():
        parsed_seconds = float(value)
    else:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        parsed_seconds = (retry_at - datetime.now(UTC)).total_seconds()
    return max(0.0, min(max_delay_seconds, parsed_seconds))


def retry_delay_seconds(
    *,
    attempt_number: int,
    max_delay_seconds: float,
    retry_after_header: str | None,
) -> float:
    exponential = min(max_delay_seconds, float(2 ** max(0, attempt_number - 1)))
    parsed_retry_after = parse_retry_after(retry_after_header, max_delay_seconds)
    if parsed_retry_after is None:
        return exponential
    return min(max_delay_seconds, max(exponential, parsed_retry_after))


def upstream_response(response: httpx.Response, body: bytes) -> Response:
    content_type = response.headers.get("content-type", "application/json")
    headers = {
        name: value
        for name, value in response.headers.items()
        if name.lower() in SAFE_UPSTREAM_RESPONSE_HEADERS
    }
    return Response(
        content=body,
        status_code=response.status_code,
        media_type=content_type.split(";", 1)[0],
        headers=headers,
    )


async def stream_response(
    chunks: Any,
    first_chunk: bytes,
    context: Any,
    *,
    request_id: str,
    backend_id: str,
    cooldown_seconds: float,
    model: str,
    pricing: dict[str, Any],
    status_code: int,
    set_backend_cooldown: Any,
    credit_store: Any,
    metrics_store: Any,
) -> Any:
    started_at = time.monotonic()
    charged_cost: float | None = None
    metric_status_code = status_code
    pending_event_bytes = b""

    def process_event_payload(payload: bytes) -> None:
        nonlocal charged_cost
        lines = payload.splitlines()
        for raw_line in lines:
            line = raw_line.strip()
            if not line.startswith(b"data:"):
                continue
            data_field = line[5:].lstrip()
            if not data_field or data_field == b"[DONE]":
                continue
            try:
                parsed = json.loads(data_field.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(parsed, dict):
                continue
            usage = parsed.get("usage")
            if not isinstance(usage, dict):
                continue
            usage_response = Response(
                content=json.dumps({"usage": usage}).encode("utf-8"),
                media_type="application/json",
            )
            estimated_cost = estimate_response_usage_cost(usage_response, model, pricing)
            if estimated_cost is not None:
                charged_cost = estimated_cost

    try:
        yield first_chunk
        pending_event_bytes += first_chunk
        while True:
            event_payload, pending_event_bytes = _extract_next_sse_event(pending_event_bytes)
            if event_payload is None:
                break
            process_event_payload(event_payload)
        async for chunk in chunks:
            yield chunk
            pending_event_bytes += chunk
            while True:
                event_payload, pending_event_bytes = _extract_next_sse_event(pending_event_bytes)
                if event_payload is None:
                    break
                process_event_payload(event_payload)
    except httpx.HTTPError:
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=cooldown_seconds,
        )
        metric_status_code = 502
        yield b'data: {"error":{"message":"Upstream stream failed","type":"upstream_error"}}\n\n'
    finally:
        if pending_event_bytes.strip():
            process_event_payload(pending_event_bytes)
        await context.__aexit__(None, None, None)
        is_stream_success = metric_status_code < 400
        await credit_store.finalize_request(
            request_id,
            charge_reserved=is_stream_success or (charged_cost is not None),
            charged_cost_usd=charged_cost if is_stream_success else None,
        )
        await metrics_store.observe_request(
            model=model,
            backend=backend_id,
            status_code=metric_status_code,
            latency_seconds=max(0.0, time.monotonic() - started_at),
            estimated_cost_usd=charged_cost if is_stream_success else None,
        )


async def forward_non_streaming_with_retries(
    *,
    settings: Any,
    backend_id: str,
    operation: str,
    headers: dict[str, str],
    body: dict[str, Any],
    get_backend_client: Any,
    set_backend_active: Any,
    set_backend_cooldown: Any,
    sleep: Any,
    api_error: Any,
) -> BackendRequestResult:
    max_attempts = max(1, settings.retry_attempts)
    backend_client = get_backend_client()

    for attempt in range(1, max_attempts + 1):
        try:
            upstream = await backend_client.request_backend(
                backend_id,
                operation,
                headers=headers,
                json=body,
            )
        except httpx.TransportError:
            await set_backend_cooldown(
                backend_id,
                state=BackendHealthState.ERROR_COOLDOWN,
                cooldown_seconds=settings.retry_max_delay_seconds,
            )
            if attempt < max_attempts:
                delay_seconds = retry_delay_seconds(
                    attempt_number=attempt,
                    max_delay_seconds=settings.retry_max_delay_seconds,
                    retry_after_header=None,
                )
                if delay_seconds > 0:
                    await sleep(delay_seconds)
                continue
            return BackendRequestResult(
                response=api_error(
                    502,
                    "Unable to contact the configured backend",
                    "upstream_error",
                ),
                retryable_failure=True,
            )
        except httpx.HTTPError:
            return BackendRequestResult(
                response=api_error(
                    502,
                    "Unable to contact the configured backend",
                    "upstream_error",
                ),
                retryable_failure=False,
            )

        forwarded_body = (
            upstream.content
            if HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT
            else upstream.content[:MAX_UPSTREAM_ERROR_BYTES]
        )
        candidate_response = upstream_response(upstream, forwarded_body)
        if HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT:
            await set_backend_active(backend_id)
            return BackendRequestResult(response=candidate_response, retryable_failure=False)
        if not is_retryable_status(upstream.status_code):
            return BackendRequestResult(response=candidate_response, retryable_failure=False)

        cooldown_state = (
            BackendHealthState.QUOTA_COOLDOWN
            if upstream.status_code == HTTP_TOO_MANY_REQUESTS
            else BackendHealthState.ERROR_COOLDOWN
        )
        retry_after_seconds = parse_retry_after(
            upstream.headers.get("retry-after"),
            settings.retry_max_delay_seconds,
        )
        await set_backend_cooldown(
            backend_id,
            state=cooldown_state,
            cooldown_seconds=(
                settings.retry_max_delay_seconds
                if retry_after_seconds is None
                else retry_after_seconds
            ),
        )
        if attempt < max_attempts:
            delay_seconds = retry_delay_seconds(
                attempt_number=attempt,
                max_delay_seconds=settings.retry_max_delay_seconds,
                retry_after_header=upstream.headers.get("retry-after"),
            )
            if delay_seconds > 0:
                await sleep(delay_seconds)
            continue
        return BackendRequestResult(response=candidate_response, retryable_failure=True)

    return BackendRequestResult(
        response=api_error(502, "Unable to contact the configured backend", "upstream_error"),
        retryable_failure=True,
    )


async def forward_streaming_with_retries(
    *,
    settings: Any,
    backend_id: str,
    request_id: str,
    headers: dict[str, str],
    body: dict[str, Any],
    get_backend_client: Any,
    set_backend_active: Any,
    set_backend_cooldown: Any,
    sleep: Any,
    api_error: Any,
    credit_store: Any,
    metrics_store: Any,
    pre_output_timeout_seconds: float = PRE_OUTPUT_TIMEOUT_SECONDS,
) -> BackendRequestResult:
    max_attempts = max(1, settings.retry_attempts)
    backend_client = get_backend_client()

    for attempt in range(1, max_attempts + 1):
        context = backend_client.stream_backend(
            backend_id,
            "responses",
            headers=headers,
            json=body,
        )
        try:
            upstream = await context.__aenter__()
        except httpx.TransportError:
            await set_backend_cooldown(
                backend_id,
                state=BackendHealthState.ERROR_COOLDOWN,
                cooldown_seconds=settings.retry_max_delay_seconds,
            )
            if attempt < max_attempts:
                delay_seconds = retry_delay_seconds(
                    attempt_number=attempt,
                    max_delay_seconds=settings.retry_max_delay_seconds,
                    retry_after_header=None,
                )
                if delay_seconds > 0:
                    await sleep(delay_seconds)
                continue
            return BackendRequestResult(
                response=api_error(
                    502,
                    "Unable to contact the configured backend",
                    "upstream_error",
                ),
                retryable_failure=True,
            )
        except httpx.HTTPError:
            return BackendRequestResult(
                response=api_error(
                    502,
                    "Unable to contact the configured backend",
                    "upstream_error",
                ),
                retryable_failure=False,
            )

        if upstream.status_code < HTTP_OK or upstream.status_code >= HTTP_SUCCESS_LIMIT:
            try:
                error_body = (await upstream.aread())[:MAX_UPSTREAM_ERROR_BYTES]
            except httpx.TransportError:
                await set_backend_cooldown(
                    backend_id,
                    state=BackendHealthState.ERROR_COOLDOWN,
                    cooldown_seconds=settings.retry_max_delay_seconds,
                )
                return BackendRequestResult(
                    response=api_error(
                        502,
                        "Unable to read the configured backend error response",
                        "upstream_error",
                    ),
                    retryable_failure=True,
                )
            except httpx.HTTPError:
                return BackendRequestResult(
                    response=api_error(
                        502,
                        "Unable to read the configured backend error response",
                        "upstream_error",
                    ),
                    retryable_failure=False,
                )
            finally:
                await context.__aexit__(None, None, None)
            candidate_response = upstream_response(upstream, error_body)
            if not is_retryable_status(upstream.status_code):
                return BackendRequestResult(response=candidate_response, retryable_failure=False)

            cooldown_state = (
                BackendHealthState.QUOTA_COOLDOWN
                if upstream.status_code == HTTP_TOO_MANY_REQUESTS
                else BackendHealthState.ERROR_COOLDOWN
            )
            retry_after_seconds = parse_retry_after(
                upstream.headers.get("retry-after"),
                settings.retry_max_delay_seconds,
            )
            await set_backend_cooldown(
                backend_id,
                state=cooldown_state,
                cooldown_seconds=(
                    settings.retry_max_delay_seconds
                    if retry_after_seconds is None
                    else retry_after_seconds
                ),
            )
            if attempt < max_attempts:
                delay_seconds = retry_delay_seconds(
                    attempt_number=attempt,
                    max_delay_seconds=settings.retry_max_delay_seconds,
                    retry_after_header=upstream.headers.get("retry-after"),
                )
                if delay_seconds > 0:
                    await sleep(delay_seconds)
                continue
            return BackendRequestResult(response=candidate_response, retryable_failure=True)

        chunks = upstream.aiter_raw()
        try:
            async with asyncio.timeout(pre_output_timeout_seconds):
                first_chunk = b""
                for _ in range(MAX_EMPTY_PRE_OUTPUT_CHUNKS):
                    first_chunk = await anext(chunks)
                    if first_chunk:
                        break
                if not first_chunk:
                    raise httpx.ReadError("Backend emitted too many empty pre-output chunks")
        except (StopAsyncIteration, TimeoutError, httpx.TransportError):
            await context.__aexit__(None, None, None)
            await set_backend_cooldown(
                backend_id,
                state=BackendHealthState.ERROR_COOLDOWN,
                cooldown_seconds=settings.retry_max_delay_seconds,
            )
            if attempt < max_attempts:
                delay_seconds = retry_delay_seconds(
                    attempt_number=attempt,
                    max_delay_seconds=settings.retry_max_delay_seconds,
                    retry_after_header=None,
                )
                if delay_seconds > 0:
                    await sleep(delay_seconds)
                continue
            return BackendRequestResult(
                response=api_error(
                    502,
                    "Unable to read the configured backend stream",
                    "upstream_error",
                ),
                retryable_failure=True,
            )
        except httpx.HTTPError:
            await context.__aexit__(None, None, None)
            return BackendRequestResult(
                response=api_error(
                    502,
                    "Unable to read the configured backend stream",
                    "upstream_error",
                ),
                retryable_failure=False,
            )

        await set_backend_active(backend_id)
        return BackendRequestResult(
            response=StreamingResponse(
                stream_response(
                    chunks,
                    first_chunk,
                    context,
                    request_id=request_id,
                    backend_id=backend_id,
                    cooldown_seconds=settings.retry_max_delay_seconds,
                    model=body.get("model", ""),
                    pricing=settings.pricing,
                    status_code=upstream.status_code,
                    set_backend_cooldown=set_backend_cooldown,
                    credit_store=credit_store,
                    metrics_store=metrics_store,
                ),
                status_code=upstream.status_code,
                media_type="text/event-stream",
                headers={"cache-control": "no-cache"},
            ),
            retryable_failure=False,
        )

    return BackendRequestResult(
        response=api_error(502, "Unable to contact the configured backend", "upstream_error"),
        retryable_failure=True,
    )
