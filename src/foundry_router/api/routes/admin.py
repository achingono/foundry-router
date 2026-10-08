"""Admin and observability endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from foundry_router.auth import verify_admin_auth
from foundry_router.credit_groups import credit_membership, metered_credit_groups


async def _rate_limit_snapshots_by_backend(settings: Any, rate_limit_store: Any) -> dict[str, Any]:
    if rate_limit_store is None:
        return {}

    await rate_limit_store.sync_from_settings(settings)
    group_by_backend = {
        backend_id: (getattr(config, "quota_group", None) or backend_id)
        for backend_id, config in settings.backends.items()
    }
    groups = sorted(
        {
            quota_group
            for quota_group in group_by_backend.values()
            if quota_group in settings.quota_group_rate_limits
        }
    )
    group_snapshots = await rate_limit_store.snapshot_quota_groups(groups)
    return {
        backend_id: group_snapshots[quota_group]
        for backend_id, quota_group in group_by_backend.items()
        if quota_group in group_snapshots
    }


def _admin_backend_status(
    name: str,
    config: Any,
    settings: Any,
    *,
    health_snapshot: Any,
    credit_snapshot: Any,
    rate_limit_snapshot: Any = None,
) -> dict[str, Any]:
    group = getattr(config, "credit_group", None) or name
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
        "oldest_reservation_age_seconds": (
            round(credit_snapshot.oldest_reservation_age_seconds, 3)
            if credit_snapshot is not None
            and credit_snapshot.oldest_reservation_age_seconds is not None
            else None
        ),
        "current_cycle_start_utc": (
            credit_snapshot.current_cycle_start_utc.isoformat()
            if credit_snapshot is not None
            else None
        ),
        "next_reset_utc": credit_snapshot.next_reset_utc.isoformat()
        if credit_snapshot is not None
        else None,
        "rate_limit": (
            {
                "quota_group": rate_limit_snapshot.quota_group,
                "rpm_used_60s": rate_limit_snapshot.rpm_used_60s,
                "input_tpm_used_60s": rate_limit_snapshot.input_tpm_used_60s,
                "rpd_used": rate_limit_snapshot.rpd_used,
                "remaining_rpm": rate_limit_snapshot.remaining_rpm,
                "remaining_input_tpm": rate_limit_snapshot.remaining_input_tpm,
                "remaining_rpd": rate_limit_snapshot.remaining_rpd,
                "exhausted": rate_limit_snapshot.exhausted,
                "retry_after_seconds": rate_limit_snapshot.retry_after_seconds,
            }
            if rate_limit_snapshot is not None
            else None
        ),
    }
    return {
        "endpoint": str(config.endpoint),
        "provider": getattr(config, "provider", "azure_foundry"),
        "api_surface": getattr(config, "api_surface", "openai_compat"),
        "region": config.region,
        "deployment": config.deployment,
        "supported_operations": list(getattr(config, "supported_operations", []) or []),
        "google_features": list(config.google_features.features),
        "credit_group": group,
        "cycle_start_day": settings.backend_cycle_start_day.get(group),
        "cycle_allowance_usd": settings.backend_cycle_allowance_usd.get(group),
        "initial_estimated_remaining_usd": settings.backend_initial_estimated_remaining_usd.get(
            group
        ),
        "live": live_status,
    }


def build_router(
    *,
    load_settings_fn: Any,
    health_store: Any,
    credit_store: Any,
    metrics_store: Any,
    rate_limit_store: Any | None = None,
    reconciliation_status_snapshot: Any,
    exclusion_store: Any = None,
) -> APIRouter:
    router = APIRouter()

    @router.get("/admin/status", tags=["Admin"], dependencies=[Depends(verify_admin_auth)])
    async def admin_status(_request: Request) -> dict[str, Any]:
        settings = load_settings_fn()
        backend_ids = list(settings.backends.keys())
        health_snapshots = await health_store.snapshot_backend_health(backend_ids)
        exclusion_snapshot: dict[str, Any] = {}
        if exclusion_store is not None:
            raw_snapshot = await exclusion_store.snapshot()
            for key, info in raw_snapshot.items():
                try:
                    backend_id, operation, stream_mode = key
                except (TypeError, ValueError):
                    continue
                if not isinstance(info, dict):
                    continue
                logical_models = sorted(
                    model_name
                    for model_name, pool in settings.models.items()
                    if backend_id in getattr(pool, "backends", {})
                )
                mode = "stream" if stream_mode else "nonstream"
                exclusion_snapshot[f"{backend_id}\u241e{operation}\u241e{mode}"] = {
                    "backend_id": backend_id,
                    "operation": operation,
                    "stream_mode": mode,
                    "consecutive_failures": info.get("consecutive_failures", 0),
                    "excluded": bool(info.get("excluded", False)),
                    "excluded_until_wall": info.get("excluded_until_wall"),
                    "logical_models": logical_models,
                }
        await credit_store.sync_from_settings(settings)
        aliases = credit_membership(settings)
        groups = sorted(metered_credit_groups(settings))
        credit_snapshots = await credit_store.live_snapshot(
            groups,
            min_credit_reserve_usd=settings.min_credit_reserve_usd,
            min_credit_reserve_percent=settings.min_credit_reserve_percent,
        )
        rate_limit_snapshots = await _rate_limit_snapshots_by_backend(settings, rate_limit_store)

        return {
            "version": "0.1.0",
            "credit_groups": {
                group: {
                    "cycle_start_day": settings.backend_cycle_start_day.get(group),
                    "cycle_allowance_usd": settings.backend_cycle_allowance_usd.get(group),
                    "initial_estimated_remaining_usd": settings.backend_initial_estimated_remaining_usd.get(
                        group
                    ),
                    "live": {
                        "credit_state": snapshot.state,
                        "available_credit_usd": snapshot.available_credit_usd,
                        "estimated_remaining_usd": snapshot.estimated_remaining_usd,
                        "reserved_inflight_usd": snapshot.reserved_inflight_usd,
                        "active_reservations": snapshot.active_reservations,
                        "oldest_reservation_age_seconds": snapshot.oldest_reservation_age_seconds,
                        "current_cycle_start_utc": snapshot.current_cycle_start_utc.isoformat(),
                        "next_reset_utc": snapshot.next_reset_utc.isoformat(),
                    }
                    if (snapshot := credit_snapshots.get(group)) is not None
                    else None,
                }
                for group in groups
            },
            "backends": {
                name: _admin_backend_status(
                    name,
                    config,
                    settings,
                    health_snapshot=health_snapshots.get(name),
                    credit_snapshot=credit_snapshots.get(aliases[name]),
                    rate_limit_snapshot=rate_limit_snapshots.get(name),
                )
                for name, config in settings.backends.items()
            },
            "models": {
                name: {
                    "backends": pool.backends,
                }
                for name, pool in settings.models.items()
            },
            "model_aliases": dict(getattr(settings, "model_aliases", {}) or {}),
            "combination_exclusions": exclusion_snapshot,
            "config": {
                "reconciliation_interval_minutes": settings.reconciliation_interval_minutes,
                "min_credit_reserve_usd": settings.min_credit_reserve_usd,
                "min_credit_reserve_percent": settings.min_credit_reserve_percent,
                "retry_attempts": settings.retry_attempts,
                "retry_max_delay_seconds": settings.retry_max_delay_seconds,
                "protected_emergency_fallback": settings.protected_emergency_fallback,
            },
            "reconciliation": reconciliation_status_snapshot(),
        }

    @router.get("/metrics", tags=["Observability"], dependencies=[Depends(verify_admin_auth)])
    async def metrics() -> Response:
        settings = load_settings_fn()
        backend_ids = list(settings.backends.keys())
        health_snapshots = await health_store.snapshot_backend_health(backend_ids)
        await credit_store.sync_from_settings(settings)
        aliases = credit_membership(settings)
        credit_snapshots = await credit_store.live_snapshot(
            sorted(metered_credit_groups(settings)),
            min_credit_reserve_usd=settings.min_credit_reserve_usd,
            min_credit_reserve_percent=settings.min_credit_reserve_percent,
        )
        rate_limit_snapshots = await _rate_limit_snapshots_by_backend(settings, rate_limit_store)
        payload = await metrics_store.render_prometheus(
            backend_health_states={
                backend_id: health_snapshot.state
                for backend_id, health_snapshot in health_snapshots.items()
            },
            backend_available_credit_usd={
                backend_id: credit_snapshots[group].available_credit_usd
                for backend_id, group in aliases.items()
                if group in credit_snapshots
            },
            credit_group_available_credit_usd={
                group: snapshot.available_credit_usd for group, snapshot in credit_snapshots.items()
            },
            backend_rate_limit_snapshots=rate_limit_snapshots,
            model_aliases=dict(getattr(settings, "model_aliases", {}) or {}),
        )
        return Response(content=payload, media_type="text/plain; version=0.0.4; charset=utf-8")

    return router
