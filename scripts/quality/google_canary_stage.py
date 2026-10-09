"""Finite real-TCP Google 3.8 stream/cleanup acceptance; no credential output."""

import argparse
import asyncio
import hashlib
import json
import logging
from pathlib import Path

import httpx
from google_decoder_observer import DecoderObserver
from google_incremental_usage import IncrementalUsage
from google_live_budget import locked, write_atomic
from google_live_execute import fetch_credential
from google_stream_runtime import PROMPTS, run_case

from foundry_router.api.adapters.google_ai_studio import normalize_google_usage

DIRECTORY = Path(__file__).resolve().parents[2] / "docs/plans/google-38-production-canary"
KEY_COUNT = 5
MAX_ATTEMPTS = 12
MAX_PROJECT_STAGE = 6
FIRST_PROJECT_INDEX = 2
TRANSIENT_STATUSES = {500, 502, 503, 504}
PRIOR_SHA = "64688f571b57087605948aa597719a6eb2112a2ea7873a586666398ee8ae61cf"

MODEL = "gemini-3.8-flash"


def retry_allowed(result):
    return (
        result.get("provider_http_status") in TRANSIENT_STATUSES
        and result.get("http_status") in TRANSIENT_STATUSES
        and not result.get("public_text_before_upstream_eof")
        and not result.get("public_completed")
        and result.get("natural_cleanup") is True
        and result.get("settlement_matches") is True
        and result.get("budget_overrun") is False
    )


class AggregateNonstream(IncrementalUsage):
    def _usage(self, usage, *, final):
        return super()._usage(normalize_google_usage(usage), final=final)


class AggregateObserver(DecoderObserver):
    def _usage(self, usage, *, final):
        return super()._usage(normalize_google_usage(usage), final=final)


async def execute(secret_ref, path, *, recovery=False, project4_only=False):  # noqa: PLR0912, PLR0915 -- finite stage owns locked ledger lifecycle
    logging.disable(logging.CRITICAL)
    if recovery and project4_only:
        raise ValueError("Stage modes are mutually exclusive")
    canonical = DIRECTORY / (
        "stage-project4-ledger.json"
        if project4_only
        else "stage-recovery-ledger.json"
        if recovery
        else "stage-ledger.json"
    )
    if path.resolve() != canonical.resolve():
        raise ValueError("Canary stage requires canonical ledger")
    shared = DIRECTORY.parent / "google-compatible-text-verification" / "stage"
    with locked(shared), locked(canonical):
        if path.exists():
            raise ValueError("Canary stage cannot replay")
        data = {
            "scope": "google-38-canary-staging",
            "maximum_attempts": MAX_ATTEMPTS,
            "maximum_reserved_tokens": MAX_ATTEMPTS * 1280,
            "attempts": [],
            "halted": False,
        }
        write_atomic(path, data)
        prior_counts = {"project-3": 0, "project-4": 0}
        if project4_only:
            exhausted = (DIRECTORY / "stage-recovery-ledger.json").read_bytes()
            if (
                hashlib.sha256(exhausted).hexdigest()
                != "320b0395e60ce9e1ac02c2b3960f3820af7db0b9b8a181152cab2ea274dacef9"
            ):
                raise ValueError("Retained recovery digest mismatch")
            prior_counts["project-3"] = 3
        if recovery:
            retained = (DIRECTORY / "stage-ledger.json").read_bytes()
            if hashlib.sha256(retained).hexdigest() != PRIOR_SHA:
                raise ValueError("Retained stage digest mismatch")
            prior = json.loads(retained)
            if not prior.get("halted") or len(prior["attempts"]) != 1:
                raise ValueError("Unexpected retained stage")
            first = prior["attempts"][0]
            if (
                first["project"] != "project-3"
                or first["result"]["http_status"] not in TRANSIENT_STATUSES
            ):
                raise ValueError("Unexpected retained failure")
            prior_counts["project-3"] = 1
        credentials = json.loads(fetch_credential(secret_ref))
        if (
            not isinstance(credentials, list)
            or len(credentials) != KEY_COUNT
            or any(not isinstance(k, str) or not k for k in credentials)
        ):
            raise ValueError("Invalid credential array")
        for index in [3] if project4_only else [2, 3]:
            for mode in ["nonstream", "stream", "cancel"]:
                case = {
                    "case_id": f"canary-stage-project-{index + 1}-{mode}",
                    "project": f"project-{index + 1}",
                    "prompt": "cancel" if mode == "cancel" else "ordinary",
                    "stream": mode != "nonstream",
                    "cancel": mode == "cancel",
                }
                for attempt in range(
                    1,
                    (3 if recovery and index == FIRST_PROJECT_INDEX and mode == "nonstream" else 4),
                ):
                    row = {
                        "project": case["project"],
                        "case_id": case["case_id"] + f"-attempt-{attempt}",
                        "reserved_tokens": 1280,
                        "dispatched": False,
                        "result": None,
                    }
                    data["attempts"].append(row)
                    write_atomic(path, data)

                    def reserve(row=row, project=case["project"]):
                        if (
                            row["dispatched"]
                            or sum(prior_counts.values()) >= MAX_ATTEMPTS
                            or prior_counts[project] >= MAX_PROJECT_STAGE
                        ):
                            raise ValueError("Canary stage allowance exhausted")
                        row["dispatched"] = True
                        prior_counts[project] += 1
                        write_atomic(path, data)

                    def progress(facts, row=row):
                        row["observation"] = facts
                        write_atomic(path, data)

                    result = await run_case(
                        credential=credentials[index],
                        case=case,
                        model=MODEL,
                        transport=httpx.AsyncHTTPTransport(retries=0, trust_env=False),
                        reserve=reserve,
                        progress=progress,
                        observer=(
                            AggregateObserver(prompt=PROMPTS[case["prompt"]])
                            if case["stream"]
                            else AggregateNonstream()
                        ),
                    )
                    row["result"] = result
                    transient = retry_allowed(result)
                    failed = result["status"] != "passed"
                    exhausted = attempt >= (
                        2
                        if recovery and index == FIRST_PROJECT_INDEX and mode == "nonstream"
                        else 3
                    )
                    data["halted"] = failed and (not transient or exhausted)
                    write_atomic(path, data)
                    print(
                        json.dumps(
                            {
                                "case_id": case["case_id"],
                                "status": result["status"],
                                "http_status": result["http_status"],
                                "early_text": result["public_text_before_upstream_eof"],
                                "natural_cleanup": result["natural_cleanup"],
                                "settlement_matches": result["settlement_matches"],
                            }
                        ),
                        flush=True,
                    )
                    if data["halted"]:
                        return
                    if not failed:
                        break
                    await asyncio.sleep(13)
                await asyncio.sleep(13)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyvault-ref", required=True)
    parser.add_argument("--ledger", type=Path, default=DIRECTORY / "stage-ledger.json")
    parser.add_argument("--recovery", action="store_true")
    parser.add_argument("--project4-only", action="store_true")
    args = parser.parse_args()
    asyncio.run(
        execute(
            args.keyvault_ref, args.ledger, recovery=args.recovery, project4_only=args.project4_only
        )
    )
