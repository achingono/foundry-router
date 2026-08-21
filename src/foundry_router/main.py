"""Foundry Router main application."""

from __future__ import annotations

import re
import uuid
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from structlog import get_logger

from foundry_router.auth import verify_admin_auth, verify_client_auth
from foundry_router.backends import close_backend_client, get_backend_client
from foundry_router.config import load_settings
from foundry_router.logging import setup_logging

logger = get_logger(__name__)


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

    yield

    # Shutdown
    logger.info("foundry_router_shutting_down")
    await close_backend_client()


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
        "models_configured": len(settings.models) > 0,
        "client_auth_configured": len(settings.client_api_keys) > 0,
        "admin_auth_configured": len(settings.admin_api_keys) > 0,
    }

    ready = all(checks.values())

    return JSONResponse(
        status_code=200 if ready else 503,
        content={"ready": ready, "checks": checks},
    )


# Admin endpoint (requires admin authentication)
@app.get("/admin/status", tags=["Admin"], dependencies=[Depends(verify_admin_auth)])
async def admin_status(_request: Request) -> dict[str, Any]:
    """Administrative status endpoint - requires admin authentication."""
    settings = load_settings()

    return {
        "version": "0.1.0",
        "backends": {
            name: {
                "endpoint": str(config.endpoint),
                "region": config.region,
                "deployment": config.deployment,
                "cycle_start_day": settings.backend_cycle_start_day.get(name),
            }
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
    }


# OpenAI-compatible endpoints (require client authentication)
# These are stubs for Phase 1 - full implementation in Phase 2+


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
async def create_response(_request: Request) -> Response:
    """Create a response - stub implementation."""
    return JSONResponse(
        status_code=501,
        content={
            "error": {
                "message": "Responses API not yet implemented",
                "type": "not_implemented",
            }
        },
    )


@app.post("/openai/v1/embeddings", tags=["OpenAI"], dependencies=[Depends(verify_client_auth)])
async def create_embeddings(_request: Request) -> Response:
    """Create embeddings - stub implementation."""
    return JSONResponse(
        status_code=501,
        content={
            "error": {
                "message": "Embeddings API not yet implemented",
                "type": "not_implemented",
            }
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
