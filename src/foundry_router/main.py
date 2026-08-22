"""Foundry Router application assembly and lifecycle."""

from __future__ import annotations

import asyncio
import re
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from structlog import get_logger

import foundry_router.forwarding as forwarding_module
from foundry_router.api.routes.admin import build_router as build_admin_router
from foundry_router.api.routes.health import build_router as build_health_router
from foundry_router.api.routes.openai import build_router as build_openai_router
from foundry_router.backends import close_backend_client, get_backend_client
from foundry_router.config import load_settings
from foundry_router.credit import CreditStore, InMemoryCreditStore
from foundry_router.forwarding import BackendRequestResult
from foundry_router.health import (
    BackendHealthRecord,
    BackendHealthSnapshot,
    BackendHealthState,
    InMemoryHealthStore,
)
from foundry_router.logging import setup_logging
from foundry_router.main_compat import (
    _execute_with_single_failover,
    _forward_non_streaming_with_retries,
    _forward_streaming_with_retries,
    _parse_retry_after,
    _ranked_model_backends,
    _retry_delay_seconds,
    _select_backend,
    _stream_response,
)
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.reconciliation import (
    ReconciliationLoop,
    ReconciliationProvider,
    StaticSettingsReconciliationProvider,
)

logger = get_logger(__name__)
_health_store = InMemoryHealthStore()
_credit_store: CreditStore = InMemoryCreditStore()
_metrics_store = InMemoryMetricsStore()
_reconciliation_provider: ReconciliationProvider = StaticSettingsReconciliationProvider()
_reconciliation_loop: ReconciliationLoop | None = None

# Compatibility aliases used by existing tests.
_backend_health_state = _health_store.state
_backend_health_lock = _health_store.lock
PRE_OUTPUT_TIMEOUT_SECONDS = forwarding_module.PRE_OUTPUT_TIMEOUT_SECONDS


async def _set_backend_active(backend_id: str) -> None:
    await _health_store.set_backend_active(backend_id)


async def _set_backend_cooldown(
    backend_id: str, *, state: BackendHealthState, cooldown_seconds: float
) -> None:
    await _health_store.set_backend_cooldown(
        backend_id, state=state, cooldown_seconds=cooldown_seconds
    )


async def _snapshot_backend_health(backend_ids: list[str]) -> dict[str, BackendHealthSnapshot]:
    return await _health_store.snapshot_backend_health(backend_ids)


async def _reset_backend_health_state() -> None:
    await _health_store.reset()


async def _reset_credit_state() -> None:
    await _credit_store.reset()


async def _reset_metrics_state() -> None:
    await _metrics_store.reset()


async def _reset_reconciliation_state() -> None:
    global _reconciliation_loop
    if _reconciliation_loop is not None:
        await _reconciliation_loop.stop()
    _reconciliation_loop = None


def set_reconciliation_provider(provider: ReconciliationProvider) -> None:
    global _reconciliation_provider
    _reconciliation_provider = provider


def _reconciliation_status_snapshot() -> dict[str, Any]:
    return (
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
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> Any:
    settings = load_settings()
    setup_logging(settings.log_level)
    logger.info(
        "foundry_router_starting",
        version="0.1.0",
        backends=list(settings.backends.keys()),
        models=list(settings.models.keys()),
    )
    get_backend_client()
    await _credit_store.sync_from_settings(settings)
    global _reconciliation_loop
    _reconciliation_loop = ReconciliationLoop(
        provider=_reconciliation_provider,
        credit_store=_credit_store,
        settings=settings,
        logger=logger,
    )
    await _reconciliation_loop.start()
    yield
    logger.info("foundry_router_shutting_down")
    await _reset_reconciliation_state()
    await close_backend_client()
    await _reset_backend_health_state()
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
    supplied_id = request.headers.get("x-request-id")
    correlation_id = (
        supplied_id
        if supplied_id and re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", supplied_id)
        else str(uuid.uuid4())
    )
    request.state.correlation_id = correlation_id
    structlog.contextvars.bind_contextvars(request_id=correlation_id)
    try:
        response: Response = await call_next(request)
        response.headers["x-request-id"] = correlation_id
        return response
    finally:
        structlog.contextvars.clear_contextvars()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
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


def _current_load_settings() -> Any:
    module = sys.modules[__name__]
    loader = getattr(module, "load_settings", load_settings)
    return loader()


def _current_get_backend_client() -> Any:
    module = sys.modules[__name__]
    getter = getattr(module, "get_backend_client", get_backend_client)
    return getter()


async def _current_sleep(seconds: float) -> None:
    module = sys.modules[__name__]
    sleeper = getattr(getattr(module, "asyncio", asyncio), "sleep", asyncio.sleep)
    await sleeper(seconds)


app.include_router(build_health_router(load_settings_fn=_current_load_settings))
app.include_router(
    build_admin_router(
        load_settings_fn=_current_load_settings,
        health_store=_health_store,
        credit_store=_credit_store,
        metrics_store=_metrics_store,
        reconciliation_status_snapshot=_reconciliation_status_snapshot,
    )
)
app.include_router(
    build_openai_router(
        load_settings_fn=_current_load_settings,
        get_backend_client_fn=_current_get_backend_client,
        sleep_fn=_current_sleep,
        health_store=_health_store,
        credit_store=_credit_store,
        metrics_store=_metrics_store,
        logger=logger,
    )
)

__all__ = [
    "PRE_OUTPUT_TIMEOUT_SECONDS",
    "BackendHealthRecord",
    "BackendHealthSnapshot",
    "BackendHealthState",
    "BackendRequestResult",
    "_backend_health_lock",
    "_backend_health_state",
    "_credit_store",
    "_execute_with_single_failover",
    "_forward_non_streaming_with_retries",
    "_forward_streaming_with_retries",
    "_health_store",
    "_metrics_store",
    "_parse_retry_after",
    "_ranked_model_backends",
    "_reconciliation_loop",
    "_reconciliation_provider",
    "_reset_backend_health_state",
    "_reset_credit_state",
    "_reset_metrics_state",
    "_reset_reconciliation_state",
    "_retry_delay_seconds",
    "_select_backend",
    "_set_backend_active",
    "_set_backend_cooldown",
    "_snapshot_backend_health",
    "_stream_response",
    "app",
    "close_backend_client",
    "get_backend_client",
    "global_exception_handler",
    "lifespan",
    "load_settings",
    "logger",
    "set_reconciliation_provider",
]
