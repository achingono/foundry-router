"""Foundry Router application assembly and lifecycle."""

from __future__ import annotations

import asyncio
import re
import sys
import time
import uuid
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING, Any, cast

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from structlog import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import foundry_router.forwarding as forwarding_module
from foundry_router.api.google_output_delivery import (
    GeneratedOutputDeliveryMiddleware,
    delivery_owner,
)
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
from foundry_router.ratelimit import InMemoryRateLimitStore, RateLimitStore, zero_share_dimensions
from foundry_router.reconciliation import (
    ReconciliationLoop,
    ReconciliationProvider,
    StaticSettingsReconciliationProvider,
)
from foundry_router.routing.exclusion import CombinationExclusionStore

logger = get_logger(__name__)
_health_store = InMemoryHealthStore()
_exclusion_store = CombinationExclusionStore()
_credit_store: CreditStore = InMemoryCreditStore()
_metrics_store: Any = InMemoryMetricsStore()
_rate_limit_store: RateLimitStore = InMemoryRateLimitStore()
_reconciliation_provider: ReconciliationProvider = StaticSettingsReconciliationProvider()
_reconciliation_loop: ReconciliationLoop | None = None
# Phase 11: Table clients owned by the lifespan when state_backend == "table".
_table_clients: tuple[Any, ...] = ()
# Phase 11: bounded readiness probe cache (at most 5 seconds stale).
_STATE_PROBE_CACHE_SECONDS = 5.0
_state_probe_cache: dict[str, Any] = {"at": None, "ok": False}


class _LiveStore:
    """Indirection so lifespan-built stores reach already-assembled routers.

    Routers are assembled at import time with these proxies; the lifespan store
    factory rebinds the module globals for ``table`` backends and the proxies
    delegate to the current instances. Routing, reconciliation and
    ``/admin/status`` therefore always share the same store instances.
    """

    def __init__(self, attr: str) -> None:
        self._attr = attr

    def _target(self) -> Any:
        return sys.modules[__name__].__dict__[self._attr]

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        return getattr(self._target(), name)


def build_stores(settings: Any) -> tuple[Any, Any, Any, tuple[Any, ...]]:
    """Build health/credit/rate-limit stores from settings (Phase 11 step 10).

    Returns ``(health_store, credit_store, rate_limit_store, table_clients)``.
    The ``memory`` backend returns the module-level in-memory singletons so
    existing behaviour and fixtures are unchanged; the ``table`` backend
    constructs shared Azure Table stores with identity-only clients.
    """
    module = sys.modules[__name__]
    health, credit, rate = (
        module.__dict__[name] for name in ("_health_store", "_credit_store", "_rate_limit_store")
    )
    clients = []
    shared_state = getattr(settings, "state_backend", "memory") == "table"
    shared_quota = getattr(settings, "rate_limit_backend", "memory") == "table"
    if shared_state or shared_quota:
        from foundry_router.state.azure import AzureTableEntityClient
        from foundry_router.state.quota import AzureTableRateLimitStore
        from foundry_router.state.table import AzureTableCreditStore, AzureTableHealthStore

        def client(name: str) -> Any:
            result = AzureTableEntityClient(
                endpoint=settings.table_endpoint,
                table_name=name,
                request_timeout_seconds=float(
                    getattr(settings, "table_request_timeout_seconds", 5.0)
                ),
            )
            clients.append(result)
            return result

        if shared_state:
            health = AzureTableHealthStore(client(settings.table_health_name))
            credit = AzureTableCreditStore(client(settings.table_credit_name))
        if shared_quota:
            rate = AzureTableRateLimitStore(client(settings.table_quota_name))
    return health, credit, rate, tuple(clients)


def _table_client_for(table: str) -> Any | None:
    for client in _table_clients:
        if getattr(client, "_table_name", None) == table:
            return client
    return None


async def _probe_state_stores(settings: Any) -> bool:
    """Bounded table-reachability probe, cached for at most 5 seconds."""
    from foundry_router.credit_groups import credit_membership, metered_credit_groups

    now = time.monotonic()
    cached_at = _state_probe_cache.get("at")
    if cached_at is not None and now - float(cached_at) <= _STATE_PROBE_CACHE_SECONDS:
        return bool(_state_probe_cache.get("ok", True))
    backend_ids = list(getattr(settings, "backends", {}).keys())
    aliases = credit_membership(settings)
    routable = (
        {
            backend_id
            for pool in getattr(settings, "models", {}).values()
            for backend_id in pool.backends
        }
        if hasattr(settings, "models")
        else set(backend_ids)
    )
    groups = metered_credit_groups(settings) & {aliases[key] for key in routable}
    timeout = float(getattr(settings, "table_request_timeout_seconds", 5.0))
    ok = True
    if not backend_ids:
        ok = False
    else:
        credit_client = _table_client_for(settings.table_credit_name)
        health_client = _table_client_for(settings.table_health_name)
        if credit_client is None or health_client is None:
            ok = False
        else:
            probes = [
                credit_client.probe_reachable(
                    backend_id, "balance", timeout_seconds=timeout, require_entity=True
                )
                for backend_id in sorted(groups)
            ]
            probes.append(
                health_client.probe_reachable(backend_ids[0], "health", timeout_seconds=timeout)
            )
            try:
                ok = all(await asyncio.gather(*probes))
            except Exception:
                ok = False
    _state_probe_cache.update(at=now, ok=ok)
    return ok


async def _extra_readiness_checks() -> dict[str, bool]:
    """Phase 11 readiness additions: table reachability + replica-share validity."""
    settings = _current_load_settings()
    checks: dict[str, bool] = {}
    try:
        bad = zero_share_dimensions(
            {group: dict(limits) for group, limits in settings.quota_group_rate_limits.items()},
            int(getattr(settings, "rate_limit_replica_share", 1)),
        )
    except Exception:
        bad = []
    if getattr(settings, "rate_limit_backend", "memory") == "table":
        bad = []
    checks["rate_limit_share_valid"] = not bad
    for group, dim in bad:
        logger.warning(
            "rate_limit_share_invalid",
            quota_group=group,
            dimension=dim,
            share=getattr(settings, "rate_limit_replica_share", 1),
        )
        checks[f"rate_limit_share_{group}_{dim}_valid"] = False
    if getattr(settings, "state_backend", "memory") == "table":
        checks["state_store_reachable"] = await _probe_state_stores(settings)
    if getattr(settings, "rate_limit_backend", "memory") == "table":
        try:
            client = _table_client_for(settings.table_quota_name)
            snapshots = await _rate_limit_store.snapshot_quota_groups(
                sorted(settings.quota_group_rate_limits)
            )
            checks["quota_store_reachable"] = client is not None and len(snapshots) == len(
                settings.quota_group_rate_limits
            )
        except Exception:
            checks["quota_store_reachable"] = False
    return checks


# Phase 07: Graceful shutdown with request draining
_active_requests = 0
_active_requests_lock = asyncio.Lock()
_shutdown_event: asyncio.Event | None = None

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


async def _reset_rate_limit_state() -> None:
    await _rate_limit_store.reset()


async def _reset_reconciliation_state() -> None:
    global _reconciliation_loop
    if _reconciliation_loop is not None:
        await _reconciliation_loop.stop()
    _reconciliation_loop = None


def set_reconciliation_provider(provider: ReconciliationProvider) -> None:
    global _reconciliation_provider
    _reconciliation_provider = provider


async def _increment_active_requests() -> None:
    """Increment active request counter."""
    global _active_requests
    async with _active_requests_lock:
        _active_requests += 1


async def _decrement_active_requests() -> None:
    """Decrement active request counter."""
    global _active_requests
    async with _active_requests_lock:
        _active_requests -= 1


async def _drain_active_requests(timeout_seconds: float) -> None:
    """Wait for active requests to complete, up to timeout."""
    start_time = time.time()
    check_interval = 0.1
    while time.time() - start_time < timeout_seconds:
        async with _active_requests_lock:
            if _active_requests == 0:
                logger.info("all_active_requests_drained")
                return
        logger.debug("waiting_for_requests_to_drain", active_count=_active_requests)
        await asyncio.sleep(check_interval)
    async with _active_requests_lock:
        remaining = _active_requests
    logger.warning(
        "graceful_shutdown_timeout_reached",
        active_requests=remaining,
        timeout_seconds=timeout_seconds,
    )


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


def _build_metrics_store(settings: Any) -> Any:
    if settings.telemetry_enabled:
        from foundry_router.metrics.otlp import OtlpMetricsStore

        return OtlpMetricsStore(settings)
    return InMemoryMetricsStore()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> Any:
    global _shutdown_event
    settings = load_settings()
    setup_logging(settings.log_level)
    logger.info(
        "foundry_router_starting",
        version="0.1.0",
        backends=list(settings.backends.keys()),
        models=list(settings.models.keys()),
    )
    global _metrics_store
    if settings.telemetry_enabled or not isinstance(_metrics_store, InMemoryMetricsStore):
        _metrics_store = _build_metrics_store(settings)
    try:
        # Combination-exclusion counters are process-local by design (memory-backed
        # single replica): every restart re-learns sick combinations, costing at most
        # three user-visible failures per sick triple before re-exclusion.
        await _exclusion_store.reset()
        logger.info("combination_exclusion_reset", reason="process_start")
        get_backend_client()
        # Phase 11: build lifespan-owned stores (memory singletons or Table stores).
        global _health_store, _credit_store, _rate_limit_store, _table_clients
        _health_store, _credit_store, _rate_limit_store, _table_clients = build_stores(settings)
        await _credit_store.sync_from_settings(settings)
        await _rate_limit_store.sync_from_settings(settings)
        global _reconciliation_loop
        _reconciliation_loop = ReconciliationLoop(
            provider=_reconciliation_provider,
            credit_store=_credit_store,
            settings=settings,
            logger=logger,
        )
        await _reconciliation_loop.start()
        # Phase 07: Initialize shutdown event for graceful draining
        _shutdown_event = asyncio.Event()
        yield
    finally:
        original_failure = sys.exc_info()[0] is not None
        try:
            logger.info("foundry_router_shutting_down")
            await _drain_active_requests(settings.graceful_shutdown_timeout_seconds)
            await _reset_reconciliation_state()
            await close_backend_client()
            for table_client in _table_clients:
                with suppress(Exception):
                    await table_client.close()
            _table_clients = ()
            await _reset_backend_health_state()
            await _reset_credit_state()
            await _reset_rate_limit_state()
        except BaseException as exc:
            logger.warning("lifespan_cleanup_failed", error_type=type(exc).__name__)
            if not original_failure:
                raise
        finally:
            try:
                if hasattr(_metrics_store, "shutdown"):
                    await _metrics_store.shutdown()
            except BaseException as exc:
                logger.warning("metrics_shutdown_failed", error_type=type(exc).__name__)
            finally:
                await _reset_metrics_state()
                _shutdown_event = None


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
    # Server-owned identity for credit reservation/finalization; never derived from client input.
    request.state.request_key = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=correlation_id)
    try:
        response: Response = await call_next(request)
        response.headers["x-request-id"] = correlation_id
        return response
    finally:
        structlog.contextvars.clear_contextvars()


@app.middleware("http")
async def track_active_requests(request: Request, call_next: Any) -> Response:
    """Phase 07: Track active requests for graceful shutdown draining.

    N7: Health probes are excluded so orchestrator polling does not prevent
    drain. N1: For StreamingResponse, the count is held until the body
    iterator completes (stream's finally finalizes credit), restoring the
    guarantee that drain waits for streams to finish before closing the
    shared httpx client.
    """
    # N7: exclude liveness/readiness probes
    if request.url.path.startswith("/health"):
        return cast(Response, await call_next(request))  # noqa: TC006

    await _increment_active_requests()
    response: Response | None = None
    is_streaming = False
    counter_transferred = False
    try:
        response = cast(Response, await call_next(request))  # noqa: TC006
        owner = delivery_owner(request.state)
        if owner is not None and owner.lease is not None:
            owner.attach_drain_cleanup(_decrement_active_requests)
            counter_transferred = True
            return response
        is_streaming = isinstance(response, StreamingResponse)
        if is_streaming:
            # Hold drain counter until stream body is fully consumed.
            original_iterator = response.body_iterator  # type: ignore[attr-defined]

            async def _tracked_stream() -> AsyncIterator[bytes]:
                try:
                    if hasattr(original_iterator, "__aiter__"):
                        async for chunk in original_iterator:
                            yield chunk
                    else:
                        for chunk in original_iterator:
                            yield chunk
                finally:
                    await _decrement_active_requests()

            response.body_iterator = _tracked_stream()  # type: ignore[attr-defined]
            # Caller will stream; decrement deferred to iterator's finally.
            return response
        return response
    finally:
        if not is_streaming and not counter_transferred:
            await _decrement_active_requests()
        elif response is None:
            # call_next raised before response was produced
            await _decrement_active_requests()


app.add_middleware(GeneratedOutputDeliveryMiddleware)


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


app.include_router(
    build_health_router(
        load_settings_fn=_current_load_settings,
        extra_checks_fn=_extra_readiness_checks,
    )
)
app.include_router(
    build_admin_router(
        load_settings_fn=_current_load_settings,
        health_store=_LiveStore("_health_store"),
        credit_store=_LiveStore("_credit_store"),
        metrics_store=_LiveStore("_metrics_store"),
        rate_limit_store=_LiveStore("_rate_limit_store"),
        reconciliation_status_snapshot=_reconciliation_status_snapshot,
        exclusion_store=_exclusion_store,
    )
)
app.include_router(
    build_openai_router(
        load_settings_fn=_current_load_settings,
        get_backend_client_fn=_current_get_backend_client,
        sleep_fn=_current_sleep,
        health_store=_LiveStore("_health_store"),
        credit_store=_LiveStore("_credit_store"),
        metrics_store=_LiveStore("_metrics_store"),
        logger=logger,
        rate_limit_store=_LiveStore("_rate_limit_store"),
        exclusion_store=_exclusion_store,
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
    "_rate_limit_store",
    "_reconciliation_loop",
    "_reconciliation_provider",
    "_reset_backend_health_state",
    "_reset_credit_state",
    "_reset_metrics_state",
    "_reset_rate_limit_state",
    "_reset_reconciliation_state",
    "_retry_delay_seconds",
    "_select_backend",
    "_set_backend_active",
    "_set_backend_cooldown",
    "_snapshot_backend_health",
    "_stream_response",
    "app",
    "build_stores",
    "close_backend_client",
    "get_backend_client",
    "global_exception_handler",
    "lifespan",
    "load_settings",
    "logger",
    "set_reconciliation_provider",
]
