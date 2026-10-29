"""Bounded MAI generation projection into Responses image output."""

from __future__ import annotations

import base64
import binascii
import hashlib
import time
import uuid
from typing import TYPE_CHECKING, Any

from foundry_router.api.adapters.base import AdapterRejection, TranslatedSuccess
from foundry_router.api.adapters.compatible_text import CompatibleTextAdapter
from foundry_router.api.adapters.google_image_request import _IMAGE_TOOL, image_output_request
from foundry_router.api.google_output_png import MAX_PNG_BYTES

if TYPE_CHECKING:
    from foundry_router.api.google_output_work import OutputInspectionLease
    from foundry_router.api.google_pdf import PreparedGoogleMedia

MAX_MAI_PROMPT_BYTES = 64 * 1024
_REQUEST_FIELDS = {"model", "input", "tools", "stream", "store", "metadata"}


class AzureMaiAdapter(CompatibleTextAdapter):
    """One PNG generation; every output requires the existing isolated inspector."""

    provider = "azure_mai"
    provider_label = "Foundry MAI"

    def supports_operation(self, operation: str) -> bool:
        return operation == "responses"

    def check_request(
        self,
        operation: str,
        body: dict[str, Any],
        *,
        deadline_monotonic: float | None = None,
        prepared_media: PreparedGoogleMedia | None = None,
    ) -> AdapterRejection | None:
        _ = deadline_monotonic
        prompt = body.get("input")
        if (
            operation != "responses"
            or set(body) - _REQUEST_FIELDS
            or not image_output_request(body)
            or body.get("stream", False) is not False
            or body.get("store", False) is not False
            or prepared_media is not None
            or not isinstance(prompt, str)
            or not prompt.strip()
            or len(prompt.encode()) > MAX_MAI_PROMPT_BYTES
        ):
            return AdapterRejection(
                422, "unsupported_input", "MAI requires a bounded prompt and one nonstream PNG tool"
            )
        # Reuse the existing metadata shape/size validator without forwarding image tools.
        text_body = {key: value for key, value in body.items() if key != "tools"}
        return super().check_request(operation, text_body)

    def build_upstream_body(
        self,
        operation: str,
        body: dict[str, Any],
        *,
        deployment: str,
        default_output_tokens: int,
        prepared_media: PreparedGoogleMedia | None = None,
    ) -> dict[str, Any]:
        _ = default_output_tokens
        if self.check_request(operation, body, prepared_media=prepared_media):
            raise ValueError("Unsupported MAI request")
        return {"model": deployment, "prompt": body["input"], "width": 1024, "height": 1024}

    def extract_usage(self, operation: str, upstream: Any) -> tuple[int | None, int | None]:
        _ = operation, upstream
        # MAI's documented envelope has no token usage. Keep the reserved image ceiling.
        return None, None

    def translate_success(self, *args: Any, **kwargs: Any) -> TranslatedSuccess:
        _ = args, kwargs
        raise ValueError("MAI output requires bounded PNG inspection")

    def create_stream_decoder(self, **kwargs: Any) -> Any:
        _ = kwargs
        raise ValueError("MAI streaming is disabled")


async def translate_mai_image_output(
    upstream: Any,
    *,
    request_body: dict[str, Any],
    logical_model: str,
    lease: OutputInspectionLease,
    deadline: float,
) -> TranslatedSuccess:
    if AzureMaiAdapter().check_request("responses", request_body):
        raise ValueError("Unsupported MAI request")
    if not isinstance(upstream, dict) or "data" not in upstream:
        raise ValueError("Invalid MAI envelope")
    data = upstream["data"]
    if (
        not isinstance(data, list)
        or len(data) != 1
        or not isinstance(data[0], dict)
        or set(data[0]) != {"b64_json"}
    ):
        raise ValueError("MAI requires exactly one inline PNG")
    encoded = data[0]["b64_json"]
    if not isinstance(encoded, str) or not encoded or len(encoded) > 4 * ((MAX_PNG_BYTES + 2) // 3):
        raise ValueError("MAI PNG exceeds encoded bound")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid MAI PNG encoding") from exc
    if len(raw) > MAX_PNG_BYTES or base64.b64encode(raw).decode() != encoded:
        raise ValueError("Invalid canonical MAI PNG")
    facts = await lease.inspect(raw, deadline=deadline)
    if facts.decoded_bytes != len(raw) or facts.digest != hashlib.sha256(raw).hexdigest():
        raise ValueError("MAI PNG inspection identity mismatch")
    return TranslatedSuccess(
        body={
            "id": f"resp_{uuid.uuid4().hex}",
            "object": "response",
            "created_at": int(time.time()),
            "status": "completed",
            "error": None,
            "incomplete_details": None,
            "model": logical_model,
            "output": [
                {
                    "type": "image_generation_call",
                    "id": f"ig_{uuid.uuid4().hex}",
                    "status": "completed",
                    "result": encoded,
                }
            ],
            "usage": None,
            "metadata": dict(request_body.get("metadata") or {}),
            "tools": [dict(_IMAGE_TOOL)],
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "store": False,
        },
        input_tokens=None,
        output_tokens=None,
    )
