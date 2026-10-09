"""Single remaining-slot cancellation after pinned observed normal route facts."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from decimal import Decimal

from google_compatible_runtime import compatible_settings
from google_decoder_observer import DecoderObserver
from google_stream_runtime import PROMPTS, run_case
from google_stream_stage import DIRECTORY as FIRST_DIRECTORY
from google_stream_stage import (
    HTTP_OK,
    LEDGER_PATH,
    MAX_FILE_BYTES,
    MAX_INPUT_TOKENS,
    MAX_OUTPUT_TOKENS,
    execute,
    read_file,
    validate_progress,
    validate_result,
)
from google_terminal_stage import DIRECTORY as PREVIOUS_DIRECTORY
from google_terminal_stage import result_validator as historical_validator

from foundry_router.credit import estimate_request_cost

DIRECTORY = FIRST_DIRECTORY.parent / "google-final-cancellation"
MIRROR_KEYS = {
    "mirror_terminal_valid",
    "complete_usage",
    "decoded_done",
    "upstream_eof",
    "mirror_terminal_seen",
}
INITIAL = dict.fromkeys(MIRROR_KEYS, False)
CASE = {
    "case_id": "f09-cancel-project-2",
    "project": "project-2",
    "stream": True,
    "cancel": True,
    "prompt": "cancel",
}


def validate_prerequisite(
    directory=DIRECTORY, results_path=PREVIOUS_DIRECTORY / "results.json", ledger_path=LEDGER_PATH
):
    manifest = read_file(directory / "prerequisite-manifest.json")
    if not isinstance(manifest, dict) or set(manifest) != {"results_sha256", "cases"}:
        raise ValueError("Cancellation prerequisite manifest")
    expected_ids = [f"t09-stream-project-{i}" for i in range(3, 6)]
    if manifest["cases"] != expected_ids or not isinstance(manifest["results_sha256"], str):
        raise ValueError("Cancellation prerequisite identities")
    if (
        results_path.stat().st_size > MAX_FILE_BYTES
        or hashlib.sha256(results_path.read_bytes()).hexdigest() != manifest["results_sha256"]
    ):
        raise ValueError("Cancellation prerequisite digest")
    results, ledger = read_file(results_path), read_file(ledger_path)
    if (
        results.get("stage") != "terminal-text-2026-10-09"
        or not isinstance(results.get("attempts"), list)
        or len(results["attempts"]) != len(expected_ids)
    ):
        raise ValueError("Cancellation prerequisite stage")
    for project, value in zip(range(3, 6), results["attempts"], strict=True):
        if (
            value.get("case_id") != f"t09-stream-project-{project}"
            or value.get("project") != f"project-{project}"
            or value.get("model") != "gemini-3.5-flash-lite"
            or value.get("stream") is not True
            or value.get("cancel") is not False
        ):
            raise ValueError("Cancellation prerequisite case")
        historical_validator(value, {key: value[key] for key in CASE}, ledger)
        if (
            value["http_status"] != HTTP_OK
            or value["provider_http_status"] != HTTP_OK
            or not all(
                value[key] is True
                for key in (
                    "public_completed",
                    "public_text_before_upstream_eof",
                    "natural_cleanup",
                    "usage_matches",
                )
            )
            or value["budget_overrun"] is not False
            or value["usage_invalid"] is not False
        ):
            raise ValueError("Cancellation prerequisite facts")
        prompt, output, total = (
            value["input_tokens"],
            value["output_tokens"],
            value["actual_tokens"],
        )
        if (
            type(prompt) is not int
            or not 0 <= prompt <= MAX_INPUT_TOKENS
            or type(output) is not int
            or not 0 <= output <= MAX_OUTPUT_TOKENS
            or total != prompt + output
        ):
            raise ValueError("Cancellation prerequisite usage")
        if abs(Decimal(str(value["synthetic_debit_usd"])) - Decimal(total) / 1000) > Decimal(
            "0.000000001"
        ):
            raise ValueError("Cancellation prerequisite debit")
    return True


def validate_mirror(value):
    if (
        not isinstance(value, dict)
        or not set(value) >= MIRROR_KEYS
        or any(type(value[key]) is not bool for key in MIRROR_KEYS)
    ):
        raise ValueError("Cancellation mirror evidence")


def progress_validator(value):
    validate_mirror(value)
    validate_progress({key: item for key, item in value.items() if key not in MIRROR_KEYS})


def result_validator(value, case, current):
    validate_mirror(value)
    validate_result(
        {key: item for key, item in value.items() if key not in MIRROR_KEYS}, case, current
    )
    if value["status"] == "passed" and (
        value["terminal_usage"]
        or any(value[key] for key in MIRROR_KEYS - {"complete_usage"})
        or value["settlement_kind"] != "conservative_reservation"
    ):
        raise ValueError("Cancellation completed before disconnect")
    if value["status"] == "passed":
        config = compatible_settings("synthetic", "synthetic")
        estimate = estimate_request_cost(
            model="m",
            operation="responses",
            body={"model": "m", "input": PROMPTS["cancel"], "max_output_tokens": MAX_OUTPUT_TOKENS},
            pricing=config.pricing,
            settings=config,
        )
        if abs(
            Decimal(str(value["synthetic_debit_usd"])) - Decimal(str(estimate.estimated_cost_usd))
        ) > Decimal("0.000000001"):
            raise ValueError("Cancellation conservative debit mismatch")


async def runner(**kwargs):
    observer = DecoderObserver(prompt=PROMPTS["cancel"])
    return await run_case(**kwargs, observer=observer)


def run(
    secret_ref,
    *,
    directory=DIRECTORY,
    ledger_path=LEDGER_PATH,
    case_runner=runner,
    prerequisite_results=PREVIOUS_DIRECTORY / "results.json",
    **kwargs,
):
    return execute(
        secret_ref,
        directory=directory,
        ledger_path=ledger_path,
        phase_cases=[CASE],
        stage_identity="final-cancel-2026-10-09",
        progress_validator=progress_validator,
        result_validator=result_validator,
        initial_progress=INITIAL,
        preflight=lambda: validate_prerequisite(directory, prerequisite_results, ledger_path),
        runner=case_runner,
        **kwargs,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--keyvault-ref")
    args = parser.parse_args()
    if not args.execute or not args.keyvault_ref:
        return 2
    logging.disable(logging.CRITICAL)
    try:
        result = run(args.keyvault_ref)
    except (ValueError, RuntimeError, OSError):
        print(json.dumps({"status": "refused_or_interrupted"}))
        return 2
    print(json.dumps(result, indent=2))
    return int(any(item["status"] != "passed" for item in result["attempts"]))


if __name__ == "__main__":
    raise SystemExit(main())
