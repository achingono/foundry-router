"""Only unattempted 3.8 surface slots, with combined immutable historical bounds."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import time

import google_38_diagnostics as diagnostic
import httpx
from google_compatible_runtime import run_compatible_case
from google_live_budget import locked, write_atomic
from google_live_execute import fetch_project_credentials

PINS = {
    "ledger.json": "a10ad7b2498677d26b26a934db66a8d88125bc8b4cca571b85a87d942448dc02",
    "usage-diagnostic-ledger.json": (
        "0bf0fccf49e90c86b2a4dbc3e809edf5ba5f27bb44d09ef90d9a563f357fbce8"
    ),
}


def originals():
    data = []
    for name, digest in PINS.items():
        raw = (diagnostic.DIRECTORY / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Historical diagnostic changed")
        data.append(json.loads(raw))
    return data


class Ledger(diagnostic.DiagnosticLedger):
    def start_physical(self, case):
        prior = originals()
        canonical = case.replace("g38-verified-", "g38-")
        if case == diagnostic.VERIFIED_CASE:
            slot_used = sum(
                len(d["attempts"].get(canonical, {}).get("physical_attempts", [])) for d in prior
            )
            if (
                slot_used + len(self.data["attempts"][case]["physical_attempts"])
                >= diagnostic.MAX_ATTEMPTS
            ):
                raise ValueError("Corrected surface slot exhausted")
        elif any(case in d["attempts"] for d in prior):
            raise ValueError("Consumed slot cannot replay")
        used = sum(len(x["physical_attempts"]) for d in prior for x in d["attempts"].values())
        if (
            used + sum(len(x["physical_attempts"]) for x in self.data["attempts"].values())
            >= diagnostic.MAX_PHYSICAL
        ):
            raise ValueError("Combined attempts exhausted")
        super().start_physical(case)


async def execute(secret):
    path = diagnostic.DIRECTORY / "remaining-ledger.json"
    with (
        locked(diagnostic.DIRECTORY.parent / "google-compatible-text-verification/stage"),
        locked(path),
    ):
        prior = originals()
        ledger = Ledger(path, diagnostic.HISTORICAL.read_bytes())
        ledger.data["prior_pins"] = PINS
        write_atomic(path, ledger.data)
        keys = fetch_project_credentials(secret)
        cases = [("project-1", "verified-nonstream"), ("project-1", "stream")] + [
            (f"project-{i}", surface)
            for i in range(2, 6)
            for surface in ("native", "nonstream", "stream")
        ]
        for project, surface in cases:
            if ledger.data["halted"]:
                break
            if (
                surface == "stream"
                and project != "project-1"
                and ledger.data["attempts"]
                .get(f"g38-nonstream-{project}", {})
                .get("result", {})
                .get("status")
                != "passed"
            ):
                continue
            case = f"g38-{surface}-{project}"
            if any(case in d["attempts"] for d in prior):
                raise ValueError("Consumed surface")
            started = time.monotonic()
            key = keys[int(project.split("-")[1]) - 1]
            if surface == "native":
                result, observation = await diagnostic.native_case(key, ledger, project, case)
            else:
                observer = diagnostic.ObservingTransport(
                    httpx.AsyncHTTPTransport(retries=0, trust_env=False), ledger, project, case
                )
                if case == diagnostic.VERIFIED_CASE:
                    observer.max_attempts = 1
                result = await run_compatible_case(
                    credential=key,
                    ledger=ledger,
                    project=project,
                    case_id=case,
                    transport=observer,
                    stream=surface == "stream",
                    model=diagnostic.MODEL,
                    case_timeout_seconds=diagnostic.MAX_LOGICAL_SECONDS,
                )
                observation = observer.observation
            result["elapsed_seconds"] = round(time.monotonic() - started, 3)
            ledger.finish(case, result, observation)
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
