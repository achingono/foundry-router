"""Final four-slot stream stage with explicit conditional cancellation prerequisite."""

from __future__ import annotations

import argparse
import json
import logging

from google_stream_runtime import run_case
from google_stream_stage import DIRECTORY as PREVIOUS_DIRECTORY
from google_stream_stage import execute, validate_progress, validate_result

DIRECTORY = PREVIOUS_DIRECTORY.parent / "google-stream-terminal-amendment"
TERMINAL_KEYS = {"stop_seen", "done_seen", "upstream_eof", "final_usage_shape"}
INITIAL_TERMINAL = {
    "stop_seen": False,
    "done_seen": False,
    "upstream_eof": False,
    "final_usage_shape": "absent",
}


def cases():
    return [
        {
            "case_id": f"t09-stream-project-{project}",
            "project": f"project-{project}",
            "stream": True,
            "cancel": False,
            "prompt": "reasoning",
        }
        for project in range(3, 6)
    ] + [
        {
            "case_id": "t09-cancel-project-2",
            "project": "project-2",
            "stream": True,
            "cancel": True,
            "prompt": "cancel",
        }
    ]


def validate_terminal(value):
    if not isinstance(value, dict) or not set(value) >= TERMINAL_KEYS:
        raise ValueError("Verification terminal schema")
    for key in TERMINAL_KEYS - {"final_usage_shape"}:
        if type(value[key]) is not bool:
            raise ValueError("Verification terminal flags")
    if value["final_usage_shape"] not in {"absent", "usage_only", "stop_choice"}:
        raise ValueError("Verification terminal shape")


def progress_validator(value):
    validate_terminal(value)
    validate_progress({key: item for key, item in value.items() if key not in TERMINAL_KEYS})


def result_validator(value, case, current):
    validate_terminal(value)
    validate_result(
        {key: item for key, item in value.items() if key not in TERMINAL_KEYS}, case, current
    )
    if value["terminal_usage"] and (
        not all(value[key] for key in ("stop_seen", "done_seen", "upstream_eof"))
        or value["final_usage_shape"] == "absent"
    ):
        raise ValueError("Verification terminal evidence incomplete")


def prerequisite(case, by_id):
    return not case["cancel"] or any(
        result["status"] == "passed" and not result["cancel"] for result in by_id.values()
    )


async def runner(**kwargs):
    return await run_case(**kwargs, terminal_facts=True)


def run(secret_ref, *, directory=DIRECTORY, case_runner=runner, **kwargs):
    return execute(
        secret_ref,
        directory=directory,
        phase_cases=cases(),
        stage_identity="terminal-text-2026-10-09",
        progress_validator=progress_validator,
        result_validator=result_validator,
        prerequisite=prerequisite,
        initial_progress=INITIAL_TERMINAL,
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
