"""Health endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from foundry_router.credit_groups import credit_membership


def build_router(*, load_settings_fn: Any, extra_checks_fn: Any | None = None) -> APIRouter:
    router = APIRouter(tags=["Health"])

    @router.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "alive"}

    @router.get("/health/ready")
    async def readiness() -> Response:
        settings = load_settings_fn()
        aliases = credit_membership(settings)
        routable_backend_ids = {
            backend_id for pool in settings.models.values() for backend_id in pool.backends
        }
        metered_backend_ids = {
            aliases.get(backend_id, backend_id)
            for backend_id in routable_backend_ids
            if backend_id not in settings.backends or settings.backends[backend_id].credit_metered
        }
        backend_credit_config_complete = all(
            backend_id in settings.backend_cycle_start_day
            and backend_id in settings.backend_cycle_allowance_usd
            and backend_id in settings.backend_initial_estimated_remaining_usd
            for backend_id in metered_backend_ids
        )
        model_pricing_complete = all(
            model_name in settings.pricing for model_name in settings.models
        )
        checks = {
            "config_valid": True,
            "backends_configured": len(settings.backends) > 0,
            "deployments_configured": bool(settings.backends)
            and all(config.deployment for config in settings.backends.values()),
            "models_configured": len(settings.models) > 0,
            "client_auth_configured": len(settings.client_api_keys) > 0,
            "admin_auth_configured": len(settings.admin_api_keys) > 0,
            "backend_credit_config_complete": backend_credit_config_complete,
            "model_pricing_complete": model_pricing_complete,
        }
        if extra_checks_fn is not None:
            extra = await extra_checks_fn()
            checks = {**checks, **dict(extra)}
        ready = all(checks.values())
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"ready": ready, "checks": checks},
        )

    return router
