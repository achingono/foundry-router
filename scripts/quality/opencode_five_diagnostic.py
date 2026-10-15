# ruff: noqa: TRY301 -- terminal failures become durable redacted outcomes
"""One consumed, bounded native diagnostic; exports only allowlisted structure."""

import asyncio
import hashlib
import json
import math
import os
import time
from pathlib import Path

import httpx
import opencode_five_validation as validation

from foundry_router.api.adapters import get_adapter
from foundry_router.config import BackendConfig

ROOT = "https://opencode.ai/inference/v1/models/gemini-3.8-flash:generateContent"
REQUEST = {
    "model": "gemini-3.8-flash-zen",
    "input": "Reply with the single word OK.",
    "max_output_tokens": 512,
    "stream": False,
    "store": False,
}
KEYS = frozenset(
    {
        "candidates",
        "usageMetadata",
        "promptFeedback",
        "modelVersion",
        "responseId",
        "index",
        "content",
        "finishReason",
        "safetyRatings",
        "tokenCount",
        "avgLogprobs",
        "role",
        "parts",
        "text",
        "thoughtSignature",
        "thought",
        "functionCall",
        "inlineData",
        "promptTokenCount",
        "candidatesTokenCount",
        "thoughtsTokenCount",
        "toolUsePromptTokenCount",
        "cachedContentTokenCount",
        "totalTokenCount",
        "promptTokensDetails",
        "candidatesTokensDetails",
        "modality",
        "blockReason",
        "blockReasonMessage",
        "category",
        "probability",
        "error",
        "code",
        "message",
        "status",
    }
)
TOKEN_KEYS = frozenset(
    {
        "promptTokenCount",
        "candidatesTokenCount",
        "thoughtsTokenCount",
        "toolUsePromptTokenCount",
        "cachedContentTokenCount",
        "totalTokenCount",
    }
)
FINISH = frozenset(
    {
        "STOP",
        "MAX_TOKENS",
        "SAFETY",
        "RECITATION",
        "OTHER",
        "BLOCKLIST",
        "PROHIBITED_CONTENT",
        "SPII",
        "MALFORMED_FUNCTION_CALL",
        "IMAGE_SAFETY",
        "NO_IMAGE",
    }
)


def structure(value, *, field="", depth=0):
    if depth > MAX_DEPTH:
        return {"type": "depth_bound"}
    if isinstance(value, dict):
        return {
            "type": "object",
            "fields": {
                k: structure(v, field=k, depth=depth + 1) for k, v in value.items() if k in KEYS
            },
            "unknown_field_count": sum(k not in KEYS for k in value),
        }
    if isinstance(value, list):
        return {
            "type": "array",
            "length": len(value),
            "items": [structure(v, depth=depth + 1) for v in value[:MAX_DEPTH]],
        }
    if field in TOKEN_KEYS and type(value) is int and 0 <= value <= MAX_TOKEN_COUNT:
        return {"type": "integer", "value": value}
    if field == "finishReason" and isinstance(value, str) and value in FINISH:
        return {"type": "enum", "value": value}
    return {"type": type(value).__name__}


PRIVATE = Path("/private/tmp/opencode-five-release")
DIRECTORY = PRIVATE / "diagnostic-once"
MAX_BYTES = 256 * 1024
TIMEOUT = 120
DEBIT = 0.004
REMAINING = 0.099982
MIN_RESERVE = 0.05
ORIGINAL_MANIFEST = "423915f04e4810fb9b68ccce6af68bf7350aabffe12953d4c6d46e0e53b4ff69"
MAX_DEPTH = 8
MAX_TOKEN_COUNT = 1_000_000
REASONS = frozenset(
    {
        "Invalid native usage dimensions",
        "Native thinking or tool prompt usage is disabled",
        "Unsupported native envelope or provider state",
        "Unsupported native candidate or provider state",
        "Unsupported native output or provider state",
        "Native response lacks candidate or block evidence",
        "Native response requires finish evidence",
        "Unsupported native finish reason",
    }
)


def fingerprint(data):
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def fsync_directory(directory):
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def prepare():
    snapshot = json.loads((PRIVATE / "failed-stage-final-admin.json").read_text())
    live = snapshot["credit_groups"]["opencode-account"]["live"]
    prior = live["estimated_remaining_usd"]
    stopped = json.loads((PRIVATE / "failed-stage-stopped-proof.json").read_text())
    ledger = json.loads((PRIVATE / "runner/ledger.json").read_text())
    identity = json.loads((PRIVATE / "runner/identity.json").read_text())
    specification = json.loads((PRIVATE / "runner/manifest.json").read_text())
    expected = validation.manifest(
        specification["image_digest"], specification["configuration_fingerprints"]
    )
    if (
        specification != expected
        or fingerprint(specification) != ORIGINAL_MANIFEST
        or identity != {"manifest_sha256": ORIGINAL_MANIFEST}
        or set(ledger) != {"manifest_sha256", "entries"}
        or len(ledger["entries"]) != len(validation.CASES)
        or any(
            set(e) != {"reserved", "result"} or type(e["reserved"]) is not bool
            for e in ledger["entries"]
        )
        or any(e != {"reserved": False, "result": None} for e in ledger["entries"][1:])
    ):
        raise ValueError("Original manifest or ledger binding unavailable")
    first = ledger["entries"][0]
    if (
        type(prior) not in {int, float}
        or not math.isfinite(prior)
        or not math.isclose(prior, REMAINING, abs_tol=1e-12, rel_tol=0)
        or prior - DEBIT <= MIN_RESERVE
        or live["active_reservations"] != 0
        or live["reserved_inflight_usd"] != 0
        or stopped["running"] is not False
        or stopped["container_id"] != (PRIVATE / "stage-container-id.txt").read_text()
        or identity["manifest_sha256"] != ledger["manifest_sha256"]
        or not first["reserved"]
        or first["result"]["status"] != "failed"
        or first["result"]["id"] != "staging-0-nonstream"
        or any(e["reserved"] for e in ledger["entries"][1:])
    ):
        raise ValueError("Failed stopped staging binding unavailable")
    key = json.loads((Path.home() / ".local/share/opencode/auth.json").read_text())["opencode"][
        "key"
    ]
    profile = {"native_thinking_level": "low", "thought_token_pricing": True}
    config = BackendConfig.model_validate(
        {
            "provider": "opencode_google",
            "api_surface": "native",
            "endpoint": "https://opencode.ai/inference/v1",
            "credential": key,
            "deployment": "gemini-3.8-flash",
            "google_features": profile,
        }
    )
    adapter = get_adapter(config.provider, google_features=config.google_features)
    body = adapter.build_upstream_body(
        "responses",
        REQUEST,
        deployment=config.deployment,
        default_output_tokens=512,
    )
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    fsync_directory(PRIVATE)
    consumed = {
        "diagnostic_id": "opencode-five-flash-structural-20261013-once",
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "original_manifest_sha256": identity["manifest_sha256"],
        "original_ledger_sha256": fingerprint(ledger),
        "snapshot_sha256": fingerprint(snapshot),
        "stopped_proof_sha256": fingerprint(stopped),
        "url": ROOT,
        "request_sha256": fingerprint(REQUEST),
        "native_body_sha256": fingerprint(body),
        "profile": profile,
        "price_input_usd_per_million": 1.5,
        "price_output_usd_per_million": 7.5,
        "remaining_before_usd": prior,
        "conservative_debit_usd": DEBIT,
        "remaining_after_usd": prior - DEBIT,
        "max_dispatches": 1,
        "max_bytes": MAX_BYTES,
        "deadline_seconds": TIMEOUT,
    }
    with (DIRECTORY / "consumed.json").open("x") as handle:
        json.dump(consumed, handle)
        handle.flush()
        os.fsync(handle.fileno())
    fsync_directory(DIRECTORY)
    return key, adapter, body


def enforce_bounds(data, chunk, deadline):
    if time.monotonic() >= deadline or len(data) + len(chunk) > MAX_BYTES:
        raise ValueError("Bound exceeded")


async def dispatch(key, adapter, body):
    result = {"status": "consumed_failed", "http_status": None}
    deadline = time.monotonic() + TIMEOUT
    try:
        async with (
            asyncio.timeout(TIMEOUT),
            httpx.AsyncClient(
                trust_env=False,
                timeout=30,
                follow_redirects=False,
                transport=httpx.AsyncHTTPTransport(retries=0),
            ) as client,
            client.stream(
                "POST",
                ROOT,
                headers={
                    "authorization": "Bearer " + key,
                    "accept-encoding": "identity",
                },
                json=body,
            ) as response,
        ):
            result["http_status"] = response.status_code
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                raise ValueError("Unexpected compressed response")
            data = bytearray()
            async for chunk in response.aiter_raw(chunk_size=4096):
                enforce_bounds(data, chunk, deadline)
                data.extend(chunk)
            enforce_bounds(data, b"", deadline)
            parsed = json.loads(data)
            result["structure"] = structure(parsed)
            try:
                translated = adapter.translate_success(
                    "responses",
                    parsed,
                    logical_model=REQUEST["model"],
                    request_body=REQUEST,
                )
                result["translation"] = {
                    "accepted": True,
                    "status": translated.body.get("status"),
                }
            except ValueError as error:
                result["translation"] = {
                    "accepted": False,
                    "reason": str(error) if str(error) in REASONS else "other_validation",
                }
            enforce_bounds(data, b"", deadline)
            result["status"] = "diagnostic_complete"
    except (TimeoutError, httpx.HTTPError, ValueError, TypeError, RecursionError):
        result["status"] = "consumed_failed"
        result["error_category"] = "transport_or_bound"
    return result


def execute():
    key, adapter, body = prepare()
    result = asyncio.run(dispatch(key, adapter, body))
    with (DIRECTORY / "result.json").open("x") as handle:
        json.dump(result, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    fsync_directory(DIRECTORY)
    print(json.dumps(result))


if __name__ == "__main__":
    execute()
