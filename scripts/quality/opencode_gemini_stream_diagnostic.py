# ruff: noqa: TRY301 -- terminal failures become durable redacted outcomes
"""One consumed, bounded Flash streaming structural diagnostic.

Drives the production GoogleNativeStreamDecoder event-by-event over a single
bounded SSE response and exports only allowlisted structure, numeric usage and
fixed validation-reason enums. No model text, prompts, credentials, response
headers, raw SSE or translated output is ever persisted or printed.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path

import httpx
import opencode_five_validation as validation

from foundry_router.api.adapters import get_adapter
from foundry_router.config import BackendConfig

IDENTITY = "opencode-gemini-flash-stream-diagnostic-v1"
ROOT = "https://opencode.ai/inference/v1/models/gemini-3.8-flash:streamGenerateContent?alt=sse"
REQUEST = {
    "model": "gemini-3.8-flash-zen",
    "input": "Reply with the single word OK.",
    "max_output_tokens": 512,
    "stream": True,
    "store": False,
}
KEYS = frozenset(
    {
        "candidates",
        "usageMetadata",
        "promptFeedback",
        "modelVersion",
        "responseId",
        "modelStatus",
        "createTime",
        "modelStage",
        "message",
        "retirementTime",
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
REASONS = frozenset(
    {
        "Invalid native response envelope",
        "Unsupported native envelope or provider state",
        "Invalid native creation time metadata",
        "Invalid native model status metadata",
        "Native model status metadata exceeds bound",
        "Native usage must be an object",
        "Invalid native usage dimensions",
        "Native thinking or tool prompt usage is disabled",
        "Native cumulative usage decreased",
        "Native SSE envelope lacks content",
        "Unsupported native feedback or provider state",
        "Invalid native candidates",
        "Native response lacks candidate or block evidence",
        "Native response requires one candidate",
        "Unsupported native candidate or provider state",
        "Native candidate index must be zero",
        "Invalid native output role",
        "Unsupported native content or provider state",
        "Native output parts exceed bound",
        "Invalid native output part",
        "Native function identity/arguments required",
        "Unsupported native output or provider state",
        "Native output exceeds aggregate byte bound",
        "Invalid native finish reason",
        "Unsupported native finish reason",
        "Native content arrived after finish",
        "Native stream ended without clean finish evidence",
        "Google stream framing exceeds bound",
        "Google stream event exceeds bound",
        "Duplicate JSON keys are unsupported",
        "Nonfinite JSON values are unsupported",
        "JSON exceeds the byte bound",
        "Invalid bounded JSON",
        "JSON exceeds the depth bound",
        "Validation exceeds the work bound",
        "Native message segments exceed bound",
        "Invalid bounded tool call identity",
        "Invalid function identity or argument shape",
        "Provider called an undeclared function",
        "Function arguments must be a JSON object",
        "Provider exceeded the configured call count",
        "Invalid or duplicate provider function call",
        "Provider violated tool choice",
        "Provider violated named tool choice",
        "Named tool choice requires exactly one call",
        "Provider omitted a required tool call",
        "Provider tool calls must be an array",
        "Unsupported provider call or continuation state",
        "Unsupported provider function or continuation state",
        "Provider function arguments exceed their bound",
        "Unsupported Google tool deltas",
        "Unsupported Google signature wrapper",
    }
)

PRIVATE = Path("/private/tmp/opencode-five-release")
DIRECTORY = PRIVATE / "stream-diagnostic-v1"
PACKET_NAME = "stream-diagnostic-packet.json"
MANIFEST_NAME = "runner5/manifest.json"
IDENTITY_NAME = "runner5/identity.json"
LEDGER_NAME = "runner5/ledger.json"
FINAL_ADMIN_NAME = "staging5-final-admin.json"
STOPPED_NAME = "staging5-stopped.json"
CONTAINER_ID_NAME = "stage5-container-id.txt"
FUNDS_NAME = "stream-funds-admin.json"
MAX_BYTES = 256 * 1024
EVENT_BYTES = 256 * 1024
MAX_EVENTS = 512
TIMEOUT = 120
R_FUNDS = 0.104
DEBIT = 0.004
STAGE_SEED = 0.10
WORST_STAGING_USD = 0.046335
MIN_RESERVE = 0.05
CA6_IMAGE = "sha256:180b9d9efc0f5ccb01528ac8178ac28babae2470e991cbd34f212a22cad6d27e"
CA6_STAGE_SEED = 0.088
PROD_SEED = 9.9
HTTP_OK = 200
EPS = 1e-9
MAX_DEPTH = 8
MAX_TOKEN_COUNT = 1_000_000

assert abs((R_FUNDS - DEBIT) - STAGE_SEED) < EPS
assert STAGE_SEED - WORST_STAGING_USD > MIN_RESERVE


def fingerprint(data):
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def dependency_hashes():
    root = Path(__file__).resolve().parent.parent.parent
    names = {
        "google_native": root / "src/foundry_router/api/adapters/google_native.py",
        "google_ai_studio": root / "src/foundry_router/api/adapters/google_ai_studio.py",
        "openai_compatible": root / "src/foundry_router/api/adapters/openai_compatible.py",
        "google_schema": root / "src/foundry_router/api/adapters/google_schema.py",
        "google_tools": root / "src/foundry_router/api/adapters/google_tools.py",
        "five_validation": root / "scripts/quality/opencode_five_validation.py",
    }
    return {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in names.items()}


def fsync_directory(directory):
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


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


def split_events(raw):
    """Split raw SSE bytes preserving each frame's original delimiter.

    The trailing remainder (no terminating blank line) is retained as an
    unterminated part so the production decoder observes the same EOF shape
    instead of a repaired framing.
    """
    parts = []
    pos = 0
    for match in re.finditer(rb"\r\n\r\n|\n\n", raw):
        frame = raw[pos : match.start()]
        if len(frame):
            parts.append((frame, match.group(0)))
        pos = match.end()
    tail = raw[pos:]
    if len(tail):
        parts.append((tail, b""))
    if len(parts) > MAX_EVENTS:
        raise ValueError("Diagnostic event bound exceeded")
    return parts


def event_data(frame):
    return b"\n".join(line[5:].lstrip() for line in frame.splitlines() if line.startswith(b"data:"))


def map_reason(error):
    message = str(error)
    return message if message in REASONS else "other_validation"


def feed_event(decoder, frame, delimiter):
    """Feed exactly the received bytes; never synthesize a missing delimiter."""
    try:
        emitted = decoder.feed(frame + delimiter)
    except ValueError as error:
        return map_reason(error), 0
    return None, len(emitted)


def classify_stream(decoder, raw):
    frames = split_events(raw)
    events = []
    translated = 0
    rejected = None
    for index, (frame, delimiter) in enumerate(frames):
        terminated = len(delimiter) > 0
        if len(frame) > EVENT_BYTES:
            reason, _ = feed_event(decoder, frame, delimiter)
            entry = {
                "index": index,
                "bytes": len(frame),
                "kind": "oversized",
                "decoder": reason or "accepted",
            }
            events.append(entry)
            rejected = reason or "accepted_oversized_frame"
            break
        data = event_data(frame)
        if not data.strip():
            reason, count = feed_event(decoder, frame, delimiter)
            translated += count
            events.append(
                {"index": index, "bytes": len(frame), "kind": "no_data", "decoder": "accepted"}
                if reason is None
                else {
                    "index": index,
                    "bytes": len(frame),
                    "kind": "no_data",
                    "decoder": reason,
                }
            )
            if reason is not None:
                rejected = reason
                break
            continue
        try:
            payload = json.loads(data)
        except (ValueError, TypeError, RecursionError):
            payload = None
        entry = {
            "index": index,
            "bytes": len(frame),
            "kind": "unterminated" if not terminated else "data",
            "structure": structure(payload) if payload is not None else {"kind": "unparseable"},
        }
        reason, count = feed_event(decoder, frame, delimiter)
        translated += count
        if not terminated and reason is None:
            entry["decoder"] = "buffered"
        else:
            entry["decoder"] = "accepted" if reason is None else reason
        events.append(entry)
        if reason is not None:
            rejected = reason
            break
    unprocessed = len(frames) - len(events)
    outcome = {"events": events, "translated_events": translated, "unprocessed": unprocessed}
    if rejected is not None:
        outcome["finish"] = "not_attempted_after_rejection"
        outcome["rejected"] = rejected
        outcome["usage"] = {"input_tokens": None, "output_tokens": None}
        return outcome
    try:
        decoder.finish()
    except ValueError as error:
        outcome["finish"] = map_reason(error)
        outcome["usage"] = {"input_tokens": None, "output_tokens": None}
        return outcome
    known = decoder.usage
    usage = {
        "input_tokens": known[0] if type(known[0]) is int else None,
        "output_tokens": known[1] if type(known[1]) is int else None,
    }
    outcome["finish"] = "accepted"
    outcome["usage"] = usage
    return outcome


def read_json(path):
    try:
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("Diagnostic state unavailable")
        return json.loads(path.read_text())
    except OSError as error:
        raise ValueError("Diagnostic state unavailable") from error


def check_packet(packet):
    if packet.get("diagnostic_id") != IDENTITY:
        raise ValueError("Diagnostic packet unavailable")
    if packet.get("executor_sha256") != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError("Diagnostic executor binding changed")
    if packet.get("dependency_sha256") != dependency_hashes():
        raise ValueError("Diagnostic dependency binding changed")
    if (
        packet.get("funds_before_usd") != R_FUNDS
        or packet.get("conservative_debit_usd") != DEBIT
        or packet.get("stage_seed_usd") != STAGE_SEED
    ):
        raise ValueError("Diagnostic funding binding changed")


def check_history(sources):
    manifest = sources["manifest"]
    identity = sources["identity"]
    ledger = sources["ledger"]
    snapshot = sources["snapshot"]
    expected_cases = validation.cases_for(validation.ANTHROPIC_RUN)
    if (
        manifest.get("run") != validation.ANTHROPIC_RUN
        or manifest.get("image_digest") != CA6_IMAGE
        or manifest.get("staging_allocation_usd") != CA6_STAGE_SEED
        or manifest.get("production_seed_usd") != PROD_SEED
        or manifest.get("cases") != expected_cases
        or identity != {"manifest_sha256": fingerprint(manifest)}
        or set(ledger) != {"manifest_sha256", "entries"}
        or ledger["manifest_sha256"] != identity["manifest_sha256"]
        or len(ledger["entries"]) != len(expected_cases)
    ):
        raise ValueError("ca6 historical binding unavailable")
    for case, entry in zip(expected_cases[:7], ledger["entries"][:7], strict=True):
        if (
            set(entry) != {"reserved", "result"}
            or entry["reserved"] is not True
            or entry["result"]["status"] != "passed"
        ):
            raise ValueError("ca6 staging acceptance unavailable")
        validation.validate_passed_result(case, entry["result"])
    if any(entry != {"reserved": False, "result": None} for entry in ledger["entries"][7:]):
        raise ValueError("ca6 production slots must remain unconsumed")
    stopped_live = snapshot["credit_groups"]["opencode-account"]["live"]
    debit_sum = sum(entry["result"]["estimated_debit_usd"] for entry in ledger["entries"][:7])
    if not math.isclose(
        stopped_live["estimated_remaining_usd"],
        CA6_STAGE_SEED - debit_sum,
        abs_tol=1e-9,
        rel_tol=0,
    ):
        raise ValueError("ca6 debit history does not reconcile")
    return stopped_live


def check_funding(sources, stopped_live):
    live = sources["funds"]["credit_groups"]["opencode-account"]["live"]
    stopped = sources["stopped"]
    prior = live["estimated_remaining_usd"]
    if (
        type(prior) not in {int, float}
        or not math.isfinite(prior)
        or not math.isclose(prior, R_FUNDS, abs_tol=1e-12, rel_tol=0)
        or prior - DEBIT < STAGE_SEED - EPS
        or prior - DEBIT <= MIN_RESERVE
        or live["active_reservations"] != 0
        or live["reserved_inflight_usd"] != 0
        or stopped_live["active_reservations"] != 0
        or stopped_live["reserved_inflight_usd"] != 0
        or stopped.get("stopped") is not True
        or stopped.get("unused_allocation_not_transferred") is not True
    ):
        raise ValueError("Fresh staging funding or stopped-history binding unavailable")
    return prior


def history_pins(sources):
    return {
        "ca6_manifest_sha256": fingerprint(sources["manifest"]),
        "ca6_ledger_sha256": fingerprint(sources["ledger"]),
        "ca6_snapshot_sha256": fingerprint(sources["snapshot"]),
        "ca6_stopped_proof_sha256": fingerprint(sources["stopped"]),
        "container_id_sha256": hashlib.sha256(sources["container_id"]).hexdigest(),
        "funds_snapshot_sha256": fingerprint(sources["funds"]),
    }


def check_pins(packet, pins):
    for key, value in pins.items():
        if packet.get(key) != value:
            raise ValueError("Diagnostic history binding changed")


def prepare():
    packet = read_json(PRIVATE / PACKET_NAME)
    check_packet(packet)
    funds = read_json(PRIVATE / FUNDS_NAME)
    live = funds["credit_groups"]["opencode-account"]["live"]
    manifest = read_json(PRIVATE / MANIFEST_NAME)
    identity = read_json(PRIVATE / IDENTITY_NAME)
    ledger = read_json(PRIVATE / LEDGER_NAME)
    snapshot = read_json(PRIVATE / FINAL_ADMIN_NAME)
    stopped = read_json(PRIVATE / STOPPED_NAME)
    container_id = (PRIVATE / CONTAINER_ID_NAME).read_bytes()
    sources = {
        "funds": funds,
        "live": live,
        "manifest": manifest,
        "identity": identity,
        "ledger": ledger,
        "snapshot": snapshot,
        "stopped": stopped,
        "container_id": container_id,
    }
    stopped_live = check_history(sources)
    check_pins(packet, history_pins(sources))
    prior = check_funding(sources, stopped_live)
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
    if fingerprint(REQUEST) != packet.get("request_sha256") or fingerprint(body) != packet.get(
        "native_body_sha256"
    ):
        raise ValueError("Diagnostic request binding changed")
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    if (DIRECTORY / "consumed.json").exists() or (DIRECTORY / "result.json").exists():
        raise ValueError("Diagnostic identity already claimed")
    fsync_directory(PRIVATE)
    consumed = {
        "diagnostic_id": IDENTITY,
        "packet_sha256": hashlib.sha256((PRIVATE / PACKET_NAME).read_bytes()).hexdigest(),
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "ca6_manifest_sha256": fingerprint(manifest),
        "ca6_ledger_sha256": fingerprint(ledger),
        "ca6_snapshot_sha256": fingerprint(snapshot),
        "ca6_stopped_proof_sha256": fingerprint(stopped),
        "funds_snapshot_sha256": fingerprint(funds),
        "url": ROOT,
        "request_sha256": fingerprint(REQUEST),
        "native_body_sha256": fingerprint(body),
        "profile": profile,
        "price_input_usd_per_million": 1.5,
        "price_output_usd_per_million": 7.5,
        "funds_before_usd": prior,
        "conservative_debit_usd": DEBIT,
        "funds_after_diagnostic_usd": prior - DEBIT,
        "stage_seed_usd": STAGE_SEED,
        "max_dispatches": 1,
        "max_bytes": MAX_BYTES,
        "max_events": MAX_EVENTS,
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
    result = {
        "status": "consumed_failed",
        "http_status": None,
        "diagnostic_id": IDENTITY,
        "conservative_debit_usd": DEBIT,
    }
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
            if response.status_code != HTTP_OK:
                raise ValueError("Unexpected upstream status")
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                raise ValueError("Unexpected compressed response")
            decoder = adapter.create_stream_decoder(
                logical_model=REQUEST["model"], metadata={}, request_body=REQUEST
            )
            data = bytearray()
            async for chunk in response.aiter_raw(chunk_size=4096):
                enforce_bounds(data, chunk, deadline)
                data.extend(chunk)
            enforce_bounds(data, b"", deadline)
            result.update(classify_stream(decoder, bytes(data)))
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
