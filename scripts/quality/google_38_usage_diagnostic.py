"""One separately owned same-wire numeric diagnostic; retain the halted original run."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
from pathlib import Path

import google_38_diagnostics as diagnostic
import google_compatible_runtime as compatible
import httpx
from google_live_budget import locked, write_atomic
from google_live_execute import fetch_project_credentials

from foundry_router.api.adapters.google_schema import load_bounded_json

FIELDS = {"prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens"}
CASE = "g38-nonstream-project-1"
ORIGINAL_SHA256 = "a10ad7b2498677d26b26a934db66a8d88125bc8b4cca571b85a87d942448dc02"


def numeric_shape(wire):
    data = load_bounded_json(wire.decode(), max_bytes=diagnostic.MAX_BODY)
    usage = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return {"usage_object": False}
    details = usage.get("completion_tokens_details")
    values = {k: usage.get(k) for k in FIELDS - {"reasoning_tokens"}}
    values["reasoning_tokens"] = (
        details.get("reasoning_tokens") if isinstance(details, dict) else None
    )
    return {
        "usage_object": True,
        "counts": {
            k: {
                "type": "integer" if type(v) is int else "null" if v is None else "other",
                "value": v if type(v) is int and v >= 0 else None,
            }
            for k, v in sorted(values.items())
        },
    }


class Ledger(diagnostic.DiagnosticLedger):
    def __init__(self, path, historical):
        super().__init__(path, historical)
        self.source = "observer"
        self.data["usage_callbacks"] = []

    def record_usage(self, project, case, tokens):
        self.data["usage_callbacks"].append({"source": self.source, "tokens": tokens})
        super().record_usage(project, case, tokens)

    def start_physical(self, case):
        original = validate_original((diagnostic.DIRECTORY / "ledger.json").read_bytes())
        consumed = sum(len(x["physical_attempts"]) for x in original["attempts"].values())
        if (
            consumed + sum(len(x["physical_attempts"]) for x in self.data["attempts"].values())
            >= diagnostic.MAX_PHYSICAL
        ):
            raise ValueError("Combined budget exhausted")
        slot_consumed = len(original["attempts"].get(case, {}).get("physical_attempts", []))
        if (
            slot_consumed + len(self.data["attempts"][case]["physical_attempts"])
            >= diagnostic.MAX_ATTEMPTS
        ):
            raise ValueError("Surface slot budget exhausted")
        super().start_physical(case)


def validate_original(raw):
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA256:
        raise ValueError("Original ledger changed")
    data = json.loads(raw)
    if data.get("halted") is not True or set(data.get("attempts", {})) != {
        "g38-native-project-1",
        CASE,
    }:
        raise ValueError("Original case contract changed")
    if any(len(item["physical_attempts"]) != 1 for item in data["attempts"].values()):
        raise ValueError("Original attempt contract changed")
    return data


async def execute(secret):
    original = (diagnostic.DIRECTORY / "ledger.json").read_bytes()
    path = diagnostic.DIRECTORY / "usage-diagnostic-ledger.json"
    with (
        locked(diagnostic.DIRECTORY.parent / "google-compatible-text-verification/stage"),
        locked(path),
    ):
        validate_original(original)
        ledger = Ledger(path, diagnostic.HISTORICAL.read_bytes())
        sources = {
            name: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()  # noqa: ASYNC240 -- small pinned local source
            for name, module in [("observer", diagnostic), ("guard", compatible)]
        }
        safe = {"sources": sources, "observer": None, "guard": None, "wire_equal": None}
        observer_wire = None

        class Observer(diagnostic.ObservingTransport):
            def _compatible_usage(self, wire, stream):
                nonlocal observer_wire
                observer_wire = hashlib.sha256(wire).hexdigest()
                safe["observer"] = numeric_shape(wire)
                ledger.source = "observer"
                super()._compatible_usage(wire, stream)
                ledger.data["numeric_observation"] = safe
                write_atomic(path, ledger.data)

        class Guard(compatible.CompatibleGuard):
            def _capture_usage(self, wire):
                safe["guard"] = numeric_shape(wire)
                safe["wire_equal"] = observer_wire == hashlib.sha256(wire).hexdigest()
                ledger.source = "guard"
                super()._capture_usage(wire)
                ledger.data["numeric_observation"] = safe
                write_atomic(path, ledger.data)

        keys = fetch_project_credentials(secret)
        observer = Observer(
            httpx.AsyncHTTPTransport(retries=0, trust_env=False), ledger, "project-1", CASE
        )
        observer.max_attempts = 2
        result = await compatible.run_compatible_case(
            credential=keys[0],
            ledger=ledger,
            project="project-1",
            case_id=CASE,
            transport=observer,
            stream=False,
            model=diagnostic.MODEL,
            guard_factory=Guard,
            case_timeout_seconds=diagnostic.MAX_LOGICAL_SECONDS,
        )
        result["elapsed_seconds"] = 0.0
        ledger.finish(CASE, result, observer.observation)
        assert (diagnostic.DIRECTORY / "ledger.json").read_bytes() == original
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
