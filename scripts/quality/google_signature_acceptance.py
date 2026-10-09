"""Fixed post-repair eight-case compatible text acceptance stage."""

from __future__ import annotations

import argparse
import json
import logging

from google_compatible_stage import STAGE_DIR, execute_stage

DIRECTORY = STAGE_DIR.parent / "google-compatible-signature-text"
CASES = [
    (
        f"project-{project}",
        stream,
        f"s08-{'stream' if stream else 'nonstream'}-gemini-3.5-flash-lite-project-{project}",
    )
    for project in range(2, 6)
    for stream in (False, True)
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--keyvault-ref")
    args = parser.parse_args()
    if not args.execute or not args.keyvault_ref:
        return 2
    logging.disable(logging.CRITICAL)
    try:
        result = execute_stage(
            args.keyvault_ref,
            stage_dir=DIRECTORY,
            cases=CASES,
            stage_identity="signature-text-2026-10-08",
        )
    except (ValueError, OSError, RuntimeError):
        print(json.dumps({"status": "refused_or_interrupted"}))
        return 2
    print(json.dumps(result, indent=2))
    return int(any(case["status"] != "passed" for case in result["attempts"]))


if __name__ == "__main__":
    raise SystemExit(main())
