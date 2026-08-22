"""OpenAI-compatible proxy routes."""

from __future__ import annotations

from functools import partial
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from foundry_router.api.common import (
    api_error,
    finalize_non_streaming_credit,
    forward_headers,
    request_body,
)
from foundry_router.auth import verify_client_auth
from foundry_router.forwarding import (
    BackendRequestResult,
    forward_non_streaming_with_retries,
    forward_streaming_with_retries,
    parse_retry_after,
    retry_delay_seconds,
    stream_response,
)
from foundry_router.routing import (
    execute_with_single_failover,
    ranked_model_backends,
    select_backend,
)


def build_router(
    *,
    load_settings_fn: Any,
    get_backend_client_fn: Any,
    sleep_fn: Any,
    health_store: Any,
    credit_store: Any,
    metrics_store: Any,
    logger: Any,
) -> APIRouter:
    router = APIRouter()

    @router.get("/openai/v1/models", tags=["OpenAI"], dependencies=[Depends(verify_client_auth)])
    async def list_models() -> dict[str, Any]:
        settings = load_settings_fn()
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

    @router.post(
        "/openai/v1/responses", tags=["OpenAI"], dependencies=[Depends(verify_client_auth)]
    )
    async def create_response(request: Request) -> Response:
        body = await request_body(request, "responses")
        if isinstance(body, JSONResponse):
            return body
        settings = load_settings_fn()
        if body["model"] not in settings.models:
            return api_error(404, f"Model '{body['model']}' not found", "model_not_found")
        headers = forward_headers(request)

        if body.get("stream") is True:
            return await execute_with_single_failover(
                settings,
                body["model"],
                operation="responses",
                body=body,
                request_id=request.state.correlation_id,
                execute_backend=lambda backend_id: forward_streaming_with_retries(
                    settings=settings,
                    backend_id=backend_id,
                    request_id=request.state.correlation_id,
                    headers=headers,
                    body=body,
                    get_backend_client=get_backend_client_fn,
                    set_backend_active=health_store.set_backend_active,
                    set_backend_cooldown=health_store.set_backend_cooldown,
                    sleep=sleep_fn,
                    api_error=api_error,
                    credit_store=credit_store,
                    metrics_store=metrics_store,
                ),
                health_store=health_store,
                credit_store=credit_store,
                metrics_store=metrics_store,
                logger=logger,
                api_error=api_error,
                finalize_non_streaming_credit=partial(
                    finalize_non_streaming_credit,
                    credit_store=credit_store,
                ),
            )

        return await execute_with_single_failover(
            settings,
            body["model"],
            operation="responses",
            body=body,
            request_id=request.state.correlation_id,
            execute_backend=lambda backend_id: forward_non_streaming_with_retries(
                settings=settings,
                backend_id=backend_id,
                operation="responses",
                headers=headers,
                body=body,
                get_backend_client=get_backend_client_fn,
                set_backend_active=health_store.set_backend_active,
                set_backend_cooldown=health_store.set_backend_cooldown,
                sleep=sleep_fn,
                api_error=api_error,
            ),
            health_store=health_store,
            credit_store=credit_store,
            metrics_store=metrics_store,
            logger=logger,
            api_error=api_error,
            finalize_non_streaming_credit=partial(
                finalize_non_streaming_credit,
                credit_store=credit_store,
            ),
        )

    @router.post(
        "/openai/v1/embeddings", tags=["OpenAI"], dependencies=[Depends(verify_client_auth)]
    )
    async def create_embeddings(request: Request) -> Response:
        body = await request_body(request, "embeddings")
        if isinstance(body, JSONResponse):
            return body
        settings = load_settings_fn()
        if body["model"] not in settings.models:
            return api_error(404, f"Model '{body['model']}' not found", "model_not_found")
        return await execute_with_single_failover(
            settings,
            body["model"],
            operation="embeddings",
            body=body,
            request_id=request.state.correlation_id,
            execute_backend=lambda backend_id: forward_non_streaming_with_retries(
                settings=settings,
                backend_id=backend_id,
                operation="embeddings",
                headers=forward_headers(request),
                body=body,
                get_backend_client=get_backend_client_fn,
                set_backend_active=health_store.set_backend_active,
                set_backend_cooldown=health_store.set_backend_cooldown,
                sleep=sleep_fn,
                api_error=api_error,
            ),
            health_store=health_store,
            credit_store=credit_store,
            metrics_store=metrics_store,
            logger=logger,
            api_error=api_error,
            finalize_non_streaming_credit=partial(
                finalize_non_streaming_credit,
                credit_store=credit_store,
            ),
        )

    return router


__all__ = [
    "BackendRequestResult",
    "build_router",
    "execute_with_single_failover",
    "forward_non_streaming_with_retries",
    "forward_streaming_with_retries",
    "parse_retry_after",
    "ranked_model_backends",
    "retry_delay_seconds",
    "select_backend",
    "stream_response",
]
