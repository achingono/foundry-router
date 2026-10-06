"""Unattached finite native image-output projection; worker validates every artifact."""

from __future__ import annotations

import base64
import binascii
import hashlib
import uuid
from typing import TYPE_CHECKING, Any

from foundry_router.api.adapters.google_native import _native_output, native_usage
from foundry_router.api.google_output_png import MAX_PNG_BYTES

if TYPE_CHECKING:
    from foundry_router.api.google_output_work import OutputInspectionLease

from foundry_router.api.adapters.google_image_request import (
    _IMAGE_TOOL,
    validate_image_output_request,
)


async def project_image_output(
    upstream: Any,
    *,
    lease: OutputInspectionLease,
    deadline: float,
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Return validated text envelope and ordered public item descriptors.

    No routing, pricing or enablement occurs here. Image bytes remain unchanged.
    Non-STOP output never yields a completed artifact; usage is retained by forwarding.
    """
    if not isinstance(upstream, dict):
        raise ValueError("Invalid generated image envelope")
    native_usage(upstream, strict=True)
    candidate_list = upstream.get("candidates", [])
    # Ordinary native validation owns envelope/feedback/finish and signature strictness.
    candidate = (
        candidate_list[0] if isinstance(candidate_list, list) and len(candidate_list) == 1 else None
    )
    content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
    if not isinstance(content, dict):
        raise ValueError("Invalid generated image content")
    parts = content.get("parts", [])
    if not isinstance(parts, list) or len(parts) > 64:
        raise ValueError("Invalid generated image parts")
    # Validate the entire envelope/state before any worker await. Only exact inline
    # image parts are removed from this projection; unknown state stays rejected.
    preflight_parts = []
    image_count = 0
    for part in parts:
        if isinstance(part, dict) and set(part) == {"text"} and isinstance(part["text"], str):
            preflight_parts.append(part)
        elif isinstance(part, dict) and set(part) == {"inlineData"}:
            image_count += 1
            media = part["inlineData"]
            if (
                image_count > 1
                or not isinstance(media, dict)
                or set(media) != {"mimeType", "data"}
                or media.get("mimeType") != "image/png"
                or not isinstance(media.get("data"), str)
                or not media["data"]
                or len(media["data"]) > 4 * ((MAX_PNG_BYTES + 2) // 3)
            ):
                raise ValueError("Unsupported bounded generated PNG")
        else:
            raise ValueError("Unsupported generated output or provider state")
    sanitized = dict(upstream)
    if isinstance(candidate, dict):
        sanitized["candidates"] = [{**candidate, "content": {**content, "parts": preflight_parts}}]
    _native_output(sanitized)
    ordered = []
    images = 0
    text_parts = []
    for part in parts:
        if isinstance(part, dict) and set(part) == {"text"} and isinstance(part["text"], str):
            text_parts.append(part)
            ordered.append({"type": "text", "text": part["text"]})
        elif isinstance(part, dict) and set(part) == {"inlineData"}:
            images += 1
            media = part["inlineData"]
            if images > 1 or not isinstance(media, dict) or set(media) != {"mimeType", "data"}:
                raise ValueError("Unsupported generated image artifact")
            encoded = media.get("data")
            if (
                media.get("mimeType") != "image/png"
                or not isinstance(encoded, str)
                or not encoded
                or len(encoded) > 4 * ((MAX_PNG_BYTES + 2) // 3)
            ):
                raise ValueError("Unsupported bounded generated PNG")
            try:
                raw = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError("Invalid generated PNG encoding") from exc
            if len(raw) > MAX_PNG_BYTES or base64.b64encode(raw).decode() != encoded:
                raise ValueError("Invalid canonical generated PNG")
            facts = await lease.inspect(raw, deadline=deadline)
            if facts.decoded_bytes != len(raw) or facts.digest != hashlib.sha256(raw).hexdigest():
                raise ValueError("Generated PNG inspection identity mismatch")
            if isinstance(candidate, dict) and candidate.get("finishReason") == "STOP":
                ordered.append(
                    {
                        "type": "image_generation_call",
                        "id": f"ig_{uuid.uuid4().hex}",
                        "status": "completed",
                        "result": encoded,
                    }
                )
        else:
            raise ValueError("Unsupported generated output or provider state")
    if candidate is not None:
        sanitized["candidates"][0]["content"] = {
            **candidate.get("content", {}),
            "parts": text_parts,
        }
    _native_output(sanitized)
    return sanitized, tuple(ordered)


async def translate_image_output(
    upstream: Any,
    *,
    adapter: Any,
    request_body: dict[str, Any],
    logical_model: str,
    lease: OutputInspectionLease,
    deadline: float,
) -> Any:
    """Compose standard Responses items after bounded artifact validation."""
    validate_image_output_request(request_body)
    sanitized, ordered = await project_image_output(upstream, lease=lease, deadline=deadline)
    text_request = {key: value for key, value in request_body.items() if key != "tools"}
    translated = adapter.translate_success(
        "responses",
        sanitized,
        logical_model=logical_model,
        metadata=request_body.get("metadata"),
        request_body=text_request,
    )
    # Preserve ordinary refusal semantics. Image-only STOP must not fabricate a
    # text message or refusal from the sanitized empty text projection.
    candidate = upstream.get("candidates", [])
    finish = candidate[0].get("finishReason") if candidate else None
    if finish in {"STOP", "MAX_TOKENS"}:
        output: list[dict[str, Any]] = []
        for item in ordered:
            if item["type"] == "image_generation_call":
                output.append(item)
            elif item["text"]:
                if output and output[-1]["type"] == "message":
                    output[-1]["content"][0]["text"] += item["text"]
                else:
                    output.append(
                        {
                            "type": "message",
                            "id": f"msg_{uuid.uuid4().hex}",
                            "role": "assistant",
                            "status": translated.body["status"],
                            "content": [
                                {"type": "output_text", "text": item["text"], "annotations": []}
                            ],
                        }
                    )
        translated.body["output"] = output
    translated.body["tools"] = [dict(_IMAGE_TOOL)]
    translated.body["tool_choice"] = "auto"
    translated.body["parallel_tool_calls"] = False
    return translated
