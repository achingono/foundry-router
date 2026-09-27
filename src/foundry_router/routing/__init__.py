"""Candidate ranking, credit-aware selection, and single failover orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from fastapi import Response
from fastapi.responses import StreamingResponse

from foundry_router.credit import (
    CreditAssessment,
    CreditAssessmentContext,
    CreditReservePolicy,
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
    pricing_unavailable: bool = False
    rate_limit_unavailable: bool = False


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
    rate_limit_store: Any | None = None,
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
            reason="pricing_unavailable",
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
        return BackendSelectionResult(None, ranked_candidates, snapshots, False, True)

    quota_limits = getattr(settings, "quota_group_rate_limits", {})
    quota_group_by_backend = {
        backend_id: (getattr(settings.backends[backend_id], "quota_group", None) or backend_id)
        for backend_id in ranked_candidates
    }
    configured_groups = sorted(
        {
            quota_group
            for quota_group in quota_group_by_backend.values()
            if quota_group in quota_limits
        }
    )
    quota_snapshots: dict[str, Any] = {}
    if (
        rate_limit_store is not None
        and hasattr(rate_limit_store, "sync_from_settings")
        and (
            getattr(rate_limit_store, "quota_limits", None) != quota_limits
            or getattr(rate_limit_store, "reservation_max_age_seconds", None)
            != settings.reservation_max_age_seconds
        )
    ):
        await rate_limit_store.sync_from_settings(settings)
    if rate_limit_store is not None and configured_groups:
        quota_snapshots = await rate_limit_store.snapshot_quota_groups(configured_groups)
        exhausted_groups = {
            quota_group
            for quota_group, quota_snapshot in quota_snapshots.items()
            if quota_snapshot.exhausted
        }
        for quota_group in exhausted_groups:
            quota_snapshot = quota_snapshots[quota_group]
            cooldown_seconds = getattr(quota_snapshot, "retry_after_seconds", None) or 1.0
            for backend_id, backend_config in settings.backends.items():
                backend_group = getattr(backend_config, "quota_group", None) or backend_id
                if backend_group == quota_group:
                    await health_store.set_backend_cooldown(
                        backend_id,
                        state=BackendHealthState.QUOTA_COOLDOWN,
                        cooldown_seconds=cooldown_seconds,
                    )
        if exhausted_groups:
            snapshots = await health_store.snapshot_backend_health(ranked_candidates)

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

    def quota_headroom(backend_id: str) -> float | None:
        quota_group = quota_group_by_backend[backend_id]
        limits = quota_limits.get(quota_group)
        quota_snapshot = quota_snapshots.get(quota_group)
        if not limits or quota_snapshot is None:
            return None

        headroom_ratios: list[float] = []
        if "rpm" in limits:
            headroom_ratios.append((quota_snapshot.remaining_rpm - 1) / limits["rpm"])
        if "tpm" in limits:
            headroom_ratios.append(
                (quota_snapshot.remaining_input_tpm - estimate.input_tokens) / limits["tpm"]
            )
        if "rpd" in limits:
            headroom_ratios.append((quota_snapshot.remaining_rpd - 1) / limits["rpd"])
        return max(0.0, min(1.0, *headroom_ratios)) if headroom_ratios else None

    def quota_can_fit(backend_id: str) -> bool:
        limits = quota_limits.get(quota_group_by_backend[backend_id])
        quota_snapshot = quota_snapshots.get(quota_group_by_backend[backend_id])
        if not limits or quota_snapshot is None:
            return True
        return (
            not quota_snapshot.exhausted
            and ("rpm" not in limits or quota_snapshot.remaining_rpm >= 1)
            and ("tpm" not in limits or quota_snapshot.remaining_input_tpm >= estimate.input_tokens)
            and ("rpd" not in limits or quota_snapshot.remaining_rpd >= 1)
        )

    quota_eligible = [backend_id for backend_id in health_eligible if quota_can_fit(backend_id)]
    protected_quota_fallback = (
        not quota_eligible
        and settings.protected_emergency_fallback
        and len(ranked_candidates) == 1
        and health_eligible == ranked_candidates
    )
    if protected_quota_fallback:
        quota_eligible = health_eligible

    if not quota_eligible:
        logger.info(
            "routing_decision",
            model=model,
            operation=operation,
            request_id=request_id,
            selected_backend=None,
            reason=(
                "rate_limit_capacity_unavailable"
                if health_eligible
                else "all_candidates_in_cooldown_or_disabled"
            ),
            estimated_request_cost_usd=estimate.estimated_cost_usd,
            candidates=[
                {
                    "backend_id": backend_id,
                    "health_state": snapshots[backend_id].state,
                    "cooldown_remaining_seconds": round(
                        snapshots[backend_id].cooldown_remaining_seconds,
                        3,
                    ),
                    "quota_group": quota_group_by_backend[backend_id],
                    "quota_headroom": quota_headroom(backend_id),
                    "remaining_rpm": (
                        quota_snapshots[quota_group_by_backend[backend_id]].remaining_rpm
                        if quota_group_by_backend[backend_id] in quota_snapshots
                        else None
                    ),
                    "remaining_input_tpm": (
                        quota_snapshots[quota_group_by_backend[backend_id]].remaining_input_tpm
                        if quota_group_by_backend[backend_id] in quota_snapshots
                        else None
                    ),
                    "remaining_rpd": (
                        quota_snapshots[quota_group_by_backend[backend_id]].remaining_rpd
                        if quota_group_by_backend[backend_id] in quota_snapshots
                        else None
                    ),
                }
                for backend_id in ranked_candidates
            ],
        )
        return BackendSelectionResult(
            None,
            ranked_candidates,
            snapshots,
            False,
            rate_limit_unavailable=bool(health_eligible),
        )

    scored_candidates: list[tuple[float, float, str]] = []
    candidate_details: list[dict[str, Any]] = []
    has_credit_capacity = False
    rate_limit_reservation_failed = False
    for backend_id in quota_eligible:
        credit_metered = settings.backends[backend_id].credit_metered
        if not credit_metered:
            assessment = CreditAssessment(
                state=CreditState.USABLE,
                available_credit_usd=0.0,
                projected_unused_credit_usd=0.0,
                estimated_request_cost_usd=0.0,
                cycle_allowance_usd=0.0,
            )
        elif hasattr(credit_store, "assess_with_context"):
            # Use bundled context when available; retain scalar args for test doubles.
            ctx = CreditAssessmentContext(
                reserve_policy=CreditReservePolicy(
                    min_credit_reserve_usd=settings.min_credit_reserve_usd,
                    min_credit_reserve_percent=settings.min_credit_reserve_percent,
                ),
                reservation_max_age_seconds=settings.reservation_max_age_seconds,
            )
            assessment = await credit_store.assess_with_context(
                backend_id, estimate.estimated_cost_usd, ctx
            )
        else:
            assessment = await credit_store.assess(
                backend_id,
                estimate.estimated_cost_usd,
                min_credit_reserve_usd=settings.min_credit_reserve_usd,
                min_credit_reserve_percent=settings.min_credit_reserve_percent,
                reservation_max_age_seconds=settings.reservation_max_age_seconds,
            )
        candidate_detail = {
            "backend_id": backend_id,
            "health_state": snapshots[backend_id].state,
            "cooldown_remaining_seconds": round(
                snapshots[backend_id].cooldown_remaining_seconds,
                3,
            ),
            "credit_state": assessment.state if credit_metered else "NOT_METERED",
            "available_credit_usd": assessment.available_credit_usd if credit_metered else None,
            "projected_unused_credit_usd": (
                assessment.projected_unused_credit_usd if credit_metered else None
            ),
            "estimated_request_cost_usd": assessment.estimated_request_cost_usd,
            "cycle_allowance_usd": assessment.cycle_allowance_usd if credit_metered else None,
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
            quota_headroom=quota_headroom(backend_id),
            credit_metered=credit_metered,
        )
        candidate_detail["score"] = score
        candidate_detail["quota_group"] = quota_group_by_backend[backend_id]
        candidate_detail["quota_headroom"] = quota_headroom(backend_id)
        quota_snapshot = quota_snapshots.get(quota_group_by_backend[backend_id])
        if quota_snapshot is not None:
            candidate_detail["remaining_rpm"] = quota_snapshot.remaining_rpm
            candidate_detail["remaining_input_tpm"] = quota_snapshot.remaining_input_tpm
            candidate_detail["remaining_rpd"] = quota_snapshot.remaining_rpd
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
        credit_metered = settings.backends[backend_id].credit_metered
        if not credit_metered:
            reserved = True
            if hasattr(credit_store, "finalize_request"):
                try:
                    await credit_store.finalize_request(
                        request_id,
                        backend_id=None,
                        charge_reserved=False,
                        charged_cost_usd=None,
                    )
                except TypeError as exc:
                    if "backend_id" not in str(exc):
                        raise
                    await credit_store.finalize_request(
                        request_id,
                        charge_reserved=False,
                        charged_cost_usd=None,
                    )
        elif hasattr(credit_store, "try_assign_with_context"):
            ctx2 = CreditAssessmentContext(
                reserve_policy=CreditReservePolicy(
                    min_credit_reserve_usd=settings.min_credit_reserve_usd,
                    min_credit_reserve_percent=settings.min_credit_reserve_percent,
                ),
                reservation_max_age_seconds=settings.reservation_max_age_seconds,
            )
            reserved = await credit_store.try_assign_with_context(
                request_id, backend_id, estimate.estimated_cost_usd, ctx2
            )
        else:
            reserved = await credit_store.try_assign_reservation(
                request_id,
                backend_id,
                estimate.estimated_cost_usd,
                min_credit_reserve_usd=settings.min_credit_reserve_usd,
                min_credit_reserve_percent=settings.min_credit_reserve_percent,
                reservation_max_age_seconds=settings.reservation_max_age_seconds,
            )
        if reserved:
            quota_group = quota_group_by_backend[backend_id]
            if rate_limit_store is not None and quota_group in quota_limits:
                quota_reserved = await rate_limit_store.try_reserve_estimate(
                    request_id,
                    quota_group,
                    estimated_input_tokens=estimate.input_tokens,
                    reservation_max_age_seconds=settings.reservation_max_age_seconds,
                    allow_over_limit=protected_quota_fallback,
                )
                if not quota_reserved:
                    rate_limit_reservation_failed = True
                    try:
                        await credit_store.finalize_request(
                            request_id,
                            backend_id=backend_id,
                            charge_reserved=False,
                            charged_cost_usd=None,
                        )
                    except TypeError as exc:
                        if "backend_id" not in str(exc):
                            raise
                        await credit_store.finalize_request(
                            request_id,
                            charge_reserved=False,
                            charged_cost_usd=None,
                        )
                    continue
            logger.info(
                "routing_decision",
                model=model,
                operation=operation,
                request_id=request_id,
                selected_backend=backend_id,
                reason="selected",
                estimated_request_cost_usd=estimate.estimated_cost_usd,
                protected_quota_fallback=protected_quota_fallback,
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
    return BackendSelectionResult(
        None,
        ranked_candidates,
        snapshots,
        not rate_limit_reservation_failed,
        rate_limit_unavailable=rate_limit_reservation_failed,
    )


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
    rate_limit_store: Any | None = None,
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
        rate_limit_store=rate_limit_store,
    )
    if first_selection.backend_id is None:
        if first_selection.pricing_unavailable:
            return await record_and_return(
                api_error(
                    503,
                    "Model pricing is unavailable for routing decisions",
                    "pricing_unavailable",
                ),
                backend_id=None,
            )
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
        if first_selection.rate_limit_unavailable:
            return await record_and_return(
                api_error(
                    429,
                    "Configured quota limits cannot accommodate the request",
                    "rate_limit_exhausted",
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
                    backend_id=first_backend_id,
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
            rate_limit_store=rate_limit_store,
            excluded={first_backend_id},
        )
        second_backend_id = second_selection.backend_id
        if second_backend_id is None:
            if second_selection.pricing_unavailable:
                await finalize_non_streaming_credit(
                    request_id=request_id,
                    model=model,
                    settings=settings,
                    response=first_result.response,
                    backend_id=first_backend_id,
                )
                reservation_closed_or_transferred = True
                return await record_and_return(
                    api_error(
                        503,
                        "Model pricing is unavailable for routing decisions",
                        "pricing_unavailable",
                    ),
                    backend_id=first_backend_id,
                )
            if (
                first_result.response.status_code >= 500
                and second_selection.insufficient_credit_capacity
            ):
                await finalize_non_streaming_credit(
                    request_id=request_id,
                    model=model,
                    settings=settings,
                    response=first_result.response,
                    backend_id=first_backend_id,
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
                    backend_id=first_backend_id,
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
                    backend_id=first_backend_id,
                )
                reservation_closed_or_transferred = True
                return await record_and_return(
                    candidate_cooldown_response, backend_id=first_backend_id
                )
            if second_selection.rate_limit_unavailable:
                await finalize_non_streaming_credit(
                    request_id=request_id,
                    model=model,
                    settings=settings,
                    response=first_result.response,
                    backend_id=first_backend_id,
                )
                reservation_closed_or_transferred = True
                return await record_and_return(
                    api_error(
                        429,
                        "Configured quota limits cannot accommodate the request",
                        "rate_limit_exhausted",
                    ),
                    backend_id=first_backend_id,
                )
            finalized_cost = await finalize_non_streaming_credit(
                request_id=request_id,
                model=model,
                settings=settings,
                response=first_result.response,
                backend_id=first_backend_id,
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
                backend_id=second_backend_id,
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
            if rate_limit_store is not None:
                await rate_limit_store.release_request(request_id)
            try:
                await credit_store.finalize_request(
                    request_id,
                    backend_id=None,
                    charge_reserved=False,
                    charged_cost_usd=None,
                )
            except TypeError as exc:
                if "backend_id" in str(exc):
                    await credit_store.finalize_request(
                        request_id,
                        charge_reserved=False,
                        charged_cost_usd=None,
                    )
                else:
                    raise
