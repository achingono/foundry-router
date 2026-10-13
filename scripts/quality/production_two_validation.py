"""Fixed Luna/Haiku deployment checks; isolated immutable four-slot ledger."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import staging_validation as sv
from zen_openrouter_live_budget import locked, write_atomic

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "docs/plans/openrouter-production-two"
RUN = "openrouter-production-two-2026-10-12"
DIGEST = "sha256:ee24fc37d9198a7824937339337468a355b937a57b53c03d79b05138355c8b57"
BOUND = 65536
PAIRS = (
    ("gpt-6-luna-or", "openai/gpt-6-luna"),
    ("claude-haiku-5.5-or", "anthropic/claude-haiku-5.5"),
)
CASES = tuple(
    {
        "id": f"{environment}-{index}",
        "pool": pool,
        "deployment": deployment,
        "provider": "openrouter",
        "operation": "responses",
        "stream": False,
        "input_per_million": 0.1,
        "output_per_million": 0.5,
    }
    for environment in ("staging", "production")
    for index, (pool, deployment) in enumerate(PAIRS)
)
MANIFEST = {
    "run": RUN,
    "image_digest": DIGEST,
    "cases": CASES,
    "streaming_enabled": False,
    "evidence_scope": sv.EVIDENCE_SCOPE,
    "aggregate_estimate_usd": 0.00654336,
}


def _load(path: Path) -> dict:
    if not path.exists() or path.stat().st_size > BOUND:
        raise ValueError("Validation state unavailable")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("Invalid validation state")  # noqa: TRY004 -- unified refusal contract
    return data


def case_manifest(case: dict) -> dict:
    # Reuse the bounded case primitive's roster policy contract only. Its old
    # run ledger is never opened; this module owns the new four-slot identity.
    inherited = (
        ["zen-staging"] if case["id"].startswith("staging-") else ["fs-openclaw", "fs-swarm"]
    )
    return {
        "run": sv.ROSTER_RUN_ID,
        "cases": [case],
        "evidence_scope": sv.EVIDENCE_SCOPE,
        "configuration": {**sv.ROSTER_CONFIGURATION, "inherited_groups": inherited},
        "case_timeout_seconds": sv.CASE_TIMEOUT_SECONDS,
        "prompt": sv.PROMPT,
        "max_output_tokens": sv.MAX_OUTPUT_TOKENS,
    }


def validate_state(data: dict) -> None:
    expected = json.loads(json.dumps(MANIFEST))
    if set(data) != {"manifest", "entries"} or data["manifest"] != expected:
        raise ValueError("Validation identity changed")
    entries = data["entries"]
    if not isinstance(entries, list) or len(entries) != len(CASES):
        raise ValueError("Invalid validation entries")
    incomplete = False
    for case, entry in zip(CASES, entries, strict=True):
        if not isinstance(entry, dict) or set(entry) != {"reserved", "result"}:
            raise ValueError("Invalid validation entry")
        if type(entry["reserved"]) is not bool:
            raise ValueError("Invalid reservation")
        result = entry["result"]
        if entry["reserved"]:
            if result is None:
                raise ValueError("Unresolved validation reservation")
            sv.validate_result(result, case_manifest(case))
            if result["status"] != "passed" or incomplete:
                raise ValueError("Failed validation cannot resume")
        elif result is not None:
            raise ValueError("Invalid unreserved result")
        else:
            incomplete = True


async def _restricted_case(
    case: dict, *, base_url: str, caller: str, admin: str, factory: Any
) -> dict:
    async with httpx.AsyncClient(
        base_url=base_url, transport=factory(), timeout=5, trust_env=False
    ) as client:
        async with asyncio.timeout(5):
            snapshot = await sv._read_admin(client, admin)
        pool = snapshot.get("models", {}).get(case["pool"]) if snapshot else None
        if not isinstance(pool, dict) or pool.get("streaming_enabled") is not False:
            raise ValueError("Deployed streaming restriction unavailable")
    return await sv.run_validation_case(
        case=case,
        manifest=case_manifest(case),
        base_url=base_url,
        caller_key=caller,
        admin_key=admin,
        transport=factory(),
    )


def execute(  # noqa: PLR0913 -- explicit deployment inputs
    environment: str,
    *,
    base_url: str,
    caller: str,
    admin: str,
    directory: Path = DIRECTORY,
    factory: Any = None,
) -> dict:
    if environment not in {"staging", "production"}:
        raise ValueError("Invalid environment")
    manifest = _load(directory / "manifest.json")
    if manifest != json.loads(json.dumps(MANIFEST)):
        raise ValueError("Manifest changed")
    old = [
        sv._load_canonical_manifest(sv.STAGE_DIR, name)
        for name in (
            "manifest.staging.json",
            "manifest.production.json",
            "manifest.roster.json",
            "manifest.roster-remaining.json",
            "manifest.roster-final.json",
        )
    ]
    estimate = sv.combined_preflight_estimate(*old) + sum(
        (512 * c["input_per_million"] + 128 * c["output_per_million"]) / 1e6 for c in CASES
    )
    if estimate > sv.ALLOWANCE_USD:
        raise ValueError("Combined allowance exceeded")
    path = directory / "ledger.json"
    identity = directory / "ledger.json.identity"
    transport_factory = factory or (lambda: httpx.AsyncHTTPTransport(retries=0, trust_env=False))
    with locked(sv.STAGE_DIR / "stage"), locked(directory / "stage"):
        if not path.exists():
            if identity.exists() or environment != "staging":
                raise ValueError("Ledger unavailable")
            write_atomic(
                path,
                {
                    "manifest": manifest,
                    "entries": [{"reserved": False, "result": None} for _ in CASES],
                },
            )
            write_atomic(identity, {"run": RUN})
        if _load(identity) != {"run": RUN}:
            raise ValueError("Identity unavailable")
        state = _load(path)
        validate_state(state)
        if environment == "production" and not all(e["reserved"] for e in state["entries"][:2]):
            raise ValueError("Staging acceptance required")
        for index, case in enumerate(CASES):
            if not case["id"].startswith(environment + "-") or state["entries"][index]["reserved"]:
                continue
            entry = state["entries"][index]
            entry["reserved"] = True
            write_atomic(path, state)
            result = asyncio.run(
                _restricted_case(
                    case, base_url=base_url, caller=caller, admin=admin, factory=transport_factory
                )
            )
            entry["result"] = result
            write_atomic(path, state)
            if result["status"] != "passed":
                raise ValueError("Validation failed; no successor")
        validate_state(state)
        return state
