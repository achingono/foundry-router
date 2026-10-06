"""OpenAI-compatible proxy routes."""

from __future__ import annotations

import sys
import time
from functools import partial
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from foundry_router.api.adapters import get_adapter
from foundry_router.api.adapters.google_audio_request import (
    audio_output_request,
    validate_audio_output_request,
)
from foundry_router.api.adapters.google_image_request import (
    image_output_request,
    validate_image_output_request,
)
from foundry_router.api.common import (
    api_error,
    finalize_non_streaming_credit,
    forward_headers,
    request_body,
)
from foundry_router.api.google_audio import PreparedAudio, prepare_audio
from foundry_router.api.google_history import STATE_FIELD
from foundry_router.api.google_intake import prepare_signed_request
from foundry_router.api.google_output_delivery import delivery_owner
from foundry_router.api.google_output_wav import output_wav_ready
from foundry_router.api.google_output_work import OutputInspectionLease
from foundry_router.api.google_pdf import (
    PdfPreparationError,
    PreparedGoogleMedia,
    pdf_parts,
    pdf_preparer,
)
from foundry_router.api.google_state import ProviderStateError
from foundry_router.api.google_video import PreparedVideo, prepare_video
from foundry_router.api.google_work import SignedIntakeError, SignedWorkLease
from foundry_router.auth import verify_client_auth
from foundry_router.config.model_aliases import (
    canonical_request_copy,
    catalog_model_names,
    resolve_model_alias,
)
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
    rate_limit_store: Any | None = None,
) -> APIRouter:
    router = APIRouter()

    @router.get("/openai/v1/models", tags=["OpenAI"], dependencies=[Depends(verify_client_auth)])
    async def list_models() -> dict[str, Any]:
        settings = load_settings_fn()
        aliases = getattr(settings, "model_aliases", {}) or {}
        names = catalog_model_names(settings.models, aliases)
        return {
            "object": "list",
            "data": [
                {
                    "id": model_name,
                    "object": "model",
                    "owned_by": "foundry-router",
                }
                for model_name in names
            ],
        }

    @router.post(
        "/openai/v1/responses", tags=["OpenAI"], dependencies=[Depends(verify_client_auth)]
    )
    async def create_response(request: Request) -> Response:
        settings = load_settings_fn()
        intake_deadline = time.monotonic() + settings.intake_timeout_seconds
        body = await request_body(
            request,
            "responses",
            max_body_bytes=settings.max_request_body_bytes,
            deadline_monotonic=intake_deadline,
            **(
                {"offload_json": True}
                if any(
                    pool.continuation_policy == "bound_history_required"
                    for pool in settings.models.values()
                )
                else {}
            ),
        )
        if isinstance(body, JSONResponse):
            return body
        aliases = getattr(settings, "model_aliases", {}) or {}
        resolution = resolve_model_alias(body["model"], aliases)
        if resolution.resolved_model not in settings.models:
            return api_error(
                404, f"Model '{resolution.requested_model}' not found", "model_not_found"
            )
        canonical_body = canonical_request_copy(body, resolution.resolved_model)
        pool = settings.models[resolution.resolved_model]
        work_lease = None
        output_lease = None
        output_transferred = False
        try:
            if audio_output_request(canonical_body) and any(
                "audio_output" in settings.backends[name].google_features.features
                for name in pool.backends
            ):
                profiles = [settings.backends[name].google_features for name in pool.backends]
                try:
                    if not profiles or any(p != profiles[0] for p in profiles):
                        return api_error(
                            422, "Generated audio pool is unavailable", "unsupported_input"
                        )
                    validate_audio_output_request(canonical_body, profiles[0])
                    canonical_body["max_output_tokens"] = profiles[0].generated_output_tokens_bound
                except ValueError:
                    return api_error(422, "Invalid generated audio request", "unsupported_input")
                if not output_wav_ready():
                    return api_error(503, "Generated audio inspector unavailable", "upstream_error")
                try:
                    output_lease = OutputInspectionLease(slots=2)
                except ValueError:
                    return api_error(503, "Generated output inspection is busy", "upstream_error")
            if image_output_request(canonical_body) and any(
                "image_output" in settings.backends[name].google_features.features
                for name in pool.backends
            ):
                try:
                    validate_image_output_request(canonical_body)
                    profiles = [settings.backends[name].google_features for name in pool.backends]
                    bounds = {p.generated_output_tokens_bound for p in profiles}
                    if (
                        any("image_output" not in p.features for p in profiles)
                        or len(bounds) != 1
                        or profiles[0].generated_output_tokens_bound is None
                    ):
                        return api_error(
                            422, "Generated image capability is disabled", "unsupported_parameter"
                        )
                    bound = profiles[0].generated_output_tokens_bound
                    if (
                        type(canonical_body.get("max_output_tokens", bound)) is not int
                        or canonical_body.get("max_output_tokens", bound) != bound
                    ):
                        return api_error(
                            422,
                            "Generated image output bound must match configuration",
                            "unsupported_parameter",
                        )
                    canonical_body["max_output_tokens"] = bound
                    eligible = False
                    for name in pool.backends:
                        config = settings.backends[name]
                        rejection = get_adapter(
                            config.provider,
                            google_features=config.google_features,
                            api_surface=config.api_surface,
                        ).check_request(
                            "responses", canonical_body, deadline_monotonic=intake_deadline
                        )
                        if rejection is None:
                            eligible = True
                            break
                    if not eligible:
                        return api_error(
                            422, "Invalid image generation request", "unsupported_input"
                        )
                except ValueError as exc:
                    return api_error(422, str(exc), "unsupported_parameter")
                if sys.platform != "linux":
                    return api_error(503, "Generated output requires Linux", "upstream_error")
                try:
                    capacity = 2 if any("inline_images" in p.features for p in profiles) else 1
                    output_lease = OutputInspectionLease(slots=capacity)
                except ValueError:
                    return api_error(503, "Generated output inspection is busy", "upstream_error")
                if not await output_lease.ready(deadline=intake_deadline):
                    return api_error(
                        503, "Generated output inspector is unavailable", "upstream_error"
                    )
            if pool.continuation_policy == "bound_history_required":
                try:
                    work_lease = SignedWorkLease()
                except ValueError:
                    return api_error(
                        503, "Provider state preparation is busy", "provider_state_unavailable"
                    )
            prepared_media = None
            try:
                audio: tuple[PreparedAudio, ...] = ()
                video: tuple[PreparedVideo, ...] = ()
                if any(
                    "inline_video" in settings.backends[backend_id].google_features.features
                    for backend_id in pool.backends
                ):
                    video = prepare_video(canonical_body)
                if any(
                    "inline_audio" in settings.backends[backend_id].google_features.features
                    for backend_id in pool.backends
                ):
                    audio = prepare_audio(canonical_body)
                if any(
                    "inline_pdfs" in settings.backends[backend_id].google_features.features
                    for backend_id in pool.backends
                ) and pdf_parts(canonical_body):
                    prepared_media = await pdf_preparer.prepare(
                        canonical_body, deadline=intake_deadline
                    )
                if audio or video:
                    prepared_media = PreparedGoogleMedia(
                        prepared_media.pdfs if prepared_media is not None else (), audio, video
                    )
            except PdfPreparationError as exc:
                return api_error(exc.status_code, str(exc), "unsupported_input")
            media_options: dict[str, Any] = (
                {"prepared_media": prepared_media} if prepared_media is not None else {}
            )
            if pool.continuation_policy == "bound_history_required":
                keys = settings.google_state_keys
                if (
                    keys is None
                    or getattr(request.state, "google_state_key_configuration", None) is not keys
                ):
                    return api_error(
                        503, "Provider state is unavailable", "provider_state_unavailable"
                    )
                try:
                    seal_context, prepared = await prepare_signed_request(
                        settings,
                        resolution.resolved_model,
                        canonical_body,
                        caller=request.state.google_caller_scope,
                        media=prepared_media,
                        deadline=intake_deadline,
                        lease=work_lease,
                    )
                    media_options["seal_context"] = seal_context
                    if prepared is not None:
                        media_options["prepared_continuation"] = prepared
                except SignedIntakeError as exc:
                    return api_error(exc.status, str(exc), exc.code)
                except TimeoutError:
                    return api_error(408, "Request intake exceeded its deadline", "request_timeout")
                except (ProviderStateError, ValueError, TypeError, KeyError):
                    return api_error(422, "Invalid provider state", "invalid_provider_state")
            elif STATE_FIELD in canonical_body or any(
                isinstance(item, dict) and STATE_FIELD in item
                for item in canonical_body.get("input", [])
            ):
                return api_error(
                    422, "Provider state requires a bound-history pool", "invalid_provider_state"
                )
            headers = forward_headers(request)

            if canonical_body.get("stream") is True:
                return await execute_with_single_failover(
                    settings,
                    resolution.resolved_model,
                    operation="responses",
                    body=canonical_body,
                    request_id=request.state.request_key,
                    execute_backend=lambda backend_id, *, reservation_deadline_monotonic: (
                        forward_streaming_with_retries(
                            settings=settings,
                            backend_id=backend_id,
                            request_id=request.state.request_key,
                            headers=headers,
                            body=canonical_body,
                            get_backend_client=get_backend_client_fn,
                            set_backend_active=health_store.set_backend_active,
                            set_backend_cooldown=health_store.set_backend_cooldown,
                            sleep=sleep_fn,
                            api_error=api_error,
                            credit_store=credit_store,
                            metrics_store=metrics_store,
                            rate_limit_store=rate_limit_store,
                            reservation_deadline_monotonic=reservation_deadline_monotonic,
                            **media_options,
                        )
                    ),
                    health_store=health_store,
                    credit_store=credit_store,
                    rate_limit_store=rate_limit_store,
                    metrics_store=metrics_store,
                    logger=logger,
                    api_error=api_error,
                    finalize_non_streaming_credit=partial(
                        finalize_non_streaming_credit,
                        credit_store=credit_store,
                        rate_limit_store=rate_limit_store,
                    ),
                    requested_model=resolution.requested_model,
                    is_alias=resolution.is_alias,
                    intake_deadline_monotonic=intake_deadline,
                    **media_options,
                )

            result = await execute_with_single_failover(
                settings,
                resolution.resolved_model,
                operation="responses",
                body=canonical_body,
                request_id=request.state.request_key,
                execute_backend=lambda backend_id, *, reservation_deadline_monotonic: (
                    forward_non_streaming_with_retries(
                        output_lease=output_lease,
                        settings=settings,
                        backend_id=backend_id,
                        operation="responses",
                        headers=headers,
                        body=canonical_body,
                        get_backend_client=get_backend_client_fn,
                        set_backend_active=health_store.set_backend_active,
                        set_backend_cooldown=health_store.set_backend_cooldown,
                        sleep=sleep_fn,
                        api_error=api_error,
                        reservation_deadline_monotonic=reservation_deadline_monotonic,
                        **media_options,
                    )
                ),
                health_store=health_store,
                credit_store=credit_store,
                rate_limit_store=rate_limit_store,
                metrics_store=metrics_store,
                logger=logger,
                api_error=api_error,
                finalize_non_streaming_credit=partial(
                    finalize_non_streaming_credit,
                    credit_store=credit_store,
                    rate_limit_store=rate_limit_store,
                ),
                requested_model=resolution.requested_model,
                is_alias=resolution.is_alias,
                intake_deadline_monotonic=intake_deadline,
                **media_options,
            )
            owner = delivery_owner(request.state)
            if output_lease is not None and result.status_code == 200 and owner is not None:
                if output_lease.delivery_deadline is None:
                    return api_error(
                        502, "Generated output delivery is unavailable", "upstream_error"
                    )
                owner.transfer(output_lease, output_lease.delivery_deadline)
                output_transferred = True
            return result

        finally:
            if output_lease is not None and not output_transferred:
                output_lease.close()
            if work_lease is not None:
                work_lease.close()

    @router.post(
        "/openai/v1/embeddings", tags=["OpenAI"], dependencies=[Depends(verify_client_auth)]
    )
    async def create_embeddings(request: Request) -> Response:
        settings = load_settings_fn()
        body = await request_body(
            request, "embeddings", max_body_bytes=settings.max_request_body_bytes
        )
        if isinstance(body, JSONResponse):
            return body
        aliases = getattr(settings, "model_aliases", {}) or {}
        resolution = resolve_model_alias(body["model"], aliases)
        if resolution.resolved_model not in settings.models:
            return api_error(
                404, f"Model '{resolution.requested_model}' not found", "model_not_found"
            )
        canonical_body = canonical_request_copy(body, resolution.resolved_model)
        return await execute_with_single_failover(
            settings,
            resolution.resolved_model,
            operation="embeddings",
            body=canonical_body,
            request_id=request.state.request_key,
            execute_backend=lambda backend_id, *, reservation_deadline_monotonic: (
                forward_non_streaming_with_retries(
                    settings=settings,
                    backend_id=backend_id,
                    operation="embeddings",
                    headers=forward_headers(request),
                    body=canonical_body,
                    get_backend_client=get_backend_client_fn,
                    set_backend_active=health_store.set_backend_active,
                    set_backend_cooldown=health_store.set_backend_cooldown,
                    sleep=sleep_fn,
                    api_error=api_error,
                    reservation_deadline_monotonic=reservation_deadline_monotonic,
                )
            ),
            health_store=health_store,
            credit_store=credit_store,
            rate_limit_store=rate_limit_store,
            metrics_store=metrics_store,
            logger=logger,
            api_error=api_error,
            finalize_non_streaming_credit=partial(
                finalize_non_streaming_credit,
                credit_store=credit_store,
                rate_limit_store=rate_limit_store,
            ),
            requested_model=resolution.requested_model,
            is_alias=resolution.is_alias,
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
