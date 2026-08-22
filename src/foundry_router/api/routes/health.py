"""Health endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse


def build_router(*, load_settings_fn: Any) -> APIRouter:
    router = APIRouter(tags=["Health"])

    @router.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "alive"}

    @router.get("/health/ready")
    async def readiness() -> Response:
        settings = load_settings_fn()
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

    return router
