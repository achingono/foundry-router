"""Foundry Router main application."""

from __future__ import annotations

import re
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import httpx
import structlog
from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from structlog import get_logger

from foundry_router.auth import verify_admin_auth, verify_client_auth
from foundry_router.backends import close_backend_client, get_backend_client
from foundry_router.config import load_settings
from foundry_router.logging import setup_logging

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger(__name__)
MAX_UPSTREAM_ERROR_BYTES = 64 * 1024
HTTP_OK = 200
HTTP_SUCCESS_LIMIT = 300


def _select_backend(settings: Any, model: str) -> str | None:
    pool = settings.models.get(model)
    if pool is None:
        return None
    highest_weight = max(pool.backends.values())
    return str(
        min(backend for backend, weight in pool.backends.items() if weight == highest_weight)
    )


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
    return Response(
        content=body, status_code=response.status_code, media_type=content_type.split(";", 1)[0]
    )


async def _stream_response(
    chunks: AsyncIterator[bytes],
    first_chunk: bytes,
    context: Any,
) -> AsyncIterator[bytes]:
    try:
        yield first_chunk
        async for chunk in chunks:
            yield chunk
    except httpx.HTTPError:
        yield b'data: {"error":{"message":"Upstream stream failed","type":"upstream_error"}}\n\n'
    finally:
        await context.__aexit__(None, None, None)


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
async def create_response(request: Request) -> Response:  # noqa: PLR0911
    """Forward a non-streaming or streaming Responses request."""
    body = await _request_body(request, "responses")
    if isinstance(body, JSONResponse):
        return body
    settings = load_settings()
    backend_id = _select_backend(settings, body["model"])
    if backend_id is None:
        return _api_error(404, f"Model '{body['model']}' not found", "model_not_found")
    backend_client = get_backend_client()
    headers = _forward_headers(request)

    if body.get("stream") is True:
        context = backend_client.stream_backend(backend_id, "responses", headers=headers, json=body)
        try:
            upstream = await context.__aenter__()
        except httpx.HTTPError:
            await context.__aexit__(None, None, None)
            return _api_error(502, "Unable to contact the configured backend", "upstream_error")
        if upstream.status_code < HTTP_OK or upstream.status_code >= HTTP_SUCCESS_LIMIT:
            error_body = (await upstream.aread())[:MAX_UPSTREAM_ERROR_BYTES]
            await context.__aexit__(None, None, None)
            return _upstream_response(upstream, error_body)
        chunks = upstream.aiter_raw()
        try:
            first_chunk = await anext(chunks)
        except (StopAsyncIteration, httpx.HTTPError):
            await context.__aexit__(None, None, None)
            return _api_error(502, "Unable to read the configured backend stream", "upstream_error")
        return StreamingResponse(
            _stream_response(chunks, first_chunk, context),
            status_code=upstream.status_code,
            media_type="text/event-stream",
            headers={"cache-control": "no-cache"},
        )

    try:
        upstream = await backend_client.request_backend(
            backend_id, "responses", headers=headers, json=body
        )
    except httpx.HTTPError:
        return _api_error(502, "Unable to contact the configured backend", "upstream_error")
    forwarded_body = (
        upstream.content
        if HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT
        else upstream.content[:MAX_UPSTREAM_ERROR_BYTES]
    )
    return _upstream_response(upstream, forwarded_body)


@app.post("/openai/v1/embeddings", tags=["OpenAI"], dependencies=[Depends(verify_client_auth)])
async def create_embeddings(request: Request) -> Response:
    """Forward an embeddings request."""
    body = await _request_body(request, "embeddings")
    if isinstance(body, JSONResponse):
        return body
    settings = load_settings()
    backend_id = _select_backend(settings, body["model"])
    if backend_id is None:
        return _api_error(404, f"Model '{body['model']}' not found", "model_not_found")
    try:
        upstream = await get_backend_client().request_backend(
            backend_id, "embeddings", headers=_forward_headers(request), json=body
        )
    except httpx.HTTPError:
        return _api_error(502, "Unable to contact the configured backend", "upstream_error")
    forwarded_body = (
        upstream.content
        if HTTP_OK <= upstream.status_code < HTTP_SUCCESS_LIMIT
        else upstream.content[:MAX_UPSTREAM_ERROR_BYTES]
    )
    return _upstream_response(upstream, forwarded_body)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
