"""Complete only remaining failed streaming attempt allowances on projects 2 and 5."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import time

import google_38_diagnostics as diagnostic
import google_38_remaining as remaining
import httpx
from google_compatible_runtime import run_compatible_case
from google_live_budget import locked, write_atomic
from google_live_execute import fetch_project_credentials

PINS = {
    **remaining.PINS,
    "remaining-ledger.json": ("05fe7e3b74348729fbcbda9fddab00bd12ed8639dd79785b9d09bb5a83fa5e5b"),
}


def originals():
    data = []
    for name, digest in PINS.items():
        raw = (diagnostic.DIRECTORY / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Prior ledger changed")
        data.append(json.loads(raw))
    completed = data[-1]["attempts"]
    for project in (2, 5):
        prefix = f"project-{project}"
        if completed[f"g38-nonstream-{prefix}"]["result"]["status"] != "passed":
            raise ValueError("Nonstream prerequisite failed")
        stream = completed[f"g38-stream-{prefix}"]
        if len(stream["physical_attempts"]) != 1 or stream["result"]["status"] != "failed":
            raise ValueError("Original stream allowance changed")
    return data


class Ledger(diagnostic.DiagnosticLedger):
    def start_physical(self, case):
        prior = originals()
        canonical = case.replace("g38-retry-", "g38-")
        if case not in diagnostic.RETRY_CASES:
            raise ValueError("Retry completion outside scope")
        used = sum(
            len(d["attempts"].get(canonical, {}).get("physical_attempts", [])) for d in prior
        )
        if used + len(self.data["attempts"][case]["physical_attempts"]) >= diagnostic.MAX_ATTEMPTS:
            raise ValueError("Surface slot consumed")
        total = sum(len(x["physical_attempts"]) for d in prior for x in d["attempts"].values())
        if (
            total + sum(len(x["physical_attempts"]) for x in self.data["attempts"].values())
            >= diagnostic.MAX_PHYSICAL
        ):
            raise ValueError("Combined attempts exhausted")
        super().start_physical(case)


async def execute(secret):
    path = diagnostic.DIRECTORY / "stream-retry-ledger.json"
    with (
        locked(diagnostic.DIRECTORY.parent / "google-compatible-text-verification/stage"),
        locked(path),
    ):
        originals()
        ledger = Ledger(path, diagnostic.HISTORICAL.read_bytes())
        ledger.data["prior_pins"] = PINS
        write_atomic(path, ledger.data)
        keys = fetch_project_credentials(secret)
        for i in (2, 5):
            if ledger.data["halted"]:
                break
            case = f"g38-retry-stream-project-{i}"
            project = f"project-{i}"
            observer = diagnostic.ObservingTransport(
                httpx.AsyncHTTPTransport(retries=0, trust_env=False), ledger, project, case
            )
            observer.max_attempts = 2
            started = time.monotonic()
            result = await run_compatible_case(
                credential=keys[i - 1],
                ledger=ledger,
                project=project,
                case_id=case,
                transport=observer,
                stream=True,
                model=diagnostic.MODEL,
                case_timeout_seconds=diagnostic.MAX_LOGICAL_SECONDS,
            )
            result["elapsed_seconds"] = round(time.monotonic() - started, 3)
            ledger.finish(case, result, observer.observation)
        originals()
        return ledger.data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--keyvault-ref")
    args = parser.parse_args()
    if not args.execute or not args.keyvault_ref:
        return 2
    logging.disable(logging.CRITICAL)
    try:
        result = asyncio.run(execute(args.keyvault_ref))
    except (ValueError, OSError, RuntimeError, httpx.HTTPError, TimeoutError):
        print(json.dumps({"status": "refused_or_interrupted"}))
        return 2
    print(json.dumps(result, indent=2))
    return int(result["halted"])


if __name__ == "__main__":
    raise SystemExit(main())
