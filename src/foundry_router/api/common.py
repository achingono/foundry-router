"""Common API helpers shared across route modules."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Literal

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.api.azure_intake import (
    IO_CHUNK_BYTES,
    SMALL_INPUT_BYTES,
    AzureIntakeError,
    AzureIntakeRequest,
    intake_delivery_owner,
    intake_runtime,
)
from foundry_router.api.google_work import SignedIntakeError, SignedWorkLease, bounded_signed_work
from foundry_router.credit import (
    estimate_response_usage_cost,
    extract_response_usage_tokens,
)


def api_error(status_code: int, message: str, error_type: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, "type": error_type}},
    )


def _body_header_error(request: Request, max_body_bytes: int) -> JSONResponse | None:
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
        return api_error(415, "Content-Type must be application/json", "invalid_request")

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError:
            return api_error(400, "Invalid Content-Length header", "invalid_request")
        if declared_length > max_body_bytes:
            return api_error(
                413, "Request body exceeds the maximum allowed size", "invalid_request"
            )

    return None


async def request_body(
    request: Request,
    endpoint: str,
    *,
    max_body_bytes: int,
    deadline_monotonic: float | None = None,
    offload_json: bool = False,
    _read_with_deadline: bool = True,
) -> dict[str, Any] | JSONResponse:
    if deadline_monotonic is not None and _read_with_deadline:
        try:
            async with asyncio.timeout_at(deadline_monotonic):
                result = await request_body(
                    request,
                    endpoint,
                    max_body_bytes=max_body_bytes,
                    deadline_monotonic=deadline_monotonic,
                    offload_json=offload_json,
                    _read_with_deadline=False,
                )
        except TimeoutError:
            return api_error(408, "Request intake deadline exceeded", "request_timeout")
        else:
            if time.monotonic() >= deadline_monotonic:
                return api_error(408, "Request intake deadline exceeded", "request_timeout")
            return result
    header_error = _body_header_error(request, max_body_bytes)
    if header_error is not None:
        return header_error

    intake_lease = None
    try:
        if offload_json:
            try:
                intake_lease = SignedWorkLease()
            except ValueError:
                return api_error(
                    503, "Provider state preparation is busy", "provider_state_unavailable"
                )
        raw_body = bytearray()
        async for chunk in request.stream():
            if len(chunk) > max_body_bytes - len(raw_body):
                return api_error(
                    413, "Request body exceeds the maximum allowed size", "invalid_request"
                )
            raw_body.extend(chunk)

        try:
            if offload_json:
                wire = b""

                def capture() -> None:
                    nonlocal wire
                    wire = bytes(raw_body)

                body = await bounded_signed_work(
                    lambda: load_bounded_json(wire.decode(), max_bytes=max_body_bytes),
                    deadline=deadline_monotonic or time.monotonic() + 5,
                    before_submit=capture,
                    lease=intake_lease,
                )
            else:
                body = load_bounded_json(bytes(raw_body).decode(), max_bytes=max_body_bytes)
        except SignedIntakeError as exc:
            return api_error(exc.status, str(exc), exc.code)
        except (ValueError, UnicodeDecodeError, RecursionError):
            return api_error(400, "Request body must contain valid JSON", "invalid_request")
    finally:
        if intake_lease is not None:
            intake_lease.close()
    if not isinstance(body, dict):
        return api_error(400, "Request body must be a JSON object", "invalid_request")
    model = body.get("model")
    if not isinstance(model, str) or not model.strip():
        return api_error(422, "The 'model' field must be a non-empty string", "invalid_request")
    if endpoint == "responses" and "stream" in body and not isinstance(body["stream"], bool):
        return api_error(422, "The 'stream' field must be a boolean", "invalid_request")
    if endpoint == "embeddings":
        input_value = body.get("input")
        if not isinstance(input_value, (str, list)) or (
            isinstance(input_value, list) and not input_value
        ):
            return api_error(
                422, "The 'input' field must be a non-empty string or array", "invalid_request"
            )
        if isinstance(input_value, list) and any(
            not isinstance(item, str) or not item.strip() for item in input_value
        ):
            return api_error(
                422, "The 'input' array must contain non-empty strings", "invalid_request"
            )
    return body


def forward_headers(request: Request) -> dict[str, str]:
    headers = {"content-type": "application/json", "accept": "application/json"}
    if request.headers.get("user-agent"):
        headers["user-agent"] = request.headers["user-agent"]
    headers["x-request-id"] = request.state.correlation_id
    return headers


async def finalize_non_streaming_credit(
    *,
    request_id: str,
    model: str,
    settings: Any,
    response: Response,
    credit_store: Any,
    rate_limit_store: Any | None = None,
    quota_attempt_id: str | None = None,
    backend_id: str | None = None,
) -> float | None:
    is_success = 200 <= response.status_code < 300
    charged_cost = (
        estimate_response_usage_cost(response, model, settings.pricing) if is_success else None
    )
    try:
        try:
            await credit_store.finalize_request(
                request_id,
                backend_id=backend_id,
                charge_reserved=is_success,
                charged_cost_usd=charged_cost,
            )
        except TypeError as exc:
            if "backend_id" in str(exc):
                await credit_store.finalize_request(
                    request_id,
                    charge_reserved=is_success,
                    charged_cost_usd=charged_cost,
                )
            else:
                raise
    finally:
        if rate_limit_store is not None:
            usage = extract_response_usage_tokens(response)
            await rate_limit_store.finalize_request(
                quota_attempt_id or request_id,
                actual_input_tokens=usage[0] if usage is not None else None,
            )
    return charged_cost


async def azure_request_body(
    request: Request,
    endpoint: Literal["responses", "embeddings"],
    *,
    settings: Any,
    started: float,
    ordinary_deadline: float,
    offload_json: bool = False,
) -> AzureIntakeRequest | JSONResponse:
    """Capture network input once; ordinary parsing replays only the bounded private spool."""
    header_error = _body_header_error(request, settings.azure_effective_max_request_body_bytes)
    if header_error is not None:
        return header_error
    runtime = intake_runtime(request)
    if (
        runtime is None
        or not runtime.matches(settings)
        or intake_delivery_owner(request.state) is None
    ):
        return api_error(503, "Azure intake is unavailable", "router_intake_unavailable")
    assert runtime.resources is not None and runtime.policy is not None
    lease = None
    captured = False
    try:
        lease = runtime.resources.acquire()
        lease.started = started
        deadline = ordinary_deadline
        incoming = request.stream().__aiter__()
        while True:
            try:
                async with asyncio.timeout_at(deadline):
                    chunk = await anext(incoming)
            except StopAsyncIteration:
                break
            if len(chunk) > runtime.resources.limits.max_input_bytes - lease.input_bytes:
                raise AzureIntakeError(413, "invalid_request")  # noqa: TRY301 -- bounded intake rejection
            total = lease.input_bytes + len(chunk)
            if (
                total > settings.max_request_body_bytes
                and lease.input_bytes <= settings.max_request_body_bytes
            ):
                if time.monotonic() >= ordinary_deadline:
                    raise AzureIntakeError(408, "request_timeout")  # noqa: TRY301 -- absolute deadline
                deadline = started + settings.azure_effective_intake_timeout_seconds
            if total > SMALL_INPUT_BYTES:
                runtime.resources.upgrade(lease)
            for offset in range(0, len(chunk), IO_CHUNK_BYTES):
                async with asyncio.timeout_at(deadline):
                    await lease.write(bytes(memoryview(chunk)[offset : offset + IO_CHUNK_BYTES]))
            if time.monotonic() >= deadline:
                raise AzureIntakeError(408, "request_timeout")  # noqa: TRY301 -- absolute deadline
        if lease.input_bytes <= settings.max_request_body_bytes:
            chunks = lease.input_chunks() if lease.input_bytes else None

            async def replay_receive() -> dict[str, Any]:
                if chunks is None:
                    return {"type": "http.request", "body": b"", "more_body": False}
                try:
                    return {"type": "http.request", "body": await anext(chunks), "more_body": True}
                except StopAsyncIteration:
                    return {"type": "http.request", "body": b"", "more_body": False}

            try:
                body = await request_body(
                    Request(request.scope, receive=replay_receive),
                    endpoint,
                    max_body_bytes=settings.max_request_body_bytes,
                    deadline_monotonic=ordinary_deadline,
                    offload_json=offload_json,
                )
            finally:
                if chunks is not None:
                    await chunks.aclose()
            if isinstance(body, JSONResponse):
                return body
            result = AzureIntakeRequest(lease, runtime.policy, ordinary_deadline, body=body)
        else:
            prepared = await lease.prepare(runtime.policy, endpoint, deadline=deadline)
            result = AzureIntakeRequest(lease, runtime.policy, deadline, prepared=prepared)
        captured = True
        return result  # noqa: TRY300 -- lease transfer is explicit
    except TimeoutError:
        return api_error(408, "Request intake deadline exceeded", "request_timeout")
    except AzureIntakeError as error:
        return api_error(error.status, "Azure request intake failed", error.code)
    finally:
        if lease is not None and not captured:
            await lease.close()
