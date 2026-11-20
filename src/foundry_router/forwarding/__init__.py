"""Backend forwarding, bounded retries, and streaming passthrough."""

from __future__ import annotations

import asyncio
import json
import math
import sys
import time
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from functools import partial
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import Response
from fastapi.responses import StreamingResponse

if TYPE_CHECKING:
    from foundry_router.api.google_continuation import PreparedContinuation
    from foundry_router.api.google_output_work import OutputInspectionLease
    from foundry_router.api.google_pdf import PreparedGoogleMedia
    from foundry_router.api.google_sealing import SealContext

from foundry_router.api.adapters import get_adapter
from foundry_router.api.adapters.azure_mai import translate_mai_image_output
from foundry_router.api.adapters.google_audio_request import (
    MAX_AUDIO_RESPONSE_BYTES,
    audio_output_request,
)
from foundry_router.api.adapters.google_image_output import translate_image_output
from foundry_router.api.adapters.google_image_request import image_output_request
from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.api.azure_intake import AzureIntakeError, AzureIntakeRequest
from foundry_router.api.google_work import SignedIntakeError, bounded_signed_work
from foundry_router.cleanup import DEFAULT_CLEANUP_TIMEOUT_SECONDS, protected_cleanup
from foundry_router.credit import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    estimate_request_cost,
    estimate_response_usage_cost,
    extract_response_usage_tokens,
)
from foundry_router.health import BackendHealthState
from foundry_router.logging import get_logger

_logger = get_logger(__name__)


def _log_translated_rejection(
    exc: BaseException, *, operation: str | None = None, backend_id: str | None = None
) -> None:
    """Debug-log sanitized rejected field names; never values or bodies."""
    try:
        fields = getattr(exc, "fields", ())
        names = list(fields) if isinstance(fields, tuple) else []
    except Exception:
        return
    if not names:
        return
    _logger.debug(
        "translated_response_rejected",
        operation=operation,
        backend=backend_id,
        fields=names,
    )


MAX_UPSTREAM_ERROR_BYTES = 64 * 1024
MAX_SSE_EVENT_BUFFER_BYTES = 1024 * 1024
SSE_INSPECTION_PIECE_BYTES = 64 * 1024
MAX_GOOGLE_RESPONSE_BYTES = 4 * 1024 * 1024
HTTP_OK = 200
HTTP_SUCCESS_LIMIT = 300
HTTP_TOO_MANY_REQUESTS = 429
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
GOOGLE_RETRYABLE_STATUS_CODES = frozenset({429})
GOOGLE_AUTH_STATUS_CODES = frozenset({401, 403})
SAFE_UPSTREAM_RESPONSE_HEADERS = frozenset({"cache-control", "retry-after"})
MAX_EMPTY_PRE_OUTPUT_CHUNKS = 16
PRE_OUTPUT_TIMEOUT_SECONDS = 60.0


def _extract_next_sse_event(buffer: bytes) -> tuple[bytes | None, bytes]:
    boundaries = [(buffer.find(delimiter), delimiter) for delimiter in (b"\r\n\r\n", b"\n\n")]
    found = [(index, delimiter) for index, delimiter in boundaries if index >= 0]
    if found:
        index, delimiter = min(found)
        return buffer[:index], buffer[index + len(delimiter) :]
    return None, buffer


@dataclass(frozen=True)
class BackendRequestResult:
    response: Response
    retryable_failure: bool
    settlement_cost_usd: float | None = None
    settlement_input_tokens: int | None = None
    force_charge: bool = False
    confirmed_pre_dispatch: bool = False


def _prepared_result(
    intake: AzureIntakeRequest | None, result: BackendRequestResult
) -> BackendRequestResult:
    if intake is None or isinstance(result.response, StreamingResponse):
        return result
    is_success = 200 <= result.response.status_code < 300
    if is_success:
        assert intake.prepared is not None
        actual = (
            None
            if (
                intake.backend is not None
                and intake.policy.document.backends[intake.backend].provider == "azure_mai"
            )
            else estimate_response_usage_cost(
                result.response,
                intake.prepared.model,
                {intake.prepared.model: intake.policy.document.models[intake.prepared.model].price},
            )
        )
        usage = extract_response_usage_tokens(result.response)
        intake.succeeded(
            actual if actual is not None else intake.estimate.estimated_cost_usd,
            usage[0] if usage is not None else intake.estimate.input_tokens,
        )
        return replace(
            result,
            force_charge=True,
            settlement_cost_usd=(
                actual if actual is not None else intake.estimate.estimated_cost_usd
            )
            + intake.prior_uncertain_cost,
            settlement_input_tokens=(
                usage[0] if usage is not None else intake.estimate.input_tokens
            ),
        )
    if intake.has_liability:
        return replace(
            result,
            force_charge=True,
            confirmed_pre_dispatch=False,
            settlement_cost_usd=intake.uncertain_cost,
            settlement_input_tokens=intake.settlement_input_tokens,
        )
    return replace(result, confirmed_pre_dispatch=not intake.possible_dispatch)


def is_retryable_status(status_code: int) -> bool:
    return status_code in RETRYABLE_STATUS_CODES


def _provider_of(settings: Any, backend_id: str) -> str:
    config = getattr(settings, "backends", {}).get(backend_id)
    return str(getattr(config, "provider", "azure_foundry") or "azure_foundry")


def _uses_translated_forwarding(settings: Any, backend_id: str) -> bool:
    return _provider_of(settings, backend_id) in {
        "google_ai_studio",
        "openai_compatible",
        "openrouter",
        "opencode_google",
        "opencode_anthropic",
        "azure_anthropic",
        "azure_mai",
    }


def _is_zen_provider(settings: Any, backend_id: str) -> bool:
    return _provider_of(settings, backend_id) == "opencode_zen"


def _google_pre_output_failover(settings: Any, backend_id: str, status: int) -> bool:
    config = settings.backends[backend_id]
    return (
        _provider_of(settings, backend_id) == "google_ai_studio"
        and not getattr(config, "credit_metered", True)
        and getattr(config, "google_pre_output_failover", False)
        and status in {500, 502, 503, 504}
    )


def _default_output_tokens(body: dict[str, Any]) -> int:
    value = body.get("max_output_tokens")
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return int(DEFAULT_MAX_OUTPUT_TOKENS)


def _build_upstream_body(
    settings: Any,
    backend_id: str,
    operation: str,
    public_body: dict[str, Any],
    *,
    prepared_media: PreparedGoogleMedia | None = None,
    seal_context: SealContext | None = None,
    prepared_continuation: PreparedContinuation | None = None,
) -> dict[str, Any]:
    backends = getattr(settings, "backends", None)
    if not isinstance(backends, dict) or backend_id not in backends:
        # Legacy test doubles without backend configs keep identity.
        return dict(public_body)
    # Fail closed: adapter errors propagate to the caller, which returns a
    # sanitized 502 without egress. Never fall back to the raw Responses body.
    provider = _provider_of(settings, backend_id)
    config = backends[backend_id]
    adapter = get_adapter(
        provider,
        google_features=getattr(config, "google_features", None),
        api_surface=getattr(config, "api_surface", "openai_compat"),
        seal_context=seal_context,
        backend_id=backend_id,
        prepared_continuation=prepared_continuation,
    )
    deployment = str(getattr(config, "deployment", "") or "")
    if not deployment:
        return dict(public_body)
    return adapter.build_upstream_body(
        operation,
        public_body,
        deployment=deployment,
        default_output_tokens=_default_output_tokens(public_body),
        **({"prepared_media": prepared_media} if prepared_media is not None else {}),
    )


def _sanitized_google_error_response(
    status_code: int, api_error: Any, provider_status: int, *, provider: str = "google_ai_studio"
) -> Any:
    adapter = get_adapter(provider)
    translated = adapter.translate_error(provider_status, None)
    return api_error(translated.status_code or status_code, translated.message, translated.code)


def _estimate_cost_for_tokens(
    settings: Any, logical_model: str, input_tokens: int, output_tokens: int
) -> float | None:
    pricing = getattr(settings, "pricing", {}) or {}
    model_pricing = pricing.get(logical_model)
    if model_pricing is None:
        return None
    try:
        input_price = float(getattr(model_pricing, "input_per_million", float("nan")))
        output_price = float(getattr(model_pricing, "output_per_million", float("nan")))
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(input_price) and math.isfinite(output_price)):
        return None
    if input_price == 0.0 and output_price == 0.0:
        return 0.0
    cost = ((input_tokens * input_price) + (output_tokens * output_price)) / 1_000_000
    return cost if (math.isfinite(cost) and cost >= 0.0) else None


def _fallback_estimate_cost(
    settings: Any,
    public_body: dict[str, Any],
    logical_model: str,
    operation: str | None = None,
) -> tuple[float | None, int | None]:
    """Return the conservative reservation estimate for the actual operation.

    The operation must be supplied by Google call sites: estimating an
    embeddings request as a Responses request would add message overhead and
    a full output-token allowance that was never reserved.
    """
    operations = (operation,) if operation is not None else ("responses", "embeddings")
    for candidate in operations:
        try:
            estimate = estimate_request_cost(
                model=logical_model,
                operation=candidate,
                body=public_body,
                pricing=getattr(settings, "pricing", {}),
                settings=settings,
            )
        except Exception:
            continue
        if estimate is not None:
            return estimate.estimated_cost_usd, estimate.input_tokens
    return None, None


async def _read_stream_bounded(stream: Any, *, limit_bytes: int) -> tuple[bytes, bool]:
    """Incrementally read decoded bytes up to a finite bound.

    Returns (body, breached). Counts decoded bytes so compressed or chunked
    bodies without Content-Length cannot bypass the limit.
    """
    collected = bytearray()
    async for chunk in stream.aiter_bytes():
        collected.extend(chunk)
        if len(collected) > limit_bytes:
            return bytes(collected), True
    return bytes(collected), False


async def _close_quietly(context: Any) -> None:
    with suppress(Exception):
        await context.__aexit__(None, None, None)


async def _set_quota_group_cooldown(
    settings: Any,
    backend_id: str,
    *,
    set_backend_cooldown: Any,
    cooldown_seconds: float,
) -> None:
    selected_config = settings.backends[backend_id]
    quota_group = getattr(selected_config, "quota_group", None) or backend_id
    for candidate_id, config in settings.backends.items():
        candidate_group = getattr(config, "quota_group", None) or candidate_id
        if candidate_group == quota_group:
            await set_backend_cooldown(
                candidate_id,
                state=BackendHealthState.QUOTA_COOLDOWN,
                cooldown_seconds=cooldown_seconds,
            )


def parse_retry_after(raw_value: str | None, max_delay_seconds: float) -> float | None:
    if raw_value is None:
        return None
    value = raw_value.strip()
    if not value:
        return None
    parsed_seconds: float | None = None
    if value.isascii() and value.isdigit():
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


def _backend_retry_delay_seconds(
    settings: Any,
    backend_id: str,
    *,
    attempt_number: int,
    retry_after_header: str | None,
) -> float:
    # Google attempts are single-shot per backend (routing owns every retry
    # with fresh quota admission), so no provider-specific sleep policy remains.
    _ = backend_id
    return retry_delay_seconds(
        attempt_number=attempt_number,
        max_delay_seconds=settings.retry_max_delay_seconds,
        retry_after_header=retry_after_header,
    )


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
    rate_limit_store: Any | None = None,
    cleanup_timeout_seconds: float = DEFAULT_CLEANUP_TIMEOUT_SECONDS,
    azure_intake: AzureIntakeRequest | None = None,
) -> Any:
    started_at = time.monotonic()
    charged_cost: float | None = (
        azure_intake.estimate.estimated_cost_usd + azure_intake.prior_uncertain_cost
        if azure_intake is not None
        else None
    )
    metric_status_code = status_code
    pending_event_bytes = b""
    discarding_event = False
    actual_input_tokens: int | None = (
        azure_intake.estimate.input_tokens if azure_intake is not None else None
    )

    def process_event_payload(payload: bytes) -> None:
        nonlocal actual_input_tokens, charged_cost
        if b"usage" not in payload:
            return
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
            if not isinstance(usage, dict) and parsed.get("type") in {
                "response.completed",
                "response.incomplete",
                "response.failed",
            }:
                response = parsed.get("response")
                if isinstance(response, dict):
                    usage = response.get("usage")
            if not isinstance(usage, dict):
                continue
            usage_response = Response(
                content=json.dumps({"usage": usage}).encode("utf-8"),
                media_type="application/json",
            )
            usage_tokens = extract_response_usage_tokens(usage_response)
            if usage_tokens is not None:
                actual_input_tokens = usage_tokens[0]
            estimated_cost = estimate_response_usage_cost(usage_response, model, pricing)
            if estimated_cost is not None:
                charged_cost = estimated_cost + (
                    azure_intake.prior_uncertain_cost if azure_intake is not None else 0
                )

    def inspect_chunk(chunk: bytes) -> None:
        nonlocal pending_event_bytes, discarding_event
        offset = 0
        while offset < len(chunk):
            piece_size = min(
                SSE_INSPECTION_PIECE_BYTES,
                MAX_SSE_EVENT_BUFFER_BYTES - len(pending_event_bytes),
                len(chunk) - offset,
            )
            pending_event_bytes += chunk[offset : offset + piece_size]
            offset += piece_size
            while True:
                event_payload, pending_event_bytes = _extract_next_sse_event(pending_event_bytes)
                if event_payload is None:
                    break
                if discarding_event:
                    discarding_event = False
                else:
                    process_event_payload(event_payload)
            if len(pending_event_bytes) == MAX_SSE_EVENT_BUFFER_BYTES:
                discarding_event = True
            if discarding_event:
                # Retain only the suffix needed to recognize a split CRLF delimiter.
                pending_event_bytes = pending_event_bytes[-3:]

    try:
        inspect_chunk(first_chunk)
        yield first_chunk
        async for chunk in chunks:
            inspect_chunk(chunk)
            yield chunk
    except httpx.HTTPError:
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=cooldown_seconds,
        )
        metric_status_code = 502
        yield b'data: {"error":{"message":"Upstream stream failed","type":"upstream_error"}}\n\n'
    finally:
        if not discarding_event and pending_event_bytes.strip():
            process_event_payload(pending_event_bytes)

        if azure_intake is not None:
            azure_intake.succeeded(
                (charged_cost if charged_cost is not None else azure_intake.uncertain_cost)
                - azure_intake.prior_uncertain_cost,
                actual_input_tokens
                if actual_input_tokens is not None
                else azure_intake.estimate.input_tokens,
            )

        async def settle_credit() -> None:
            try:
                await credit_store.finalize_request(
                    request_id,
                    backend_id=backend_id,
                    # This generator owns a stream after meaningful output, never a free rejection.
                    charge_reserved=True,
                    charged_cost_usd=charged_cost,
                )
            except TypeError as exc:
                if "backend_id" in str(exc):
                    await credit_store.finalize_request(
                        request_id,
                        charge_reserved=True,
                        charged_cost_usd=charged_cost,
                    )
                else:
                    raise

            if azure_intake is not None:
                azure_intake.financially_finalized()

        async def settle_quota() -> None:
            if rate_limit_store is not None:
                await rate_limit_store.finalize_request(
                    request_id, actual_input_tokens=actual_input_tokens
                )

        await protected_cleanup(
            [
                settle_credit,
                settle_quota,
                lambda: metrics_store.observe_request(
                    model=model,
                    backend=backend_id,
                    status_code=metric_status_code,
                    latency_seconds=max(0.0, time.monotonic() - started_at),
                    estimated_cost_usd=charged_cost,
                ),
                lambda: context.__aexit__(None, None, None),
            ],
            timeout_seconds=cleanup_timeout_seconds,
        )


class _PreparedUpstreamCloseError(Exception):
    """Failed close is terminal delivery cleanup, never a new upload trigger."""


class _PreparedTranslatedUpstreamOwner:
    """Retain one exact close task until both stream and context closure are proved."""

    def __init__(self, context: Any) -> None:
        self.context = context
        self.response: Any = None
        self.entered = False
        self.stream_closed = False
        self.context_closed = False
        self.closed = False
        self._task: asyncio.Task[None] | None = None

    async def _close(self) -> None:
        if self.response is not None and not self.stream_closed:
            # HTTPX marks Response.is_closed before awaiting its stream. A failed
            # Response.aclose can then become a no-op, so retry the actual stream.
            await self.response.stream.aclose()
            self.stream_closed = True
        if self.entered and not self.context_closed:
            await self.context.__aexit__(None, None, None)
            self.context_closed = True
        self.closed = True

    @staticmethod
    def _observe(task: asyncio.Task[None]) -> None:
        if not task.cancelled():
            task.exception()

    async def _join(self) -> None:
        assert self._task is not None
        await asyncio.shield(self._task)

    async def close(self) -> None:
        if self.closed:
            return
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._close())
            self._task.add_done_callback(self._observe)
        # Timed-out joins do not cancel or replace the producer close task. The
        # intake lease keeps its capacity and callback until that task finishes.
        await protected_cleanup([self._join], timeout_seconds=DEFAULT_CLEANUP_TIMEOUT_SECONDS)


async def _forward_prepared_translated(
    *,
    settings: Any,
    backend_id: str,
    operation: str,
    headers: dict[str, str],
    backend_client: Any,
    azure_intake: AzureIntakeRequest,
    set_backend_active: Any,
    set_backend_cooldown: Any,
    sleep: Any,
    api_error: Any,
    deadline: float,
    output_lease: OutputInspectionLease | None,
) -> BackendRequestResult:
    context = azure_intake.response_context(backend_id)
    provider = settings.backends[backend_id].provider
    adapter = get_adapter(provider)
    assert azure_intake.prepared is not None
    model = azure_intake.prepared.model
    for attempt in range(1, max(1, settings.retry_attempts) + 1):
        if attempt > 1 and azure_intake.quota is not None:  # noqa: SIM102 -- admission precedes dispatch
            if not await azure_intake.quota.retry(deadline):
                return _prepared_result(
                    azure_intake,
                    BackendRequestResult(
                        response=api_error(
                            429, "Retry quota capacity is unavailable", "rate_limit_exhausted"
                        ),
                        retryable_failure=False,
                    ),
                )
        retry_after_header = None
        upstream_context = backend_client.stream_backend(
            backend_id,
            operation,
            headers=headers,
            azure_intake=azure_intake,
        )
        owner = _PreparedTranslatedUpstreamOwner(upstream_context)
        close_upstream = owner.close
        azure_intake.lease.delivery_cleanup = close_upstream
        try:
            try:
                async with asyncio.timeout_at(deadline):
                    upstream = await upstream_context.__aenter__()
                    owner.response = upstream
                    owner.entered = True
                    outcome = await _read_google_non_streaming_body(
                        upstream,
                        limit_bytes=MAX_GOOGLE_RESPONSE_BYTES,
                        error_limit_bytes=MAX_UPSTREAM_ERROR_BYTES,
                    )
                    if outcome["read_failed"]:
                        raise httpx.ReadError("Unable to read prepared translated response")
                    if outcome["breached"]:
                        return _prepared_result(
                            azure_intake,
                            BackendRequestResult(
                                response=api_error(
                                    502, "Backend response exceeded size limits", "upstream_error"
                                ),
                                retryable_failure=False,
                            ),
                        )
                    if HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT:
                        # Retain successful-upload liability before context exit or any later await.
                        azure_intake.succeeded(
                            azure_intake.estimate.estimated_cost_usd,
                            azure_intake.estimate.input_tokens,
                        )
                        try:
                            payload = load_bounded_json(
                                outcome["body"].decode(), max_bytes=MAX_GOOGLE_RESPONSE_BYTES
                            )
                            input_tokens, output_tokens = adapter.extract_usage(operation, payload)
                            if input_tokens is not None and output_tokens is not None:
                                price = azure_intake.policy.document.models[model].price
                                assert price is not None
                                azure_intake.succeeded(
                                    (
                                        input_tokens * price.input_per_million
                                        + output_tokens * price.output_per_million
                                    )
                                    / 1_000_000,
                                    input_tokens,
                                )
                            if provider == "azure_mai":
                                if output_lease is None:
                                    raise ValueError("Prepared MAI inspection lease required")  # noqa: TRY301 -- bounded local rejection
                                output_lease.bind_delivery_deadline(deadline)
                                translated = await translate_mai_image_output(
                                    payload,
                                    prepared_context=context,
                                    backend_id=backend_id,
                                    logical_model=model,
                                    lease=output_lease,
                                    deadline=deadline,
                                )
                            else:
                                context.for_backend(backend_id, provider)
                                translated = adapter.translate_success(
                                    operation,
                                    payload,
                                    logical_model=model,
                                    metadata=context.metadata_dict(),
                                )
                        except (ValueError, UnicodeDecodeError, OSError):
                            return _prepared_result(
                                azure_intake,
                                BackendRequestResult(
                                    response=api_error(
                                        502,
                                        "Backend response could not be completed",
                                        "upstream_error",
                                    ),
                                    retryable_failure=False,
                                ),
                            )
                        result = _prepared_result(
                            azure_intake,
                            BackendRequestResult(
                                response=Response(
                                    content=json.dumps(translated.body).encode(),
                                    status_code=200,
                                    media_type="application/json",
                                ),
                                retryable_failure=False,
                            ),
                        )
                        await set_backend_active(backend_id)
                        return result
                    if upstream.status_code >= 500:
                        # A complete 5xx reply does not prove that generation was
                        # unbilled; each uploaded attempt retains its estimate.
                        azure_intake.uncertain()
                    else:
                        azure_intake.completed()
                    status = upstream.status_code
                    retry_after_header = upstream.headers.get("retry-after")
            finally:
                body_cancelled = isinstance(sys.exception(), asyncio.CancelledError)
                try:
                    await close_upstream()
                except (Exception, asyncio.CancelledError) as close_error:
                    azure_intake.lease.resources.uncertain.add(azure_intake.lease)
                    _logger.warning(
                        "azure_prepared_upstream_close_unconfirmed",
                        error_type=type(close_error).__name__,
                    )
                    caller = asyncio.current_task()
                    caller_cancelled = caller is not None and caller.cancelling() > 0
                    if (
                        body_cancelled
                        or caller_cancelled
                        or isinstance(close_error, asyncio.CancelledError)
                    ):
                        raise asyncio.CancelledError() from close_error
                    raise _PreparedUpstreamCloseError() from close_error
                else:
                    if azure_intake.lease.delivery_cleanup is close_upstream:
                        azure_intake.lease.delivery_cleanup = None
        except _PreparedUpstreamCloseError:
            return _prepared_result(
                azure_intake,
                BackendRequestResult(
                    response=api_error(
                        502, "Backend response cleanup could not be confirmed", "upstream_error"
                    ),
                    retryable_failure=False,
                ),
            )
        except (httpx.TransportError, TimeoutError):
            azure_intake.uncertain()
            status = 502
        except asyncio.CancelledError:
            azure_intake.uncertain()
            raise
        if not is_retryable_status(status):
            error = adapter.translate_error(status, None)
            return _prepared_result(
                azure_intake,
                BackendRequestResult(
                    response=api_error(error.status_code, error.message, error.code),
                    retryable_failure=False,
                ),
            )
        retry_after_seconds = parse_retry_after(
            retry_after_header, settings.retry_max_delay_seconds
        )
        cooldown_seconds = (
            settings.retry_max_delay_seconds if retry_after_seconds is None else retry_after_seconds
        )
        if status == 429:
            await _set_quota_group_cooldown(
                settings,
                backend_id,
                set_backend_cooldown=set_backend_cooldown,
                cooldown_seconds=cooldown_seconds,
            )
        else:
            await set_backend_cooldown(
                backend_id,
                state=BackendHealthState.ERROR_COOLDOWN,
                cooldown_seconds=cooldown_seconds,
            )
        if attempt < max(1, settings.retry_attempts):
            delay = _backend_retry_delay_seconds(
                settings, backend_id, attempt_number=attempt, retry_after_header=retry_after_header
            )
            if delay > 0:
                await sleep(delay)
    error = adapter.translate_error(status, None)
    return _prepared_result(
        azure_intake,
        BackendRequestResult(
            response=api_error(error.status_code, error.message, error.code),
            retryable_failure=True,
        ),
    )


async def forward_non_streaming_with_retries(
    *,
    settings: Any,
    backend_id: str,
    operation: str,
    headers: dict[str, str],
    body: dict[str, Any] | None,
    get_backend_client: Any,
    set_backend_active: Any,
    set_backend_cooldown: Any,
    sleep: Any,
    api_error: Any,
    reservation_deadline_monotonic: float | None = None,
    azure_intake: AzureIntakeRequest | None = None,
    prepared_media: PreparedGoogleMedia | None = None,
    seal_context: SealContext | None = None,
    prepared_continuation: PreparedContinuation | None = None,
    output_lease: OutputInspectionLease | None = None,
) -> BackendRequestResult:
    max_attempts = max(1, settings.retry_attempts)
    backend_client = get_backend_client()
    try:
        if azure_intake is not None:
            assert azure_intake.prepared is not None
            azure_intake.validate(settings, azure_intake.prepared.model, operation)
            await azure_intake.encode(
                backend_id,
                reservation_deadline_monotonic
                or time.monotonic() + settings.reservation_max_age_seconds,
            )
            upstream_body = None
        else:
            assert body is not None
            build = partial(
                _build_upstream_body,
                settings,
                backend_id,
                operation,
                body,
                prepared_media=prepared_media,
                seal_context=seal_context,
                prepared_continuation=prepared_continuation,
            )
            upstream_body = (
                build()
                if seal_context is None
                else await bounded_signed_work(
                    build,
                    lease=seal_context.work_lease,
                    deadline=reservation_deadline_monotonic
                    or time.monotonic() + settings.reservation_max_age_seconds,
                )
            )
    except AzureIntakeError as exc:
        return _prepared_result(
            azure_intake,
            BackendRequestResult(
                response=api_error(exc.status, "Backend preparation failed", exc.code),
                retryable_failure=False,
                confirmed_pre_dispatch=True,
            ),
        )
    except SignedIntakeError as exc:
        return _prepared_result(
            azure_intake,
            BackendRequestResult(
                response=api_error(exc.status, str(exc), exc.code),
                retryable_failure=False,
                confirmed_pre_dispatch=True,
            ),
        )
    except Exception:
        return _prepared_result(
            azure_intake,
            BackendRequestResult(
                response=api_error(502, "Unable to prepare the backend request", "upstream_error"),
                retryable_failure=False,
            ),
        )
    if azure_intake is not None and _provider_of(settings, backend_id) in {
        "azure_anthropic",
        "azure_mai",
    }:
        return await _forward_prepared_translated(
            settings=settings,
            backend_id=backend_id,
            operation=operation,
            headers=headers,
            backend_client=backend_client,
            azure_intake=azure_intake,
            set_backend_active=set_backend_active,
            set_backend_cooldown=set_backend_cooldown,
            sleep=sleep,
            api_error=api_error,
            output_lease=output_lease,
            deadline=reservation_deadline_monotonic
            or time.monotonic() + settings.reservation_max_age_seconds,
        )
    if azure_intake is None and _uses_translated_forwarding(settings, backend_id):
        assert body is not None and upstream_body is not None
        return await _forward_google_non_streaming(
            output_lease=output_lease,
            seal_context=seal_context,
            prepared_continuation=prepared_continuation,
            settings=settings,
            backend_id=backend_id,
            operation=operation,
            headers=headers,
            public_body=body,
            upstream_body=upstream_body,
            backend_client=backend_client,
            set_backend_active=set_backend_active,
            set_backend_cooldown=set_backend_cooldown,
            api_error=api_error,
            reservation_deadline_monotonic=reservation_deadline_monotonic,
        )
    if azure_intake is None and _is_zen_provider(settings, backend_id):
        assert body is not None and upstream_body is not None
        return await _forward_zen_non_streaming(
            settings=settings,
            backend_id=backend_id,
            operation=operation,
            headers=headers,
            public_body=body,
            upstream_body=upstream_body,
            backend_client=backend_client,
            set_backend_active=set_backend_active,
            set_backend_cooldown=set_backend_cooldown,
            api_error=api_error,
            reservation_deadline_monotonic=reservation_deadline_monotonic,
        )

    for attempt in range(1, max_attempts + 1):
        if azure_intake is not None and attempt > 1 and azure_intake.quota is not None:  # noqa: SIM102 -- admit before dispatch
            if not await azure_intake.quota.retry(
                reservation_deadline_monotonic
                or time.monotonic() + settings.reservation_max_age_seconds
            ):
                return _prepared_result(
                    azure_intake,
                    BackendRequestResult(
                        response=api_error(
                            429, "Retry quota capacity is unavailable", "rate_limit_exhausted"
                        ),
                        retryable_failure=False,
                    ),
                )
        try:
            upstream = await backend_client.request_backend(
                backend_id,
                operation,
                headers=headers,
                **(
                    {"azure_intake": azure_intake}
                    if azure_intake is not None
                    else {"json": upstream_body}
                ),
            )
        except httpx.TransportError:
            if azure_intake is not None:
                azure_intake.uncertain()
            await set_backend_cooldown(
                backend_id,
                state=BackendHealthState.ERROR_COOLDOWN,
                cooldown_seconds=settings.retry_max_delay_seconds,
            )
            if attempt < max_attempts:
                delay_seconds = _backend_retry_delay_seconds(
                    settings,
                    backend_id,
                    attempt_number=attempt,
                    retry_after_header=None,
                )
                if delay_seconds > 0:
                    await sleep(delay_seconds)
                continue
            return _prepared_result(
                azure_intake,
                BackendRequestResult(
                    response=api_error(
                        502,
                        "Unable to contact the configured backend",
                        "upstream_error",
                    ),
                    retryable_failure=True,
                ),
            )
        except httpx.HTTPError:
            if azure_intake is not None:
                azure_intake.uncertain()
            return _prepared_result(
                azure_intake,
                BackendRequestResult(
                    response=api_error(
                        502,
                        "Unable to contact the configured backend",
                        "upstream_error",
                    ),
                    retryable_failure=False,
                ),
            )

        if azure_intake is not None and not HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT:
            azure_intake.completed()
        forwarded_body = (
            upstream.content
            if HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT
            else upstream.content[:MAX_UPSTREAM_ERROR_BYTES]
        )
        candidate_response = upstream_response(upstream, forwarded_body)
        if HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT:
            result = _prepared_result(
                azure_intake,
                BackendRequestResult(response=candidate_response, retryable_failure=False),
            )
            await set_backend_active(backend_id)
            return result
        if not is_retryable_status(upstream.status_code):
            return _prepared_result(
                azure_intake,
                BackendRequestResult(response=candidate_response, retryable_failure=False),
            )

        cooldown_state = (
            BackendHealthState.QUOTA_COOLDOWN
            if upstream.status_code == HTTP_TOO_MANY_REQUESTS
            else BackendHealthState.ERROR_COOLDOWN
        )
        retry_after_seconds = parse_retry_after(
            upstream.headers.get("retry-after"),
            settings.retry_max_delay_seconds,
        )
        cooldown_seconds = (
            settings.retry_max_delay_seconds if retry_after_seconds is None else retry_after_seconds
        )
        if cooldown_state == BackendHealthState.QUOTA_COOLDOWN:
            await _set_quota_group_cooldown(
                settings,
                backend_id,
                set_backend_cooldown=set_backend_cooldown,
                cooldown_seconds=cooldown_seconds,
            )
        else:
            await set_backend_cooldown(
                backend_id,
                state=cooldown_state,
                cooldown_seconds=cooldown_seconds,
            )
        if attempt < max_attempts:
            delay_seconds = _backend_retry_delay_seconds(
                settings,
                backend_id,
                attempt_number=attempt,
                retry_after_header=upstream.headers.get("retry-after"),
            )
            if delay_seconds > 0:
                await sleep(delay_seconds)
            continue
        return _prepared_result(
            azure_intake, BackendRequestResult(response=candidate_response, retryable_failure=True)
        )

    return _prepared_result(
        azure_intake,
        BackendRequestResult(
            response=api_error(502, "Unable to contact the configured backend", "upstream_error"),
            retryable_failure=True,
        ),
    )


async def _shielded_google_cancel_cleanup(
    context: Any | None, *, settings: Any, backend_id: str, set_backend_cooldown: Any
) -> None:
    """Bounded connection cleanup that survives repeated caller cancellation.

    Close and cooldown run concurrently with independent timeouts. Repeated
    cancellations cannot detach cleanup or prevent the billable result from
    reaching settlement.
    """
    operations = [
        lambda: set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=settings.retry_max_delay_seconds,
        )
    ]
    if context is not None:
        operations.append(lambda: context.__aexit__(None, None, None))
    # protected_cleanup finishes each operation (or bounds its timeout) before
    # propagating cancellation/failure. Preserve the billable result regardless.
    with suppress(Exception, asyncio.CancelledError):
        await protected_cleanup(operations)


class DeadlineStreamingResponse(StreamingResponse):
    """Enforce the reservation deadline around ASGI delivery, including send."""

    def __init__(
        self,
        content: Any,
        *,
        deadline: float,
        cleanup: Any,
        always_cleanup: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(content, **kwargs)
        self.deadline = deadline
        self.cleanup = cleanup
        self.always_cleanup = always_cleanup
        self._close_task: asyncio.Task[None] | None = None
        self.iterator_started = False
        self.original_iterator: Any = content

        async def iterate() -> Any:
            self.iterator_started = True
            async for chunk in self.original_iterator:
                yield chunk

        self.body_iterator = iterate()

    async def stream_response(self, send: Any) -> None:
        try:
            async with asyncio.timeout_at(self.deadline):
                await super().stream_response(send)
        finally:
            await self.close_stream()

    async def _close_stream(self) -> None:
        failure: BaseException | None = None
        try:
            await protected_cleanup([self.original_iterator.aclose])
        except BaseException as exc:
            failure = exc
        if self.always_cleanup or not self.iterator_started:
            await protected_cleanup([self.cleanup])
        elif failure is not None:
            raise failure

    async def close_stream(self) -> None:
        if self._close_task is None or (
            self._close_task.done()
            and (self._close_task.cancelled() or self._close_task.exception() is not None)
        ):
            self._close_task = asyncio.create_task(self._close_stream())
        cancelled = False
        while not self._close_task.done():
            try:
                await asyncio.shield(self._close_task)
            except asyncio.CancelledError:
                cancelled = True
        self._close_task.result()
        if cancelled:
            raise asyncio.CancelledError()


@dataclass
class GoogleAttemptSettlement:
    """Retained settlement facts across every post-dispatch await."""

    cost: float | None
    input_tokens: int | None
    dispatched: bool = False
    context: Any = None
    decoder: Any = None
    retain_full_cost: bool = False

    def capture_stream_usage(self, settings: Any, model: str) -> None:
        if self.decoder is None:
            return
        if getattr(self.decoder, "usage_invalid", False):
            self.cost = None
            self.input_tokens = None
            return
        input_tokens, output_tokens = self.decoder.usage
        if input_tokens is not None:
            self.input_tokens = input_tokens
        if (
            getattr(self.decoder, "prefetch_finished", False) is True
            and input_tokens is not None
            and output_tokens is not None
        ):
            cost = _estimate_cost_for_tokens(settings, model, input_tokens, output_tokens)
            if cost is not None:
                self.cost = cost

    def capture_usage(
        self, raw_body: bytes, settings: Any, model: str, operation: str, adapter: Any
    ) -> None:
        try:
            payload = load_bounded_json(raw_body.decode(), max_bytes=MAX_GOOGLE_RESPONSE_BYTES)
        except (ValueError, UnicodeDecodeError):
            return
        input_tokens, output_tokens = adapter.extract_usage(operation, payload)
        if input_tokens is None or output_tokens is None:
            return
        self.input_tokens = input_tokens
        if not self.retain_full_cost:
            self.cost = _estimate_cost_for_tokens(settings, model, input_tokens, output_tokens)


async def _forward_google_non_streaming(
    *,
    settings: Any,
    backend_id: str,
    operation: str,
    headers: dict[str, str],
    public_body: dict[str, Any],
    upstream_body: dict[str, Any],
    backend_client: Any,
    set_backend_active: Any,
    set_backend_cooldown: Any,
    api_error: Any,
    reservation_deadline_monotonic: float | None = None,
    seal_context: SealContext | None = None,
    prepared_continuation: PreparedContinuation | None = None,
    output_lease: OutputInspectionLease | None = None,
) -> BackendRequestResult:
    model = str(public_body.get("model", ""))
    cost, input_tokens = _fallback_estimate_cost(settings, public_body, model, operation)
    image = image_output_request(public_body)
    audio = audio_output_request(public_body)
    if (image or audio) and (output_lease is None or cost is None):
        return BackendRequestResult(
            response=api_error(503, "Generated output is unavailable", "upstream_error"),
            retryable_failure=False,
            confirmed_pre_dispatch=True,
        )
    settlement = GoogleAttemptSettlement(cost, input_tokens, retain_full_cost=image or audio)
    try:
        return await _google_non_streaming_attempt(
            output_lease=output_lease,
            seal_context=seal_context,
            prepared_continuation=prepared_continuation,
            settings=settings,
            backend_id=backend_id,
            operation=operation,
            headers=headers,
            public_body=public_body,
            upstream_body=upstream_body,
            backend_client=backend_client,
            set_backend_active=set_backend_active,
            set_backend_cooldown=set_backend_cooldown,
            api_error=api_error,
            reservation_deadline_monotonic=reservation_deadline_monotonic,
            settlement=settlement,
        )
    except asyncio.CancelledError:
        if settlement.dispatched:
            await _shielded_google_cancel_cleanup(
                settlement.context,
                settings=settings,
                backend_id=backend_id,
                set_backend_cooldown=set_backend_cooldown,
            )
        return BackendRequestResult(
            response=api_error(502, "Backend request interrupted", "upstream_error"),
            retryable_failure=False,
            force_charge=settlement.dispatched,
            settlement_cost_usd=settlement.cost,
            settlement_input_tokens=settlement.input_tokens,
            confirmed_pre_dispatch=not settlement.dispatched,
        )


async def _google_non_streaming_attempt(
    *,
    settings: Any,
    backend_id: str,
    operation: str,
    headers: dict[str, str],
    public_body: dict[str, Any],
    upstream_body: dict[str, Any],
    backend_client: Any,
    set_backend_active: Any,
    set_backend_cooldown: Any,
    api_error: Any,
    reservation_deadline_monotonic: float | None = None,
    settlement: GoogleAttemptSettlement,
    seal_context: SealContext | None = None,
    prepared_continuation: PreparedContinuation | None = None,
    output_lease: OutputInspectionLease | None = None,
) -> BackendRequestResult:
    """Google non-streaming translation with conservative settlement.

    Single-shot per backend: every retry/failover decision is owned by routing
    with fresh quota admission, so each upstream attempt is accounted exactly
    once. Settlement table: 429 returns retryable (routing failovers with fresh
    admission); 401/403 and other 4xx are terminal without force-charge
    (provider validation rejections establish non-generation and refund via the
    standard finalizer, which retains quota estimates); ambiguous 5xx and
    transport/read/size/translation/cancellation outcomes after a possible
    dispatch are terminal with force-charge (settle known usage or the
    reservation estimate, retain quota). 5xx is never treated as proof of
    non-generation.
    """
    adapter = get_adapter(
        _provider_of(settings, backend_id),
        google_features=settings.backends[backend_id].google_features,
        api_surface=settings.backends[backend_id].api_surface,
        seal_context=seal_context,
        backend_id=backend_id,
        prepared_continuation=prepared_continuation,
    )
    logical_model = str(public_body.get("model", ""))
    fallback_cost, fallback_input = _fallback_estimate_cost(
        settings, public_body, logical_model, operation
    )
    if reservation_deadline_monotonic is None:
        reservation_age = float(getattr(settings, "reservation_max_age_seconds", 900.0))
        reservation_deadline_monotonic = time.monotonic() + max(
            1.0, reservation_age - float(DEFAULT_CLEANUP_TIMEOUT_SECONDS)
        )
    if time.monotonic() >= reservation_deadline_monotonic:
        # Confirmed pre-dispatch: this backend was never contacted, so its
        # reservation is released rather than charged.
        return BackendRequestResult(
            response=api_error(502, "Backend request exceeded its deadline", "upstream_error"),
            retryable_failure=False,
            confirmed_pre_dispatch=True,
        )
    if not hasattr(backend_client, "stream_backend"):
        if output_lease is not None:
            return BackendRequestResult(
                response=api_error(
                    503, "Generated output requires bounded transport", "upstream_error"
                ),
                retryable_failure=False,
                confirmed_pre_dispatch=True,
            )
        # Legacy test doubles expose only request_backend; apply bounded
        # post-read checks instead of incremental streaming reads.
        return await _forward_google_non_streaming_buffered(
            seal_context=seal_context,
            prepared_continuation=prepared_continuation,
            settings=settings,
            backend_id=backend_id,
            operation=operation,
            headers=headers,
            public_body=public_body,
            upstream_body=upstream_body,
            backend_client=backend_client,
            set_backend_active=set_backend_active,
            set_backend_cooldown=set_backend_cooldown,
            api_error=api_error,
            reservation_deadline_monotonic=reservation_deadline_monotonic,
            settlement=settlement,
        )

    if seal_context is not None:
        try:
            seal_context.validate_dispatch(settings, backend_client, backend_id, logical_model)
        except ValueError:
            return BackendRequestResult(
                response=api_error(
                    503, "Provider state is unavailable", "provider_state_unavailable"
                ),
                retryable_failure=False,
                confirmed_pre_dispatch=True,
            )
    context = backend_client.stream_backend(
        backend_id,
        operation,
        headers=headers,
        json=upstream_body,
        **(
            {"native_generation_stream": False}
            if settings.backends[backend_id].api_surface == "native"
            else {}
        ),
    )
    settlement.context = context
    settlement.dispatched = True
    try:
        entered = await _enter_google_stream(
            context,
            settings=settings,
            backend_id=backend_id,
            set_backend_cooldown=set_backend_cooldown,
            api_error=api_error,
            fallback_cost=fallback_cost,
            fallback_input=fallback_input,
        )
    except asyncio.CancelledError:
        await _shielded_google_cancel_cleanup(
            context,
            settings=settings,
            backend_id=backend_id,
            set_backend_cooldown=set_backend_cooldown,
        )
        return BackendRequestResult(
            response=api_error(502, "Unable to contact the configured backend", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )
    if isinstance(entered, BackendRequestResult):
        return entered
    upstream = entered
    remaining = reservation_deadline_monotonic - time.monotonic()
    if remaining <= 0:
        # The connection was established but the reservation expired before
        # the body could be read: dispatch is possible, so settle conservatively.
        await _close_quietly(context)
        return BackendRequestResult(
            response=api_error(502, "Backend request exceeded its deadline", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )
    try:
        async with asyncio.timeout(remaining):
            outcome = await _read_google_non_streaming_body(
                upstream,
                limit_bytes=MAX_AUDIO_RESPONSE_BYTES
                if audio_output_request(public_body)
                else MAX_GOOGLE_RESPONSE_BYTES,
                error_limit_bytes=MAX_UPSTREAM_ERROR_BYTES,
            )
    except (TimeoutError, asyncio.CancelledError):
        await _shielded_google_cancel_cleanup(
            context,
            settings=settings,
            backend_id=backend_id,
            set_backend_cooldown=set_backend_cooldown,
        )
        return BackendRequestResult(
            response=api_error(502, "Unable to read the backend response", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )
    if outcome["read_failed"]:
        await _close_quietly(context)
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=settings.retry_max_delay_seconds,
        )
        return BackendRequestResult(
            response=api_error(502, "Unable to read the backend response", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )
    raw_body = outcome["body"]
    breached = outcome["breached"]
    if not breached and HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT:
        settlement.capture_usage(raw_body, settings, logical_model, operation, adapter)
    await _close_quietly(context)
    if breached:
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=settings.retry_max_delay_seconds,
        )
        return BackendRequestResult(
            response=api_error(502, "Backend response exceeded size limits", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )
    if not (HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT):
        return await _handle_google_error_status(
            upstream,
            settings=settings,
            backend_id=backend_id,
            set_backend_cooldown=set_backend_cooldown,
            api_error=api_error,
            fallback_cost=fallback_cost,
            fallback_input=fallback_input,
        )
    translate = partial(
        _translate_google_success,
        raw_body,
        adapter=adapter,
        operation=operation,
        logical_model=logical_model,
        settings=settings,
        api_error=api_error,
        public_body=public_body,
    )
    try:
        if output_lease is not None:
            output_lease.bind_delivery_deadline(reservation_deadline_monotonic)
            payload = load_bounded_json(raw_body.decode(), max_bytes=MAX_GOOGLE_RESPONSE_BYTES)
            async with asyncio.timeout_at(reservation_deadline_monotonic):
                if audio_output_request(public_body):
                    generated_body = adapter.translate_success(
                        operation,
                        payload,
                        logical_model=logical_model,
                        request_body=public_body,
                        metadata=public_body.get("metadata"),
                    )
                elif _provider_of(settings, backend_id) == "azure_mai":
                    generated_body = await translate_mai_image_output(
                        payload,
                        request_body=public_body,
                        logical_model=logical_model,
                        lease=output_lease,
                        deadline=reservation_deadline_monotonic,
                    )
                else:
                    generated_body = await translate_image_output(
                        payload,
                        adapter=adapter,
                        request_body=public_body,
                        logical_model=logical_model,
                        lease=output_lease,
                        deadline=reservation_deadline_monotonic,
                    )
            translated = (generated_body, settlement.cost, settlement.input_tokens)
        else:
            translated = (
                translate()
                if seal_context is None
                else await bounded_signed_work(
                    translate,
                    lease=seal_context.work_lease,
                    deadline=reservation_deadline_monotonic
                    or time.monotonic() + settings.reservation_max_age_seconds,
                )
            )
    except (SignedIntakeError, TimeoutError, ValueError, UnicodeDecodeError, OSError):
        return BackendRequestResult(
            response=api_error(502, "Backend response could not be completed", "upstream_error"),
            retryable_failure=False,
            force_charge=True,
            settlement_cost_usd=settlement.cost,
            settlement_input_tokens=settlement.input_tokens,
        )
    if isinstance(translated, BackendRequestResult):
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=settings.retry_max_delay_seconds,
        )
        return translated
    translated_body, known_cost, known_input = translated
    _ = known_cost
    _ = known_input
    await set_backend_active(backend_id)
    body_bytes = json.dumps(translated_body.body).encode("utf-8")
    headers_out: dict[str, str] = {}
    with suppress(Exception):
        headers_out = {
            name: value
            for name, value in upstream.headers.items()
            if name.lower() in SAFE_UPSTREAM_RESPONSE_HEADERS
        }
    return BackendRequestResult(
        response=Response(
            content=body_bytes,
            status_code=200,
            media_type="application/json",
            headers=headers_out,
        ),
        retryable_failure=False,
        settlement_cost_usd=settlement.cost if settlement.retain_full_cost else None,
        settlement_input_tokens=settlement.input_tokens if settlement.retain_full_cost else None,
        force_charge=settlement.retain_full_cost,
    )


async def _forward_google_non_streaming_buffered(
    *,
    settings: Any,
    backend_id: str,
    operation: str,
    headers: dict[str, str],
    public_body: dict[str, Any],
    upstream_body: dict[str, Any],
    backend_client: Any,
    set_backend_active: Any,
    set_backend_cooldown: Any,
    api_error: Any,
    reservation_deadline_monotonic: float | None = None,
    settlement: GoogleAttemptSettlement,
    seal_context: SealContext | None = None,
    prepared_continuation: PreparedContinuation | None = None,
) -> BackendRequestResult:
    """Buffered fallback for doubles without streaming transport (tests only).

    Single-shot like the streaming-transport path: routing owns every retry
    with fresh quota admission.
    """
    adapter = get_adapter(
        _provider_of(settings, backend_id),
        google_features=settings.backends[backend_id].google_features,
        api_surface=settings.backends[backend_id].api_surface,
        seal_context=seal_context,
        backend_id=backend_id,
        prepared_continuation=prepared_continuation,
    )
    logical_model = str(public_body.get("model", ""))
    fallback_cost, fallback_input = _fallback_estimate_cost(
        settings, public_body, logical_model, operation
    )
    if (
        reservation_deadline_monotonic is not None
        and time.monotonic() >= reservation_deadline_monotonic
    ):
        # Confirmed pre-dispatch: never contacted; release, don't charge.
        return BackendRequestResult(
            response=api_error(502, "Backend request exceeded its deadline", "upstream_error"),
            retryable_failure=False,
            confirmed_pre_dispatch=True,
        )

    def _cancelled_result() -> BackendRequestResult:
        return BackendRequestResult(
            response=api_error(502, "Unable to contact the configured backend", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )

    if seal_context is not None:
        try:
            seal_context.validate_dispatch(settings, backend_client, backend_id, logical_model)
        except ValueError:
            return BackendRequestResult(
                response=api_error(
                    503, "Provider state is unavailable", "provider_state_unavailable"
                ),
                retryable_failure=False,
                confirmed_pre_dispatch=True,
            )
    settlement.dispatched = True
    try:
        upstream = await backend_client.request_backend(
            backend_id, operation, headers=headers, json=upstream_body
        )
    except httpx.TransportError:
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=settings.retry_max_delay_seconds,
        )
        return BackendRequestResult(
            response=api_error(502, "Unable to contact the configured backend", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )
    except httpx.HTTPError:
        return BackendRequestResult(
            response=api_error(502, "Unable to contact the configured backend", "upstream_error"),
            retryable_failure=False,
        )
    except asyncio.CancelledError:
        await _shielded_google_cancel_cleanup(
            None,
            settings=settings,
            backend_id=backend_id,
            set_backend_cooldown=set_backend_cooldown,
        )
        return _cancelled_result()
    limit = (
        MAX_GOOGLE_RESPONSE_BYTES
        if HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT
        else MAX_UPSTREAM_ERROR_BYTES
    )
    raw_body = upstream.content if hasattr(upstream, "content") else b""
    if len(raw_body) <= limit and HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT:
        settlement.capture_usage(raw_body, settings, logical_model, operation, adapter)
    if len(raw_body) > limit:
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=settings.retry_max_delay_seconds,
        )
        return BackendRequestResult(
            response=api_error(502, "Backend response exceeded size limits", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )
    if not (HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT):
        return await _handle_google_error_status(
            upstream,
            settings=settings,
            backend_id=backend_id,
            set_backend_cooldown=set_backend_cooldown,
            api_error=api_error,
            fallback_cost=fallback_cost,
            fallback_input=fallback_input,
        )
    translate = partial(
        _translate_google_success,
        raw_body,
        adapter=adapter,
        operation=operation,
        logical_model=logical_model,
        settings=settings,
        api_error=api_error,
        public_body=public_body,
    )
    try:
        translated = (
            translate()
            if seal_context is None
            else await bounded_signed_work(
                translate,
                lease=seal_context.work_lease,
                deadline=reservation_deadline_monotonic
                or time.monotonic() + settings.reservation_max_age_seconds,
            )
        )
    except (SignedIntakeError, TimeoutError):
        return BackendRequestResult(
            response=api_error(502, "Backend response could not be completed", "upstream_error"),
            retryable_failure=False,
            force_charge=True,
            settlement_cost_usd=settlement.cost,
            settlement_input_tokens=settlement.input_tokens,
        )
    if isinstance(translated, BackendRequestResult):
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=settings.retry_max_delay_seconds,
        )
        return translated
    translated_body, _, _ = translated
    await set_backend_active(backend_id)
    body_bytes = json.dumps(translated_body.body).encode("utf-8")
    return BackendRequestResult(
        response=Response(content=body_bytes, status_code=200, media_type="application/json"),
        retryable_failure=False,
    )


async def _handle_zen_error_status(
    upstream: Any,
    *,
    settings: Any,
    backend_id: str,
    set_backend_cooldown: Any,
    api_error: Any,
    fallback_cost: float | None,
    fallback_input: int | None,
) -> BackendRequestResult:
    """Preserve Zen's upstream status while applying single-shot health policy."""
    _ = api_error
    status = int(upstream.status_code)
    response = upstream_response(upstream, upstream.content[:MAX_UPSTREAM_ERROR_BYTES])
    if status in GOOGLE_AUTH_STATUS_CODES:
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=settings.retry_max_delay_seconds,
        )
        return BackendRequestResult(response=response, retryable_failure=False)
    if status == HTTP_TOO_MANY_REQUESTS:
        retry_after = parse_retry_after(
            _safe_header(upstream, "retry-after"), settings.retry_max_delay_seconds
        )
        cooldown_seconds = settings.retry_max_delay_seconds if retry_after is None else retry_after
        await _set_quota_group_cooldown(
            settings,
            backend_id,
            set_backend_cooldown=set_backend_cooldown,
            cooldown_seconds=cooldown_seconds,
        )
        return BackendRequestResult(response=response, retryable_failure=True)
    if 500 <= status < 600:
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=settings.retry_max_delay_seconds,
        )
        return BackendRequestResult(
            response=response,
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )
    return BackendRequestResult(response=response, retryable_failure=False)


async def _forward_zen_non_streaming(
    *,
    settings: Any,
    backend_id: str,
    operation: str,
    headers: dict[str, str],
    public_body: dict[str, Any],
    upstream_body: dict[str, Any],
    backend_client: Any,
    set_backend_active: Any,
    set_backend_cooldown: Any,
    api_error: Any,
    reservation_deadline_monotonic: float | None = None,
) -> BackendRequestResult:
    """Zen Responses pass-through with single-shot conservative settlement.

    Wire bytes are forwarded unchanged; the attempt policy is independent of
    Azure's retry loop. Single-shot per backend regardless of
    ``retry_attempts``: only a pre-output 429 is failover-eligible (routing
    re-admits with fresh quota). Confirmed pre-dispatch failures release the
    reservation; dispatched ambiguous failures retain known usage or the full
    estimate. Missing/invalid usage settles through the standard finalizer,
    which charges the reserved estimate rather than zero.
    """
    logical_model = str(public_body.get("model", ""))
    fallback_cost, fallback_input = _fallback_estimate_cost(
        settings, public_body, logical_model, operation
    )
    if (
        reservation_deadline_monotonic is not None
        and time.monotonic() >= reservation_deadline_monotonic
    ):
        # Confirmed pre-dispatch: never contacted; release, don't charge.
        return BackendRequestResult(
            response=api_error(502, "Backend request exceeded its deadline", "upstream_error"),
            retryable_failure=False,
            confirmed_pre_dispatch=True,
        )
    try:
        upstream = await backend_client.request_backend(
            backend_id, operation, headers=headers, json=upstream_body
        )
    except httpx.TransportError:
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=settings.retry_max_delay_seconds,
        )
        return BackendRequestResult(
            response=api_error(502, "Unable to contact the configured backend", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )
    except httpx.HTTPError:
        return BackendRequestResult(
            response=api_error(502, "Unable to contact the configured backend", "upstream_error"),
            retryable_failure=False,
        )
    except asyncio.CancelledError:
        await _shielded_google_cancel_cleanup(
            None,
            settings=settings,
            backend_id=backend_id,
            set_backend_cooldown=set_backend_cooldown,
        )
        return BackendRequestResult(
            response=api_error(502, "Backend request interrupted", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )
    limit = (
        MAX_GOOGLE_RESPONSE_BYTES
        if HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT
        else MAX_UPSTREAM_ERROR_BYTES
    )
    raw_body = upstream.content if hasattr(upstream, "content") else b""
    if len(raw_body) > limit:
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=settings.retry_max_delay_seconds,
        )
        return BackendRequestResult(
            response=api_error(502, "Backend response exceeded size limits", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )
    if not (HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT):
        return await _handle_zen_error_status(
            upstream,
            settings=settings,
            backend_id=backend_id,
            set_backend_cooldown=set_backend_cooldown,
            api_error=api_error,
            fallback_cost=fallback_cost,
            fallback_input=fallback_input,
        )
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else None
    except (UnicodeDecodeError, ValueError):
        payload = None
    if not isinstance(payload, dict):
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=settings.retry_max_delay_seconds,
        )
        return BackendRequestResult(
            response=api_error(502, "Backend returned an invalid response", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )
    await set_backend_active(backend_id)
    headers_out: dict[str, str] = {}
    with suppress(Exception):
        headers_out = {
            name: value
            for name, value in upstream.headers.items()
            if name.lower() in SAFE_UPSTREAM_RESPONSE_HEADERS
        }
    return BackendRequestResult(
        response=Response(
            content=raw_body,
            status_code=200,
            media_type="application/json",
            headers=headers_out,
        ),
        retryable_failure=False,
    )


async def _enter_google_stream(
    context: Any,
    *,
    settings: Any,
    backend_id: str,
    set_backend_cooldown: Any,
    api_error: Any,
    fallback_cost: float | None,
    fallback_input: int | None,
) -> Any:
    try:
        return await context.__aenter__()
    except httpx.TransportError:
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=settings.retry_max_delay_seconds,
        )
        return BackendRequestResult(
            response=api_error(502, "Unable to contact the configured backend", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )
    except httpx.HTTPError:
        await _close_quietly(context)
        return BackendRequestResult(
            response=api_error(502, "Unable to contact the configured backend", "upstream_error"),
            retryable_failure=False,
        )
    except asyncio.CancelledError:
        # Dispatch is possible once the connection starts: shield the close
        # and preserve consumption instead of leaking and refunding.
        await _shielded_google_cancel_cleanup(
            context,
            settings=settings,
            backend_id=backend_id,
            set_backend_cooldown=set_backend_cooldown,
        )
        return BackendRequestResult(
            response=api_error(502, "Unable to contact the configured backend", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )


async def _read_google_non_streaming_body(
    upstream: Any, *, limit_bytes: int, error_limit_bytes: int
) -> dict[str, Any]:
    limit = (
        limit_bytes if HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT else error_limit_bytes
    )
    try:
        raw_body, breached = await _read_stream_bounded(upstream, limit_bytes=limit)
    except (httpx.TransportError, ValueError):
        return {"read_failed": True, "body": b"", "breached": False}
    except httpx.HTTPError:
        return {"read_failed": True, "body": b"", "breached": False, "http_failed": True}
    return {"read_failed": False, "body": raw_body, "breached": breached}


async def _handle_google_error_status(
    upstream: Any,
    *,
    settings: Any,
    backend_id: str,
    set_backend_cooldown: Any,
    api_error: Any,
    fallback_cost: float | None,
    fallback_input: int | None,
) -> BackendRequestResult:
    """Map a Google error status to a terminal result.

    Every retry/failover decision is owned by routing with fresh quota
    admission: this layer never sleeps or re-dispatches internally, so each
    upstream attempt is accounted exactly once. Unmetered Google backends may
    opt into pre-output 5xx failover; otherwise only 429 is failover-eligible;
    ambiguous 5xx failures settle the estimate (non-generation cannot be
    inferred from status alone), while auth and validation rejections refund.
    """
    if upstream.status_code in GOOGLE_AUTH_STATUS_CODES:
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=settings.retry_max_delay_seconds,
        )
        return BackendRequestResult(
            response=_sanitized_google_error_response(
                502, api_error, upstream.status_code, provider=_provider_of(settings, backend_id)
            ),
            retryable_failure=False,
        )
    if upstream.status_code == HTTP_TOO_MANY_REQUESTS:
        retry_after = _safe_header(upstream, "retry-after")
        parsed = parse_retry_after(retry_after, settings.retry_max_delay_seconds)
        cooldown_seconds = settings.retry_max_delay_seconds if parsed is None else parsed
        await _set_quota_group_cooldown(
            settings,
            backend_id,
            set_backend_cooldown=set_backend_cooldown,
            cooldown_seconds=cooldown_seconds,
        )
        return BackendRequestResult(
            response=_sanitized_google_error_response(
                429, api_error, 429, provider=_provider_of(settings, backend_id)
            ),
            retryable_failure=True,
        )
    if 500 <= upstream.status_code < 600:
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=settings.retry_max_delay_seconds,
        )
        return BackendRequestResult(
            response=_sanitized_google_error_response(
                upstream.status_code,
                api_error,
                upstream.status_code,
                provider=_provider_of(settings, backend_id),
            ),
            retryable_failure=_google_pre_output_failover(
                settings, backend_id, upstream.status_code
            ),
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )
    return BackendRequestResult(
        response=_sanitized_google_error_response(
            upstream.status_code,
            api_error,
            upstream.status_code,
            provider=_provider_of(settings, backend_id),
        ),
        retryable_failure=False,
    )


def _safe_header(upstream: Any, name: str) -> Any:
    try:
        return upstream.headers.get(name)
    except Exception:
        return None


def _translate_google_success(
    raw_body: bytes,
    *,
    adapter: Any,
    operation: str,
    logical_model: str,
    settings: Any,
    api_error: Any,
    public_body: dict[str, Any],
) -> Any:
    try:
        upstream_json = (
            load_bounded_json(raw_body.decode("utf-8"), max_bytes=MAX_GOOGLE_RESPONSE_BYTES)
            if raw_body
            else None
        )
    except (UnicodeDecodeError, ValueError):
        fallback_cost, fallback_input = _fallback_estimate_cost(
            settings, public_body, logical_model, operation
        )
        return BackendRequestResult(
            response=api_error(502, "Backend returned an invalid response", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )
    known_input, known_output = adapter.extract_usage(operation, upstream_json)
    known_cost: float | None = None
    if known_input is not None and known_output is not None:
        known_cost = _estimate_cost_for_tokens(settings, logical_model, known_input, known_output)
    expected_input_count: int | None = None
    expected_dimensions: int | None = None
    if operation == "embeddings":
        raw_input = public_body.get("input")
        if isinstance(raw_input, str):
            expected_input_count = 1
        elif isinstance(raw_input, list):
            expected_input_count = len(raw_input)
        dimensions = public_body.get("dimensions")
        if isinstance(dimensions, int) and not isinstance(dimensions, bool) and dimensions > 0:
            expected_dimensions = dimensions
    try:
        translated = adapter.translate_success(
            operation,
            upstream_json,
            logical_model=logical_model,
            expected_input_count=expected_input_count,
            expected_dimensions=expected_dimensions,
            metadata=public_body.get("metadata"),
            request_body=public_body,
        )
    except ValueError as exc:
        _log_translated_rejection(exc, operation=operation)
        fallback_cost, fallback_input = _fallback_estimate_cost(
            settings, public_body, logical_model, operation
        )
        return BackendRequestResult(
            response=api_error(502, "Backend returned an invalid response", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=known_cost if known_cost is not None else fallback_cost,
            settlement_input_tokens=known_input if known_input is not None else fallback_input,
            force_charge=True,
        )
    return (translated, known_cost, known_input)


async def forward_streaming_with_retries(
    *,
    settings: Any,
    backend_id: str,
    request_id: str,
    headers: dict[str, str],
    body: dict[str, Any] | None,
    get_backend_client: Any,
    set_backend_active: Any,
    set_backend_cooldown: Any,
    sleep: Any,
    api_error: Any,
    credit_store: Any,
    metrics_store: Any,
    rate_limit_store: Any | None = None,
    pre_output_timeout_seconds: float = PRE_OUTPUT_TIMEOUT_SECONDS,
    reservation_deadline_monotonic: float | None = None,
    azure_intake: AzureIntakeRequest | None = None,
    prepared_media: PreparedGoogleMedia | None = None,
    seal_context: SealContext | None = None,
    prepared_continuation: PreparedContinuation | None = None,
) -> BackendRequestResult:
    max_attempts = max(1, settings.retry_attempts)
    backend_client = get_backend_client()
    try:
        if azure_intake is not None:
            assert azure_intake.prepared is not None
            azure_intake.validate(settings, azure_intake.prepared.model, "responses")
            await azure_intake.encode(
                backend_id,
                reservation_deadline_monotonic
                or time.monotonic() + settings.reservation_max_age_seconds,
            )
            upstream_body = None
        else:
            assert body is not None
            build = partial(
                _build_upstream_body,
                settings,
                backend_id,
                "responses",
                body,
                prepared_media=prepared_media,
                seal_context=seal_context,
                prepared_continuation=prepared_continuation,
            )
            upstream_body = (
                build()
                if seal_context is None
                else await bounded_signed_work(
                    build,
                    lease=seal_context.work_lease,
                    deadline=reservation_deadline_monotonic
                    or time.monotonic() + settings.reservation_max_age_seconds,
                )
            )
    except AzureIntakeError as exc:
        return _prepared_result(
            azure_intake,
            BackendRequestResult(
                response=api_error(exc.status, "Backend preparation failed", exc.code),
                retryable_failure=False,
                confirmed_pre_dispatch=True,
            ),
        )
    except SignedIntakeError as exc:
        return _prepared_result(
            azure_intake,
            BackendRequestResult(
                response=api_error(exc.status, str(exc), exc.code),
                retryable_failure=False,
                confirmed_pre_dispatch=True,
            ),
        )
    except Exception:
        return _prepared_result(
            azure_intake,
            BackendRequestResult(
                response=api_error(502, "Unable to prepare the backend request", "upstream_error"),
                retryable_failure=False,
            ),
        )
    if azure_intake is None and _uses_translated_forwarding(settings, backend_id):
        assert body is not None and upstream_body is not None
        return await _forward_google_streaming(
            seal_context=seal_context,
            prepared_continuation=prepared_continuation,
            settings=settings,
            backend_id=backend_id,
            request_id=request_id,
            headers=headers,
            public_body=body,
            upstream_body=upstream_body,
            backend_client=backend_client,
            set_backend_active=set_backend_active,
            set_backend_cooldown=set_backend_cooldown,
            api_error=api_error,
            credit_store=credit_store,
            metrics_store=metrics_store,
            rate_limit_store=rate_limit_store,
            pre_output_timeout_seconds=pre_output_timeout_seconds,
            reservation_deadline_monotonic=reservation_deadline_monotonic,
        )
    if azure_intake is None and _is_zen_provider(settings, backend_id):
        assert body is not None and upstream_body is not None
        return await _forward_zen_streaming(
            settings=settings,
            backend_id=backend_id,
            request_id=request_id,
            headers=headers,
            body=body,
            upstream_body=upstream_body,
            backend_client=backend_client,
            set_backend_active=set_backend_active,
            set_backend_cooldown=set_backend_cooldown,
            api_error=api_error,
            credit_store=credit_store,
            metrics_store=metrics_store,
            rate_limit_store=rate_limit_store,
            pre_output_timeout_seconds=pre_output_timeout_seconds,
            reservation_deadline_monotonic=reservation_deadline_monotonic,
        )

    for attempt in range(1, max_attempts + 1):
        if azure_intake is not None and attempt > 1 and azure_intake.quota is not None:  # noqa: SIM102 -- admit before dispatch
            if not await azure_intake.quota.retry(
                reservation_deadline_monotonic
                or time.monotonic() + settings.reservation_max_age_seconds
            ):
                return _prepared_result(
                    azure_intake,
                    BackendRequestResult(
                        response=api_error(
                            429, "Retry quota capacity is unavailable", "rate_limit_exhausted"
                        ),
                        retryable_failure=False,
                    ),
                )
        context = backend_client.stream_backend(
            backend_id,
            "responses",
            headers=headers,
            **(
                {"azure_intake": azure_intake}
                if azure_intake is not None
                else {"json": upstream_body}
            ),
        )
        try:
            upstream = await context.__aenter__()
        except httpx.TransportError:
            if azure_intake is not None:
                azure_intake.uncertain()
            await set_backend_cooldown(
                backend_id,
                state=BackendHealthState.ERROR_COOLDOWN,
                cooldown_seconds=settings.retry_max_delay_seconds,
            )
            if attempt < max_attempts:
                delay_seconds = _backend_retry_delay_seconds(
                    settings,
                    backend_id,
                    attempt_number=attempt,
                    retry_after_header=None,
                )
                if delay_seconds > 0:
                    await sleep(delay_seconds)
                continue
            return _prepared_result(
                azure_intake,
                BackendRequestResult(
                    response=api_error(
                        502,
                        "Unable to contact the configured backend",
                        "upstream_error",
                    ),
                    retryable_failure=True,
                ),
            )
        except httpx.HTTPError:
            if azure_intake is not None:
                azure_intake.uncertain()
            return _prepared_result(
                azure_intake,
                BackendRequestResult(
                    response=api_error(
                        502,
                        "Unable to contact the configured backend",
                        "upstream_error",
                    ),
                    retryable_failure=False,
                ),
            )

        if upstream.status_code < HTTP_OK or upstream.status_code >= HTTP_SUCCESS_LIMIT:
            try:
                error_body = (await upstream.aread())[:MAX_UPSTREAM_ERROR_BYTES]
            except httpx.TransportError:
                if azure_intake is not None:
                    azure_intake.uncertain()
                await set_backend_cooldown(
                    backend_id,
                    state=BackendHealthState.ERROR_COOLDOWN,
                    cooldown_seconds=settings.retry_max_delay_seconds,
                )
                return _prepared_result(
                    azure_intake,
                    BackendRequestResult(
                        response=api_error(
                            502,
                            "Unable to read the configured backend error response",
                            "upstream_error",
                        ),
                        retryable_failure=True,
                    ),
                )
            except httpx.HTTPError:
                if azure_intake is not None:
                    azure_intake.uncertain()
                return _prepared_result(
                    azure_intake,
                    BackendRequestResult(
                        response=api_error(
                            502,
                            "Unable to read the configured backend error response",
                            "upstream_error",
                        ),
                        retryable_failure=False,
                    ),
                )
            finally:
                await context.__aexit__(None, None, None)
            if azure_intake is not None:
                azure_intake.completed()
            candidate_response = upstream_response(upstream, error_body)
            if not is_retryable_status(upstream.status_code):
                return _prepared_result(
                    azure_intake,
                    BackendRequestResult(response=candidate_response, retryable_failure=False),
                )

            cooldown_state = (
                BackendHealthState.QUOTA_COOLDOWN
                if upstream.status_code == HTTP_TOO_MANY_REQUESTS
                else BackendHealthState.ERROR_COOLDOWN
            )
            retry_after_seconds = parse_retry_after(
                upstream.headers.get("retry-after"),
                settings.retry_max_delay_seconds,
            )
            cooldown_seconds = (
                settings.retry_max_delay_seconds
                if retry_after_seconds is None
                else retry_after_seconds
            )
            if cooldown_state == BackendHealthState.QUOTA_COOLDOWN:
                await _set_quota_group_cooldown(
                    settings,
                    backend_id,
                    set_backend_cooldown=set_backend_cooldown,
                    cooldown_seconds=cooldown_seconds,
                )
            else:
                await set_backend_cooldown(
                    backend_id,
                    state=cooldown_state,
                    cooldown_seconds=cooldown_seconds,
                )
            if attempt < max_attempts:
                delay_seconds = _backend_retry_delay_seconds(
                    settings,
                    backend_id,
                    attempt_number=attempt,
                    retry_after_header=upstream.headers.get("retry-after"),
                )
                if delay_seconds > 0:
                    await sleep(delay_seconds)
                continue
            return _prepared_result(
                azure_intake,
                BackendRequestResult(response=candidate_response, retryable_failure=True),
            )

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
            if azure_intake is not None:
                azure_intake.uncertain()
            await context.__aexit__(None, None, None)
            await set_backend_cooldown(
                backend_id,
                state=BackendHealthState.ERROR_COOLDOWN,
                cooldown_seconds=settings.retry_max_delay_seconds,
            )
            if attempt < max_attempts:
                delay_seconds = _backend_retry_delay_seconds(
                    settings,
                    backend_id,
                    attempt_number=attempt,
                    retry_after_header=None,
                )
                if delay_seconds > 0:
                    await sleep(delay_seconds)
                continue
            return _prepared_result(
                azure_intake,
                BackendRequestResult(
                    response=api_error(
                        502,
                        "Unable to read the configured backend stream",
                        "upstream_error",
                    ),
                    retryable_failure=True,
                ),
            )
        except asyncio.CancelledError:
            if azure_intake is not None:
                azure_intake.uncertain()
            await protected_cleanup([partial(context.__aexit__, None, None, None)])
            raise
        except httpx.HTTPError:
            if azure_intake is not None:
                azure_intake.uncertain()
            await context.__aexit__(None, None, None)
            return _prepared_result(
                azure_intake,
                BackendRequestResult(
                    response=api_error(
                        502,
                        "Unable to read the configured backend stream",
                        "upstream_error",
                    ),
                    retryable_failure=False,
                ),
            )

        if azure_intake is not None:
            azure_intake.succeeded(
                azure_intake.estimate.estimated_cost_usd, azure_intake.estimate.input_tokens
            )
            fallback_cost = azure_intake.uncertain_cost
            fallback_input = azure_intake.settlement_input_tokens

            async def unstarted_cleanup(
                context: Any = context,
                fallback_cost: float = fallback_cost,
                fallback_input: int = fallback_input,
            ) -> None:
                cost = azure_intake.uncertain_cost if azure_intake.has_liability else fallback_cost
                input_tokens = (
                    azure_intake.settlement_input_tokens
                    if azure_intake.has_liability
                    else fallback_input
                )

                async def credit() -> None:
                    await credit_store.finalize_request(
                        request_id,
                        backend_id=backend_id,
                        charge_reserved=True,
                        charged_cost_usd=cost,
                    )
                    azure_intake.financially_finalized()

                await protected_cleanup(
                    [
                        credit,
                        partial(context.__aexit__, None, None, None),
                        *(
                            [
                                partial(
                                    rate_limit_store.finalize_request,
                                    request_id,
                                    actual_input_tokens=input_tokens,
                                )
                            ]
                            if rate_limit_store is not None
                            else []
                        ),
                    ]
                )

            assert azure_intake.prepared is not None
            iterator = stream_response(
                chunks,
                first_chunk,
                context,
                request_id=request_id,
                backend_id=backend_id,
                cooldown_seconds=settings.retry_max_delay_seconds,
                model=azure_intake.prepared.model,
                pricing=settings.pricing,
                status_code=upstream.status_code,
                set_backend_cooldown=set_backend_cooldown,
                credit_store=credit_store,
                metrics_store=metrics_store,
                rate_limit_store=rate_limit_store,
                azure_intake=azure_intake,
            )
            response = DeadlineStreamingResponse(
                iterator,
                deadline=reservation_deadline_monotonic
                or time.monotonic() + settings.reservation_max_age_seconds,
                cleanup=unstarted_cleanup,
                always_cleanup=True,
                status_code=upstream.status_code,
                media_type="text/event-stream",
                headers={"cache-control": "no-cache"},
            )
            azure_intake.lease.delivery_cleanup = response.close_stream
            try:
                await set_backend_active(backend_id)
            except BaseException:
                await response.close_stream()
                raise
            return BackendRequestResult(response=response, retryable_failure=False)
        await set_backend_active(backend_id)
        return _prepared_result(
            azure_intake,
            BackendRequestResult(
                response=StreamingResponse(
                    stream_response(
                        chunks,
                        first_chunk,
                        context,
                        request_id=request_id,
                        backend_id=backend_id,
                        cooldown_seconds=settings.retry_max_delay_seconds,
                        model=azure_intake.prepared.model
                        if azure_intake is not None and azure_intake.prepared is not None
                        else body.get("model", "")
                        if body is not None
                        else "",
                        pricing=settings.pricing,
                        status_code=upstream.status_code,
                        set_backend_cooldown=set_backend_cooldown,
                        credit_store=credit_store,
                        metrics_store=metrics_store,
                        rate_limit_store=rate_limit_store,
                        azure_intake=azure_intake,
                    ),
                    status_code=upstream.status_code,
                    media_type="text/event-stream",
                    headers={"cache-control": "no-cache"},
                ),
                retryable_failure=False,
            ),
        )

    return _prepared_result(
        azure_intake,
        BackendRequestResult(
            response=api_error(502, "Unable to contact the configured backend", "upstream_error"),
            retryable_failure=True,
        ),
    )


async def _forward_zen_streaming(
    *,
    settings: Any,
    backend_id: str,
    request_id: str,
    headers: dict[str, str],
    body: dict[str, Any],
    upstream_body: dict[str, Any],
    backend_client: Any,
    set_backend_active: Any,
    set_backend_cooldown: Any,
    api_error: Any,
    credit_store: Any,
    metrics_store: Any,
    rate_limit_store: Any | None = None,
    pre_output_timeout_seconds: float = PRE_OUTPUT_TIMEOUT_SECONDS,
    reservation_deadline_monotonic: float | None = None,
) -> BackendRequestResult:
    """Zen streaming pass-through with single-shot conservative settlement.

    One dispatch per backend regardless of ``retry_attempts``; only a
    pre-output 429 is failover-eligible. Post-output bytes stream unchanged
    through the shared bounded-usage inspector, which settles known usage or
    the reserved estimate on completion, failure, or cancellation.
    """
    logical_model = str(body.get("model", ""))
    fallback_cost, fallback_input = _fallback_estimate_cost(
        settings, body, logical_model, "responses"
    )
    if (
        reservation_deadline_monotonic is not None
        and time.monotonic() >= reservation_deadline_monotonic
    ):
        return BackendRequestResult(
            response=api_error(
                503,
                "Request deadline exceeded before backend dispatch",
                "deadline_exceeded",
            ),
            retryable_failure=False,
            confirmed_pre_dispatch=True,
        )
    context = backend_client.stream_backend(
        backend_id,
        "responses",
        headers=headers,
        json=upstream_body,
    )
    entered = await _enter_google_stream(
        context,
        settings=settings,
        backend_id=backend_id,
        set_backend_cooldown=set_backend_cooldown,
        api_error=api_error,
        fallback_cost=fallback_cost,
        fallback_input=fallback_input,
    )
    if isinstance(entered, BackendRequestResult):
        return entered
    upstream = entered
    if upstream.status_code < HTTP_OK or upstream.status_code >= HTTP_SUCCESS_LIMIT:
        try:
            error_body = (await upstream.aread())[:MAX_UPSTREAM_ERROR_BYTES]
            _ = error_body
        except httpx.TransportError:
            await context.__aexit__(None, None, None)
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
                retryable_failure=False,
                settlement_cost_usd=fallback_cost,
                settlement_input_tokens=fallback_input,
                force_charge=True,
            )
        except httpx.HTTPError:
            await context.__aexit__(None, None, None)
            return BackendRequestResult(
                response=api_error(
                    502,
                    "Unable to read the configured backend error response",
                    "upstream_error",
                ),
                retryable_failure=False,
            )
        await context.__aexit__(None, None, None)
        return await _handle_zen_error_status(
            upstream,
            settings=settings,
            backend_id=backend_id,
            set_backend_cooldown=set_backend_cooldown,
            api_error=api_error,
            fallback_cost=fallback_cost,
            fallback_input=fallback_input,
        )

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
        return BackendRequestResult(
            response=api_error(
                502,
                "Unable to read the configured backend stream",
                "upstream_error",
            ),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
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
    except asyncio.CancelledError:
        await _shielded_google_cancel_cleanup(
            context,
            settings=settings,
            backend_id=backend_id,
            set_backend_cooldown=set_backend_cooldown,
        )
        return BackendRequestResult(
            response=api_error(502, "Backend stream interrupted", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
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
                rate_limit_store=rate_limit_store,
            ),
            status_code=upstream.status_code,
            media_type="text/event-stream",
            headers={"cache-control": "no-cache"},
        ),
        retryable_failure=False,
    )


async def _forward_google_streaming(
    *,
    settings: Any,
    backend_id: str,
    request_id: str,
    headers: dict[str, str],
    public_body: dict[str, Any],
    upstream_body: dict[str, Any],
    backend_client: Any,
    set_backend_active: Any,
    set_backend_cooldown: Any,
    api_error: Any,
    credit_store: Any,
    metrics_store: Any,
    rate_limit_store: Any | None = None,
    pre_output_timeout_seconds: float = PRE_OUTPUT_TIMEOUT_SECONDS,
    reservation_deadline_monotonic: float | None = None,
    seal_context: SealContext | None = None,
    prepared_continuation: PreparedContinuation | None = None,
) -> BackendRequestResult:
    """Retain dispatch/usage ownership until the downstream response takes it."""
    model = str(public_body.get("model", ""))
    cost, input_tokens = _fallback_estimate_cost(settings, public_body, model, "responses")
    settlement = GoogleAttemptSettlement(cost, input_tokens)
    try:
        return await _google_streaming_attempt(
            seal_context=seal_context,
            prepared_continuation=prepared_continuation,
            settings=settings,
            backend_id=backend_id,
            request_id=request_id,
            headers=headers,
            public_body=public_body,
            upstream_body=upstream_body,
            backend_client=backend_client,
            set_backend_active=set_backend_active,
            set_backend_cooldown=set_backend_cooldown,
            api_error=api_error,
            credit_store=credit_store,
            metrics_store=metrics_store,
            rate_limit_store=rate_limit_store,
            pre_output_timeout_seconds=pre_output_timeout_seconds,
            reservation_deadline_monotonic=reservation_deadline_monotonic,
            settlement=settlement,
        )
    except (asyncio.CancelledError, httpx.HTTPError, TimeoutError):
        settlement.capture_stream_usage(settings, model)
        if settlement.dispatched:
            await _shielded_google_cancel_cleanup(
                settlement.context,
                settings=settings,
                backend_id=backend_id,
                set_backend_cooldown=set_backend_cooldown,
            )
        return BackendRequestResult(
            response=api_error(502, "Backend stream interrupted", "upstream_error"),
            retryable_failure=False,
            force_charge=settlement.dispatched,
            settlement_cost_usd=settlement.cost,
            settlement_input_tokens=settlement.input_tokens,
            confirmed_pre_dispatch=not settlement.dispatched,
        )


async def _google_streaming_attempt(
    *,
    settings: Any,
    backend_id: str,
    request_id: str,
    headers: dict[str, str],
    public_body: dict[str, Any],
    upstream_body: dict[str, Any],
    backend_client: Any,
    set_backend_active: Any,
    set_backend_cooldown: Any,
    api_error: Any,
    credit_store: Any,
    metrics_store: Any,
    rate_limit_store: Any | None = None,
    pre_output_timeout_seconds: float = PRE_OUTPUT_TIMEOUT_SECONDS,
    reservation_deadline_monotonic: float | None = None,
    settlement: GoogleAttemptSettlement,
    seal_context: SealContext | None = None,
    prepared_continuation: PreparedContinuation | None = None,
) -> BackendRequestResult:
    logical_model = str(public_body.get("model", ""))
    fallback_cost, fallback_input = _fallback_estimate_cost(
        settings, public_body, logical_model, "responses"
    )
    if reservation_deadline_monotonic is None:
        reservation_age = float(getattr(settings, "reservation_max_age_seconds", 900.0))
        reservation_deadline_monotonic = time.monotonic() + max(
            1.0, reservation_age - float(DEFAULT_CLEANUP_TIMEOUT_SECONDS)
        )
    deadline = reservation_deadline_monotonic
    adapter = get_adapter(
        _provider_of(settings, backend_id),
        google_features=settings.backends[backend_id].google_features,
        api_surface=settings.backends[backend_id].api_surface,
        seal_context=seal_context,
        backend_id=backend_id,
        prepared_continuation=prepared_continuation,
    )
    if time.monotonic() >= deadline:
        # Confirmed pre-dispatch: never contacted; release, don't charge.
        return BackendRequestResult(
            response=api_error(502, "Backend request exceeded its deadline", "upstream_error"),
            retryable_failure=False,
            confirmed_pre_dispatch=True,
        )

    if seal_context is not None:
        try:
            seal_context.validate_dispatch(settings, backend_client, backend_id, logical_model)
        except ValueError:
            return BackendRequestResult(
                response=api_error(
                    503, "Provider state is unavailable", "provider_state_unavailable"
                ),
                retryable_failure=False,
                confirmed_pre_dispatch=True,
            )
    context = backend_client.stream_backend(
        backend_id,
        "responses",
        headers=headers,
        json=upstream_body,
        **({"native_generation_stream": False} if seal_context is not None else {}),
    )
    settlement.context = context
    settlement.dispatched = True
    entered = await _enter_google_stream(
        context,
        settings=settings,
        backend_id=backend_id,
        set_backend_cooldown=set_backend_cooldown,
        api_error=api_error,
        fallback_cost=fallback_cost,
        fallback_input=fallback_input,
    )
    if isinstance(entered, BackendRequestResult):
        return entered
    upstream = entered
    if time.monotonic() >= deadline:
        await _close_quietly(context)
        return BackendRequestResult(
            response=api_error(502, "Backend request exceeded its deadline", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=fallback_cost,
            settlement_input_tokens=fallback_input,
            force_charge=True,
        )
    if not (HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT):
        try:
            async with asyncio.timeout(max(0.001, deadline - time.monotonic())):
                outcome = await _read_stream_bounded(upstream, limit_bytes=MAX_UPSTREAM_ERROR_BYTES)
        except (TimeoutError, asyncio.CancelledError):
            await _shielded_google_cancel_cleanup(
                context,
                settings=settings,
                backend_id=backend_id,
                set_backend_cooldown=set_backend_cooldown,
            )
            return BackendRequestResult(
                response=api_error(
                    502, "Unable to read the backend error response", "upstream_error"
                ),
                retryable_failure=False,
                settlement_cost_usd=fallback_cost,
                settlement_input_tokens=fallback_input,
                force_charge=True,
            )
        await _close_quietly(context)
        _body, _breached = outcome
        if upstream.status_code in GOOGLE_AUTH_STATUS_CODES:
            await set_backend_cooldown(
                backend_id,
                state=BackendHealthState.ERROR_COOLDOWN,
                cooldown_seconds=settings.retry_max_delay_seconds,
            )
            return BackendRequestResult(
                response=_sanitized_google_error_response(
                    502,
                    api_error,
                    upstream.status_code,
                    provider=_provider_of(settings, backend_id),
                ),
                retryable_failure=False,
            )
        if upstream.status_code == HTTP_TOO_MANY_REQUESTS:
            retry_after = _safe_header(upstream, "retry-after")
            parsed = parse_retry_after(retry_after, settings.retry_max_delay_seconds)
            cooldown_seconds = settings.retry_max_delay_seconds if parsed is None else parsed
            await _set_quota_group_cooldown(
                settings,
                backend_id,
                set_backend_cooldown=set_backend_cooldown,
                cooldown_seconds=cooldown_seconds,
            )
            return BackendRequestResult(
                response=_sanitized_google_error_response(
                    429, api_error, 429, provider=_provider_of(settings, backend_id)
                ),
                retryable_failure=True,
            )
        if 500 <= upstream.status_code < 600:
            await set_backend_cooldown(
                backend_id,
                state=BackendHealthState.ERROR_COOLDOWN,
                cooldown_seconds=settings.retry_max_delay_seconds,
            )
            return BackendRequestResult(
                response=_sanitized_google_error_response(
                    upstream.status_code,
                    api_error,
                    upstream.status_code,
                    provider=_provider_of(settings, backend_id),
                ),
                retryable_failure=_google_pre_output_failover(
                    settings, backend_id, upstream.status_code
                ),
                settlement_cost_usd=fallback_cost,
                settlement_input_tokens=fallback_input,
                force_charge=True,
            )
        return BackendRequestResult(
            response=_sanitized_google_error_response(
                upstream.status_code,
                api_error,
                upstream.status_code,
                provider=_provider_of(settings, backend_id),
            ),
            retryable_failure=False,
        )
    decoder = adapter.create_stream_decoder(
        logical_model=logical_model, metadata=public_body.get("metadata"), request_body=public_body
    )
    settlement.decoder = decoder
    chunks = upstream.aiter_bytes()
    prefetched: list[bytes] = []
    try:
        prefetch_failed = await _prefetch_google_events(
            chunks,
            decoder,
            prefetched,
            deadline_monotonic=deadline,
            pre_output_timeout_seconds=pre_output_timeout_seconds,
        )
    except asyncio.CancelledError:
        settlement.capture_stream_usage(settings, logical_model)
        await _shielded_google_cancel_cleanup(
            context,
            settings=settings,
            backend_id=backend_id,
            set_backend_cooldown=set_backend_cooldown,
        )
        return BackendRequestResult(
            response=api_error(502, "Unable to read the backend stream", "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=settlement.cost,
            settlement_input_tokens=settlement.input_tokens,
            force_charge=True,
        )
    settlement.capture_stream_usage(settings, logical_model)
    if prefetch_failed is not None:
        await _close_quietly(context)
        await set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=settings.retry_max_delay_seconds,
        )
        return BackendRequestResult(
            response=api_error(502, prefetch_failed, "upstream_error"),
            retryable_failure=False,
            settlement_cost_usd=settlement.cost,
            settlement_input_tokens=settlement.input_tokens,
            force_charge=True,
        )
    await set_backend_active(backend_id)

    async def cleanup_unstarted() -> None:
        operations = [
            lambda: credit_store.finalize_request(
                request_id,
                backend_id=backend_id,
                charge_reserved=True,
                charged_cost_usd=settlement.cost,
            ),
            lambda: context.__aexit__(None, None, None),
        ]
        if rate_limit_store is not None:
            operations.append(
                lambda: rate_limit_store.finalize_request(
                    request_id, actual_input_tokens=settlement.input_tokens
                )
            )
        await protected_cleanup(operations)

    return BackendRequestResult(
        response=DeadlineStreamingResponse(
            _google_stream_response(
                chunks,
                decoder,
                prefetched,
                context,
                request_id=request_id,
                backend_id=backend_id,
                cooldown_seconds=settings.retry_max_delay_seconds,
                model=logical_model,
                pricing=getattr(settings, "pricing", {}),
                status_code=upstream.status_code,
                set_backend_cooldown=set_backend_cooldown,
                credit_store=credit_store,
                metrics_store=metrics_store,
                rate_limit_store=rate_limit_store,
                deadline_monotonic=deadline,
                fallback_cost_usd=fallback_cost,
                fallback_input_tokens=fallback_input,
            ),
            status_code=upstream.status_code,
            media_type="text/event-stream",
            headers={"cache-control": "no-cache"},
            deadline=deadline,
            cleanup=cleanup_unstarted,
        ),
        retryable_failure=False,
    )


def _ensure_stream_deadline(deadline_monotonic: float | None) -> float | None:
    """Return remaining seconds or raise when the reservation deadline passed."""
    if deadline_monotonic is None:
        return None
    remaining = deadline_monotonic - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Google stream exceeded reservation lifetime")
    return remaining


async def _prefetch_google_events(
    chunks: Any,
    decoder: Any,
    prefetched: list[bytes],
    *,
    deadline_monotonic: float,
    pre_output_timeout_seconds: float,
) -> str | None:
    """Read until the first validated provider event. Returns error or None.

    The whole prefetch is bounded by the earlier of the pre-output timeout
    and the reservation deadline, so a stalled upstream read cannot outlive
    the reservation while waiting for another chunk.
    """
    remaining = deadline_monotonic - time.monotonic()
    if remaining <= 0:
        return "Backend request exceeded its deadline"
    try:
        async with asyncio.timeout(min(pre_output_timeout_seconds, remaining)):
            empty_chunks = 0
            async for chunk in chunks:
                if not chunk:
                    empty_chunks += 1
                    if empty_chunks >= MAX_EMPTY_PRE_OUTPUT_CHUNKS:
                        return "Unable to read the backend stream"
                    continue
                try:
                    events = decoder.feed(chunk)
                except ValueError as exc:
                    _log_translated_rejection(exc)
                    return "Backend returned an invalid response"
                if events:
                    prefetched.extend(events)
                    return None
            if getattr(decoder, "finish_at_prefetch_eof", False):
                try:
                    owned_finish = getattr(decoder, "finish_owned", None)
                    events = (
                        await owned_finish(deadline=deadline_monotonic)
                        if callable(owned_finish)
                        else decoder.finish()
                    )
                    prefetched.extend(events)
                except ValueError as exc:
                    _log_translated_rejection(exc)
                    return "Backend returned an invalid response"
                decoder.prefetch_finished = True
                return None
            return "Unable to read the backend stream"
    except TimeoutError:
        if time.monotonic() >= deadline_monotonic:
            return "Backend request exceeded its deadline"
        return "Unable to read the backend stream"
    except httpx.HTTPError:
        return "Unable to read the backend stream"


async def _google_stream_response(
    chunks: Any,
    decoder: Any,
    prefetched: list[bytes],
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
    rate_limit_store: Any | None = None,
    deadline_monotonic: float | None = None,
    fallback_cost_usd: float | None = None,
    fallback_input_tokens: int | None = None,
    cleanup_timeout_seconds: float = DEFAULT_CLEANUP_TIMEOUT_SECONDS,
) -> Any:
    started_at = time.monotonic()
    charged_cost: float | None = None
    actual_input_tokens: int | None = fallback_input_tokens
    metric_status_code = status_code
    stream_complete = getattr(decoder, "prefetch_finished", False) is True

    def _settle_from_decoder() -> None:
        nonlocal charged_cost, actual_input_tokens
        if getattr(decoder, "usage_invalid", False):
            charged_cost = None
            actual_input_tokens = None
            return
        usage = decoder.usage
        if usage[0] is not None:
            actual_input_tokens = usage[0]
        # Counts received before a clean validated end may be cumulative partial usage.
        # Preserve the request estimate until completion, independently of input quota.
        if stream_complete and usage[0] is not None and usage[1] is not None:
            try:
                model_pricing = (pricing or {}).get(model)
                if model_pricing is not None:
                    input_price = float(getattr(model_pricing, "input_per_million", float("nan")))
                    output_price = float(getattr(model_pricing, "output_per_million", float("nan")))
                    if math.isfinite(input_price) and math.isfinite(output_price):
                        if input_price == 0.0 and output_price == 0.0:
                            charged_cost = 0.0
                        else:
                            candidate = (
                                (usage[0] * input_price) + (usage[1] * output_price)
                            ) / 1_000_000
                            charged_cost = (
                                candidate if math.isfinite(candidate) and candidate >= 0 else None
                            )
            except Exception:
                pass
        if charged_cost is None and fallback_cost_usd is not None:
            charged_cost = fallback_cost_usd

    try:
        for event in prefetched:
            # Bound delivery, not just reads: a stalled downstream consumer
            # must not stretch delivery past the reservation lifetime.
            _ensure_stream_deadline(deadline_monotonic)
            mark_delivered = getattr(decoder, "mark_delivered", None)
            if callable(mark_delivered):
                mark_delivered(event)
            yield event
        chunk_iterator = chunks.__aiter__()
        while True:
            remaining = _ensure_stream_deadline(deadline_monotonic)
            try:
                if remaining is None:
                    chunk = await chunk_iterator.__anext__()
                else:
                    async with asyncio.timeout(remaining):
                        chunk = await chunk_iterator.__anext__()
            except StopAsyncIteration:
                break
            events = decoder.feed(chunk)
            for event in events:
                _ensure_stream_deadline(deadline_monotonic)
                yield event
        terminal = [] if getattr(decoder, "prefetch_finished", False) else decoder.finish()
        stream_complete = True
        for event in terminal:
            _ensure_stream_deadline(deadline_monotonic)
            mark_delivered = getattr(decoder, "mark_delivered", None)
            if callable(mark_delivered):
                mark_delivered(event)
            yield event
        _settle_from_decoder()
    except ValueError as exc:
        _log_translated_rejection(exc, backend_id=backend_id)
        metric_status_code = 502
        _settle_from_decoder()
        await set_backend_cooldown(
            backend_id, state=BackendHealthState.ERROR_COOLDOWN, cooldown_seconds=cooldown_seconds
        )
        for event in decoder.build_failure("Backend returned an invalid response"):
            yield event
    except (httpx.HTTPError, TimeoutError):
        await set_backend_cooldown(
            backend_id, state=BackendHealthState.ERROR_COOLDOWN, cooldown_seconds=cooldown_seconds
        )
        metric_status_code = 502
        _settle_from_decoder()
        for event in decoder.build_failure("Upstream stream failed"):
            yield event
    finally:
        _settle_from_decoder()

        async def settle_credit() -> None:
            try:
                await credit_store.finalize_request(
                    request_id,
                    backend_id=backend_id,
                    charge_reserved=True,
                    charged_cost_usd=charged_cost,
                )
            except TypeError as exc:
                if "backend_id" in str(exc):
                    await credit_store.finalize_request(
                        request_id, charge_reserved=True, charged_cost_usd=charged_cost
                    )
                else:
                    raise

        async def settle_quota() -> None:
            if rate_limit_store is not None:
                await rate_limit_store.finalize_request(
                    request_id, actual_input_tokens=actual_input_tokens
                )

        await protected_cleanup(
            [
                settle_credit,
                settle_quota,
                lambda: metrics_store.observe_request(
                    model=model,
                    backend=backend_id,
                    status_code=metric_status_code,
                    latency_seconds=max(0.0, time.monotonic() - started_at),
                    estimated_cost_usd=charged_cost,
                ),
                lambda: context.__aexit__(None, None, None),
            ],
            timeout_seconds=cleanup_timeout_seconds,
        )
