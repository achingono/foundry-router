"""Black-box staging/production validation for Zen/OpenRouter enablement.

Test-only verification tooling; never production configuration. Exercises a
deployed router through its public and admin routes only: readiness, catalog,
bounded inference, and canonical credit-group evidence. No provider transport
is observed, so independent upstream cross-checks are recorded as a limitation
rather than claimed. Prompts, outputs, vectors, error bodies, and credentials
are never persisted, printed, or logged; only statuses, counts, numeric deltas
and acceptance flags leave this module.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Any

import httpx
from zen_openrouter_live_budget import locked, write_atomic

from foundry_router.api.adapters.google_schema import load_bounded_json

ROOT = Path(__file__).resolve().parents[2]
STAGE_DIR = ROOT / "docs/plans/production-zen-openrouter"
MAX_RESULTS_BYTES = 65536

STAGING_RUN_ID = "staging-zen-openrouter-2026-10-11"
PRODUCTION_RUN_ID = "production-zen-openrouter-2026-10-11"

PROMPT = "Reply with the word ready."
MAX_OUTPUT_TOKENS = 128
PREFLIGHT_INPUT_TOKENS = 512
PREFLIGHT_OUTPUT_TOKENS = 128
CASE_TIMEOUT_SECONDS = 120
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_FRAME_BYTES = 256 * 1024
ALLOWANCE_USD = 0.01
ADMIN_TIMEOUT_SECONDS = 5
CLEANUP_POLLS = 10
CLEANUP_INTERVAL_SECONDS = 1.0
HTTP_OK = 200
HTTP_STATUS_MIN = 100
HTTP_STATUS_MAX = 599
MAX_SECRET_STRING = 256
MAX_RETRY_DELAY_SECONDS = 3600
MAX_REQUEST_BYTES = 4096
SETTLEMENT_TOLERANCE_USD = 2e-6

STAGING_CASES = (
    "staging-zen-nonstream",
    "staging-zen-stream",
    "staging-openai-nonstream",
    "staging-haiku-nonstream",
)
PRODUCTION_CASES = (
    "production-zen-nonstream",
    "production-zen-stream",
)

RUN_ENVIRONMENTS = {STAGING_RUN_ID: "staging", PRODUCTION_RUN_ID: "production"}
RUN_CASES = {STAGING_RUN_ID: STAGING_CASES, PRODUCTION_RUN_ID: PRODUCTION_CASES}
RUN_FILES = {
    STAGING_RUN_ID: ("ledger-staging.json", "results-staging.json"),
    PRODUCTION_RUN_ID: ("ledger-production.json", "results-production.json"),
}

ERROR_CATEGORIES = {
    "transport_failure",
    "encoded_response",
    "response_bound_exceeded",
    "malformed_response",
    "acceptance_mismatch",
    "cleanup_timeout",
    "request_bound_exceeded",
}

RESULT_KEYS = {
    "case_id",
    "pool",
    "stream",
    "status",
    "http_status",
    "provider",
    "deployment",
    "dispatched",
    "input_tokens",
    "output_tokens",
    "usage_coherent",
    "terminated_ok",
    "settlement_matches",
    "reservations_cleared",
    "synthetic_debit_usd",
    "retry_attempts",
    "retry_max_delay_seconds",
    "independent_upstream_observed",
    "error_category",
    "elapsed_seconds",
}


class ValidationSetupError(ValueError):
    """Local readiness/auth/admin checks failed before any inference dispatch."""


def _require_setup(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationSetupError(message)


def _strict_positive_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) > 0
    )


def validate_manifest(manifest: Any) -> dict[str, Any]:
    """Bind run identity, fixed cases, prompt, bounds, and allowance."""
    run = manifest.get("run") if isinstance(manifest, dict) else None
    cases = manifest.get("cases") if isinstance(manifest, dict) else None
    if (
        not isinstance(manifest, dict)
        or manifest.get("version") != 1
        or run not in RUN_CASES
        or manifest.get("environment") != RUN_ENVIRONMENTS[run]
        or not isinstance(cases, list)
        or [case.get("id") for case in cases] != list(RUN_CASES[run])
    ):
        raise ValueError("Invalid staging manifest")
    total = 0.0
    for case in cases:
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("id"), str)
            or not isinstance(case.get("pool"), str)
            or not case["pool"].strip()
            or case.get("operation") != "responses"
            or not isinstance(case.get("stream"), bool)
            or not isinstance(case.get("provider"), str)
            or not case["provider"].strip()
            or not isinstance(case.get("deployment"), str)
            or not case["deployment"].strip()
            or not _strict_positive_number(case.get("input_per_million"))
            or not _strict_positive_number(case.get("output_per_million"))
        ):
            raise ValueError("Invalid staging case")
        total += (
            PREFLIGHT_INPUT_TOKENS * float(case["input_per_million"])
            + PREFLIGHT_OUTPUT_TOKENS * float(case["output_per_million"])
        ) / 1_000_000
    if (
        manifest.get("prompt") != PROMPT
        or manifest.get("max_output_tokens") != MAX_OUTPUT_TOKENS
        or manifest.get("case_timeout_seconds") != CASE_TIMEOUT_SECONDS
        or manifest.get("max_response_bytes") != MAX_RESPONSE_BYTES
        or manifest.get("max_frame_bytes") != MAX_FRAME_BYTES
        or manifest.get("allowance_usd") != ALLOWANCE_USD
        or not total <= ALLOWANCE_USD
    ):
        raise ValueError("Invalid staging bounds or allowance")
    return {"run": run, "cases": [case["id"] for case in cases]}


def manifest_fingerprint(manifest: dict[str, Any]) -> dict[str, Any]:
    # The fixed prompt text stays out of persisted state by redaction policy;
    # run identity, environment, cases, bounds, and allowance bind the run.
    return {
        "run": manifest["run"],
        "environment": manifest["environment"],
        "cases": [{key: case[key] for key in sorted(case)} for case in manifest["cases"]],
        "max_output_tokens": manifest["max_output_tokens"],
        "allowance_usd": manifest["allowance_usd"],
    }


class StagingLedger:
    """Durable reserve-before-egress ledger for one validation run."""

    def __init__(self, path: Path, *, initialize: bool = False, run: str):
        if run not in RUN_CASES:
            raise ValueError("Unknown validation run")
        self.path = path
        self.run = run
        self.identity_path = path.with_name(path.name + ".identity")
        with locked(path):
            if not path.exists():
                if not initialize or self.identity_path.exists():
                    raise ValueError("Initialized ledger is missing")
                write_atomic(
                    path,
                    {
                        "run": run,
                        "dispatches": 0,
                        "halted": False,
                        "cases": {
                            case_id: {"reserved": False, "outcome": None}
                            for case_id in RUN_CASES[run]
                        },
                    },
                )
                write_atomic(self.identity_path, {"run": run})
            if not self.identity_path.exists():
                raise ValueError("Ledger identity is missing")
            identity = load_bounded_json(self.identity_path.read_bytes().decode(), max_bytes=1024)
            if identity != {"run": run}:
                raise ValueError("Invalid ledger identity")
            self._read()

    def _read(self) -> dict[str, Any]:
        if self.path.stat().st_size > MAX_RESULTS_BYTES:
            raise ValueError("Invalid ledger")
        data = load_bounded_json(self.path.read_bytes().decode(), max_bytes=MAX_RESULTS_BYTES)
        if (
            not isinstance(data, dict)
            or data.get("run") != self.run
            or type(data.get("dispatches")) is not int
            or type(data.get("halted")) is not bool
            or not isinstance(data.get("cases"), dict)
            or set(data["cases"]) != set(RUN_CASES[self.run])
        ):
            raise ValueError("Invalid ledger")
        reserved = 0
        for case in data["cases"].values():
            if (
                not isinstance(case, dict)
                or set(case) != {"reserved", "outcome"}
                or type(case["reserved"]) is not bool
                or case["outcome"] not in {None, "passed", "failed"}
                or (case["outcome"] is not None and not case["reserved"])
            ):
                raise ValueError("Invalid ledger")
            reserved += int(case["reserved"])
        if data["dispatches"] != reserved or reserved > len(RUN_CASES[self.run]):
            raise ValueError("Invalid ledger")
        if (
            any(case["outcome"] == "failed" for case in data["cases"].values())
            and not data["halted"]
        ):
            raise ValueError("Invalid ledger")
        return data

    def reserve(self, case_id: str) -> None:
        if case_id not in RUN_CASES[self.run]:
            raise ValueError("Unknown validation case")
        with locked(self.path):
            data = self._read()
            case = data["cases"][case_id]
            if data["halted"] or case["reserved"]:
                raise ValueError("Case reservation unavailable")
            case["reserved"] = True
            data["dispatches"] += 1
            write_atomic(self.path, data)

    def record_outcome(self, case_id: str, *, failed: bool) -> None:
        if case_id not in RUN_CASES[self.run]:
            raise ValueError("Invalid case outcome")
        with locked(self.path):
            data = self._read()
            case = data["cases"][case_id]
            if not case["reserved"] or case["outcome"] is not None:
                raise ValueError("Case outcome already recorded")
            case["outcome"] = "failed" if failed else "passed"
            if failed:
                data["halted"] = True
            write_atomic(self.path, data)

    def runnable(self, case_id: str) -> bool:
        with locked(self.path):
            data = self._read()
            return (
                not data["halted"]
                and case_id in RUN_CASES[self.run]
                and not data["cases"][case_id]["reserved"]
            )


def _serialized_size(data: Any) -> int:
    return len(json.dumps(data).encode("utf-8"))


def validate_result(  # noqa: PLR0912 -- bounded evidence schema
    result: Any, manifest: dict[str, Any]
) -> None:
    """Bounded schema for persisted validation outcomes."""
    cases = {case["id"]: case for case in manifest["cases"]}
    if not isinstance(result, dict) or set(result) != RESULT_KEYS:
        raise ValueError("Invalid validation result")
    case = cases.get(result.get("case_id"))
    if case is None or result.get("pool") != case["pool"]:
        raise ValueError("Invalid result binding")
    if type(result.get("stream")) is not bool or result["stream"] != case["stream"]:
        raise ValueError("Invalid result stream mode")
    if result.get("status") not in {"passed", "failed"}:
        raise ValueError("Invalid result status")
    status = result.get("http_status")
    if status is not None and (
        type(status) is not int or not HTTP_STATUS_MIN <= status <= HTTP_STATUS_MAX
    ):
        raise ValueError("Invalid result status code")
    for name in ("provider", "deployment"):
        value = result.get(name)
        if value is not None and (not isinstance(value, str) or len(value) > MAX_SECRET_STRING):
            raise ValueError("Invalid result backend identity")
    if type(result.get("dispatched")) is not bool:
        raise ValueError("Invalid result dispatch flag")
    for name in ("input_tokens", "output_tokens"):
        value = result.get(name)
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("Invalid result token counts")
    for name in (
        "usage_coherent",
        "terminated_ok",
        "settlement_matches",
        "reservations_cleared",
        "independent_upstream_observed",
    ):
        if type(result.get(name)) is not bool:
            raise ValueError("Invalid result flags")
    for name in ("retry_attempts", "retry_max_delay_seconds"):
        value = result.get(name)
        if value is not None and (type(value) is not int or isinstance(value, bool) or value < 0):
            raise ValueError("Invalid result retry policy")
        if (
            name == "retry_max_delay_seconds"
            and value is not None
            and value > MAX_RETRY_DELAY_SECONDS
        ):
            raise ValueError("Invalid result retry policy")
    debit = result.get("synthetic_debit_usd")
    if type(debit) not in {int, float} or not 0 <= debit <= ALLOWANCE_USD:
        raise ValueError("Invalid result debit")
    if result.get("error_category") not in {
        None,
        "transport_failure",
        "encoded_response",
        "response_bound_exceeded",
        "malformed_response",
        "acceptance_mismatch",
        "cleanup_timeout",
        "request_bound_exceeded",
    }:
        raise ValueError("Invalid result error category")
    elapsed = result.get("elapsed_seconds")
    if type(elapsed) not in {int, float} or not 0 <= elapsed <= CASE_TIMEOUT_SECONDS + 60:
        raise ValueError("Invalid result elapsed time")
    if _serialized_size(result) > MAX_RESULTS_BYTES:
        raise ValueError("Invalid result size")
    if result["status"] == "passed" and (
        not result["dispatched"]
        or result["http_status"] != HTTP_OK
        or not result["usage_coherent"]
        or not result["terminated_ok"]
        or not result["settlement_matches"]
        or not result["reservations_cleared"]
        or result["error_category"] is not None
        or result["input_tokens"] is None
        or result["output_tokens"] is None
    ):
        raise ValueError("Invalid passed validation evidence")


def load_validation_results(path: Path, manifest: dict[str, Any], *, data: Any = None) -> dict:
    if data is None:
        if not path.exists():
            return {
                "run": manifest["run"],
                "manifest": manifest_fingerprint(manifest),
                "attempts": [],
            }
        if path.stat().st_size > MAX_RESULTS_BYTES:
            raise ValueError("Invalid validation results")
        data = load_bounded_json(path.read_text(), max_bytes=MAX_RESULTS_BYTES)
    if (
        not isinstance(data, dict)
        or set(data) != {"run", "manifest", "attempts"}
        or data.get("run") != manifest["run"]
        or data.get("manifest") != manifest_fingerprint(manifest)
        or not isinstance(data.get("attempts"), list)
    ):
        raise ValueError("Invalid validation results")
    if _serialized_size(data) > MAX_RESULTS_BYTES:
        raise ValueError("Invalid validation results")
    seen = set()
    for attempt in data["attempts"]:
        validate_result(attempt, manifest)
        if attempt["case_id"] in seen:
            raise ValueError("Duplicate validation result")
        seen.add(attempt["case_id"])
    return data


async def _read_json_response(response: httpx.Response) -> dict | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


async def _check_health(client: httpx.AsyncClient) -> None:
    try:
        async with asyncio.timeout(ADMIN_TIMEOUT_SECONDS):
            live = await client.get("/health/live")
            ready = await client.get("/health/ready")
    except (TimeoutError, OSError, RuntimeError, httpx.HTTPError) as exc:
        raise ValidationSetupError("Validation health checks failed") from exc
    if live.status_code != HTTP_OK:
        raise ValidationSetupError("Validation liveness failed")
    body = await _read_json_response(ready)
    if ready.status_code != HTTP_OK or body is None or body.get("ready") is not True:
        raise ValidationSetupError("Validation readiness failed")


async def _read_admin(client: httpx.AsyncClient, admin_key: str) -> dict | None:
    try:
        async with asyncio.timeout(ADMIN_TIMEOUT_SECONDS):
            response = await client.get("/admin/status", headers={"x-admin-key": admin_key})
    except (TimeoutError, OSError, RuntimeError, httpx.HTTPError):
        return None
    if response.status_code != HTTP_OK:
        return None
    return await _read_json_response(response)


def _resolve_group(admin: dict, pool: str) -> tuple[str, dict, dict] | None:
    """Resolve pool to its backend config and credit group from admin evidence."""
    try:
        models = admin["models"]
        backends = admin["backends"]
        groups = admin["credit_groups"]
        backend_id = next(iter(models[pool]["backends"]))
        config = backends[backend_id]
        group = config["credit_group"]
        live = groups[group]["live"]
    except (KeyError, TypeError, StopIteration):
        return None
    if not isinstance(live, dict):
        return None
    return group, config, live


def _live_numbers(live: dict) -> tuple[float, int, float] | None:
    try:
        remaining = live["estimated_remaining_usd"]
        active = live["active_reservations"]
        inflight = live["reserved_inflight_usd"]
    except (KeyError, TypeError):
        return None
    if (
        isinstance(remaining, bool)
        or not isinstance(remaining, (int, float))
        or not math.isfinite(float(remaining))
        or float(remaining) < 0
        or isinstance(active, bool)
        or not isinstance(active, int)
        or active < 0
        or isinstance(inflight, bool)
        or not isinstance(inflight, (int, float))
        or not math.isfinite(float(inflight))
        or float(inflight) < 0
    ):
        return None
    return float(remaining), active, float(inflight)


def _public_usage(public: Any) -> tuple[int, int] | None:
    if not isinstance(public, dict):
        return None
    usage = public.get("usage")
    if not isinstance(usage, dict):
        return None
    values = []
    for name in ("input_tokens", "output_tokens"):
        value = usage.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        values.append(value)
    total = usage.get("total_tokens")
    if total is not None and total != values[0] + values[1]:
        return None
    return values[0], values[1]


def _public_text_present(public: Any) -> bool:
    output = public.get("output") if isinstance(public, dict) else None
    if not isinstance(output, list):
        return False
    return any(
        isinstance(part, dict)
        and part.get("type") == "output_text"
        and isinstance(part.get("text"), str)
        and bool(part["text"].strip())
        for item in output
        if isinstance(item, dict) and isinstance(item.get("content"), list)
        for part in item["content"]
    )


def _public_completed(public: Any) -> bool:
    return (
        isinstance(public, dict)
        and public.get("status") == "completed"
        and not public.get("error")
        and not public.get("incomplete_details")
    )


async def _read_stream_terminal(
    client: httpx.AsyncClient, caller_key: str, body: dict
) -> tuple[int, dict]:
    """Read router SSE to a single terminal response; failures yield no terminal."""
    wire = bytearray()
    async with client.stream(
        "POST", "/openai/v1/responses", headers={"api-key": caller_key}, json=body
    ) as response:
        if response.status_code != HTTP_OK:
            return response.status_code, {}
        async for chunk in response.aiter_bytes():
            if len(wire) + len(chunk) > MAX_RESPONSE_BYTES:
                raise ValueError("Validation stream bound exceeded")
            wire.extend(chunk)
    try:
        text = bytes(wire).decode("utf-8")
    except UnicodeDecodeError:
        return 200, {}
    terminal: dict = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("data:"):
            continue
        payload = stripped[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            event = load_bounded_json(payload, max_bytes=MAX_FRAME_BYTES)
        except (ValueError, TypeError):
            return 200, {}
        if not isinstance(event, dict):
            continue
        if event.get("type") in {"response.failed", "error"}:
            return 200, {"failed": True}
        if event.get("type") in {"response.completed", "response.incomplete"}:
            response_body = event.get("response")
            terminal = response_body if isinstance(response_body, dict) else {}
    return 200, terminal


async def run_validation_case(  # noqa: PLR0911, PLR0912, PLR0913, PLR0915 -- fixed validation contract
    *,
    case: dict,
    manifest: dict,
    base_url: str,
    caller_key: str,
    admin_key: str,
    transport: httpx.AsyncBaseTransport,
) -> dict:
    """One bounded black-box case; only redacted numerics are returned."""
    started = time.monotonic()
    result: dict = {
        "case_id": case["id"],
        "pool": case["pool"],
        "stream": case["stream"],
        "status": "failed",
        "http_status": None,
        "provider": None,
        "deployment": None,
        "dispatched": False,
        "input_tokens": None,
        "output_tokens": None,
        "usage_coherent": False,
        "terminated_ok": False,
        "settlement_matches": False,
        "reservations_cleared": False,
        "synthetic_debit_usd": 0.0,
        "retry_attempts": None,
        "retry_max_delay_seconds": None,
        "independent_upstream_observed": False,
        "error_category": None,
        "elapsed_seconds": 0.0,
    }

    def finish(category: str | None) -> dict:
        result["error_category"] = category
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        validate_result(result, manifest)
        return result

    body = {
        "model": case["pool"],
        "input": manifest.get("prompt", PROMPT),
        "max_output_tokens": manifest.get("max_output_tokens", MAX_OUTPUT_TOKENS),
        "store": False,
    }
    if case["stream"]:
        body["stream"] = True
    raw_size = len(json.dumps(body).encode("utf-8"))
    if raw_size > MAX_REQUEST_BYTES:
        return finish("request_bound_exceeded")
    try:
        async with asyncio.timeout(manifest.get("case_timeout_seconds", CASE_TIMEOUT_SECONDS)):
            async with httpx.AsyncClient(
                transport=transport,
                timeout=CASE_TIMEOUT_SECONDS,
                trust_env=False,
                base_url=base_url,
                follow_redirects=False,
            ) as client:
                await _check_health(client)
                admin = await _read_admin(client, admin_key)
                _require_setup(admin is not None, "Validation admin evidence unavailable")
                resolved = _resolve_group(admin, case["pool"])
                _require_setup(resolved is not None, "Validation pool has no credit group")
                _group, config, live = resolved
                _require_setup(
                    config.get("provider") == case["provider"]
                    and config.get("deployment") == case["deployment"],
                    "Validation backend identity mismatch",
                )
                _require_setup(
                    config.get("supported_operations") == ["responses"],
                    "Validation backend operation mismatch",
                )
                numbers = _live_numbers(live)
                _require_setup(numbers is not None, "Validation credit evidence unavailable")
                before, active, inflight = numbers
                _require_setup(active == 0 and inflight == 0, "Validation account is not quiet")
                retry_config = admin.get("config") if isinstance(admin, dict) else None
                if isinstance(retry_config, dict):
                    attempts = retry_config.get("retry_attempts")
                    delay = retry_config.get("retry_max_delay_seconds")
                    if isinstance(attempts, int) and not isinstance(attempts, bool):
                        result["retry_attempts"] = attempts
                    if isinstance(delay, (int, float)) and not isinstance(delay, bool):
                        result["retry_max_delay_seconds"] = int(delay)
                result["provider"] = config.get("provider")
                result["deployment"] = config.get("deployment")
                if case["stream"]:
                    status, public = await _read_stream_terminal(client, caller_key, body)
                else:
                    response = await client.post(
                        "/openai/v1/responses",
                        headers={"api-key": caller_key},
                        json=body,
                    )
                    status = response.status_code
                    public = await _read_json_response(response)
                    if public is None:
                        public = {}
                result["dispatched"] = True
                result["http_status"] = int(status)
                if status != HTTP_OK or not _public_completed(public):
                    return finish("acceptance_mismatch")
                if not _public_text_present(public):
                    return finish("acceptance_mismatch")
                usage = _public_usage(public)
                if usage is None:
                    return finish("acceptance_mismatch")
                result["input_tokens"], result["output_tokens"] = usage
                if usage[0] > PREFLIGHT_INPUT_TOKENS or usage[1] > PREFLIGHT_OUTPUT_TOKENS:
                    return finish("acceptance_mismatch")
                result["usage_coherent"] = True
                result["terminated_ok"] = True
                cleared = False
                after = None
                for _ in range(CLEANUP_POLLS):
                    snapshot = await _read_admin(client, admin_key)
                    resolved_now = _resolve_group(snapshot, case["pool"]) if snapshot else None
                    closing = _live_numbers(resolved_now[2]) if resolved_now else None
                    if closing is not None and closing[1] == 0 and closing[2] == 0:
                        cleared = True
                        after = closing[0]
                        break
                    await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                result["reservations_cleared"] = cleared
                if not cleared or after is None:
                    return finish("cleanup_timeout")
                expected = (
                    usage[0] * float(case["input_per_million"])
                    + usage[1] * float(case["output_per_million"])
                ) / 1_000_000
                debit = before - after
                result["synthetic_debit_usd"] = round(debit, 9)
                result["settlement_matches"] = bool(
                    math.isclose(debit, expected, abs_tol=SETTLEMENT_TOLERANCE_USD)
                )
                if not result["settlement_matches"]:
                    return finish("acceptance_mismatch")
                result["status"] = "passed"
                return finish(None)
    except ValidationSetupError:
        raise
    except TimeoutError:
        return finish("transport_failure")
    except ValueError as exc:
        if "bound exceeded" in str(exc):
            return finish("response_bound_exceeded")
        return finish("transport_failure")
    except (OSError, RuntimeError, httpx.HTTPError):
        return finish("transport_failure")


def _run_files(run: str, stage_dir: Path) -> tuple[Path, Path]:
    names = {
        STAGING_RUN_ID: ("ledger-staging.json", "results-staging.json"),
        PRODUCTION_RUN_ID: ("ledger-production.json", "results-production.json"),
    }
    ledger_name, results_name = names[run]
    return stage_dir / ledger_name, stage_dir / results_name


def _staging_results_passed(stage_dir: Path) -> bool:
    ledger_path, results_path = _run_files(STAGING_RUN_ID, stage_dir)
    try:
        ledger = StagingLedger(ledger_path, run=STAGING_RUN_ID)
        if any(case["outcome"] != "passed" for case in ledger._read()["cases"].values()):
            return False
        if not results_path.exists() or results_path.stat().st_size > MAX_RESULTS_BYTES:
            return False
        data = load_bounded_json(results_path.read_text(), max_bytes=MAX_RESULTS_BYTES)
        if (
            not isinstance(data, dict)
            or data.get("run") != STAGING_RUN_ID
            or not isinstance(data.get("attempts"), list)
        ):
            return False
        by_id = {item["case_id"]: item for item in data["attempts"] if isinstance(item, dict)}
        if set(by_id) != set(STAGING_CASES):
            return False
        return all(
            item.get("status") == "passed"
            and item.get("http_status") == HTTP_OK
            and isinstance(item.get("input_tokens"), int)
            and isinstance(item.get("output_tokens"), int)
            and item.get("usage_coherent") is True
            and item.get("settlement_matches") is True
            and item.get("reservations_cleared") is True
            and item.get("error_category") is None
            for item in by_id.values()
        )
    except (OSError, ValueError):
        return False


def execute_validation(  # noqa: PLR0912, PLR0913 -- fail-closed phase contract
    manifest: dict,
    *,
    stage_dir: Path | None = None,
    base_url: str | None = None,
    caller_key: str | None = None,
    admin_key: str | None = None,
    production: bool = False,
    transport_factory: Any = None,
) -> dict:
    """Run listed cases sequentially; halt on failure; never replay outcomes."""
    summary = validate_manifest(manifest)
    _ = summary
    run = manifest["run"]
    if run == PRODUCTION_RUN_ID and not production:
        raise ValueError("Production validation requires explicit approval")
    if not base_url or not base_url.strip():
        raise ValueError("Validation app URL unavailable")
    if not caller_key or not caller_key.strip():
        raise ValueError("Validation client credential unavailable")
    if not admin_key or not admin_key.strip():
        raise ValueError("Validation admin credential unavailable")
    directory = stage_dir if stage_dir is not None else STAGE_DIR
    ledger_path, results_path = _run_files(run, directory)
    with locked(directory / "stage"):
        ledger = StagingLedger(ledger_path, initialize=not ledger_path.exists(), run=run)
        results = load_validation_results(results_path, manifest)
        by_id = {item["case_id"]: item for item in results["attempts"]}
        if any(item["status"] != "passed" for item in results["attempts"]):
            return results
        if run == PRODUCTION_RUN_ID and not _staging_results_passed(directory):
            raise ValueError("Production validation requires passing staging results")
        factory = transport_factory or (
            lambda: httpx.AsyncHTTPTransport(trust_env=False, retries=0)
        )
        case_map = {case["id"]: case for case in manifest["cases"]}
        for case_id in [case["id"] for case in manifest["cases"]]:
            if case_id in by_id:
                continue
            if not ledger.runnable(case_id):
                raise ValueError("Case reservation unavailable")
            ledger.reserve(case_id)
            started = time.monotonic()
            try:
                result = asyncio.run(
                    run_validation_case(
                        case=case_map[case_id],
                        manifest=manifest,
                        base_url=base_url,
                        caller_key=caller_key,
                        admin_key=admin_key,
                        transport=factory(),
                    )
                )
            except ValidationSetupError as exc:
                raise ValueError("Validation setup failed before dispatch") from exc
            except Exception:
                ledger.record_outcome(case_id, failed=True)
                raise
            result["elapsed_seconds"] = round(time.monotonic() - started, 3)
            validate_result(result, manifest)
            results["attempts"].append(result)
            load_validation_results(results_path, manifest, data=results)
            if _serialized_size(results) > MAX_RESULTS_BYTES:
                raise ValueError("Validation results exceed bound")
            write_atomic(results_path, results)
            by_id[case_id] = result
            ledger.record_outcome(case_id, failed=result["status"] != "passed")
            if result["status"] != "passed":
                break
        return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--app-url-env", default=None)
    parser.add_argument("--client-key-env", default=None)
    parser.add_argument("--admin-key-env", default=None)
    args = parser.parse_args()
    if not args.execute or args.manifest is None:
        print(json.dumps({"status": "refused", "cases": 0}))
        return 2
    logging.disable(logging.CRITICAL)
    try:
        raw = args.manifest.read_text()
    except OSError:
        print(json.dumps({"status": "refused_or_interrupted", "cases": "unknown"}))
        return 2
    if len(raw.encode("utf-8")) > MAX_RESULTS_BYTES:
        print(json.dumps({"status": "refused_or_interrupted", "cases": "unknown"}))
        return 2
    try:
        manifest = load_bounded_json(raw, max_bytes=MAX_RESULTS_BYTES)
        environment = manifest.get("environment") if isinstance(manifest, dict) else None
        suffix = "PROD" if environment == "production" else "STAGING"
        url = os.environ.get(args.app_url_env or f"{suffix}_APP_URL", "")
        caller = os.environ.get(args.client_key_env or f"{suffix}_CLIENT_KEY", "")
        admin = os.environ.get(args.admin_key_env or f"{suffix}_ADMIN_KEY", "")
        results = execute_validation(
            manifest,
            base_url=url,
            caller_key=caller,
            admin_key=admin,
            production=args.production,
        )
    except (OSError, ValueError, RuntimeError):
        print(json.dumps({"status": "refused_or_interrupted", "cases": "unknown"}))
        return 2
    summary = {
        item["case_id"]: {
            "status": item["status"],
            "http_status": item["http_status"],
            "input_tokens": item["input_tokens"],
            "output_tokens": item["output_tokens"],
            "synthetic_debit_usd": item["synthetic_debit_usd"],
            "error_category": item["error_category"],
        }
        for item in results["attempts"]
    }
    print(json.dumps({"run": manifest["run"], "results": summary}, indent=2, sort_keys=True))
    return int(any(item["status"] != "passed" for item in results["attempts"]))


if __name__ == "__main__":
    raise SystemExit(main())
