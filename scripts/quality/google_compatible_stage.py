"""Fixed bounded compatible-text stage; refuse missing/reset/ambiguous ledgers."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path

import httpx
from google_compatible_runtime import (
    INITIAL_USD,
    MODEL,
    OUTPUT_TOKENS,
    RESERVED_TOKENS,
    run_compatible_case,
)
from google_live_budget import BudgetLedger, locked, write_atomic
from google_live_execute import fetch_project_credentials

from foundry_router.api.adapters.google_schema import load_bounded_json

ROOT = Path(__file__).resolve().parents[2]
STAGE_DIR = ROOT / "docs/plans/google-compatible-text-verification"
LEDGER_PATH = ROOT / "docs/plans/google-ai-routing-order/ledger-native-text-2026-10-08.json"
BASELINE_PATH = STAGE_DIR / "ledger-baseline.json"
RESULTS_PATH = STAGE_DIR / "results.json"
MAX_DISPATCHES = 9
MAX_RESULTS_BYTES = 65536
MAX_CASE_ELAPSED_SECONDS = 60
PROJECT_COUNT = 5


def stage_cases():
    return [
        (f"project-{project}", stream, f"c08{'s' if stream else 'n'}-txt-{MODEL}-project-{project}")
        for project in range(1, 6)
        for stream in ([False] if project == 1 else [False, True])
    ]


def validate_ledger(path, baseline, cases=None):
    """Require exact historical prefix; only this stage's deterministic cases append."""
    if not path.exists():
        raise ValueError("Existing cumulative ledger required")
    ledger = BudgetLedger(path)
    current = ledger._read()
    expected = {
        project: {case for owner, _, case in (cases or stage_cases()) if owner == project}
        for project in baseline["projects"]
    }
    if current["session"] != baseline["session"]:
        raise ValueError("Cumulative ledger mismatch")
    for project, old in baseline["projects"].items():
        now = current["projects"][project]
        if any(now["cases"].get(case) != value for case, value in old["cases"].items()):
            raise ValueError("Historical debit mismatch")
        if set(now["cases"]) - set(old["cases"]) - expected[project]:
            raise ValueError("Unexpected stage debit")
        if (
            now["requests"] < old["requests"]
            or now["tokens"] < old["tokens"]
            or (old["halted"] and not now["halted"])
        ):
            raise ValueError("Historical budget reset rejected")
    return ledger, current


def load_results(
    path, current, cases=None, stage_identity="compatible-text-2026-10-08", *, data=None
):
    if data is None and not path.exists():
        return {"stage": stage_identity, "attempts": []}
    if data is None and path.stat().st_size > MAX_RESULTS_BYTES:
        raise ValueError("Invalid stage result bound")
    if data is None:
        data = load_bounded_json(path.read_text(), max_bytes=MAX_RESULTS_BYTES)
    if (
        not isinstance(data, dict)
        or set(data) != {"stage", "attempts"}
        or data.get("stage") != stage_identity
        or not isinstance(data.get("attempts"), list)
    ):
        raise ValueError("Invalid stage results")
    result_keys = {
        "case_id",
        "project",
        "model",
        "surface",
        "stream",
        "thinking_policy",
        "status",
        "http_status",
        "provider_http_status",
        "dispatched",
        "actual_tokens",
        "input_tokens",
        "output_tokens",
        "thought_tokens",
        "budget_overrun",
        "public_completed",
        "public_text_present",
        "usage_matches",
        "synthetic_debit_usd",
        "settlement_matches",
        "reservations_cleared",
        "error_category",
        "elapsed_seconds",
    }
    allowed = {case: (project, stream) for project, stream, case in (cases or stage_cases())}
    seen = set()
    for result in data["attempts"]:
        if (
            not isinstance(result, dict)
            or set(result) != result_keys
            or result.get("case_id") not in allowed
            or result["case_id"] in seen
            or result.get("status") not in {"passed", "failed"}
        ):
            raise ValueError("Invalid stage result identity")
        validate_result_values(result)
        case = result["case_id"]
        project, stream = allowed[case]
        seen.add(case)
        if (
            result.get("project") != project
            or result.get("stream") is not stream
            or result.get("model") != MODEL
        ):
            raise ValueError("Invalid stage result binding")
        debit = current["projects"][project]["cases"].get(case)
        if type(result.get("dispatched")) is not bool or (
            debit is not None and result.get("dispatched") is not True
        ):
            raise ValueError("Invalid stage dispatch binding")
        if result.get("dispatched") and (
            debit is None or debit["actual_tokens"] != result.get("actual_tokens")
        ):
            raise ValueError("Invalid stage result ledger binding")
        if result["status"] == "passed" and (
            not result.get("dispatched")
            or not all(
                result.get(key) is True
                for key in (
                    "public_completed",
                    "public_text_present",
                    "usage_matches",
                    "settlement_matches",
                    "reservations_cleared",
                )
            )
            or result.get("budget_overrun") is not False
            or type(result.get("actual_tokens")) is not int
            or type(result.get("input_tokens")) is not int
            or type(result.get("output_tokens")) is not int
            or result["input_tokens"] < 0
            or not 0 <= result["output_tokens"] <= OUTPUT_TOKENS
            or result["actual_tokens"] != result["input_tokens"] + result["output_tokens"]
            or result["actual_tokens"] > RESERVED_TOKENS
            or (
                result.get("thought_tokens") is not None
                and (
                    type(result["thought_tokens"]) is not int
                    or not 0 <= result["thought_tokens"] <= result["output_tokens"]
                )
            )
        ):
            raise ValueError("Invalid stage success evidence")
    return data


def validate_result_values(result):
    if (
        result["surface"] != "openai_compat"
        or result["thinking_policy"] != "provider_default"
        or result["error_category"] not in {None, "provider_or_protocol_failure"}
    ):
        raise ValueError("Invalid stage result semantics")
    for name in (
        "dispatched",
        "budget_overrun",
        "public_completed",
        "public_text_present",
        "usage_matches",
        "settlement_matches",
        "reservations_cleared",
    ):
        if type(result[name]) is not bool:
            raise ValueError("Invalid stage result flags")
    for name in (
        "http_status",
        "provider_http_status",
        "actual_tokens",
        "input_tokens",
        "output_tokens",
        "thought_tokens",
    ):
        if result[name] is not None and (type(result[name]) is not int or result[name] < 0):
            raise ValueError("Invalid stage result numbers")
    if (
        type(result["synthetic_debit_usd"]) not in {int, float}
        or not 0 <= result["synthetic_debit_usd"] <= INITIAL_USD
        or type(result["elapsed_seconds"]) not in {int, float}
        or not 0 <= result["elapsed_seconds"] <= MAX_CASE_ELAPSED_SECONDS
    ):
        raise ValueError("Invalid stage result numeric bounds")


def execute_stage(  # noqa: PLR0913 -- fixed phase contract and fixture injection
    secret_ref,
    *,
    stage_dir=STAGE_DIR,
    ledger_path=LEDGER_PATH,
    credentials=None,
    transport_factory=None,
    cases=None,
    stage_identity="compatible-text-2026-10-08",
):
    """Test injection may relocate fixture paths; CLI never accepts a ledger override."""
    with locked(STAGE_DIR / "stage"):
        baseline = load_bounded_json(
            (stage_dir / "ledger-baseline.json").read_text(), max_bytes=MAX_RESULTS_BYTES
        )
        phase_cases = cases or stage_cases()
        ledger, current = validate_ledger(ledger_path, baseline, phase_cases)
        results_path = stage_dir / "results.json"
        results = load_results(results_path, current, phase_cases, stage_identity)
        by_id = {result["case_id"]: result for result in results["attempts"]}
        halted = {
            project
            for project, _, case in phase_cases
            if case in current["projects"][project]["cases"] and case not in by_id
        }
        halted.update(
            result["project"] for result in results["attempts"] if result["status"] != "passed"
        )
        runnable = [case for case in phase_cases if case[0] not in halted and case[2] not in by_id]
        if not runnable:
            return results
        keys = credentials if credentials is not None else fetch_project_credentials(secret_ref)
        if len(keys) != PROJECT_COUNT:
            raise ValueError("Invalid project credentials")
        factory = transport_factory or (
            lambda: httpx.AsyncHTTPTransport(trust_env=False, retries=0)
        )
        dispatches = 0
        for project, stream, case_id in phase_cases:
            if project in halted or case_id in by_id:
                continue
            if stream:
                preceding = (
                    case_id.replace("-stream-", "-nonstream-", 1)
                    if "-stream-" in case_id
                    else case_id.replace("c08s-", "c08n-", 1)
                )
                if preceding not in by_id or by_id[preceding]["status"] != "passed":
                    halted.add(project)
                    continue
            if dispatches >= MAX_DISPATCHES or not ledger.can_reserve(project, RESERVED_TOKENS):
                continue
            started = time.time()
            result = asyncio.run(
                run_compatible_case(
                    credential=keys[int(project[-1]) - 1],
                    ledger=ledger,
                    project=project,
                    case_id=case_id,
                    transport=factory(),
                    stream=stream,
                )
            )
            result["elapsed_seconds"] = round(time.time() - started, 3)
            results["attempts"].append(result)
            load_results(results_path, ledger._read(), phase_cases, stage_identity, data=results)
            write_atomic(results_path, results)
            by_id[case_id] = result
            dispatches += int(result.get("dispatched", False))
            if result["status"] != "passed" or result.get("budget_overrun"):
                halted.add(project)
        return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--keyvault-ref")
    args = parser.parse_args()
    if not args.execute or not args.keyvault_ref:
        print(json.dumps({"status": "refused", "provider_requests": 0}))
        return 2
    logging.disable(logging.CRITICAL)
    try:
        results = execute_stage(args.keyvault_ref)
    except (OSError, ValueError, RuntimeError):
        print(
            json.dumps({"status": "refused_or_interrupted", "reason": "stage_inputs_or_execution"})
        )
        return 2
    print(json.dumps(results, indent=2))
    return int(any(result["status"] != "passed" for result in results["attempts"]))


if __name__ == "__main__":
    raise SystemExit(main())
