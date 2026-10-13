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
ROSTER_RUN_ID = "staging-or-roster-2026-10-12"
REMAINING_RUN_ID = "staging-or-roster-remaining-2026-10-12"
FINAL_RUN_ID = "staging-or-roster-final-2026-10-12"
ROSTER_RUN_IDS = {ROSTER_RUN_ID, REMAINING_RUN_ID, FINAL_RUN_ID}

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
EVIDENCE_SCOPE = "deployed-public-admin-v1"
HTTP_STATUS_MIN = 100
HTTP_STATUS_MAX = 599
MAX_SECRET_STRING = 256
MAX_RETRY_DELAY_SECONDS = 3600
MAX_REQUEST_BYTES = 4096
# Admin canonical balances are unrounded floats: float64 subtraction on
# ~1e3-magnitude balances carries error well below 1e-9, so the tolerance
# derives from arithmetic precision, not display rounding.
SETTLEMENT_TOLERANCE_USD = 1e-9
# Absolute coherence tolerance for recomputed debits (stored values round to 1e-9).
DEBIT_COHERENCE_TOLERANCE_USD = 1e-9
# Roster run release/configuration binding (reviewed staging experiment only).
ROSTER_IMAGE_DIGEST = "sha256:71addc1701611f4c6210df28007b3f03d57eb05b9ccd3fe9eed4e6a13e4165ff"
ROSTER_GLOBAL_RESERVE_USD = 10.0
ROSTER_GLOBAL_RESERVE_PERCENT = 5.0
ROSTER_OR_GROUP = "or-shared"
ROSTER_ZEN_GROUP = "zen-staging"
ROSTER_OR_OVERRIDE = {
    "min_credit_reserve_usd": 0.05,
    "min_credit_reserve_percent": 5.0,
}
ROSTER_CONFIGURATION = {
    "global_reserve_usd": ROSTER_GLOBAL_RESERVE_USD,
    "global_reserve_percent": ROSTER_GLOBAL_RESERVE_PERCENT,
    "credit_group": ROSTER_OR_GROUP,
    "group_overrides": {ROSTER_OR_GROUP: dict(ROSTER_OR_OVERRIDE)},
    "inherited_groups": [ROSTER_ZEN_GROUP],
}
ROSTER_RELEASE = {"image_digest": ROSTER_IMAGE_DIGEST}

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
ROSTER_CASES = (
    "roster-luna-nonstream",
    "roster-haiku-nonstream",
    "roster-deepseek-nonstream",
    "roster-mimo-nonstream",
    "roster-spark-nonstream",
)

REMAINING_CASES = ("remaining-mimo-nonstream", "remaining-spark-nonstream")
FINAL_CASES = ("final-mimo-nonstream", "final-spark-nonstream")

RUN_ENVIRONMENTS = {
    STAGING_RUN_ID: "staging",
    PRODUCTION_RUN_ID: "production",
    ROSTER_RUN_ID: "staging",
    REMAINING_RUN_ID: "staging",
    FINAL_RUN_ID: "staging",
}
RUN_CASES = {
    STAGING_RUN_ID: STAGING_CASES,
    PRODUCTION_RUN_ID: PRODUCTION_CASES,
    ROSTER_RUN_ID: ROSTER_CASES,
    REMAINING_RUN_ID: REMAINING_CASES,
    FINAL_RUN_ID: FINAL_CASES,
}
RUN_FILES = {
    STAGING_RUN_ID: ("ledger-staging.json", "results-staging.json"),
    PRODUCTION_RUN_ID: ("ledger-production.json", "results-production.json"),
    ROSTER_RUN_ID: ("ledger-roster.json", "results-roster.json"),
    REMAINING_RUN_ID: ("ledger-roster-remaining.json", "results-roster-remaining.json"),
    FINAL_RUN_ID: ("ledger-roster-final.json", "results-roster-final.json"),
}

# Immutable reviewed case specifications. Manifests must match their run's
# spec exactly; substitution is refused even when otherwise shape-valid.
RUN_SPECS = {
    STAGING_RUN_ID: (
        {
            "id": "staging-zen-nonstream",
            "pool": "gpt-5.4-mini-zen",
            "operation": "responses",
            "stream": False,
            "provider": "opencode_zen",
            "deployment": "gpt-5.4-mini",
            "input_per_million": 0.75,
            "output_per_million": 4.5,
        },
        {
            "id": "staging-zen-stream",
            "pool": "gpt-5.4-mini-zen",
            "operation": "responses",
            "stream": True,
            "provider": "opencode_zen",
            "deployment": "gpt-5.4-mini",
            "input_per_million": 0.75,
            "output_per_million": 4.5,
        },
        {
            "id": "staging-openai-nonstream",
            "pool": "gpt-4o-mini-or",
            "operation": "responses",
            "stream": False,
            "provider": "openrouter",
            "deployment": "openai/gpt-4o-mini",
            "input_per_million": 0.15,
            "output_per_million": 0.6,
        },
        {
            "id": "staging-haiku-nonstream",
            "pool": "claude-haiku-4.5-or",
            "operation": "responses",
            "stream": False,
            "provider": "openrouter",
            "deployment": "anthropic/claude-haiku-4.5",
            "input_per_million": 1.0,
            "output_per_million": 5.0,
        },
    ),
    PRODUCTION_RUN_ID: (
        {
            "id": "production-zen-nonstream",
            "pool": "gpt-5.4-mini-zen",
            "operation": "responses",
            "stream": False,
            "provider": "opencode_zen",
            "deployment": "gpt-5.4-mini",
            "input_per_million": 0.75,
            "output_per_million": 4.5,
        },
        {
            "id": "production-zen-stream",
            "pool": "gpt-5.4-mini-zen",
            "operation": "responses",
            "stream": True,
            "provider": "opencode_zen",
            "deployment": "gpt-5.4-mini",
            "input_per_million": 0.75,
            "output_per_million": 4.5,
        },
    ),
    ROSTER_RUN_ID: (
        {
            "id": "roster-luna-nonstream",
            "pool": "gpt-6-luna-or",
            "operation": "responses",
            "stream": False,
            "provider": "openrouter",
            "deployment": "openai/gpt-6-luna",
            "input_per_million": 0.10,
            "output_per_million": 0.50,
        },
        {
            "id": "roster-haiku-nonstream",
            "pool": "claude-haiku-5.5-or",
            "operation": "responses",
            "stream": False,
            "provider": "openrouter",
            "deployment": "anthropic/claude-haiku-5.5",
            "input_per_million": 0.10,
            "output_per_million": 0.50,
        },
        {
            "id": "roster-deepseek-nonstream",
            "pool": "deepseek-v4.1-flash-or",
            "operation": "responses",
            "stream": False,
            "provider": "openrouter",
            "deployment": "deepseek/deepseek-v4.1-flash",
            "input_per_million": 0.15,
            "output_per_million": 0.60,
        },
        {
            "id": "roster-mimo-nonstream",
            "pool": "mimo-v2.6-flash-or",
            "operation": "responses",
            "stream": False,
            "provider": "openrouter",
            "deployment": "xiaomi/mimo-v2.6-flash",
            "input_per_million": 0.14,
            "output_per_million": 0.28,
        },
        {
            "id": "roster-spark-nonstream",
            "pool": "muse-spark-1.3-contributor-or",
            "operation": "responses",
            "stream": False,
            "provider": "openrouter",
            "deployment": "meta/muse-spark-1.3-contributor",
            "input_per_million": 0.10,
            "output_per_million": 0.20,
        },
    ),
}

RUN_SPECS[REMAINING_RUN_ID] = tuple(
    {**case, "id": case_id}
    for case, case_id in zip(RUN_SPECS[ROSTER_RUN_ID][-2:], REMAINING_CASES, strict=True)
)

RUN_SPECS[FINAL_RUN_ID] = tuple(
    {**case, "id": case_id}
    for case, case_id in zip(RUN_SPECS[ROSTER_RUN_ID][-2:], FINAL_CASES, strict=True)
)

CASE_SPEC_KEYS = (
    "id",
    "pool",
    "operation",
    "stream",
    "provider",
    "deployment",
    "input_per_million",
    "output_per_million",
)

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
    "evidence_scope",
    "error_category",
    "elapsed_seconds",
}
ROSTER_RESULT_KEYS = RESULT_KEYS | {
    "observed_reserve_usd",
    "observed_reserve_percent",
    "reserve_source",
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
    spec = RUN_SPECS[run]
    if len(cases) != len(spec):
        raise ValueError("Invalid staging manifest")
    for case, expected in zip(cases, spec, strict=True):
        if not isinstance(case, dict) or set(case) != set(CASE_SPEC_KEYS):
            raise ValueError("Invalid staging case")
        for key in CASE_SPEC_KEYS:
            if case[key] != expected[key]:
                raise ValueError("Invalid staging case")
        total += (
            PREFLIGHT_INPUT_TOKENS * float(case["input_per_million"])
            + PREFLIGHT_OUTPUT_TOKENS * float(case["output_per_million"])
        ) / 1_000_000
    if (
        manifest.get("prompt") != PROMPT
        or manifest.get("evidence_scope") != EVIDENCE_SCOPE
        or manifest.get("max_output_tokens") != MAX_OUTPUT_TOKENS
        or manifest.get("case_timeout_seconds") != CASE_TIMEOUT_SECONDS
        or manifest.get("max_response_bytes") != MAX_RESPONSE_BYTES
        or manifest.get("max_frame_bytes") != MAX_FRAME_BYTES
        or manifest.get("allowance_usd") != ALLOWANCE_USD
        or not total <= ALLOWANCE_USD
    ):
        raise ValueError("Invalid staging bounds or allowance")
    if run in ROSTER_RUN_IDS:
        if manifest.get("release") != ROSTER_RELEASE:
            raise ValueError("Invalid roster release binding")
        if manifest.get("configuration") != ROSTER_CONFIGURATION:
            raise ValueError("Invalid roster configuration binding")
    elif "release" in manifest or "configuration" in manifest:
        raise ValueError("Unexpected release binding")
    return {"run": run, "cases": [case["id"] for case in cases]}


def manifest_fingerprint(manifest: dict[str, Any]) -> dict[str, Any]:
    # Only the exact reviewed case keys persist; unknown keys are dropped,
    # never copied into durable state. Release/configuration bindings persist
    # only when the manifest carries them; old manifests are byte-identical.
    fingerprint = {
        "run": manifest["run"],
        "environment": manifest["environment"],
        "evidence_scope": manifest["evidence_scope"],
        "cases": [{key: case[key] for key in CASE_SPEC_KEYS} for case in manifest["cases"]],
        "max_output_tokens": manifest["max_output_tokens"],
        "allowance_usd": manifest["allowance_usd"],
    }
    for name in ("release", "configuration"):
        if name in manifest:
            fingerprint[name] = manifest[name]
    return fingerprint


def combined_preflight_estimate(*manifests: Any) -> float:
    """Conservative preflight estimate across runs against one allowance."""
    total = 0.0
    for manifest in manifests:
        summary = validate_manifest(manifest)
        _ = summary
        for case in manifest["cases"]:
            total += (
                PREFLIGHT_INPUT_TOKENS * float(case["input_per_million"])
                + PREFLIGHT_OUTPUT_TOKENS * float(case["output_per_million"])
            ) / 1_000_000
    return total


def validate_run_pair(staging_manifest: Any, production_manifest: Any) -> None:
    """Both runs together must fit the single aggregate test allowance."""
    if combined_preflight_estimate(staging_manifest, production_manifest) > ALLOWANCE_USD:
        raise ValueError("Combined estimate exceeds allowance")


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


def _expected_case_debit(usage_in: int, usage_out: int, case: dict) -> float:
    return (
        usage_in * float(case["input_per_million"]) + usage_out * float(case["output_per_million"])
    ) / 1_000_000


def validate_result(  # noqa: PLR0912, PLR0915 -- bounded evidence schema
    result: Any, manifest: dict[str, Any]
) -> None:
    """Bounded schema for persisted validation outcomes."""
    cases = {case["id"]: case for case in manifest["cases"]}
    roster = manifest.get("run") in ROSTER_RUN_IDS
    expected_keys = ROSTER_RESULT_KEYS if roster else RESULT_KEYS
    if not isinstance(result, dict) or set(result) != expected_keys:
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
    # This harness never observes the provider hop: a true upstream flag is
    # fabricated evidence, and the scope tag binds the narrowed contract.
    if result.get("independent_upstream_observed") is not False:
        raise ValueError("Invalid upstream evidence claim")
    if result.get("evidence_scope") != EVIDENCE_SCOPE:
        raise ValueError("Invalid evidence scope")
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
    if roster:
        observed_missing = (
            result.get("observed_reserve_usd") is None
            or result.get("observed_reserve_percent") is None
            or result.get("reserve_source") is None
        )
        if observed_missing and not (
            result.get("status") == "failed" and result.get("dispatched") is False
        ):
            raise ValueError("Invalid roster reserve evidence")
        if not observed_missing:
            _validate_roster_reserve_evidence(result, manifest)
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
        or result["provider"] != case["provider"]
        or result["deployment"] != case["deployment"]
        or not result["input_tokens"] <= PREFLIGHT_INPUT_TOKENS
        or not result["output_tokens"] <= PREFLIGHT_OUTPUT_TOKENS
        or abs(
            result["synthetic_debit_usd"]
            - _expected_case_debit(result["input_tokens"], result["output_tokens"], case)
        )
        > DEBIT_COHERENCE_TOLERANCE_USD
    ):
        raise ValueError("Invalid passed validation evidence")


def _validate_roster_reserve_evidence(result: dict[str, Any], manifest: dict[str, Any]) -> None:
    """Observed reserve evidence must match the bound roster configuration."""
    configuration = manifest.get("configuration")
    if not isinstance(configuration, dict):
        # ValueError by harness contract: every validation refusal is ValueError.
        raise ValueError("Invalid roster reserve evidence")  # noqa: TRY004
    expected = configuration.get("group_overrides", {}).get(ROSTER_OR_GROUP)
    for name in ("observed_reserve_usd", "observed_reserve_percent"):
        value = result.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            # ValueError by harness contract: every validation refusal is ValueError.
            raise ValueError("Invalid roster reserve evidence")  # noqa: TRY004
    if result.get("reserve_source") != "override":
        raise ValueError("Invalid roster reserve evidence")
    if (
        not isinstance(expected, dict)
        or result["observed_reserve_usd"] != expected.get("min_credit_reserve_usd")
        or result["observed_reserve_percent"] != expected.get("min_credit_reserve_percent")
    ):
        raise ValueError("Invalid roster reserve evidence")
    if expected.get("min_credit_reserve_usd") == configuration.get("global_reserve_usd"):
        raise ValueError("Invalid roster policy contrast")


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


MAX_SETUP_BYTES = 65536


async def _read_bounded_json(  # noqa: PLR0913 -- fixed reader contract
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    json_body: Any = None,
    max_bytes: int = MAX_SETUP_BYTES,
) -> tuple[int, dict | None]:
    """Stream with header policy and byte bound; close on every exit."""
    async with client.stream(method, url, headers=headers, json=json_body) as response:
        status = response.status_code
        if response.headers.get("content-encoding", "identity").lower() != "identity":
            raise ValueError("Encoded validation response rejected")
        if status != HTTP_OK:
            return status, None
        chunks = bytearray()
        async for chunk in response.aiter_bytes():
            if len(chunks) + len(chunk) > max_bytes:
                raise ValueError("Validation response bound exceeded")
            chunks.extend(chunk)
    try:
        payload = load_bounded_json(bytes(chunks).decode("utf-8"), max_bytes=max_bytes)
    except (ValueError, UnicodeError):
        return status, None
    return status, payload if isinstance(payload, dict) else None


async def _check_health(client: httpx.AsyncClient) -> None:
    try:
        async with asyncio.timeout(ADMIN_TIMEOUT_SECONDS):
            live_status, _ = await _read_bounded_json(client, "GET", "/health/live")
            ready_status, body = await _read_bounded_json(client, "GET", "/health/ready")
    except (TimeoutError, OSError, RuntimeError, httpx.HTTPError, ValueError) as exc:
        raise ValidationSetupError("Validation health checks failed") from exc
    if live_status != HTTP_OK:
        raise ValidationSetupError("Validation liveness failed")
    if ready_status != HTTP_OK or body is None or body.get("ready") is not True:
        raise ValidationSetupError("Validation readiness failed")


async def _read_admin(client: httpx.AsyncClient, admin_key: str) -> dict | None:
    try:
        async with asyncio.timeout(ADMIN_TIMEOUT_SECONDS):
            _, admin = await _read_bounded_json(
                client, "GET", "/admin/status", headers={"x-admin-key": admin_key}
            )
    except (TimeoutError, OSError, RuntimeError, httpx.HTTPError, ValueError):
        return None
    return admin


def _resolve_group(admin: dict, pool: str) -> tuple[str, dict, dict, str] | None:
    """Resolve pool to its sole backend config and credit group from admin evidence."""
    try:
        models = admin["models"]
        backends = admin["backends"]
        groups = admin["credit_groups"]
        members = models[pool]["backends"]
        if not isinstance(members, dict) or len(members) != 1:
            return None
        backend_id = next(iter(members))
        config = backends[backend_id]
        group = config["credit_group"]
        live = groups[group]["live"]
    except (KeyError, TypeError, StopIteration):
        return None
    if not isinstance(live, dict):
        return None
    return group, config, live, backend_id


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


async def _read_stream_terminal(  # noqa: PLR0912 -- fixed framing checklist
    client: httpx.AsyncClient, caller_key: str, body: dict
) -> tuple[int, dict]:
    """Read router SSE to a single terminal response; failures yield no terminal.

    Frames split incrementally at the earliest boundary with per-frame and
    total bounds; a nonempty trailing residual fails. Only an unambiguous
    completed terminal counts: failed, incomplete, contradictory, malformed,
    or missing terminals yield no terminal.
    """
    observed = 0
    pending = bytearray()
    terminal: dict = {}
    terminal_kinds: list[str] = []
    invalid = False
    async with client.stream(
        "POST", "/openai/v1/responses", headers={"api-key": caller_key}, json=body
    ) as response:
        if response.status_code != HTTP_OK:
            return response.status_code, {}
        if response.headers.get("content-encoding", "identity").lower() != "identity":
            raise ValueError("Encoded validation response rejected")
        async for chunk in response.aiter_bytes():
            observed += len(chunk)
            if observed > MAX_RESPONSE_BYTES:
                raise ValueError("Validation stream bound exceeded")
            pending.extend(chunk)
            while True:
                event, rest = _split_sse_frame(bytes(pending))
                if event is None:
                    break
                pending = bytearray(rest)
                if len(event) > MAX_FRAME_BYTES:
                    raise ValueError("Validation stream bound exceeded")
                kind, parsed = _classify_sse_frame(event)
                if kind == "malformed":
                    invalid = True
                elif kind == "event":
                    event_type = parsed.get("type")
                    if event_type in {"response.failed", "error"}:
                        return HTTP_OK, {"failed": True}
                    if event_type in {"response.completed", "response.incomplete"}:
                        terminal_kinds.append(event_type)
                        if event_type == "response.completed":
                            terminal = _terminal_response(parsed)
            if len(pending) > MAX_FRAME_BYTES:
                raise ValueError("Validation stream bound exceeded")
        if pending.strip():
            return HTTP_OK, {}
    if invalid or not terminal or terminal_kinds != ["response.completed"]:
        return HTTP_OK, {}
    return HTTP_OK, terminal


def _split_sse_frame(buffer: bytes) -> tuple[bytes | None, bytes]:
    """Earliest event boundary; same semantics as the router splitter."""
    candidates = [(buffer.find(d), d) for d in (b"\r\n\r\n", b"\n\n")]
    found = [(index, delimiter) for index, delimiter in candidates if index >= 0]
    if not found:
        return None, buffer
    index, delimiter = min(found)
    return buffer[: index + len(delimiter)], buffer[index + len(delimiter) :]


def _classify_sse_frame(frame: bytes) -> tuple[str, Any]:
    """Classify one frame: event, empty, or malformed.

    Terminality is decided by the caller from parsed event types, so failed,
    incomplete, and contradictory terminals are distinguishable. Only a data
    payload that is exactly ``[DONE]`` is skipped as a terminator echo;
    markers inside content or comments never count.
    """
    try:
        text = frame.decode("utf-8")
    except UnicodeDecodeError:
        return "malformed", None
    data_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(":"):
            continue
        if ":" not in stripped:
            continue
        field, _, value = stripped.partition(":")
        field = field.strip()
        if field == "data":
            data_lines.append(value.strip())
        elif field in {"event", "id", "retry"}:
            continue
        else:
            continue
    if not data_lines:
        return "empty", None
    payload = "\n".join(data_lines)
    if payload == "[DONE]":
        return "empty", None
    try:
        event = load_bounded_json(payload, max_bytes=MAX_FRAME_BYTES)
    except (ValueError, TypeError):
        return "malformed", None
    if not isinstance(event, dict):
        return "malformed", None
    return "event", event


def _terminal_response(event: dict) -> dict:
    response_body = event.get("response")
    return dict(response_body) if isinstance(response_body, dict) else {}


class _EntryMarker(httpx.AsyncBaseTransport):
    """Records inference-POST entry: a timeout afterwards is still a dispatch.

    Health/admin setup calls pass through unmarked; only the inference POST
    path counts as dispatch evidence.
    """

    def __init__(self, transport: httpx.AsyncBaseTransport):
        self.transport = transport
        self.entered = False

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/openai/v1/responses":
            self.entered = True
        return await self.transport.handle_async_request(request)

    async def aclose(self) -> None:
        await self.transport.aclose()


def _observe_roster_policy(  # noqa: PLR0912 -- fixed roster evidence checklist
    admin: dict, manifest: dict, group: str
) -> tuple[float, float]:
    """Read and bind the observed override pair without dispatch preconditions."""
    configuration = manifest.get("configuration")
    if not isinstance(configuration, dict):
        raise ValidationSetupError("Validation roster configuration unavailable")
    if group != configuration.get("credit_group"):
        raise ValidationSetupError("Validation roster group mismatch")
    config = admin.get("config") if isinstance(admin, dict) else None
    if not isinstance(config, dict):
        raise ValidationSetupError("Validation global policy unavailable")
    global_usd = config.get("min_credit_reserve_usd")
    global_percent = config.get("min_credit_reserve_percent")
    if global_usd != configuration.get("global_reserve_usd") or global_percent != configuration.get(
        "global_reserve_percent"
    ):
        raise ValidationSetupError("Validation global reserve mismatch")
    groups = admin.get("credit_groups")
    if not isinstance(groups, dict):
        raise ValidationSetupError("Validation credit evidence unavailable")
    expected_override = configuration.get("group_overrides", {}).get(group)
    if not isinstance(expected_override, dict):
        raise ValidationSetupError("Validation roster override unavailable")
    observed: tuple[float, float] | None = None
    seen_inherited: set[str] = set()
    required_inherited = configuration.get("inherited_groups", [])
    for name, entry in groups.items():
        if not isinstance(entry, dict):
            raise ValidationSetupError("Validation credit evidence unavailable")
        policy = entry.get("reserve_policy")
        if not isinstance(policy, dict):
            raise ValidationSetupError("Validation reserve evidence unavailable")
        if name == group:
            if (
                policy.get("source") != "override"
                or policy.get("min_credit_reserve_usd")
                != expected_override.get("min_credit_reserve_usd")
                or policy.get("min_credit_reserve_percent")
                != expected_override.get("min_credit_reserve_percent")
            ):
                raise ValidationSetupError("Validation roster override mismatch")
            observed_usd = policy["min_credit_reserve_usd"]
            observed_percent = policy["min_credit_reserve_percent"]
            if observed_usd == global_usd:
                raise ValidationSetupError("Validation roster policy contrast unavailable")
            observed = (float(observed_usd), float(observed_percent))
        elif name in required_inherited:
            if (
                policy.get("source") != "inherited"
                or policy.get("min_credit_reserve_usd") != global_usd
                or policy.get("min_credit_reserve_percent") != global_percent
            ):
                raise ValidationSetupError("Validation inherited policy mismatch")
            seen_inherited.add(name)
    if observed is None:
        raise ValidationSetupError("Validation roster override unavailable")
    if not isinstance(required_inherited, list) or set(seen_inherited) != set(required_inherited):
        raise ValidationSetupError("Validation inherited evidence incomplete")
    return observed


def _roster_policy_gate(admin: dict, manifest: dict, group: str) -> tuple[float, float]:
    """Enforce the reviewed mixed-policy contrast before any roster dispatch.

    Returns the observed override pair. Refuses wrong global floors, absent
    overrides, identical policies, non-inherited Zen evidence, unrestful
    accounts and unprovable headroom contrast without dispatching.
    """
    observed_usd, observed_percent = _observe_roster_policy(admin, manifest, group)
    groups = admin.get("credit_groups")
    if not isinstance(groups, dict):
        raise ValidationSetupError("Validation credit evidence unavailable")
    for entry in groups.values():
        live = entry.get("live") if isinstance(entry, dict) else None
        numbers = _live_numbers(live) if isinstance(live, dict) else None
        if numbers is None:
            raise ValidationSetupError("Validation credit evidence unavailable")
        _remaining, active, inflight = numbers
        if active != 0 or inflight != 0:
            raise ValidationSetupError("Validation account is not quiet")
    configuration = manifest.get("configuration")
    if not isinstance(configuration, dict):
        raise ValidationSetupError("Validation roster configuration unavailable")
    overrides = configuration.get("group_overrides", {})
    if not isinstance(overrides, dict) or not isinstance(overrides.get(group), dict):
        raise ValidationSetupError("Validation roster override unavailable")
    _require_roster_headroom(
        groups[configuration.get("credit_group")],
        overrides[group].get("min_credit_reserve_usd"),
        overrides[group].get("min_credit_reserve_percent"),
        configuration.get("global_reserve_usd"),
        configuration.get("global_reserve_percent"),
    )
    return observed_usd, observed_percent


def _require_roster_headroom(
    entry: dict,
    override_usd: Any,
    override_percent: Any,
    global_usd: Any,
    global_percent: Any,
) -> None:
    """Usable headroom must exist under the override but not the global floor."""
    allowance = entry.get("cycle_allowance_usd")
    live = entry.get("live") if isinstance(entry, dict) else None
    remaining = live.get("estimated_remaining_usd") if isinstance(live, dict) else None
    values = [allowance, remaining, override_usd, override_percent, global_usd, global_percent]
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
        raise ValidationSetupError("Validation headroom evidence unavailable")
    allowance_f, remaining_f, o_usd, o_pct, g_usd, g_pct = (float(v) for v in values)
    if not all(math.isfinite(v) for v in (allowance_f, remaining_f, o_usd, o_pct, g_usd, g_pct)):
        raise ValidationSetupError("Validation headroom evidence unavailable")
    under_override = remaining_f - max(o_usd, allowance_f * o_pct / 100)
    under_global = remaining_f - max(g_usd, allowance_f * g_pct / 100)
    if not (under_override > 0 and under_global <= 0):
        raise ValidationSetupError("Validation headroom contrast unavailable")


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
    roster_run = manifest.get("run") in ROSTER_RUN_IDS
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
        "evidence_scope": EVIDENCE_SCOPE,
        "error_category": None,
        "elapsed_seconds": 0.0,
    }
    if roster_run:
        result.update(
            {
                "observed_reserve_usd": None,
                "observed_reserve_percent": None,
                "reserve_source": None,
            }
        )

    def finish(category: str | None) -> dict:
        result["error_category"] = category
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        validate_result(result, manifest)
        return result

    def harvest() -> None:
        # Router receipt is unknown after entry; preserve the conservative fact.
        result["dispatched"] = marker.entered or result["dispatched"]

    marker = _EntryMarker(transport)

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
                transport=marker,
                timeout=CASE_TIMEOUT_SECONDS,
                trust_env=False,
                base_url=base_url,
                follow_redirects=False,
            ) as client:
                await _check_health(client)
                admin = await _read_admin(client, admin_key)
                _require_setup(admin is not None, "Validation admin evidence unavailable")
                resolved = _resolve_group(admin, case["pool"])
                _require_setup(resolved is not None, "Validation pool binding unavailable")
                _group, config, live, _backend = resolved
                _require_setup(
                    config.get("provider") == case["provider"]
                    and config.get("deployment") == case["deployment"],
                    "Validation backend identity mismatch",
                )
                _require_setup(
                    config.get("provider") in {"opencode_zen", "openrouter"},
                    "Validation requires a single-shot provider path",
                )
                # Single member plus a single-shot provider path (Zen/OpenRouter
                # forward single-shot regardless of retry_attempts, proven by
                # unit tests) is the effective one-dispatch evidence. Deployed
                # retry settings are recorded, never altered.
                _require_setup(
                    config.get("supported_operations") == ["responses"],
                    "Validation backend operation mismatch",
                )
                numbers = _live_numbers(live)
                _require_setup(numbers is not None, "Validation credit evidence unavailable")
                before, active, inflight = numbers
                _require_setup(active == 0 and inflight == 0, "Validation account is not quiet")
                if roster_run:
                    observed_usd, observed_percent = _roster_policy_gate(admin, manifest, _group)
                    result["observed_reserve_usd"] = observed_usd
                    result["observed_reserve_percent"] = observed_percent
                    result["reserve_source"] = "override"
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
                opening_binding = (
                    _group,
                    _backend,
                    config.get("provider"),
                    config.get("deployment"),
                    config.get("supported_operations"),
                )
                if case["stream"]:
                    status, public = await _read_stream_terminal(client, caller_key, body)
                else:
                    status, public = await _read_bounded_json(
                        client,
                        "POST",
                        "/openai/v1/responses",
                        headers={"api-key": caller_key},
                        json_body=body,
                        max_bytes=MAX_RESPONSE_BYTES,
                    )
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
                binding_changed = False
                for _ in range(CLEANUP_POLLS):
                    snapshot = await _read_admin(client, admin_key)
                    resolved_now = _resolve_group(snapshot, case["pool"]) if snapshot else None
                    if resolved_now is not None:
                        group_now, config_now, _live_now, backend_now = resolved_now
                        closing_binding = (
                            group_now,
                            backend_now,
                            config_now.get("provider"),
                            config_now.get("deployment"),
                            config_now.get("supported_operations"),
                        )
                        if closing_binding != opening_binding:
                            binding_changed = True
                            break
                    else:
                        binding_changed = True
                        break
                    closing = _live_numbers(resolved_now[2])
                    if roster_run and snapshot is not None:
                        try:
                            now_usd, now_percent = _observe_roster_policy(
                                snapshot, manifest, _group
                            )
                        except ValidationSetupError:
                            now_usd, now_percent = None, None
                        if (now_usd, now_percent) != (
                            result["observed_reserve_usd"],
                            result["observed_reserve_percent"],
                        ):
                            binding_changed = True
                            break
                    if closing is not None and closing[1] == 0 and closing[2] == 0:
                        cleared = True
                        after = closing[0]
                        break
                    await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                result["reservations_cleared"] = cleared
                if binding_changed:
                    return finish("acceptance_mismatch")
                if not cleared or after is None:
                    return finish("cleanup_timeout")
                expected = _expected_case_debit(usage[0], usage[1], case)
                debit = before - after
                result["synthetic_debit_usd"] = round(debit, 9)
                if expected > 0 and debit == 0:
                    # A missing charge must never pass inside a tolerance.
                    return finish("acceptance_mismatch")
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
        harvest()
        return finish("transport_failure")
    except httpx.DecodingError:
        harvest()
        return finish("encoded_response")
    except ValueError as exc:
        harvest()
        message = str(exc)
        if "bound exceeded" in message:
            return finish("response_bound_exceeded")
        if "Encoded validation response" in message:
            return finish("encoded_response")
        return finish("transport_failure")
    except (OSError, RuntimeError, httpx.HTTPError):
        harvest()
        return finish("transport_failure")


def _run_files(run: str, stage_dir: Path) -> tuple[Path, Path]:
    names = {
        STAGING_RUN_ID: ("ledger-staging.json", "results-staging.json"),
        PRODUCTION_RUN_ID: ("ledger-production.json", "results-production.json"),
        ROSTER_RUN_ID: ("ledger-roster.json", "results-roster.json"),
        REMAINING_RUN_ID: ("ledger-roster-remaining.json", "results-roster-remaining.json"),
        FINAL_RUN_ID: ("ledger-roster-final.json", "results-roster-final.json"),
    }
    ledger_name, results_name = names[run]
    return stage_dir / ledger_name, stage_dir / results_name


def _load_canonical_manifest(directory: Path, name: str) -> dict:
    """Load and validate a committed manifest; execution never invents one."""
    path = directory / name
    if not path.exists() or path.stat().st_size > MAX_RESULTS_BYTES:
        raise ValueError("Staging manifest unavailable")
    manifest = load_bounded_json(path.read_text(), max_bytes=MAX_RESULTS_BYTES)
    validate_manifest(manifest)
    expected = {
        "manifest.staging.json": STAGING_RUN_ID,
        "manifest.production.json": PRODUCTION_RUN_ID,
        "manifest.roster.json": ROSTER_RUN_ID,
        "manifest.roster-remaining.json": REMAINING_RUN_ID,
        "manifest.roster-final.json": FINAL_RUN_ID,
    }.get(name)
    if expected is None or manifest["run"] != expected:
        raise ValueError("Staging manifest unavailable")
    return manifest


def _staging_results_passed(stage_dir: Path) -> bool:
    try:
        manifest = _load_canonical_manifest(stage_dir, "manifest.staging.json")
        ledger_path, results_path = _run_files(STAGING_RUN_ID, stage_dir)
        _, results = _reconcile_state(ledger_path, results_path, manifest)
    except (OSError, ValueError):
        return False
    if len(results["attempts"]) != len(STAGING_CASES):
        return False
    # Narrowed deployment-acceptance contract (reviewed amendment): public
    # completion/usage plus canonical admin debit, without independent
    # provider observation. No billing or provider claim follows.
    return all(
        item["status"] == "passed"
        and item["http_status"] == HTTP_OK
        and isinstance(item["input_tokens"], int)
        and isinstance(item["output_tokens"], int)
        and item["input_tokens"] <= PREFLIGHT_INPUT_TOKENS
        and item["output_tokens"] <= PREFLIGHT_OUTPUT_TOKENS
        and item["usage_coherent"] is True
        and item["terminated_ok"] is True
        and item["settlement_matches"] is True
        and item["reservations_cleared"] is True
        and item["error_category"] is None
        for item in results["attempts"]
    )


def _reconcile_state(
    ledger_path: Path, results_path: Path, manifest: dict, *, initialize: bool = False
) -> tuple[dict, dict]:
    """Reconcile durable ledger and results before any skip, return, or dispatch.

    Every listed case must be in exactly one coherent state: pristine
    (unreserved, no outcome, no result), or complete (reserved, recorded
    outcome, persisted result with matching status/tokens/debit). Halted runs,
    unresolved reservations, missing or contradictory records refuse. Cases
    must complete as a prefix: nothing may follow an incomplete case.
    """
    run = manifest["run"]
    ledger = StagingLedger(ledger_path, initialize=initialize, run=run)
    ledger_data = ledger._read()
    if ledger_data["halted"]:
        raise ValueError("Halted run cannot resume")
    results = load_validation_results(results_path, manifest)
    by_id = {item["case_id"]: item for item in results["attempts"]}
    ordered = [case["id"] for case in manifest["cases"]]
    prefix_open = True
    for case_id in ordered:
        entry = ledger_data["cases"][case_id]
        persisted = by_id.get(case_id)
        complete = (
            entry["reserved"]
            and entry["outcome"] in {"passed", "failed"}
            and persisted is not None
            and persisted["status"] == entry["outcome"]
        )
        if complete and persisted["status"] == "passed":
            if not prefix_open:
                raise ValueError("Ledger/result outcome mismatch")
            continue
        if complete:
            # A recorded failure ends the run; resume never continues it.
            raise ValueError("Halted run cannot resume")
        prefix_open = False
        if entry["reserved"] or entry["outcome"] is not None or persisted is not None:
            raise ValueError("Unresolved reserved case")
    return ledger_data, results


def execute_validation(  # noqa: PLR0912, PLR0913, PLR0915 -- fail-closed phase contract
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
        first_run = not ledger_path.exists() and not results_path.exists()
        _, results = _reconcile_state(ledger_path, results_path, manifest, initialize=first_run)
        ledger = StagingLedger(ledger_path, run=run)
        by_id = {item["case_id"]: item for item in results["attempts"]}
        if run == PRODUCTION_RUN_ID and not _staging_results_passed(directory):
            raise ValueError("Production validation requires passing staging results")
        if run in ROSTER_RUN_IDS:
            try:
                staging_manifest = _load_canonical_manifest(directory, "manifest.staging.json")
                production_manifest = _load_canonical_manifest(
                    directory, "manifest.production.json"
                )
            except (OSError, ValueError):
                raise ValueError("Roster validation requires committed run manifests") from None
            manifests = [manifest, staging_manifest, production_manifest]
            if run in {REMAINING_RUN_ID, FINAL_RUN_ID}:
                manifests.append(_load_canonical_manifest(directory, "manifest.roster.json"))
            if run == FINAL_RUN_ID:
                manifests.append(
                    _load_canonical_manifest(directory, "manifest.roster-remaining.json")
                )
            if combined_preflight_estimate(*manifests) > ALLOWANCE_USD:
                raise ValueError("Combined estimate exceeds allowance")
        factory = transport_factory or (
            lambda: httpx.AsyncHTTPTransport(trust_env=False, retries=0)
        )
        case_map = {case["id"]: case for case in manifest["cases"]}
        for case_id in [case["id"] for case in manifest["cases"]]:
            _reconcile_state(ledger_path, results_path, manifest)
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
            # Record the ledger outcome before persisting results: a crash
            # between the writes leaves an outcome without a result, which
            # resume reconciliation refuses instead of skipping.
            ledger.record_outcome(case_id, failed=result["status"] != "passed")
            results["attempts"].append(result)
            load_validation_results(results_path, manifest, data=results)
            if _serialized_size(results) > MAX_RESULTS_BYTES:
                raise ValueError("Validation results exceed bound")
            write_atomic(results_path, results)
            by_id[case_id] = result
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
