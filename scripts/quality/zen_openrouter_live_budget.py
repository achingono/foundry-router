"""Durable redacted dispatch ledger for Zen/OpenRouter live verification.

Test-only verification tooling; never production configuration. The ledger is
separate from router memory and uses durable atomic writes. A reservation is a
conservative possible-dispatch debit even if a crash occurs before the network
send. Restart never resets the budget or replays a reserved case.
"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from google_live_budget import locked, write_atomic

from foundry_router.api.adapters.google_schema import load_bounded_json

RUN_ID = "zen-openrouter-live-2026-10-11"
MAX_LEDGER_BYTES = 65536
MAX_MANIFEST_BYTES = 65536
MAX_DISPATCHES = 5

CASE_TIMEOUT_SECONDS = 120
MAX_OBSERVED_BYTES = 1024 * 1024
MAX_FRAME_BYTES = 256 * 1024
MAX_INPUT_BYTES = 1024
MAX_OUTPUT_TOKENS = 128

CASE_IDS = (
    "zen-nonstream",
    "zen-stream",
    "openrouter-nonstream",
    "openrouter-stream",
    "openrouter-embeddings",
)

CASE_ID_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,80}")


def _initial_ledger() -> dict[str, Any]:
    return {
        "run": RUN_ID,
        "dispatches": 0,
        "halted": False,
        "cases": {
            case_id: {"reserved": False, "actual_tokens": None, "outcome": None}
            for case_id in CASE_IDS
        },
    }


class RunLedger:
    """Fixed five-case ledger with durable reserve-before-egress semantics."""

    def __init__(self, path: Path):
        self.path = path
        with locked(path):
            if not path.exists():
                write_atomic(path, _initial_ledger())
            self._read()

    def _read(self) -> dict[str, Any]:
        if self.path.stat().st_size > MAX_LEDGER_BYTES:
            raise ValueError("Invalid run ledger")
        data = load_bounded_json(self.path.read_bytes().decode(), max_bytes=MAX_LEDGER_BYTES)
        if (
            not isinstance(data, dict)
            or data.get("run") != RUN_ID
            or type(data.get("dispatches")) is not int
            or type(data.get("halted")) is not bool
            or not isinstance(data.get("cases"), dict)
            or set(data["cases"]) != set(CASE_IDS)
        ):
            raise ValueError("Invalid run ledger")
        reserved = 0
        stopping_outcome = False
        for case in data["cases"].values():
            if (
                not isinstance(case, dict)
                or set(case) != {"reserved", "actual_tokens", "outcome"}
                or type(case["reserved"]) is not bool
                or (
                    case["actual_tokens"] is not None
                    and (type(case["actual_tokens"]) is not int or case["actual_tokens"] < 0)
                )
                or (case["outcome"] not in {None, "passed", "failed", "ambiguous"})
                or (case["outcome"] is not None and not case["reserved"])
            ):
                raise ValueError("Invalid run ledger")
            reserved += int(case["reserved"])
            stopping_outcome |= case["outcome"] in {"failed", "ambiguous"}
        if data["dispatches"] != reserved or reserved > MAX_DISPATCHES:
            raise ValueError("Invalid run ledger")
        if stopping_outcome and not data["halted"]:
            raise ValueError("Invalid run ledger")
        return data

    def reserve(self, case_id: str) -> None:
        """Durably record dispatch intent before egress; never refunds."""
        if CASE_ID_PATTERN.fullmatch(case_id) is None or case_id not in CASE_IDS:
            raise ValueError("Unknown verification case")
        with locked(self.path):
            data = self._read()
            case = data["cases"][case_id]
            if data["halted"] or case["reserved"] or data["dispatches"] >= MAX_DISPATCHES:
                raise ValueError("Case reservation unavailable")
            case["reserved"] = True
            data["dispatches"] += 1
            write_atomic(self.path, data)

    def record_outcome(self, case_id: str, actual_tokens: int | None, *, failed: bool) -> None:
        if case_id not in CASE_IDS or (
            actual_tokens is not None and (type(actual_tokens) is not int or actual_tokens < 0)
        ):
            raise ValueError("Invalid case outcome")
        with locked(self.path):
            data = self._read()
            case = data["cases"][case_id]
            if not case["reserved"] or case["outcome"] is not None:
                raise ValueError("Case outcome already recorded")
            case["actual_tokens"] = actual_tokens
            if failed:
                case["outcome"] = "failed"
                data["halted"] = True
            elif actual_tokens is None:
                # Uncertain slots are retained, never refunded or replayed.
                case["outcome"] = "ambiguous"
                data["halted"] = True
            else:
                case["outcome"] = "passed"
            write_atomic(self.path, data)

    def runnable(self, case_id: str) -> bool:
        """A case may dispatch only when unreserved and the run is unhalted."""
        with locked(self.path):
            data = self._read()
            return (
                not data["halted"]
                and case_id in CASE_IDS
                and not data["cases"][case_id]["reserved"]
            )


def validate_manifest(manifest: Any) -> dict[str, Any]:
    """Bind exact models, prices, bounds and the five fixed cases to a run."""
    if (
        not isinstance(manifest, dict)
        or manifest.get("version") != 1
        or manifest.get("run") != RUN_ID
        or not isinstance(manifest.get("zen_model"), str)
        or not manifest["zen_model"].strip()
        or not isinstance(manifest.get("openrouter_model"), str)
        or not manifest["openrouter_model"].strip()
        or not isinstance(manifest.get("openrouter_embedding_model"), str)
        or not manifest["openrouter_embedding_model"].strip()
        or not isinstance(manifest.get("input_per_million"), (int, float))
        or not isinstance(manifest.get("output_per_million"), (int, float))
        or isinstance(manifest.get("input_per_million"), bool)
        or isinstance(manifest.get("output_per_million"), bool)
        or not manifest["input_per_million"] > 0
        or not manifest["output_per_million"] > 0
        or not math.isfinite(float(manifest["input_per_million"]))
        or not math.isfinite(float(manifest["output_per_million"]))
        or manifest.get("cases") != list(CASE_IDS)
        or manifest.get("case_timeout_seconds") != CASE_TIMEOUT_SECONDS
        or manifest.get("max_observed_bytes") != MAX_OBSERVED_BYTES
        or manifest.get("max_output_tokens") != MAX_OUTPUT_TOKENS
    ):
        raise ValueError("Invalid verification manifest")
    return {
        "run": RUN_ID,
        "cases": list(CASE_IDS),
        "max_dispatches": MAX_DISPATCHES,
    }
