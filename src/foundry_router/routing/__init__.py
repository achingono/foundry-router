"""Candidate ranking, credit-aware selection, and single failover orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from fastapi import Response
from fastapi.responses import StreamingResponse

from foundry_router.credit import (
    CreditState,
    estimate_request_cost,
    score_credit_assessment,
)
from foundry_router.health import (
    COOLDOWN_STATES,
    BackendHealthState,
    cooldown_exhausted_response,
)


@dataclass(frozen=True)
class BackendSelectionResult:
    backend_id: str | None
    candidates: list[str]
    snapshots: dict[str, Any]
    insufficient_credit_capacity: bool


def ranked_model_backends(
    settings: Any, model: str, *, excluded: set[str] | None = None
) -> list[str]:
    pool = settings.models.get(model)
    if pool is None:
        return []
    excluded_ids = excluded or set()
    ranked = [backend for backend in pool.backends if backend not in excluded_ids]
    return sorted(ranked, key=lambda backend: (-pool.backends[backend], backend))


def select_backend(settings: Any, model: str) -> str | None:
    ranked = ranked_model_backends(settings, model)
    if not ranked:
        return None
    return ranked[0]


async def select_candidate_backend(
    settings: Any,
    model: str,
    *,
    operation: str,
    body: dict[str, Any],
    request_id: str,
    health_store: Any,
    credit_store: Any,
    logger: Any,
    excluded: set[str] | None = None,
) -> BackendSelectionResult:
    ranked_candidates = ranked_model_backends(settings, model, excluded=excluded)
    if not ranked_candidates:
        return BackendSelectionResult(None, [], {}, False)

    snapshots = await health_store.snapshot_backend_health(ranked_candidates)
    await credit_store.sync_from_settings(settings)

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
        assessment = await credit_store.assess(
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
        reserved = await credit_store.try_assign_reservation(
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


async def all_candidates_cooldown_response(
    settings: Any,
    model: str,
    *,
    health_store: Any,
    api_error: Any,
) -> Any:
    candidates = ranked_model_backends(settings, model)
    if not candidates:
        return None
    snapshots = await health_store.snapshot_backend_health(candidates)
    return cooldown_exhausted_response(candidates, snapshots, api_error=api_error)


async def execute_with_single_failover(
    settings: Any,
    model: str,
    *,
    operation: str,
    body: dict[str, Any],
    request_id: str,
    execute_backend: Any,
    health_store: Any,
    credit_store: Any,
    metrics_store: Any,
    logger: Any,
    api_error: Any,
    finalize_non_streaming_credit: Any,
) -> Response:
    started_at = time.monotonic()

    async def record_and_return(
        response: Response,
        *,
        backend_id: str | None,
        actual_cost_usd: float | None = None,
    ) -> Response:
        if isinstance(response, StreamingResponse):
            return response
        await metrics_store.observe_request(
            model=model,
            backend=backend_id or "none",
            status_code=response.status_code,
            latency_seconds=max(0.0, time.monotonic() - started_at),
            estimated_cost_usd=actual_cost_usd,
        )
        return response

    first_selection = await select_candidate_backend(
        settings,
        model,
        operation=operation,
        body=body,
        request_id=request_id,
        health_store=health_store,
        credit_store=credit_store,
        logger=logger,
    )
    if first_selection.backend_id is None:
        candidate_cooldown_response = cooldown_exhausted_response(
            first_selection.candidates,
            first_selection.snapshots,
            api_error=api_error,
        )
        if candidate_cooldown_response is not None:
            return await record_and_return(candidate_cooldown_response, backend_id=None)
        if first_selection.insufficient_credit_capacity:
            return await record_and_return(
                api_error(
                    503,
                    "No backend has sufficient estimated credit capacity",
                    "insufficient_credit_capacity",
                ),
                backend_id=None,
            )
        return await record_and_return(
            api_error(
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
                finalized_cost = await finalize_non_streaming_credit(
                    request_id=request_id,
                    model=model,
                    settings=settings,
                    response=first_result.response,
                )
                reservation_closed_or_transferred = True
                return await record_and_return(
                    first_result.response,
                    backend_id=first_backend_id,
                    actual_cost_usd=finalized_cost,
                )
            reservation_closed_or_transferred = True
            return await record_and_return(first_result.response, backend_id=first_backend_id)

        second_selection = await select_candidate_backend(
            settings,
            model,
            operation=operation,
            body=body,
            request_id=request_id,
            health_store=health_store,
            credit_store=credit_store,
            logger=logger,
            excluded={first_backend_id},
        )
        second_backend_id = second_selection.backend_id
        if second_backend_id is None:
            if (
                first_result.response.status_code >= 500
                and second_selection.insufficient_credit_capacity
            ):
                await finalize_non_streaming_credit(
                    request_id=request_id,
                    model=model,
                    settings=settings,
                    response=first_result.response,
                )
                reservation_closed_or_transferred = True
                return await record_and_return(
                    api_error(
                        503,
                        "No backend has sufficient estimated credit capacity",
                        "insufficient_credit_capacity",
                    ),
                    backend_id=first_backend_id,
                )
            all_cooldown = await all_candidates_cooldown_response(
                settings,
                model,
                health_store=health_store,
                api_error=api_error,
            )
            if all_cooldown is not None:
                await finalize_non_streaming_credit(
                    request_id=request_id,
                    model=model,
                    settings=settings,
                    response=first_result.response,
                )
                reservation_closed_or_transferred = True
                return await record_and_return(all_cooldown, backend_id=first_backend_id)
            candidate_cooldown_response = cooldown_exhausted_response(
                second_selection.candidates,
                second_selection.snapshots,
                api_error=api_error,
            )
            if candidate_cooldown_response is not None:
                await finalize_non_streaming_credit(
                    request_id=request_id,
                    model=model,
                    settings=settings,
                    response=first_result.response,
                )
                reservation_closed_or_transferred = True
                return await record_and_return(
                    candidate_cooldown_response, backend_id=first_backend_id
                )
            finalized_cost = await finalize_non_streaming_credit(
                request_id=request_id,
                model=model,
                settings=settings,
                response=first_result.response,
            )
            reservation_closed_or_transferred = True
            return await record_and_return(
                first_result.response,
                backend_id=first_backend_id,
                actual_cost_usd=finalized_cost,
            )

        if not isinstance(first_result.response, StreamingResponse):
            await metrics_store.observe_request(
                model=model,
                backend=first_backend_id,
                status_code=first_result.response.status_code,
                latency_seconds=max(0.0, time.monotonic() - started_at),
                estimated_cost_usd=None,
            )

        second_result = await execute_backend(second_backend_id)
        if not isinstance(second_result.response, StreamingResponse):
            finalized_cost = await finalize_non_streaming_credit(
                request_id=request_id,
                model=model,
                settings=settings,
                response=second_result.response,
            )
            reservation_closed_or_transferred = True
            if second_result.retryable_failure:
                all_cooldown = await all_candidates_cooldown_response(
                    settings,
                    model,
                    health_store=health_store,
                    api_error=api_error,
                )
                if all_cooldown is not None:
                    return await record_and_return(all_cooldown, backend_id=second_backend_id)
            return await record_and_return(
                second_result.response,
                backend_id=second_backend_id,
                actual_cost_usd=finalized_cost,
            )
        reservation_closed_or_transferred = True
        return await record_and_return(second_result.response, backend_id=second_backend_id)
    finally:
        if not reservation_closed_or_transferred:
            await credit_store.finalize_request(
                request_id,
                charge_reserved=False,
                charged_cost_usd=None,
            )
