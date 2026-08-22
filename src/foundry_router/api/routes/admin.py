"""Admin and observability endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from foundry_router.auth import verify_admin_auth


def _admin_backend_status(
    name: str,
    config: Any,
    settings: Any,
    *,
    health_snapshot: Any,
    credit_snapshot: Any,
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
        "next_reset_utc": credit_snapshot.next_reset_utc.isoformat()
        if credit_snapshot is not None
        else None,
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


def build_router(
    *,
    load_settings_fn: Any,
    health_store: Any,
    credit_store: Any,
    metrics_store: Any,
    reconciliation_status_snapshot: Any,
) -> APIRouter:
    router = APIRouter()

    @router.get("/admin/status", tags=["Admin"], dependencies=[Depends(verify_admin_auth)])
    async def admin_status(_request: Request) -> dict[str, Any]:
        settings = load_settings_fn()
        backend_ids = list(settings.backends.keys())
        health_snapshots = await health_store.snapshot_backend_health(backend_ids)
        await credit_store.sync_from_settings(settings)
        credit_snapshots = await credit_store.live_snapshot(
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
            "reconciliation": reconciliation_status_snapshot(),
        }

    @router.get("/metrics", tags=["Observability"], dependencies=[Depends(verify_admin_auth)])
    async def metrics() -> Response:
        settings = load_settings_fn()
        backend_ids = list(settings.backends.keys())
        health_snapshots = await health_store.snapshot_backend_health(backend_ids)
        await credit_store.sync_from_settings(settings)
        credit_snapshots = await credit_store.live_snapshot(
            backend_ids,
            min_credit_reserve_usd=settings.min_credit_reserve_usd,
            min_credit_reserve_percent=settings.min_credit_reserve_percent,
        )
        payload = await metrics_store.render_prometheus(
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

    return router
