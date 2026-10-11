"""Fixed five-case Zen/OpenRouter live stage; refuse missing/reset/ambiguous state.

Test-only verification tooling; never production configuration. Credentials
arrive as process-memory values read from operator-named environment variables
and are never logged, persisted, or echoed. Results carry redacted numerics only.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
from zen_openrouter_live_budget import (
    CASE_IDS,
    CASE_TIMEOUT_SECONDS,
    MAX_LEDGER_BYTES,
    MAX_OUTPUT_TOKENS,
    RUN_ID,
    RunLedger,
    locked,
    validate_manifest,
    write_atomic,
)
from zen_openrouter_live_runtime import (
    ERROR_ACCEPTANCE,
    ERROR_BOUND,
    ERROR_CLEANUP,
    ERROR_TRANSPORT,
    ERROR_UPSTREAM,
    VerificationSetupError,
    run_live_case,
)

from foundry_router.api.adapters.google_schema import load_bounded_json

ROOT = Path(__file__).resolve().parents[2]
STAGE_DIR = ROOT / "docs/plans/zen-openrouter-live-verification"
MAX_RESULTS_BYTES = 65536
MAX_DEBIT_USD = 1000

ERROR_CATEGORIES = {
    None,
    ERROR_TRANSPORT,
    ERROR_UPSTREAM,
    ERROR_ACCEPTANCE,
    ERROR_CLEANUP,
    ERROR_BOUND,
}

RESULT_KEYS = {
    "case_id",
    "kind",
    "stream",
    "status",
    "http_status",
    "provider_http_status",
    "dispatched",
    "input_tokens",
    "output_tokens",
    "usage_matches",
    "terminated_ok",
    "settlement_matches",
    "reservations_cleared",
    "synthetic_debit_usd",
    "vector_count",
    "dimensions",
    "order_matches",
    "vector_values_match",
    "error_category",
    "elapsed_seconds",
}


def empty_results(manifest: dict[str, Any]) -> dict[str, Any]:
    return {"run": RUN_ID, "manifest": manifest_fingerprint(manifest), "attempts": []}


def manifest_fingerprint(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        name: manifest[name]
        for name in (
            "zen_model",
            "openrouter_model",
            "openrouter_embedding_model",
            "input_per_million",
            "output_per_million",
        )
    }


def load_results(path: Path, manifest: dict[str, Any], *, data: Any = None) -> dict[str, Any]:
    if data is None:
        if not path.exists():
            return empty_results(manifest)
        if path.stat().st_size > MAX_RESULTS_BYTES:
            raise ValueError("Invalid stage results")
        data = load_bounded_json(path.read_text(), max_bytes=MAX_RESULTS_BYTES)
    if (
        not isinstance(data, dict)
        or set(data) != {"run", "manifest", "attempts"}
        or data.get("run") != RUN_ID
        or data.get("manifest") != manifest_fingerprint(manifest)
        or not isinstance(data.get("attempts"), list)
    ):
        raise ValueError("Invalid stage results")
    seen = set()
    listed = manifest["cases"]
    for result in data["attempts"]:
        validate_result(result)
        if result["case_id"] not in listed:
            raise ValueError("Unlisted stage result")
        if result["case_id"] in seen:
            raise ValueError("Duplicate stage result")
        seen.add(result["case_id"])
    return data


def validate_result(result: Any) -> None:
    if not isinstance(result, dict) or set(result) != RESULT_KEYS:
        raise ValueError("Invalid stage result identity")
    if (
        result.get("case_id") not in CASE_IDS
        or result.get("kind") not in CASE_IDS
        or result.get("case_id") != result.get("kind")
        or type(result.get("stream")) is not bool
        or result.get("status") not in {"passed", "failed"}
    ):
        raise ValueError("Invalid stage result binding")
    for name in (
        "dispatched",
        "usage_matches",
        "terminated_ok",
        "settlement_matches",
        "reservations_cleared",
        "order_matches",
    ):
        if type(result.get(name)) is not bool:
            raise ValueError("Invalid stage result flags")
    for name in ("http_status", "provider_http_status", "input_tokens", "output_tokens"):
        value = result.get(name)
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("Invalid stage result numbers")
    for name in ("vector_count", "dimensions"):
        value = result.get(name)
        if type(value) is not int or value < 0:
            raise ValueError("Invalid stage result numbers")
    debit = result.get("synthetic_debit_usd")
    elapsed = result.get("elapsed_seconds")
    if (
        type(debit) not in {int, float}
        or not 0 <= debit <= MAX_DEBIT_USD
        or type(elapsed) not in {int, float}
        or not 0 <= elapsed <= CASE_TIMEOUT_SECONDS
    ):
        raise ValueError("Invalid stage result numeric bounds")
    if result.get("error_category") not in ERROR_CATEGORIES:
        raise ValueError("Invalid stage result category")
    if result["status"] == "passed" and (
        not result["dispatched"]
        or result["http_status"] != HTTPStatus.OK
        or result["provider_http_status"] != HTTPStatus.OK
        or result["stream"] is not result["case_id"].endswith("-stream")
        or not result["usage_matches"]
        or not result["terminated_ok"]
        or not result["settlement_matches"]
        or not result["reservations_cleared"]
        or result["error_category"] is not None
        or result["input_tokens"] is None
        or result["output_tokens"] is None
        or result["output_tokens"] > MAX_OUTPUT_TOKENS
        or (result["case_id"] == "openrouter-embeddings" and not result["vector_values_match"])
        or (
            result["case_id"] == "openrouter-embeddings"
            and not (
                result["vector_count"] > 0 and result["dimensions"] > 0 and result["order_matches"]
            )
        )
        or (
            result["case_id"] != "openrouter-embeddings"
            and (
                result["vector_count"] != 0
                or result["dimensions"] != 0
                or result["order_matches"]
                or result["vector_values_match"]
            )
        )
    ):
        raise ValueError("Invalid stage success evidence")


def _dispatch_report() -> Any:
    """Conservatively reserved dispatches, or "unknown" when unreadable."""
    try:
        return RunLedger(STAGE_DIR / "ledger.json").dispatch_count()
    except (OSError, ValueError):
        return "unknown"


def _interrupted_report() -> str:
    return json.dumps({"status": "refused_or_interrupted", "provider_requests": _dispatch_report()})


def _credential_from_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value.strip():
        raise ValueError("Verification credential unavailable")
    return value


def execute_stage(  # noqa: PLR0912, PLR0913, PLR0915 -- fail-closed phase contract
    manifest: dict[str, Any],
    *,
    stage_dir: Path = STAGE_DIR,
    ledger_path: Path | None = None,
    results_path: Path | None = None,
    zen_credential: str | None = None,
    openrouter_credential: str | None = None,
    transport_factory: Any = None,
) -> dict[str, Any]:
    """Run fixed cases sequentially; any failure blocks the remainder."""
    summary = validate_manifest(manifest)
    _ = summary
    ledger_file = ledger_path or (stage_dir / "ledger.json")
    results_file = results_path or (stage_dir / "results.json")
    with locked(stage_dir / "stage"):
        first_initialization = not ledger_file.exists() and not results_file.exists()
        ledger = RunLedger(ledger_file, initialize=first_initialization)
        results = load_results(results_file, manifest)
        # Reconcile both durable records before any provider egress. A reservation
        # without an outcome, or an outcome without a matching result, is terminal.
        ledger_data = ledger._read()
        result_by_id = {item["case_id"]: item for item in results["attempts"]}
        for case_id, case in ledger_data["cases"].items():
            persisted = result_by_id.get(case_id)
            if case["reserved"]:
                if case["outcome"] is None or persisted is None:
                    raise ValueError("Incomplete durable case outcome")
                tokens = persisted.get("input_tokens"), persisted.get("output_tokens")
                actual = sum(tokens) if all(type(value) is int for value in tokens) else None
                expected_outcome = "passed" if persisted["status"] == "passed" else "failed"
                if case["outcome"] != expected_outcome or case["actual_tokens"] != actual:
                    raise ValueError("Ledger/result outcome mismatch")
            elif case["outcome"] is not None or persisted is not None:
                raise ValueError("Ledger/result outcome mismatch")
        by_id = result_by_id
        if any(item["status"] != "passed" for item in results["attempts"]):
            return results
        if not zen_credential or not zen_credential.strip():
            raise ValueError("Verification credential unavailable")
        if not openrouter_credential or not openrouter_credential.strip():
            raise ValueError("Verification credential unavailable")
        factory = transport_factory or (
            lambda: httpx.AsyncHTTPTransport(trust_env=False, retries=0)
        )
        for case_id in manifest["cases"]:
            if case_id in by_id:
                continue
            if not ledger.runnable(case_id):
                raise ValueError("Case reservation unavailable")
            credential = zen_credential if case_id.startswith("zen-") else openrouter_credential
            started = time.monotonic()
            try:
                result = _run_case_sync(
                    manifest,
                    case_id,
                    credential,
                    ledger,
                    factory(),
                )
            except VerificationSetupError as exc:
                # No provider dispatch occurred; block without recording a
                # dispatch outcome so a later run may proceed after setup repair.
                raise ValueError("Verification setup failed before dispatch") from exc
            except Exception:
                ledger.record_outcome(case_id, None, failed=True)
                raise
            result["elapsed_seconds"] = round(time.monotonic() - started, 3)
            validate_result(result)
            results["attempts"].append(result)
            # Record the ledger outcome first, then atomically persist results.
            # A crash between these writes is detected by bidirectional reconciliation.
            tokens = result.get("input_tokens"), result.get("output_tokens")
            actual = tokens[0] + tokens[1] if all(type(value) is int for value in tokens) else None
            ledger.record_outcome(case_id, actual, failed=result["status"] != "passed")
            write_atomic(results_file, results)
            by_id[case_id] = result
            if result["status"] != "passed":
                break
        return results


def _run_case_sync(
    manifest: dict[str, Any], case_id: str, credential: str, ledger: RunLedger, transport: Any
) -> dict[str, Any]:
    import asyncio  # noqa: PLC0415 -- isolate event-loop creation to execution

    return asyncio.run(
        run_live_case(
            kind=case_id,
            credential=credential,
            ledger=ledger,
            case_id=case_id,
            transport=transport,
            zen_model=str(manifest["zen_model"]),
            openrouter_model=str(manifest["openrouter_model"]),
            embedding_model=str(manifest["openrouter_embedding_model"]),
            input_per_million=float(manifest["input_per_million"]),
            output_per_million=float(manifest["output_per_million"]),
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--zen-key-env", default="ZEN_API_KEY")
    parser.add_argument("--openrouter-key-env", default="OPENROUTER_API_KEY")
    args = parser.parse_args()
    if not args.execute or args.manifest is None:
        print(json.dumps({"status": "refused", "provider_requests": _dispatch_report()}))
        return 2
    logging.disable(logging.CRITICAL)
    try:
        raw_manifest = args.manifest.read_text()
    except OSError:
        print(_interrupted_report())
        return 2
    if len(raw_manifest.encode("utf-8")) > MAX_LEDGER_BYTES:
        print(_interrupted_report())
        return 2
    try:
        manifest = load_bounded_json(raw_manifest, max_bytes=MAX_LEDGER_BYTES)
        # Live execution is bound to the canonical run ledger and results file;
        # path overrides exist only as execute_stage parameters for offline tests.
        results = execute_stage(
            manifest,
            zen_credential=_credential_from_env(args.zen_key_env),
            openrouter_credential=_credential_from_env(args.openrouter_key_env),
        )
    except (OSError, ValueError, RuntimeError):
        print(_interrupted_report())
        return 2
    summary = {
        case: {
            "status": item["status"],
            "http_status": item["http_status"],
            "provider_http_status": item["provider_http_status"],
            "input_tokens": item["input_tokens"],
            "output_tokens": item["output_tokens"],
            "synthetic_debit_usd": item["synthetic_debit_usd"],
            "error_category": item["error_category"],
        }
        for case, item in ((item["case_id"], item) for item in results["attempts"])
    }
    print(json.dumps({"run": RUN_ID, "results": summary}, indent=2, sort_keys=True))
    return int(any(item["status"] != "passed" for item in results["attempts"]))


if __name__ == "__main__":
    raise SystemExit(main())
