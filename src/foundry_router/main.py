"""Foundry Router main application."""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import httpx
import structlog
from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from structlog import get_logger

from foundry_router.auth import verify_admin_auth, verify_client_auth
from foundry_router.backends import close_backend_client, get_backend_client
from foundry_router.config import load_settings
from foundry_router.credit import (
    BackendCreditLiveSnapshot,
    CreditState,
    CreditStore,
    InMemoryCreditStore,
    estimate_request_cost,
    estimate_response_usage_cost,
    score_credit_assessment,
)
from foundry_router.logging import setup_logging
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.reconciliation import (
    ReconciliationLoop,
    ReconciliationProvider,
    StaticSettingsReconciliationProvider,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

logger = get_logger(__name__)
MAX_UPSTREAM_ERROR_BYTES = 64 * 1024
HTTP_OK = 200
HTTP_SUCCESS_LIMIT = 300
HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR_MIN = 500
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
SAFE_UPSTREAM_RESPONSE_HEADERS = frozenset({"cache-control", "retry-after"})
MAX_EMPTY_PRE_OUTPUT_CHUNKS = 16
PRE_OUTPUT_TIMEOUT_SECONDS = 60.0


class BackendHealthState(StrEnum):
    """Ephemeral backend routing health state."""

    ACTIVE = "ACTIVE"
    QUOTA_COOLDOWN = "QUOTA_COOLDOWN"
    ERROR_COOLDOWN = "ERROR_COOLDOWN"
    DISABLED = "DISABLED"


COOLDOWN_STATES = frozenset({BackendHealthState.QUOTA_COOLDOWN, BackendHealthState.ERROR_COOLDOWN})


@dataclass
class BackendHealthRecord:
    state: BackendHealthState = BackendHealthState.ACTIVE
    cooldown_until: float = 0.0


@dataclass(frozen=True)
class BackendHealthSnapshot:
    state: BackendHealthState
    cooldown_remaining_seconds: float


@dataclass(frozen=True)
class BackendRequestResult:
    response: Response
    retryable_failure: bool


_backend_health_state: dict[str, BackendHealthRecord] = {}
_backend_health_lock = asyncio.Lock()
_credit_store: CreditStore = InMemoryCreditStore()
_reconciliation_provider: ReconciliationProvider = StaticSettingsReconciliationProvider()
_reconciliation_loop: ReconciliationLoop | None = None
_metrics_store = InMemoryMetricsStore()


@dataclass(frozen=True)
class BackendSelectionResult:
    backend_id: str | None
    candidates: list[str]
    snapshots: dict[str, BackendHealthSnapshot]
    insufficient_credit_capacity: bool


def _ranked_model_backends(
    settings: Any, model: str, *, excluded: set[str] | None = None
) -> list[str]:
    pool = settings.models.get(model)
    if pool is None:
        return []
    excluded_ids = excluded or set()
    ranked = [backend for backend in pool.backends if backend not in excluded_ids]
    return sorted(ranked, key=lambda backend: (-pool.backends[backend], backend))


def _select_backend(settings: Any, model: str) -> str | None:
    ranked = _ranked_model_backends(settings, model)
    if not ranked:
        return None
    return ranked[0]


def _is_retryable_status(status_code: int) -> bool:
    return status_code in RETRYABLE_STATUS_CODES


def _parse_retry_after(raw_value: str | None, max_delay_seconds: float) -> float | None:
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


def _retry_delay_seconds(
    *,
    attempt_number: int,
    max_delay_seconds: float,
    retry_after_header: str | None,
) -> float:
    exponential = min(max_delay_seconds, float(2 ** max(0, attempt_number - 1)))
    parsed_retry_after = _parse_retry_after(retry_after_header, max_delay_seconds)
    if parsed_retry_after is None:
        return exponential
    return min(max_delay_seconds, max(exponential, parsed_retry_after))


async def _set_backend_active(backend_id: str) -> None:
    async with _backend_health_lock:
        existing = _backend_health_state.get(backend_id)
        if existing is not None and existing.state == BackendHealthState.DISABLED:
            return
        _backend_health_state[backend_id] = BackendHealthRecord(
            state=BackendHealthState.ACTIVE,
            cooldown_until=0.0,
        )


async def _set_backend_cooldown(
    backend_id: str,
    *,
    state: BackendHealthState,
    cooldown_seconds: float,
) -> None:
    duration = max(0.0, cooldown_seconds)
    async with _backend_health_lock:
        existing = _backend_health_state.get(backend_id)
        if existing is not None and existing.state == BackendHealthState.DISABLED:
            return
        _backend_health_state[backend_id] = BackendHealthRecord(
            state=state,
            cooldown_until=time.monotonic() + duration,
        )


async def _snapshot_backend_health(backend_ids: list[str]) -> dict[str, BackendHealthSnapshot]:
    now = time.monotonic()
    snapshots: dict[str, BackendHealthSnapshot] = {}
    async with _backend_health_lock:
        for backend_id in backend_ids:
            record = _backend_health_state.get(backend_id)
            if record is None:
                snapshots[backend_id] = BackendHealthSnapshot(BackendHealthState.ACTIVE, 0.0)
                continue
            if record.state in COOLDOWN_STATES and record.cooldown_until <= now:
                record = BackendHealthRecord(state=BackendHealthState.ACTIVE, cooldown_until=0.0)
                _backend_health_state[backend_id] = record
            remaining = (
                max(0.0, record.cooldown_until - now) if record.state in COOLDOWN_STATES else 0.0
            )
            snapshots[backend_id] = BackendHealthSnapshot(record.state, remaining)
    return snapshots


def _cooldown_exhausted_response(
    candidates: list[str],
    snapshots: dict[str, BackendHealthSnapshot],
) -> JSONResponse | None:
    if not candidates:
        return None
    candidate_states = [snapshots[backend_id] for backend_id in candidates]
    if not candidate_states or any(
        snapshot.state not in COOLDOWN_STATES for snapshot in candidate_states
    ):
        return None
    status_code = (
        HTTP_TOO_MANY_REQUESTS
        if all(snapshot.state == BackendHealthState.QUOTA_COOLDOWN for snapshot in candidate_states)
        else 503
    )
    message = (
        "All configured backends are in quota cooldown"
        if status_code == HTTP_TOO_MANY_REQUESTS
        else "All configured backends are in cooldown"
    )
    response = _api_error(status_code, message, "upstream_unavailable")
    response.headers["retry-after"] = str(
        max(0, math.ceil(min(snapshot.cooldown_remaining_seconds for snapshot in candidate_states)))
    )
    return response


async def _select_candidate_backend(  # noqa: PLR0913
    settings: Any,
    model: str,
    *,
    operation: str,
    body: dict[str, Any],
    request_id: str,
    excluded: set[str] | None = None,
) -> BackendSelectionResult:
    ranked_candidates = _ranked_model_backends(settings, model, excluded=excluded)
    if not ranked_candidates:
        return BackendSelectionResult(None, [], {}, False)

    snapshots = await _snapshot_backend_health(ranked_candidates)
    await _credit_store.sync_from_settings(settings)

    estimate = estimate_request_cost(
        model=model,
        operation=operation,
        body=body,
        pricing=settings.pricing,
    )
    if estimate is None:
        logger.info(
            "routing_decision",
            model=model,
            operation=operation,
            request_id=request_id,
            selected_backend=None,
            reason="estimate_unavailable",
            estimated_request_cost_usd=None,
            candidates=[
                {
                    "backend_id": backend_id,
                    "health_state": snapshots[backend_id].state,
                    "cooldown_remaining_seconds": round(
                        snapshots[backend_id].cooldown_remaining_seconds,
                        3,
                    ),
                }
                for backend_id in ranked_candidates
            ],
        )
        return BackendSelectionResult(None, ranked_candidates, snapshots, True)

    health_eligible = [
        backend_id
        for backend_id in ranked_candidates
        if snapshots[backend_id].state == BackendHealthState.ACTIVE
    ]
    if (
        not health_eligible
        and settings.protected_emergency_fallback
        and len(ranked_candidates) == 1
    ):
        fallback_candidate = ranked_candidates[0]
        if snapshots[fallback_candidate].state in COOLDOWN_STATES:
            health_eligible = [fallback_candidate]

    if not health_eligible:
        logger.info(
            "routing_decision",
            model=model,
            operation=operation,
            request_id=request_id,
            selected_backend=None,
            reason="all_candidates_in_cooldown_or_disabled",
            estimated_request_cost_usd=estimate.estimated_cost_usd,
            candidates=[
                {
                    "backend_id": backend_id,
                    "health_state": snapshots[backend_id].state,
                    "cooldown_remaining_seconds": round(
                        snapshots[backend_id].cooldown_remaining_seconds,
                        3,
                    ),
                }
                for backend_id in ranked_candidates
            ],
        )
        return BackendSelectionResult(None, ranked_candidates, snapshots, False)

    scored_candidates: list[tuple[float, float, str]] = []
    candidate_details: list[dict[str, Any]] = []
    has_credit_capacity = False
    for backend_id in health_eligible:
        assessment = await _credit_store.assess(
            backend_id,
            estimate.estimated_cost_usd,
            min_credit_reserve_usd=settings.min_credit_reserve_usd,
            min_credit_reserve_percent=settings.min_credit_reserve_percent,
        )
        candidate_detail = {
            "backend_id": backend_id,
            "health_state": snapshots[backend_id].state,
            "cooldown_remaining_seconds": round(
                snapshots[backend_id].cooldown_remaining_seconds,
                3,
            ),
            "credit_state": assessment.state,
            "available_credit_usd": assessment.available_credit_usd,
            "projected_unused_credit_usd": assessment.projected_unused_credit_usd,
            "estimated_request_cost_usd": assessment.estimated_request_cost_usd,
            "cycle_allowance_usd": assessment.cycle_allowance_usd,
        }
        if assessment.state not in {CreditState.USABLE, CreditState.CONSERVATION}:
            candidate_details.append(candidate_detail)
            continue
        has_credit_capacity = True
        score = score_credit_assessment(
            state=assessment.state,
            is_health_active=snapshots[backend_id].state == BackendHealthState.ACTIVE,
            is_error_cooldown=snapshots[backend_id].state == BackendHealthState.ERROR_COOLDOWN,
            available_credit_usd=assessment.available_credit_usd,
            estimated_request_cost_usd=assessment.estimated_request_cost_usd,
            projected_unused_credit_usd=assessment.projected_unused_credit_usd,
            cycle_allowance_usd=assessment.cycle_allowance_usd,
        )
        candidate_detail["score"] = score
        scored_candidates.append((score, settings.models[model].backends[backend_id], backend_id))
        candidate_details.append(candidate_detail)

    if not scored_candidates:
        logger.info(
            "routing_decision",
            model=model,
            operation=operation,
            request_id=request_id,
            selected_backend=None,
            reason=(
                "insufficient_credit_capacity" if has_credit_capacity else "no_usable_credit_state"
            ),
            estimated_request_cost_usd=estimate.estimated_cost_usd,
            candidates=candidate_details,
        )
        return BackendSelectionResult(None, ranked_candidates, snapshots, not has_credit_capacity)

    scored_candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
    for _score, _weight, backend_id in scored_candidates:
        reserved = await _credit_store.try_assign_reservation(
            request_id,
            backend_id,
            estimate.estimated_cost_usd,
            min_credit_reserve_usd=settings.min_credit_reserve_usd,
            min_credit_reserve_percent=settings.min_credit_reserve_percent,
        )
        if reserved:
            logger.info(
                "routing_decision",
                model=model,
                operation=operation,
                request_id=request_id,
                selected_backend=backend_id,
                reason="selected",
                estimated_request_cost_usd=estimate.estimated_cost_usd,
                candidates=candidate_details,
            )
            return BackendSelectionResult(backend_id, ranked_candidates, snapshots, False)

    logger.info(
        "routing_decision",
        model=model,
        operation=operation,
        request_id=request_id,
        selected_backend=None,
        reason="reservation_race_lost",
        estimated_request_cost_usd=estimate.estimated_cost_usd,
        candidates=candidate_details,
    )
    return BackendSelectionResult(None, ranked_candidates, snapshots, True)


async def _all_candidates_cooldown_response(
    settings: Any,
    model: str,
    *,
    operation: str,
    body: dict[str, Any],
    request_id: str,
) -> JSONResponse | None:
    selection = await _select_candidate_backend(
        settings,
        model,
        operation=operation,
        body=body,
        request_id=request_id,
    )
    if selection.backend_id is not None:
        return None
    return _cooldown_exhausted_response(selection.candidates, selection.snapshots)


async def _execute_with_single_failover(  # noqa: PLR0911, PLR0912, PLR0913
    settings: Any,
    model: str,
    *,
    operation: str,
    body: dict[str, Any],
    request_id: str,
    execute_backend: Callable[[str], Awaitable[BackendRequestResult]],
) -> Response:
    started_at = time.monotonic()

    async def _record_and_return(
        response: Response,
        *,
        backend_id: str | None,
        actual_cost_usd: float | None = None,
    ) -> Response:
        if isinstance(response, StreamingResponse):
            return response
        await _metrics_store.observe_request(
            model=model,
            backend=backend_id or "none",
            status_code=response.status_code,
            latency_seconds=max(0.0, time.monotonic() - started_at),
            estimated_cost_usd=actual_cost_usd,
        )
        return response

    first_selection = await _select_candidate_backend(
        settings,
        model,
        operation=operation,
        body=body,
        request_id=request_id,
    )
    if first_selection.backend_id is None:
        cooldown_response = _cooldown_exhausted_response(
            first_selection.candidates,
            first_selection.snapshots,
        )
        if cooldown_response is not None:
            return await _record_and_return(cooldown_response, backend_id=None)
        if first_selection.insufficient_credit_capacity:
            return await _record_and_return(
                _api_error(
                    503,
                    "No backend has sufficient estimated credit capacity",
                    "insufficient_credit_capacity",
                ),
                backend_id=None,
            )
        return await _record_and_return(
            _api_error(
                503,
                "No active backend available for the requested model",
                "upstream_error",
            ),
            backend_id=None,
        )

    first_backend_id = first_selection.backend_id
    reservation_closed_or_transferred = False
    try:
        first_result = await execute_backend(first_backend_id)

        if not first_result.retryable_failure:
            if not isinstance(first_result.response, StreamingResponse):
                finalized_cost = await _finalize_non_streaming_credit(
                    request_id=request_id,
                    model=model,
                    settings=settings,
                    response=first_result.response,
                )
                reservation_closed_or_transferred = True
                return await _record_and_return(
                    first_result.response,
                    backend_id=first_backend_id,
                    actual_cost_usd=finalized_cost,
                )
            reservation_closed_or_transferred = True
            return await _record_and_return(first_result.response, backend_id=first_backend_id)

        second_selection = await _select_candidate_backend(
            settings,
            model,
            operation=operation,
            body=body,
            request_id=request_id,
            excluded={first_backend_id},
        )
        second_backend_id = second_selection.backend_id
        if second_backend_id is None:
            if (
                first_result.response.status_code >= HTTP_SERVER_ERROR_MIN
                and second_selection.insufficient_credit_capacity
            ):
                await _finalize_non_streaming_credit(
                    request_id=request_id,
                    model=model,
                    settings=settings,
                    response=first_result.response,
                )
                reservation_closed_or_transferred = True
                return await _record_and_return(
                    _api_error(
                        503,
                        "No backend has sufficient estimated credit capacity",
                        "insufficient_credit_capacity",
                    ),
                    backend_id=first_backend_id,
                )
            all_cooldown_response = await _all_candidates_cooldown_response(
                settings,
                model,
                operation=operation,
                body=body,
                request_id=request_id,
            )
            if all_cooldown_response is not None:
                await _finalize_non_streaming_credit(
                    request_id=request_id,
                    model=model,
                    settings=settings,
                    response=first_result.response,
                )
                reservation_closed_or_transferred = True
                return await _record_and_return(all_cooldown_response, backend_id=first_backend_id)
            cooldown_response = _cooldown_exhausted_response(
                second_selection.candidates,
                second_selection.snapshots,
            )
            if cooldown_response is not None:
                await _finalize_non_streaming_credit(
                    request_id=request_id,
                    model=model,
                    settings=settings,
                    response=first_result.response,
                )
                reservation_closed_or_transferred = True
                return await _record_and_return(cooldown_response, backend_id=first_backend_id)
            finalized_cost = await _finalize_non_streaming_credit(
                request_id=request_id,
                model=model,
                settings=settings,
                response=first_result.response,
            )
            reservation_closed_or_transferred = True
            return await _record_and_return(
                first_result.response,
                backend_id=first_backend_id,
                actual_cost_usd=finalized_cost,
            )

        second_result = await execute_backend(second_backend_id)
        if not isinstance(second_result.response, StreamingResponse):
            finalized_cost = await _finalize_non_streaming_credit(
                request_id=request_id,
                model=model,
                settings=settings,
                response=second_result.response,
            )
            reservation_closed_or_transferred = True
            if second_result.retryable_failure:
                all_cooldown_response = await _all_candidates_cooldown_response(
                    settings,
                    model,
                    operation=operation,
                    body=body,
                    request_id=request_id,
                )
                if all_cooldown_response is not None:
                    return await _record_and_return(
                        all_cooldown_response,
                        backend_id=second_backend_id,
                    )
            return await _record_and_return(
                second_result.response,
                backend_id=second_backend_id,
                actual_cost_usd=finalized_cost,
            )
        reservation_closed_or_transferred = True
        if second_result.retryable_failure:
            all_cooldown_response = await _all_candidates_cooldown_response(
                settings,
                model,
                operation=operation,
                body=body,
                request_id=request_id,
            )
            if all_cooldown_response is not None:
                return await _record_and_return(all_cooldown_response, backend_id=second_backend_id)
        return await _record_and_return(second_result.response, backend_id=second_backend_id)
    finally:
        if not reservation_closed_or_transferred:
            await _credit_store.finalize_request(
                request_id,
                charge_reserved=False,
                charged_cost_usd=None,
            )


async def _forward_non_streaming_with_retries(
    *,
    settings: Any,
    backend_id: str,
    operation: str,
    headers: dict[str, str],
    body: dict[str, Any],
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
            await _set_backend_cooldown(
                backend_id,
                state=BackendHealthState.ERROR_COOLDOWN,
                cooldown_seconds=settings.retry_max_delay_seconds,
            )
            if attempt < max_attempts:
                delay_seconds = _retry_delay_seconds(
                    attempt_number=attempt,
                    max_delay_seconds=settings.retry_max_delay_seconds,
                    retry_after_header=None,
                )
                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)
                continue
            return BackendRequestResult(
                response=_api_error(
                    502,
                    "Unable to contact the configured backend",
                    "upstream_error",
                ),
                retryable_failure=True,
            )
        except httpx.HTTPError:
            return BackendRequestResult(
                response=_api_error(
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
        upstream_response = _upstream_response(upstream, forwarded_body)
        if HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT:
            await _set_backend_active(backend_id)
            return BackendRequestResult(response=upstream_response, retryable_failure=False)
        if not _is_retryable_status(upstream.status_code):
            return BackendRequestResult(response=upstream_response, retryable_failure=False)

        cooldown_state = (
            BackendHealthState.QUOTA_COOLDOWN
            if upstream.status_code == HTTP_TOO_MANY_REQUESTS
            else BackendHealthState.ERROR_COOLDOWN
        )
        retry_after_seconds = _parse_retry_after(
            upstream.headers.get("retry-after"),
            settings.retry_max_delay_seconds,
        )
        await _set_backend_cooldown(
            backend_id,
            state=cooldown_state,
            cooldown_seconds=(
                settings.retry_max_delay_seconds
                if retry_after_seconds is None
                else retry_after_seconds
            ),
        )
        if attempt < max_attempts:
            delay_seconds = _retry_delay_seconds(
                attempt_number=attempt,
                max_delay_seconds=settings.retry_max_delay_seconds,
                retry_after_header=upstream.headers.get("retry-after"),
            )
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
            continue
        return BackendRequestResult(response=upstream_response, retryable_failure=True)

    return BackendRequestResult(
        response=_api_error(502, "Unable to contact the configured backend", "upstream_error"),
        retryable_failure=True,
    )


async def _forward_streaming_with_retries(  # noqa: PLR0911, PLR0912, PLR0915
    *,
    settings: Any,
    backend_id: str,
    request_id: str,
    headers: dict[str, str],
    body: dict[str, Any],
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
            await _set_backend_cooldown(
                backend_id,
                state=BackendHealthState.ERROR_COOLDOWN,
                cooldown_seconds=settings.retry_max_delay_seconds,
            )
            if attempt < max_attempts:
                delay_seconds = _retry_delay_seconds(
                    attempt_number=attempt,
                    max_delay_seconds=settings.retry_max_delay_seconds,
                    retry_after_header=None,
                )
                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)
                continue
            return BackendRequestResult(
                response=_api_error(
                    502,
                    "Unable to contact the configured backend",
                    "upstream_error",
                ),
                retryable_failure=True,
            )
        except httpx.HTTPError:
            return BackendRequestResult(
                response=_api_error(
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
                await _set_backend_cooldown(
                    backend_id,
                    state=BackendHealthState.ERROR_COOLDOWN,
                    cooldown_seconds=settings.retry_max_delay_seconds,
                )
                return BackendRequestResult(
                    response=_api_error(
                        502,
                        "Unable to read the configured backend error response",
                        "upstream_error",
                    ),
                    retryable_failure=True,
                )
            except httpx.HTTPError:
                return BackendRequestResult(
                    response=_api_error(
                        502,
                        "Unable to read the configured backend error response",
                        "upstream_error",
                    ),
                    retryable_failure=False,
                )
            finally:
                await context.__aexit__(None, None, None)
            upstream_response = _upstream_response(upstream, error_body)
            if not _is_retryable_status(upstream.status_code):
                return BackendRequestResult(response=upstream_response, retryable_failure=False)

            cooldown_state = (
                BackendHealthState.QUOTA_COOLDOWN
                if upstream.status_code == HTTP_TOO_MANY_REQUESTS
                else BackendHealthState.ERROR_COOLDOWN
            )
            retry_after_seconds = _parse_retry_after(
                upstream.headers.get("retry-after"),
                settings.retry_max_delay_seconds,
            )
            await _set_backend_cooldown(
                backend_id,
                state=cooldown_state,
                cooldown_seconds=(
                    settings.retry_max_delay_seconds
                    if retry_after_seconds is None
                    else retry_after_seconds
                ),
            )
            if attempt < max_attempts:
                delay_seconds = _retry_delay_seconds(
                    attempt_number=attempt,
                    max_delay_seconds=settings.retry_max_delay_seconds,
                    retry_after_header=upstream.headers.get("retry-after"),
                )
                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)
                continue
            return BackendRequestResult(response=upstream_response, retryable_failure=True)

        chunks = upstream.aiter_raw()
        try:
            async with asyncio.timeout(PRE_OUTPUT_TIMEOUT_SECONDS):
                first_chunk = b""
                for _ in range(MAX_EMPTY_PRE_OUTPUT_CHUNKS):
                    first_chunk = await anext(chunks)
                    if first_chunk:
                        break
                if not first_chunk:
                    raise httpx.ReadError("Backend emitted too many empty pre-output chunks")
        except (StopAsyncIteration, TimeoutError, httpx.TransportError):
            await context.__aexit__(None, None, None)
            await _set_backend_cooldown(
                backend_id,
                state=BackendHealthState.ERROR_COOLDOWN,
                cooldown_seconds=settings.retry_max_delay_seconds,
            )
            if attempt < max_attempts:
                delay_seconds = _retry_delay_seconds(
                    attempt_number=attempt,
                    max_delay_seconds=settings.retry_max_delay_seconds,
                    retry_after_header=None,
                )
                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)
                continue
            return BackendRequestResult(
                response=_api_error(
                    502,
                    "Unable to read the configured backend stream",
                    "upstream_error",
                ),
                retryable_failure=True,
            )
        except httpx.HTTPError:
            await context.__aexit__(None, None, None)
            return BackendRequestResult(
                response=_api_error(
                    502,
                    "Unable to read the configured backend stream",
                    "upstream_error",
                ),
                retryable_failure=False,
            )

        await _set_backend_active(backend_id)
        return BackendRequestResult(
            response=StreamingResponse(
                _stream_response(
                    chunks,
                    first_chunk,
                    context,
                    request_id=request_id,
                    backend_id=backend_id,
                    cooldown_seconds=settings.retry_max_delay_seconds,
                    model=body.get("model", ""),
                    pricing=settings.pricing,
                    status_code=upstream.status_code,
                ),
                status_code=upstream.status_code,
                media_type="text/event-stream",
                headers={"cache-control": "no-cache"},
            ),
            retryable_failure=False,
        )

    return BackendRequestResult(
        response=_api_error(502, "Unable to contact the configured backend", "upstream_error"),
        retryable_failure=True,
    )


async def _reset_backend_health_state() -> None:
    async with _backend_health_lock:
        _backend_health_state.clear()


async def _reset_credit_state() -> None:
    await _credit_store.reset()


async def _reset_metrics_state() -> None:
    await _metrics_store.reset()


async def _reset_reconciliation_state() -> None:
    global _reconciliation_loop  # noqa: PLW0603
    if _reconciliation_loop is not None:
        await _reconciliation_loop.stop()
    _reconciliation_loop = None


def set_reconciliation_provider(provider: ReconciliationProvider) -> None:
    """Override reconciliation provider (primarily for tests and local adapters)."""
    global _reconciliation_provider  # noqa: PLW0603
    _reconciliation_provider = provider


async def _finalize_non_streaming_credit(
    *,
    request_id: str,
    model: str,
    settings: Any,
    response: Response,
) -> float | None:
    is_success = HTTP_OK <= response.status_code < HTTP_SUCCESS_LIMIT
    charged_cost = (
        estimate_response_usage_cost(response, model, settings.pricing) if is_success else None
    )
    await _credit_store.finalize_request(
        request_id,
        charge_reserved=is_success,
        charged_cost_usd=charged_cost,
    )
    return charged_cost


def _api_error(status_code: int, message: str, error_type: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, "type": error_type}},
    )


async def _request_body(  # noqa: PLR0911
    request: Request, endpoint: str
) -> dict[str, Any] | JSONResponse:
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
        return _api_error(415, "Content-Type must be application/json", "invalid_request")
    try:
        body = await request.json()
    except ValueError:
        return _api_error(400, "Request body must contain valid JSON", "invalid_request")
    if not isinstance(body, dict):
        return _api_error(400, "Request body must be a JSON object", "invalid_request")
    model = body.get("model")
    if not isinstance(model, str) or not model.strip():
        return _api_error(422, "The 'model' field must be a non-empty string", "invalid_request")
    if endpoint == "responses" and "stream" in body and not isinstance(body["stream"], bool):
        return _api_error(422, "The 'stream' field must be a boolean", "invalid_request")
    if endpoint == "embeddings":
        input_value = body.get("input")
        if not isinstance(input_value, (str, list)) or (
            isinstance(input_value, list) and not input_value
        ):
            return _api_error(
                422, "The 'input' field must be a non-empty string or array", "invalid_request"
            )
        if isinstance(input_value, list) and any(
            not isinstance(item, str) or not item.strip() for item in input_value
        ):
            return _api_error(
                422, "The 'input' array must contain non-empty strings", "invalid_request"
            )
    return body


def _forward_headers(request: Request) -> dict[str, str]:
    headers = {"content-type": "application/json", "accept": "application/json"}
    if request.headers.get("user-agent"):
        headers["user-agent"] = request.headers["user-agent"]
    headers["x-request-id"] = request.state.correlation_id
    return headers


def _upstream_response(response: httpx.Response, body: bytes) -> Response:
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


async def _stream_response(  # noqa: PLR0913
    chunks: AsyncIterator[bytes],
    first_chunk: bytes,
    context: Any,
    *,
    request_id: str,
    backend_id: str,
    cooldown_seconds: float,
    model: str,
    pricing: dict[str, Any],
    status_code: int,
) -> AsyncIterator[bytes]:
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
        while b"\n\n" in pending_event_bytes:
            event_payload, pending_event_bytes = pending_event_bytes.split(b"\n\n", 1)
            process_event_payload(event_payload)
        async for chunk in chunks:
            yield chunk
            pending_event_bytes += chunk
            while b"\n\n" in pending_event_bytes:
                event_payload, pending_event_bytes = pending_event_bytes.split(b"\n\n", 1)
                process_event_payload(event_payload)
    except httpx.HTTPError:
        await _set_backend_cooldown(
            backend_id,
            state=BackendHealthState.ERROR_COOLDOWN,
            cooldown_seconds=cooldown_seconds,
        )
        metric_status_code = 502
        yield b'data: {"error":{"message":"Upstream stream failed","type":"upstream_error"}}\n\n'
    finally:
        await context.__aexit__(None, None, None)
        await _credit_store.finalize_request(
            request_id,
            charge_reserved=True,
            charged_cost_usd=charged_cost,
        )
        await _metrics_store.observe_request(
            model=model,
            backend=backend_id,
            status_code=metric_status_code,
            latency_seconds=max(0.0, time.monotonic() - started_at),
            estimated_cost_usd=charged_cost,
        )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> Any:
    """Application lifespan handler."""
    # Startup
    settings = load_settings()
    setup_logging(settings.log_level)

    logger.info(
        "foundry_router_starting",
        version="0.1.0",
        backends=list(settings.backends.keys()),
        models=list(settings.models.keys()),
    )

    # Initialize backend client
    get_backend_client()
    await _credit_store.sync_from_settings(settings)
    global _reconciliation_loop  # noqa: PLW0603
    _reconciliation_loop = ReconciliationLoop(
        provider=_reconciliation_provider,
        credit_store=_credit_store,
        settings=settings,
        logger=logger,
    )
    await _reconciliation_loop.start()

    yield

    # Shutdown
    logger.info("foundry_router_shutting_down")
    await _reset_reconciliation_state()
    await close_backend_client()
    await _reset_credit_state()
    await _reset_metrics_state()


app = FastAPI(
    title="Foundry Router",
    description="OpenAI-compatible proxy for Azure AI Foundry with credit-aware routing",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def add_correlation_id(request: Request, call_next: Any) -> Response:
    """Add correlation ID to request and response headers."""
    supplied_id = request.headers.get("x-request-id")
    if supplied_id and re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", supplied_id):
        correlation_id = supplied_id
    else:
        correlation_id = str(uuid.uuid4())
    request.state.correlation_id = correlation_id

    # Bind correlation ID to structlog context
    structlog.contextvars.bind_contextvars(request_id=correlation_id)
    try:
        response: Response = await call_next(request)
        response.headers["x-request-id"] = correlation_id
        return response
    finally:
        structlog.contextvars.clear_contextvars()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler with structured error responses."""
    correlation_id = getattr(request.state, "correlation_id", "unknown")

    logger.error(
        "unhandled_exception",
        request_id=correlation_id,
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": "internal_error",
                "request_id": correlation_id,
            }
        },
    )


# Health endpoints (no authentication required)
@app.get("/health/live", tags=["Health"])
async def liveness() -> dict[str, str]:
    """Liveness probe - always returns 200 if process is running."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"])
async def readiness() -> Response:
    """Readiness probe - checks configuration validity and backend availability."""
    settings = load_settings()

    checks = {
        "config_valid": True,
        "backends_configured": len(settings.backends) > 0,
        "deployments_configured": bool(settings.backends)
        and all(config.deployment for config in settings.backends.values()),
        "models_configured": len(settings.models) > 0,
        "client_auth_configured": len(settings.client_api_keys) > 0,
        "admin_auth_configured": len(settings.admin_api_keys) > 0,
    }

    ready = all(checks.values())

    return JSONResponse(
        status_code=200 if ready else 503,
        content={"ready": ready, "checks": checks},
    )


def _admin_backend_status(
    name: str,
    config: Any,
    settings: Any,
    *,
    health_snapshot: BackendHealthSnapshot | None,
    credit_snapshot: BackendCreditLiveSnapshot | None,
) -> dict[str, Any]:
    live_status = {
        "health_state": health_snapshot.state if health_snapshot is not None else None,
        "cooldown_remaining_seconds": (
            round(health_snapshot.cooldown_remaining_seconds, 3)
            if health_snapshot is not None
            else None
        ),
        "credit_state": credit_snapshot.state if credit_snapshot is not None else None,
        "available_credit_usd": (
            round(credit_snapshot.available_credit_usd, 6) if credit_snapshot is not None else None
        ),
        "reserved_inflight_usd": (
            round(credit_snapshot.reserved_inflight_usd, 6) if credit_snapshot is not None else None
        ),
        "estimated_remaining_usd": (
            round(credit_snapshot.estimated_remaining_usd, 6)
            if credit_snapshot is not None
            else None
        ),
        "active_reservations": (
            credit_snapshot.active_reservations if credit_snapshot is not None else None
        ),
        "current_cycle_start_utc": (
            credit_snapshot.current_cycle_start_utc.isoformat()
            if credit_snapshot is not None
            else None
        ),
        "next_reset_utc": (
            credit_snapshot.next_reset_utc.isoformat() if credit_snapshot is not None else None
        ),
    }
    return {
        "endpoint": str(config.endpoint),
        "region": config.region,
        "deployment": config.deployment,
        "cycle_start_day": settings.backend_cycle_start_day.get(name),
        "cycle_allowance_usd": settings.backend_cycle_allowance_usd.get(name),
        "initial_estimated_remaining_usd": settings.backend_initial_estimated_remaining_usd.get(
            name
        ),
        "live": live_status,
    }


# Admin endpoint (requires admin authentication)
@app.get("/admin/status", tags=["Admin"], dependencies=[Depends(verify_admin_auth)])
async def admin_status(_request: Request) -> dict[str, Any]:
    """Administrative status endpoint - requires admin authentication."""
    settings = load_settings()
    backend_ids = list(settings.backends.keys())
    health_snapshots = await _snapshot_backend_health(backend_ids)
    await _credit_store.sync_from_settings(settings)
    credit_snapshots = await _credit_store.live_snapshot(
        backend_ids,
        min_credit_reserve_usd=settings.min_credit_reserve_usd,
        min_credit_reserve_percent=settings.min_credit_reserve_percent,
    )

    return {
        "version": "0.1.0",
        "backends": {
            name: _admin_backend_status(
                name,
                config,
                settings,
                health_snapshot=health_snapshots.get(name),
                credit_snapshot=credit_snapshots.get(name),
            )
            for name, config in settings.backends.items()
        },
        "models": {
            name: {
                "backends": pool.backends,
            }
            for name, pool in settings.models.items()
        },
        "config": {
            "reconciliation_interval_minutes": settings.reconciliation_interval_minutes,
            "min_credit_reserve_usd": settings.min_credit_reserve_usd,
            "min_credit_reserve_percent": settings.min_credit_reserve_percent,
            "retry_attempts": settings.retry_attempts,
            "retry_max_delay_seconds": settings.retry_max_delay_seconds,
            "protected_emergency_fallback": settings.protected_emergency_fallback,
        },
        "reconciliation": (
            _reconciliation_loop.status_snapshot()
            if _reconciliation_loop is not None
            else {
                "last_attempt_utc": None,
                "last_success_utc": None,
                "last_error": None,
                "last_updated_backends": 0,
                "consecutive_failures": 0,
                "stale": False,
            }
        ),
    }


@app.get("/metrics", tags=["Observability"], dependencies=[Depends(verify_admin_auth)])
async def metrics() -> Response:
    """Prometheus-compatible runtime metrics."""
    settings = load_settings()
    backend_ids = list(settings.backends.keys())
    health_snapshots = await _snapshot_backend_health(backend_ids)
    await _credit_store.sync_from_settings(settings)
    credit_snapshots = await _credit_store.live_snapshot(
        backend_ids,
        min_credit_reserve_usd=settings.min_credit_reserve_usd,
        min_credit_reserve_percent=settings.min_credit_reserve_percent,
    )
    payload = await _metrics_store.render_prometheus(
        backend_health_states={
            backend_id: health_snapshot.state
            for backend_id, health_snapshot in health_snapshots.items()
        },
        backend_available_credit_usd={
            backend_id: credit_snapshot.available_credit_usd
            for backend_id, credit_snapshot in credit_snapshots.items()
        },
    )
    return Response(content=payload, media_type="text/plain; version=0.0.4; charset=utf-8")


# OpenAI-compatible endpoints (require client authentication)


@app.get("/openai/v1/models", tags=["OpenAI"], dependencies=[Depends(verify_client_auth)])
async def list_models() -> dict[str, Any]:
    """List available logical models."""
    settings = load_settings()
    return {
        "object": "list",
        "data": [
            {
                "id": model_name,
                "object": "model",
                "owned_by": "foundry-router",
            }
            for model_name in settings.models
        ],
    }


@app.post("/openai/v1/responses", tags=["OpenAI"], dependencies=[Depends(verify_client_auth)])
async def create_response(request: Request) -> Response:
    """Forward a non-streaming or streaming Responses request."""
    body = await _request_body(request, "responses")
    if isinstance(body, JSONResponse):
        return body
    settings = load_settings()
    if body["model"] not in settings.models:
        return _api_error(404, f"Model '{body['model']}' not found", "model_not_found")
    headers = _forward_headers(request)

    if body.get("stream") is True:
        return await _execute_with_single_failover(
            settings,
            body["model"],
            operation="responses",
            body=body,
            request_id=request.state.correlation_id,
            execute_backend=lambda backend_id: _forward_streaming_with_retries(
                settings=settings,
                backend_id=backend_id,
                request_id=request.state.correlation_id,
                headers=headers,
                body=body,
            ),
        )

    return await _execute_with_single_failover(
        settings,
        body["model"],
        operation="responses",
        body=body,
        request_id=request.state.correlation_id,
        execute_backend=lambda backend_id: _forward_non_streaming_with_retries(
            settings=settings,
            backend_id=backend_id,
            operation="responses",
            headers=headers,
            body=body,
        ),
    )


@app.post("/openai/v1/embeddings", tags=["OpenAI"], dependencies=[Depends(verify_client_auth)])
async def create_embeddings(request: Request) -> Response:
    """Forward an embeddings request."""
    body = await _request_body(request, "embeddings")
    if isinstance(body, JSONResponse):
        return body
    settings = load_settings()
    if body["model"] not in settings.models:
        return _api_error(404, f"Model '{body['model']}' not found", "model_not_found")
    return await _execute_with_single_failover(
        settings,
        body["model"],
        operation="embeddings",
        body=body,
        request_id=request.state.correlation_id,
        execute_backend=lambda backend_id: _forward_non_streaming_with_retries(
            settings=settings,
            backend_id=backend_id,
            operation="embeddings",
            headers=_forward_headers(request),
            body=body,
        ),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
