"""Common API helpers shared across route modules."""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from foundry_router.credit import estimate_response_usage_cost


def api_error(status_code: int, message: str, error_type: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, "type": error_type}},
    )


async def request_body(  # noqa: PLR0911, PLR0912
    request: Request, endpoint: str, *, max_body_bytes: int
) -> dict[str, Any] | JSONResponse:
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

    raw_body = bytearray()
    async for chunk in request.stream():
        raw_body.extend(chunk)
        if len(raw_body) > max_body_bytes:
            return api_error(
                413, "Request body exceeds the maximum allowed size", "invalid_request"
            )

    try:
        body = json.loads(bytes(raw_body))
    except ValueError:
        return api_error(400, "Request body must contain valid JSON", "invalid_request")
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
) -> float | None:
    is_success = 200 <= response.status_code < 300
    charged_cost = (
        estimate_response_usage_cost(response, model, settings.pricing) if is_success else None
    )
    await credit_store.finalize_request(
        request_id,
        charge_reserved=is_success,
        charged_cost_usd=charged_cost,
    )
    return charged_cost
