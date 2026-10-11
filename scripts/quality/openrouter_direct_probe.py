"""Bounded OpenRouter direct envelope probes; never router traffic.

Test-only diagnostic tooling. Sends at most one request per fixed model,
straight at the provider, to capture envelope STRUCTURE (field names, finish
reasons, content classification with byte lengths, usage integers). Content
values, error bodies, and credentials are never persisted, printed, or logged.
Each model is probed at most once ever: existing outcomes are resumed, never
replayed, and results live in one canonical file with atomic writes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx
from zen_openrouter_live_budget import locked, write_atomic

from foundry_router.api.adapters.google_schema import load_bounded_json

ROOT = Path(__file__).resolve().parents[2]
STAGE_DIR = ROOT / "docs/plans/zen-openrouter-live-verification"
RESULTS_PATH = STAGE_DIR / "results-probe.json"
MAX_RESULTS_BYTES = 65536

PROBE_URL = "https://openrouter.ai/api/v1/chat/completions"
PROMPT = "Reply with the word ready."
MAX_COMPLETION_TOKENS = 128
PROBE_TIMEOUT_SECONDS = 120
MAX_BODY_BYTES = 1024 * 1024
MAX_REQUEST_BYTES = 4096

PROBES: tuple[tuple[str, str], ...] = (
    ("probe-gemma", "google/gemma-4-26b-a4b-it:free"),
    ("probe-openai", "openai/gpt-4o-mini"),
    ("probe-anthropic", "anthropic/claude-haiku-4.5"),
)

CONTENT_KINDS = {
    "missing",
    "empty",
    "whitespace",
    "text",
    "refusal",
    "tool_calls",
    "list-parts",
    "other",
}

EXPECTED_TOP_FIELDS = {
    "id",
    "choices",
    "created",
    "model",
    "object",
    "system_fingerprint",
    "usage",
}


def build_body(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
    }


def _strict_ints(payload: Any, *names: str) -> tuple[int, ...] | None:
    if not isinstance(payload, dict):
        return None
    values = []
    for name in names:
        value = payload.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        values.append(value)
    return tuple(values)


def classify_envelope(payload: Any) -> dict[str, Any]:  # noqa: PLR0912 -- fixed structural checklist
    """Structural summary only; never returns content values."""
    summary: dict[str, Any] = {
        "top_fields": [],
        "extra_top_fields": [],
        "finish_reason": None,
        "message_fields": [],
        "extra_message_fields": [],
        "content_kind": "missing",
        "content_length": 0,
        "usage": None,
        "usage_valid": False,
    }
    if not isinstance(payload, dict):
        summary["content_kind"] = "other"
        return summary
    summary["top_fields"] = sorted(str(key) for key in payload)
    summary["extra_top_fields"] = sorted(set(payload) - EXPECTED_TOP_FIELDS)
    choices = payload.get("choices")
    choice = choices[0] if isinstance(choices, list) and len(choices) == 1 else None
    if not isinstance(choice, dict):
        return summary
    finish = choice.get("finish_reason")
    summary["finish_reason"] = finish if isinstance(finish, str) else None
    message = choice.get("message")
    if not isinstance(message, dict):
        return summary
    summary["message_fields"] = sorted(str(key) for key in message)
    summary["extra_message_fields"] = sorted(
        set(message) - {"role", "content", "refusal", "tool_calls"}
    )
    refusal = message.get("refusal")
    calls = message.get("tool_calls")
    content = message.get("content")
    if isinstance(refusal, str) and refusal:
        summary["content_kind"] = "refusal"
        summary["content_length"] = len(refusal.encode("utf-8", "ignore"))
    elif isinstance(calls, list) and calls:
        summary["content_kind"] = "tool_calls"
    elif content is None:
        summary["content_kind"] = "missing"
    elif isinstance(content, str):
        summary["content_length"] = len(content.encode("utf-8", "ignore"))
        if not content:
            summary["content_kind"] = "empty"
        elif not content.strip():
            summary["content_kind"] = "whitespace"
        else:
            summary["content_kind"] = "text"
    elif isinstance(content, list):
        summary["content_kind"] = "list-parts"
        summary["content_length"] = len(
            json.dumps(content, sort_keys=True).encode("utf-8", "ignore")
        )
    else:
        summary["content_kind"] = "other"
    usage = payload.get("usage")
    counts = _strict_ints(usage, "prompt_tokens", "completion_tokens", "total_tokens")
    if counts is not None:
        summary["usage"] = {
            "prompt_tokens": counts[0],
            "completion_tokens": counts[1],
            "total_tokens": counts[2],
        }
        summary["usage_valid"] = counts[2] == counts[0] + counts[1]
    return summary


def load_probe_results(path: Path, *, data: Any = None) -> dict[str, Any]:
    if data is None:
        if not path.exists():
            return {"probe": "openrouter-direct", "attempts": []}
        if path.stat().st_size > MAX_RESULTS_BYTES:
            raise ValueError("Invalid probe results")
        data = load_bounded_json(path.read_text(), max_bytes=MAX_RESULTS_BYTES)
    if (
        not isinstance(data, dict)
        or data.get("probe") != "openrouter-direct"
        or not isinstance(data.get("attempts"), list)
    ):
        raise ValueError("Invalid probe results")
    seen = set()
    allowed = {probe for probe, _ in PROBES}
    for attempt in data["attempts"]:
        if (
            not isinstance(attempt, dict)
            or attempt.get("probe_id") not in allowed
            or attempt["probe_id"] in seen
        ):
            raise ValueError("Invalid probe results")
        seen.add(attempt["probe_id"])
    return data


async def run_probe(  # noqa: PLR0911 -- fixed outcome checklist
    probe_id: str, model: str, credential: str, transport: httpx.AsyncBaseTransport
) -> dict[str, Any]:
    """One bounded direct request; returns structural evidence only."""
    started = time.monotonic()
    result: dict[str, Any] = {
        "probe_id": probe_id,
        "model": model,
        "http_status": None,
        "dispatched": False,
        "elapsed_seconds": 0.0,
        "structure": None,
        "error_category": None,
    }

    def finish(category: str | None) -> dict[str, Any]:
        result["error_category"] = category
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        return result

    body = build_body(model)
    raw_body = json.dumps(body).encode()
    if len(raw_body) > MAX_REQUEST_BYTES:
        return finish("request_bound_exceeded")
    try:
        async with asyncio.timeout(PROBE_TIMEOUT_SECONDS):
            async with httpx.AsyncClient(
                transport=transport, timeout=PROBE_TIMEOUT_SECONDS, trust_env=False
            ) as client:
                response = await client.post(
                    PROBE_URL,
                    headers={
                        "authorization": "Bearer " + credential,
                        "accept-encoding": "identity",
                        "content-type": "application/json",
                    },
                    content=raw_body,
                )
    except (TimeoutError, OSError, RuntimeError, httpx.HTTPError, ValueError):
        # Transport-raised values carry no trusted content; never persist them.
        return finish("transport_failure")
    result["dispatched"] = True
    result["http_status"] = response.status_code
    if response.headers.get("content-encoding", "identity").lower() != "identity":
        return finish("encoded_response")
    try:
        chunks = bytearray()
        async for chunk in response.aiter_bytes():
            if len(chunks) + len(chunk) > MAX_BODY_BYTES:
                return finish("response_bound_exceeded")
            chunks.extend(chunk)
    except (OSError, RuntimeError, httpx.HTTPError):
        return finish("transport_failure")
    finally:
        await response.aclose()
    try:
        payload = load_bounded_json(bytes(chunks).decode("utf-8"), max_bytes=MAX_BODY_BYTES)
    except (ValueError, UnicodeError):
        return finish("malformed_response")
    result["structure"] = classify_envelope(payload)
    return finish(None)


def execute_probes(
    *,
    stage_dir: Path | None = None,
    credential: str | None = None,
    transport_factory: Any = None,
) -> dict[str, Any]:
    """Probe each unrecorded model once; never replay recorded outcomes."""
    if not credential or not credential.strip():
        raise ValueError("Verification credential unavailable")
    # Resolve at call time so tests can isolate the directory.
    directory = stage_dir if stage_dir is not None else STAGE_DIR
    results_path = directory / "results-probe.json"
    with locked(directory / "stage"):
        results = load_probe_results(results_path)
        recorded = {item["probe_id"] for item in results["attempts"]}
        factory = transport_factory or (
            lambda: httpx.AsyncHTTPTransport(trust_env=False, retries=0)
        )
        for probe_id, model in PROBES:
            if probe_id in recorded:
                continue
            outcome = asyncio.run(run_probe(probe_id, model, credential, factory()))
            results["attempts"].append(outcome)
            load_probe_results(results_path, data=results)
            write_atomic(results_path, results)
            recorded.add(probe_id)
        return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--openrouter-key-env", default="OPENROUTER_API_KEY")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status": "refused", "probes": 0}))
        return 2
    logging.disable(logging.CRITICAL)
    try:
        key = os.environ.get(args.openrouter_key_env, "")
        results = execute_probes(credential=key)
    except (OSError, ValueError, RuntimeError):
        print(json.dumps({"status": "refused_or_interrupted", "probes": "unknown"}))
        return 2
    summary = {
        item["probe_id"]: {
            "http_status": item["http_status"],
            "finish_reason": (item["structure"] or {}).get("finish_reason"),
            "content_kind": (item["structure"] or {}).get("content_kind"),
            "usage_valid": (item["structure"] or {}).get("usage_valid"),
            "error_category": item["error_category"],
        }
        for item in results["attempts"]
    }
    print(json.dumps({"probe": "openrouter-direct", "results": summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
