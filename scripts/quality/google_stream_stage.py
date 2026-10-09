"""Remaining-budget incremental text stage; preserve every consumed or ambiguous case."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from decimal import Decimal

import httpx
from google_compatible_stage import LEDGER_PATH, STAGE_DIR, validate_ledger
from google_incremental_usage import (
    MAX_INPUT_TOKENS,
    MAX_OUTPUT_TOKENS,
    MAX_TOTAL_TOKENS,
    record_progress,
)
from google_live_budget import locked, write_atomic
from google_live_execute import fetch_project_credentials
from google_stream_runtime import MODEL, run_case

from foundry_router.api.adapters.google_schema import load_bounded_json

DIRECTORY = STAGE_DIR.parent / "google-compatible-stream-lifecycle"
MAX_FILE_BYTES = 65536
MAX_CASES = 10
REASONING_PROJECT_START = 4
PROJECT_COUNT = 5
MIN_HTTP_STATUS = 100
MAX_HTTP_STATUS = 599
HTTP_OK = 200
MAX_ELAPSED_SECONDS = 30
MAX_OBSERVED_TOKENS = 10**4300 - 1
PROGRESS_KEYS = {
    "dispatches",
    "provider_http_status",
    "input_tokens",
    "output_tokens",
    "thought_tokens",
    "actual_tokens",
    "budget_overrun",
    "usage_invalid",
}
BOOL_RESULT_KEYS = {
    "budget_overrun",
    "usage_invalid",
    "terminal_usage",
    "public_completed",
    "public_text_before_upstream_eof",
    "cancelled_before_upstream_eof",
    "natural_cleanup",
    "usage_matches",
    "settlement_matches",
}
EXTRA_RESULT_KEYS = {
    "model",
    "status",
    "http_status",
    "provider_http_status",
    "dispatches",
    "actual_tokens",
    "input_tokens",
    "output_tokens",
    "thought_tokens",
    "synthetic_debit_usd",
    "settlement_kind",
    "first_upstream_chunk_seconds",
    "first_public_text_seconds",
    "elapsed_seconds",
    "error_category",
} | BOOL_RESULT_KEYS


def cases():
    result = []
    for project in range(2, 6):
        kinds = (
            ["ordinary", "cancel"]
            if project < REASONING_PROJECT_START
            else ["nonstream", "reasoning", "cancel"]
        )
        result.extend(
            {
                "case_id": f"l09-{kind}-project-{project}",
                "project": f"project-{project}",
                "stream": kind != "nonstream",
                "cancel": kind == "cancel",
                "prompt": "reasoning" if kind in {"nonstream", "reasoning"} else kind,
            }
            for kind in kinds
        )
    return result


def read_file(path, default=None):
    if not path.exists() and default is not None:
        return default
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Verification artifact bound")
    return load_bounded_json(path.read_text(), max_bytes=MAX_FILE_BYTES)


def validate_progress(value):
    if not isinstance(value, dict) or set(value) != PROGRESS_KEYS:
        raise ValueError("Verification progress schema")
    if type(value["dispatches"]) is not int or value["dispatches"] not in {0, 1}:
        raise ValueError("Verification dispatch bound")
    for key in ("budget_overrun", "usage_invalid"):
        if type(value[key]) is not bool:
            raise ValueError("Verification progress flags")
    for key in ("input_tokens", "output_tokens", "thought_tokens", "actual_tokens"):
        number = value[key]
        if number is not None and (
            type(number) is not int or not 0 <= number <= MAX_OBSERVED_TOKENS
        ):
            raise ValueError("Verification usage bound")
    status = value["provider_http_status"]
    if status is not None and (
        type(status) is not int or not MIN_HTTP_STATUS <= status <= MAX_HTTP_STATUS
    ):
        raise ValueError("Verification status bound")


def validate_result(result, case, current):  # noqa: PLR0912 -- explicit bounded evidence contract
    if not isinstance(result, dict) or set(result) != set(case) | EXTRA_RESULT_KEYS:
        raise ValueError("Verification result schema")
    if any(
        result[key] != value or type(result[key]) is not type(value) for key, value in case.items()
    ):
        raise ValueError("Verification result identity")
    if result["model"] != MODEL or result["status"] not in {"passed", "failed"}:
        raise ValueError("Verification result status")
    validate_progress({key: result[key] for key in PROGRESS_KEYS})
    if any(type(result[key]) is not bool for key in BOOL_RESULT_KEYS):
        raise ValueError("Verification result flags")
    if result["error_category"] not in {
        None,
        "provider_or_protocol_failure",
        "cleanup_or_execution_failure",
    }:
        raise ValueError("Verification error category")
    if result["settlement_kind"] not in {"observed_usage", "conservative_reservation"}:
        raise ValueError("Verification settlement category")
    status = result["http_status"]
    if status is not None and (
        type(status) is not int or not MIN_HTTP_STATUS <= status <= MAX_HTTP_STATUS
    ):
        raise ValueError("Verification public status")
    for key, limit in (
        ("synthetic_debit_usd", 100),
        ("first_upstream_chunk_seconds", MAX_ELAPSED_SECONDS),
        ("first_public_text_seconds", MAX_ELAPSED_SECONDS),
        ("elapsed_seconds", MAX_ELAPSED_SECONDS),
    ):
        value = result[key]
        if value is None and key != "elapsed_seconds":
            continue
        if type(value) not in {int, float} or not 0 <= value <= limit:
            raise ValueError("Verification result numeric bound")
    debit = current["projects"][case["project"]]["cases"].get(case["case_id"])
    if result["dispatches"] and (
        debit is None or debit["actual_tokens"] != result["actual_tokens"]
    ):
        raise ValueError("Verification result debit mismatch")
    if not result["dispatches"] and debit is not None:
        raise ValueError("Verification result dispatch mismatch")
    if result["status"] == "passed":
        required = [
            result["dispatches"] == 1,
            result["http_status"] == HTTP_OK,
            result["provider_http_status"] == HTTP_OK,
            result["natural_cleanup"],
            result["settlement_matches"],
            not result["budget_overrun"],
            not result["usage_invalid"],
            result["error_category"] is None,
        ]
        if case["cancel"]:
            required.extend(
                [result["cancelled_before_upstream_eof"], result["public_text_before_upstream_eof"]]
            )
        else:
            required.extend(
                [
                    result["terminal_usage"],
                    result["public_completed"],
                    result["usage_matches"],
                    result["actual_tokens"] is not None
                    and result["actual_tokens"] <= MAX_TOTAL_TOKENS,
                ]
            )
            if case["stream"]:
                required.append(result["public_text_before_upstream_eof"])
        if result["terminal_usage"]:
            input_tokens, output_tokens, thoughts = (
                result["input_tokens"],
                result["output_tokens"],
                result["thought_tokens"],
            )
            required.extend(
                [
                    type(input_tokens) is int and 0 <= input_tokens <= MAX_INPUT_TOKENS,
                    type(output_tokens) is int and 0 <= output_tokens <= MAX_OUTPUT_TOKENS,
                    thoughts is None
                    or (type(thoughts) is int and 0 <= thoughts <= (output_tokens or 0)),
                    result["actual_tokens"] == (input_tokens or 0) + (output_tokens or 0),
                    result["settlement_kind"] == "observed_usage",
                    result["synthetic_debit_usd"] is not None
                    and abs(
                        Decimal(str(result["synthetic_debit_usd"]))
                        - Decimal(result["actual_tokens"] or 0) / 1000
                    )
                    <= Decimal("0.000000001"),
                ]
            )
        else:
            required.append(result["settlement_kind"] == "conservative_reservation")
        if not all(required):
            raise ValueError("Verification success evidence incomplete")


def execute(  # noqa: PLR0913, PLR0912, PLR0915 -- one serialized immutable stage
    secret_ref,
    *,
    directory=DIRECTORY,
    ledger_path=LEDGER_PATH,
    credentials=None,
    transport_factory=None,
    runner=run_case,
    phase_cases=None,
    stage_identity="incremental-text-2026-10-09",
    progress_validator=validate_progress,
    result_validator=validate_result,
    prerequisite=None,
    initial_progress=None,
):
    with locked(STAGE_DIR / "stage"):
        phase_cases = cases() if phase_cases is None else phase_cases
        baseline = read_file(directory / "ledger-baseline.json")
        bindings = [(case["project"], case["stream"], case["case_id"]) for case in phase_cases]
        allowed = {(case["project"], case["case_id"]) for case in phase_cases}
        ledger, current = validate_ledger(ledger_path, baseline, bindings)
        results_path, progress_path = directory / "results.json", directory / "progress.json"
        results = read_file(results_path, {"stage": stage_identity, "attempts": []})
        progress = read_file(progress_path, {})
        if (
            not isinstance(results, dict)
            or set(results) != {"stage", "attempts"}
            or results["stage"] != stage_identity
            or not isinstance(results["attempts"], list)
            or len(results["attempts"]) > MAX_CASES
        ):
            raise ValueError("Verification stage schema")
        by_id = {}
        known = {case["case_id"]: case for case in phase_cases}
        for result in results["attempts"]:
            if (
                not isinstance(result, dict)
                or result.get("case_id") not in known
                or result["case_id"] in by_id
            ):
                raise ValueError("Verification stage identity")
            result_validator(result, known[result["case_id"]], current)
            by_id[result["case_id"]] = result
        if not isinstance(progress, dict) or set(progress) - set(known):
            raise ValueError("Verification progress identity")
        for identity, value in progress.items():
            progress_validator(value)
            case = known[identity]
            debit = current["projects"][case["project"]]["cases"].get(identity)
            if value["dispatches"] == 1 and (
                debit is None or value["actual_tokens"] != debit["actual_tokens"]
            ):
                raise ValueError("Verification progress debit mismatch")
            if value["dispatches"] == 0 and debit is not None:
                # Crash after reservation before first progress update: never replay.
                continue
        halted = {result["project"] for result in by_id.values() if result["status"] != "passed"}
        halted.update(
            case["project"]
            for case in phase_cases
            if case["case_id"] not in by_id
            and (
                case["case_id"] in progress
                or case["case_id"] in current["projects"][case["project"]]["cases"]
            )
        )
        if (
            any(item["budget_overrun"] for item in progress.values())
            or any(result["budget_overrun"] for result in by_id.values())
            or any(
                state["halted"] and not baseline["projects"][project]["halted"]
                for project, state in current["projects"].items()
            )
        ):
            return results
        runnable = [
            case
            for case in phase_cases
            if case["project"] not in halted
            and case["case_id"] not in by_id
            and ledger.can_reserve(case["project"], MAX_TOTAL_TOKENS)
        ]
        if not runnable:
            return results
        keys = credentials if credentials is not None else fetch_project_credentials(secret_ref)
        if (
            not isinstance(keys, list)
            or len(keys) != PROJECT_COUNT
            or any(not isinstance(key, str) or not key for key in keys)
        ):
            raise ValueError("Verification credential roster")
        factory = transport_factory or (
            lambda: httpx.AsyncHTTPTransport(trust_env=False, retries=0)
        )
        for case in phase_cases:
            project, identity = case["project"], case["case_id"]
            if (
                project in halted
                or identity in by_id
                or not ledger.can_reserve(project, MAX_TOTAL_TOKENS)
            ):
                continue
            predecessors = [
                item
                for item in phase_cases
                if item["project"] == project and phase_cases.index(item) < phase_cases.index(case)
            ]
            if any(
                item["case_id"] not in by_id or by_id[item["case_id"]]["status"] != "passed"
                for item in predecessors
            ):
                halted.add(project)
                continue
            if prerequisite is not None and not prerequisite(case, by_id):
                continue
            progress[identity] = {
                "dispatches": 0,
                "provider_http_status": None,
                "input_tokens": None,
                "output_tokens": None,
                "thought_tokens": None,
                "actual_tokens": None,
                "budget_overrun": False,
                "usage_invalid": False,
            }
            if initial_progress is not None:
                progress[identity].update(initial_progress)
            write_atomic(progress_path, progress)

            def reserve(owner=project, case_id=identity):
                ledger.reserve(owner, case_id, MAX_TOTAL_TOKENS)

            def persist(value, owner=project, case_id=identity):
                progress_validator(value)
                if value["actual_tokens"] is not None:
                    record_progress(
                        ledger,
                        baseline,
                        allowed,
                        owner,
                        case_id,
                        value["actual_tokens"],
                        overrun=value["budget_overrun"],
                    )
                progress[case_id] = value
                write_atomic(progress_path, progress)

            result = asyncio.run(
                runner(
                    credential=keys[int(project[-1]) - 1],
                    case=case,
                    transport=factory(),
                    reserve=reserve,
                    progress=persist,
                )
            )
            result_validator(result, case, ledger._read())
            results["attempts"].append(result)
            write_atomic(results_path, results)
            by_id[identity] = result
            if result["budget_overrun"]:
                break
            if result["status"] != "passed":
                halted.add(project)
        return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--keyvault-ref")
    args = parser.parse_args()
    if not args.execute or not args.keyvault_ref:
        return 2
    logging.disable(logging.CRITICAL)
    try:
        result = execute(args.keyvault_ref)
    except (ValueError, RuntimeError, OSError):
        print(json.dumps({"status": "refused_or_interrupted"}))
        return 2
    print(json.dumps(result, indent=2))
    return int(any(item["status"] != "passed" for item in result["attempts"]))


if __name__ == "__main__":
    raise SystemExit(main())
